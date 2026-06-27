"""第十部分 Opportunity Score(机会评分)。

输入一份 normalize 过的 Company Intelligence 记录,输出 Hitpoint 视角的机会评分:
  ICP Fit / Concur Installed / Cross Sell / Buying Intent / Relationship / Overall + 分级 + 理由。

评分逻辑是确定性的(纯 Python),可解释、可调(改 config.py 即可),不依赖模型。
"""

from __future__ import annotations

import config
from util import clamp, parse_int, safe_get


def _has_any(items, keywords) -> bool:
    """items 里任意一项(小写)包含 keywords 里任意一个关键词。"""
    blob = " ".join(str(x).lower() for x in items)
    return any(k in blob for k in keywords)


def _tech_blob(ts: dict) -> str:
    parts = []
    for key in ("erp", "expense_travel", "procurement", "hr", "itsm", "crm", "bi_cloud", "collaboration"):
        parts.extend(ts.get(key, []) or [])
    for d in ts.get("details", []) or []:
        parts.append(f"{d.get('vendor','')} {d.get('product','')}")
    return " ".join(str(p).lower() for p in parts)


def _has_target_erp(ts: dict) -> bool:
    blob = _tech_blob(ts)
    return any(e in blob for e in config.TARGET_ERP)


def _has_sap(ts: dict) -> bool:
    return "sap" in _tech_blob(ts)


def score_icp_fit(record: dict) -> tuple[int, list[str]]:
    cp, cf, ts = record["company_profile"], record["china_footprint"], record["tech_stack"]
    reasons = []

    emp_cn = parse_int(cp.get("employees_china"))
    if emp_cn is not None:
        base = next(s for floor, s in config.CHINA_EMPLOYEE_TIERS if emp_cn >= floor)
        reasons.append(f"中国员工约 {emp_cn} 人 → 基础分 {base}")
    else:
        base = 40
        reasons.append("中国员工人数未知 → 基础分 40")

    score = base
    if _has_target_erp(ts):
        score += 8
        reasons.append("已部署目标 ERP(SAP/Oracle 等) +8")
    if cf.get("has_shared_service_center"):
        score += 7
        loc = cf.get("ssc_location") or "中国"
        reasons.append(f"设有共享服务中心({loc}) +7")
    if _has_any(cf.get("entity_types", []), ["wfoe", "factory", "工厂", "r&d", "研发"]):
        score += 3
        reasons.append("有 WFOE/工厂/研发实体 +3")

    return clamp(score), reasons


def concur_status(record: dict) -> str:
    """返回 'Yes' / 'No' / 'Unknown'。"""
    val = str(safe_get(record, "tech_stack", "concur_installed", default="unknown")).lower()
    if val in ("yes", "y", "true", "是"):
        return "Yes"
    if val in ("no", "n", "false", "否"):
        return "No"
    # 兜底:技术栈里直接出现 concur 也算 Yes
    if "concur" in _tech_blob(record["tech_stack"]):
        return "Yes"
    return "Unknown"


def score_cross_sell(record: dict) -> tuple[int, list[str]]:
    ts = record["tech_stack"]
    concur = concur_status(record)
    has_erp = _has_target_erp(ts)
    has_sap = _has_sap(ts)
    reasons = []

    if concur == "No" and has_sap:
        score = 95
        reasons.append("跑 SAP 但未上 Concur → Concur 交叉销售黄金机会(95)")
    elif concur == "No" and has_erp:
        score = 82
        reasons.append("有大型 ERP 但未上 Concur → 强交叉销售(82)")
    elif concur == "Unknown" and has_sap:
        score = 72
        reasons.append("跑 SAP,Concur 状态未知 → 高潜在交叉销售(72)")
    elif concur == "Unknown" and has_erp:
        score = 60
        reasons.append("有 ERP,Concur 状态未知 → 待确认(60)")
    elif concur == "Yes":
        score = 58
        reasons.append("已用 Concur → 可交叉销售其它模块/托管运维/优化(58)")
    else:
        score = 38
        reasons.append("ERP/费控信息不足 → 暂低(38)")

    return clamp(score), reasons


def score_buying_intent(record: dict) -> tuple[int, list[str]]:
    reasons = []
    score = 30  # 基础分

    hiring = record.get("hiring_signals", []) or []
    transform_jobs = [h for h in hiring if h.get("transformation_signal")
                      or _has_any([h.get("title", ""), " ".join(h.get("keywords", []) or [])],
                                  config.TRANSFORMATION_JOB_KEYWORDS)]
    if transform_jobs:
        add = min(45, 15 * len(transform_jobs))
        score += add
        reasons.append(f"{len(transform_jobs)} 个转型相关招聘信号 +{add}")

    events = record.get("business_events", []) or []
    trigger_events = [e for e in events if e.get("sales_trigger")
                      or _has_any([e.get("title", ""), e.get("summary", ""), e.get("type", "")],
                                  config.TRIGGER_EVENT_KEYWORDS)]
    erp_events = [e for e in trigger_events
                  if _has_any([e.get("title", ""), e.get("summary", ""), e.get("type", "")],
                              ["erp", "sap", "s/4hana", "oracle", "共享中心", "shared service", "ssc"])]
    if erp_events:
        score += 20
        reasons.append(f"{len(erp_events)} 个 ERP/共享中心相关事件 +20")
    other_triggers = [e for e in trigger_events if e not in erp_events]
    if other_triggers:
        add = min(20, 8 * len(other_triggers))
        score += add
        reasons.append(f"{len(other_triggers)} 个其它销售触发事件 +{add}")

    if not transform_jobs and not trigger_events:
        reasons.append("暂无明显招聘/事件信号 → 维持基础分")

    return clamp(score), reasons


def score_relationship(record: dict) -> tuple[int, list[str]]:
    # 真实关系分应来自 Salesforce。这里用默认值占位。
    return config.DEFAULT_RELATIONSHIP_SCORE, [config.RELATIONSHIP_NOTE]


def tier_for(overall: int) -> str:
    for tier, floor in config.TIER_THRESHOLDS:
        if overall >= floor:
            return tier
    return "C"


def score_record(record: dict) -> dict:
    """主入口:返回评分 dict。"""
    icp, icp_r = score_icp_fit(record)
    concur = concur_status(record)
    cross, cross_r = score_cross_sell(record)
    intent, intent_r = score_buying_intent(record)
    rel, rel_r = score_relationship(record)

    w = config.SCORE_WEIGHTS
    overall = clamp(
        icp * w["icp_fit"]
        + cross * w["cross_sell"]
        + intent * w["buying_intent"]
        + rel * w["relationship"]
    )

    return {
        "icp_fit": icp,
        "concur_installed": concur,
        "cross_sell": cross,
        "buying_intent": intent,
        "relationship": rel,
        "overall": overall,
        "tier": tier_for(overall),
        "rationale": {
            "icp_fit": icp_r,
            "cross_sell": cross_r,
            "buying_intent": intent_r,
            "relationship": rel_r,
        },
    }
