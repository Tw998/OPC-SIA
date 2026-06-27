"""Flask web app — Hitpoint Sales Intelligence Agent."""
from __future__ import annotations

import os
import sys
import tempfile
import threading

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from flask import (Flask, abort, flash, jsonify, redirect,
                   render_template, request, send_file, url_for)

import web.db as db
from engines import get_engine
from pipeline import _read_delimited, _read_excel
from report import next_best_actions, write_excel
from scoring import score_record
from util import slugify

app = Flask(__name__)
app.secret_key = os.environ.get("FLASK_SECRET", "hitpoint-sales-intel-2025")
app.jinja_env.globals["zip"] = zip

# Vercel is serverless — no persistent background threads; run research synchronously.
_VERCEL = bool(os.environ.get("VERCEL"))


@app.template_filter("datefmt")
def datefmt(s):
    return (str(s) or "")[:10]


@app.template_filter("strip_md")
def strip_md(s):
    import re
    s = re.sub(r"\*+([^*]+)\*+", r"\1", str(s or ""))
    return re.sub(r"`([^`]+)`", r"\1", s)


# ─── Dashboard ────────────────────────────────────────────────────────────────

@app.route("/")
def dashboard():
    q = request.args.get("q", "").strip()
    companies = db.list_companies()
    if q:
        ql = q.lower()
        companies = [c for c in companies
                     if ql in (c.get("name_en") or "").lower()
                     or ql in (c.get("name_cn") or "").lower()
                     or ql in (c.get("industry") or "").lower()]
    s = db.stats()
    return render_template("index.html", companies=companies, stats=s, q=q)


# ─── Research single company ──────────────────────────────────────────────────

@app.route("/research", methods=["POST"])
def research():
    name = (request.form.get("company") or "").strip()
    engine_name = request.form.get("engine", "api")
    if not name:
        flash("请输入公司名", "warning")
        return redirect(url_for("dashboard"))
    slug = slugify(name)
    if _VERCEL:
        # Serverless: run synchronously (blocks until done, max 60s)
        _bg_research(name, engine_name)
        return redirect(url_for("company", slug=slug))
    threading.Thread(target=_bg_research, args=(name, engine_name), daemon=True).start()
    flash(f"正在调研 {name}，请稍候片刻后刷新页面", "info")
    return redirect(url_for("company", slug=slug))


@app.route("/company/<slug>")
def company(slug):
    co = db.get_company(slug)
    if co:
        co["next_actions"] = next_best_actions(co["data"], co["score"])
    return render_template("company.html", co=co, slug=slug)


@app.route("/delete/<slug>", methods=["POST"])
def delete(slug):
    db.delete_company(slug)
    flash("已删除", "success")
    return redirect(url_for("dashboard"))


# ─── Batch upload ─────────────────────────────────────────────────────────────

@app.route("/upload", methods=["POST"])
def upload():
    engine_name = request.form.get("engine", "api")
    f = request.files.get("file")
    if not f or not f.filename:
        flash("请选择文件", "warning")
        return redirect(url_for("dashboard"))
    ext = os.path.splitext(f.filename)[1].lower()
    with tempfile.NamedTemporaryFile(suffix=ext, delete=False) as tmp:
        f.save(tmp.name)
        tmppath = tmp.name
    try:
        if ext in (".csv", ".tsv"):
            companies = _read_delimited(tmppath, "\t" if ext == ".tsv" else ",")
        elif ext in (".xlsx", ".xlsm"):
            companies = _read_excel(tmppath)
        else:
            flash("不支持的格式，请用 .csv / .xlsx", "danger")
            return redirect(url_for("dashboard"))
    finally:
        os.unlink(tmppath)
    if not companies:
        flash("文件里没找到公司名", "warning")
        return redirect(url_for("dashboard"))
    job_id = db.create_job(companies, f.filename)
    if _VERCEL:
        # Serverless: synchronous batch (will time out for large lists on Vercel)
        _bg_batch(job_id, engine_name)
        return redirect(url_for("batch", job_id=job_id))
    threading.Thread(target=_bg_batch, args=(job_id, engine_name), daemon=True).start()
    return redirect(url_for("batch", job_id=job_id))


@app.route("/batch/<int:job_id>")
def batch(job_id):
    job = db.get_job(job_id)
    if not job:
        abort(404)
    return render_template("batch.html", job=job, job_id=job_id)


# ─── Export Excel ─────────────────────────────────────────────────────────────

@app.route("/export")
def export():
    rows = []
    for co_row in db.list_companies():
        co = db.get_company(co_row["slug"])
        if co:
            rows.append({"record": co["data"], "score": co["score"]})
    with tempfile.NamedTemporaryFile(suffix=".xlsx", delete=False) as tmp:
        write_excel(rows, tmp.name)
        return send_file(tmp.name, as_attachment=True,
                         download_name="sales_intelligence.xlsx",
                         mimetype="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")


# ─── JSON APIs ────────────────────────────────────────────────────────────────

@app.route("/api/job/<int:job_id>")
def api_job(job_id):
    job = db.get_job(job_id)
    if not job:
        return jsonify(error="not found"), 404
    pct = int(job["done"] / max(job["total"], 1) * 100)
    return jsonify(status=job["status"], total=job["total"],
                   done=job["done"], failed=job["failed"],
                   pct=pct, log=job["log"][-40:])


@app.route("/api/companies")
def api_companies():
    return jsonify(db.list_companies())


# ─── Background workers ───────────────────────────────────────────────────────

def _bg_research(name: str, engine_name: str):
    try:
        engine = get_engine(engine_name)
        rec = engine.research(name)
        score = score_record(rec)
        db.upsert_company(rec, score)
        print(f"[research ok] {name}", flush=True)
    except Exception as e:
        print(f"[research error] {name}: {e}", flush=True)


def _bg_batch(job_id: int, engine_name: str):
    job = db.get_job(job_id)
    companies = job["companies"]
    db.update_job(job_id, done=0, failed=0, status="running")
    engine = get_engine(engine_name)
    done = failed = 0
    for name in companies:
        try:
            rec = engine.research(name)
            score = score_record(rec)
            db.upsert_company(rec, score)
            done += 1
            db.update_job(job_id, done=done, failed=failed,
                          status="running", log_entry=f"✓ {name}")
        except Exception as e:
            failed += 1
            db.update_job(job_id, done=done, failed=failed,
                          status="running", log_entry=f"✗ {name}: {str(e)[:80]}")
    db.update_job(job_id, done=done, failed=failed, status="done")
