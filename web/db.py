"""SQLite persistence for Sales Intelligence Agent.

每次调用都开新连接 + WAL 模式,线程安全。
"""
from __future__ import annotations

import json
import os
import sqlite3
from contextlib import contextmanager

# Vercel 文件系统只有 /tmp 可写;本地用 data/intel.db
_default_db = (
    "/tmp/intel.db"
    if os.environ.get("VERCEL")
    else os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                      "data", "intel.db")
)
DB_PATH = os.environ.get("INTEL_DB", _default_db)


@contextmanager
def _db():
    conn = sqlite3.connect(DB_PATH, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA synchronous=NORMAL")
    try:
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def init_db():
    os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)
    with _db() as c:
        c.executescript("""
        CREATE TABLE IF NOT EXISTS companies (
            slug                TEXT PRIMARY KEY,
            name_en             TEXT,
            name_cn             TEXT,
            ticker              TEXT,
            industry            TEXT,
            revenue             TEXT,
            employees_china     TEXT,
            has_ssc             INTEGER DEFAULT 0,
            concur_installed    TEXT    DEFAULT 'Unknown',
            tier                TEXT,
            score_overall       INTEGER,
            score_icp           INTEGER,
            score_cross_sell    INTEGER,
            score_buying_intent INTEGER,
            score_relationship  INTEGER,
            data_json           TEXT,
            score_json          TEXT,
            engine              TEXT,
            data_confidence     TEXT,
            ai_summary_cn       TEXT,
            updated_at          TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );

        CREATE TABLE IF NOT EXISTS jobs (
            id           INTEGER PRIMARY KEY AUTOINCREMENT,
            filename     TEXT,
            company_list TEXT,
            total        INTEGER DEFAULT 0,
            done         INTEGER DEFAULT 0,
            failed       INTEGER DEFAULT 0,
            status       TEXT    DEFAULT 'pending',
            log_json     TEXT    DEFAULT '[]',
            created_at   TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );
        """)


def upsert_company(rec: dict, score: dict) -> str:
    from util import slugify
    cp = rec.get("company_profile", {})
    cf = rec.get("china_footprint", {})
    slug = slugify(cp.get("name_en") or "unknown")
    with _db() as c:
        c.execute("""
        INSERT INTO companies (
            slug, name_en, name_cn, ticker, industry, revenue,
            employees_china, has_ssc, concur_installed, tier,
            score_overall, score_icp, score_cross_sell, score_buying_intent, score_relationship,
            data_json, score_json, engine, data_confidence, ai_summary_cn,
            updated_at
        ) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?, CURRENT_TIMESTAMP)
        ON CONFLICT(slug) DO UPDATE SET
            name_en=excluded.name_en, name_cn=excluded.name_cn,
            ticker=excluded.ticker, industry=excluded.industry,
            revenue=excluded.revenue, employees_china=excluded.employees_china,
            has_ssc=excluded.has_ssc, concur_installed=excluded.concur_installed,
            tier=excluded.tier, score_overall=excluded.score_overall,
            score_icp=excluded.score_icp, score_cross_sell=excluded.score_cross_sell,
            score_buying_intent=excluded.score_buying_intent,
            score_relationship=excluded.score_relationship,
            data_json=excluded.data_json, score_json=excluded.score_json,
            engine=excluded.engine, data_confidence=excluded.data_confidence,
            ai_summary_cn=excluded.ai_summary_cn,
            updated_at=CURRENT_TIMESTAMP
        """, (
            slug,
            cp.get("name_en"), cp.get("name_cn"),
            cp.get("ticker"), cp.get("industry"),
            cp.get("revenue"), str(cp.get("employees_china") or ""),
            1 if cf.get("has_shared_service_center") else 0,
            score.get("concur_installed", "Unknown"),
            score.get("tier"), score.get("overall"),
            score.get("icp_fit"), score.get("cross_sell"),
            score.get("buying_intent"), score.get("relationship"),
            json.dumps(rec, ensure_ascii=False),
            json.dumps(score, ensure_ascii=False),
            rec.get("_engine", "manual"),
            rec.get("data_confidence", "low"),
            rec.get("ai_summary_cn", ""),
        ))
    return slug


def list_companies() -> list[dict]:
    with _db() as c:
        rows = c.execute("""
            SELECT slug, name_en, name_cn, industry, revenue, employees_china,
                   has_ssc, concur_installed, tier,
                   score_overall, score_icp, score_cross_sell, score_buying_intent, score_relationship,
                   data_confidence, engine, ai_summary_cn, updated_at
            FROM companies
            ORDER BY score_overall DESC
        """).fetchall()
    return [dict(r) for r in rows]


def get_company(slug: str) -> dict | None:
    with _db() as c:
        row = c.execute("SELECT * FROM companies WHERE slug=?", (slug,)).fetchone()
    if not row:
        return None
    d = dict(row)
    d["data"] = json.loads(d.pop("data_json") or "{}")
    d["score"] = json.loads(d.pop("score_json") or "{}")
    return d


def delete_company(slug: str):
    with _db() as c:
        c.execute("DELETE FROM companies WHERE slug=?", (slug,))


def stats() -> dict:
    with _db() as c:
        row = c.execute("""
            SELECT
                COUNT(*)                        AS total,
                SUM(CASE WHEN tier='A' THEN 1 ELSE 0 END) AS tier_a,
                SUM(CASE WHEN tier='B' THEN 1 ELSE 0 END) AS tier_b,
                SUM(CASE WHEN concur_installed='Unknown' THEN 1 ELSE 0 END) AS concur_unknown,
                SUM(CASE WHEN concur_installed='No'  THEN 1 ELSE 0 END) AS concur_no,
                SUM(CASE WHEN concur_installed='Yes' THEN 1 ELSE 0 END) AS concur_yes
            FROM companies
        """).fetchone()
    return dict(row) if row else {}


# ─── Jobs ─────────────────────────────────────────────────────────────────────

def create_job(companies: list[str], filename: str = "") -> int:
    with _db() as c:
        cur = c.execute(
            "INSERT INTO jobs (filename, company_list, total, status) VALUES (?,?,?,'pending')",
            (filename, json.dumps(companies, ensure_ascii=False), len(companies)),
        )
        return cur.lastrowid


def get_job(job_id: int) -> dict | None:
    with _db() as c:
        row = c.execute("SELECT * FROM jobs WHERE id=?", (job_id,)).fetchone()
    if not row:
        return None
    d = dict(row)
    d["companies"] = json.loads(d.pop("company_list") or "[]")
    d["log"] = json.loads(d.pop("log_json") or "[]")
    return d


def update_job(job_id: int, *, done: int, failed: int, status: str, log_entry: str = ""):
    with _db() as c:
        if log_entry:
            row = c.execute("SELECT log_json FROM jobs WHERE id=?", (job_id,)).fetchone()
            log = json.loads(row[0] or "[]") if row else []
            log.append(log_entry)
            c.execute("UPDATE jobs SET done=?,failed=?,status=?,log_json=? WHERE id=?",
                      (done, failed, status, json.dumps(log, ensure_ascii=False), job_id))
        else:
            c.execute("UPDATE jobs SET done=?,failed=?,status=? WHERE id=?",
                      (done, failed, status, job_id))


def import_enriched(enriched_dir: str) -> int:
    """启动时把 data/enriched/*.json 批量导入 DB,跳过已有记录(按 slug 比对)。"""
    import glob
    from schema import normalize
    from scoring import score_record
    count = 0
    for path in sorted(glob.glob(os.path.join(enriched_dir, "*.json"))):
        try:
            with open(path, encoding="utf-8") as f:
                raw = json.load(f)
            rec = normalize(raw)
            score = score_record(rec)
            upsert_company(rec, score)
            count += 1
        except Exception as e:
            print(f"  ⚠ skip {os.path.basename(path)}: {e}", flush=True)
    return count
