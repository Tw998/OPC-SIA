"""Company Intelligence 数据结构 / Schema.

这是整条管线流通的"标准数据格式":调研引擎(人工 / Claude API)产出它,
评分模块消费它,报告模块渲染它。字段名用英文,内容可中英混合。

EMPTY_RECORD 是模板;normalize() 保证任何引擎产出的 dict 都补齐到完整结构,
这样下游(评分 / 报告)永远不会因为缺字段而崩。
"""

from __future__ import annotations

import copy


def empty_record() -> dict:
    """返回一份完整的空记录模板。"""
    return {
        # --- 第一部分 Company Profile(公司画像 / Firmographic)---
        "company_profile": {
            "name_en": "",
            "name_cn": "",
            "website": "",
            "linkedin": "",
            "china_entity_name": "",      # 中国实体名称
            "china_legal_rep": "",        # 中国法人
            "founded_year": "",
            "parent_company": "",
            "is_public": None,            # bool
            "ticker": "",
            "industry": "",
            "revenue": "",                # 含币种,如 "USD 33.5B"
            "employees_global": "",
            "employees_china": "",
            "hq": "",
            "china_offices": [],          # ["上海", "北京", ...]
        },
        # --- 第二部分 China Footprint(中国业务)---
        "china_footprint": {
            "entity_types": [],           # WFOE / JV / Factory / R&D / Shared Service / Procurement Center
            "cities": [                   # 每个城市多少人、做什么
                # {"city": "上海", "headcount": "300", "functions": ["销售", "共享服务"]}
            ],
            "has_shared_service_center": None,  # bool
            "ssc_location": "",
            "notes": "",
        },
        # --- 第三部分 Buying Committee(采购委员会 / 关键联系人)---
        "buying_committee": [
            # {"name":"","title":"","function":"Finance/IT/Procurement/HR/Travel/SSC/Digital",
            #  "linkedin":"","location":"","in_china":True/False,"email":"",
            #  "recently_changed_job":True/False,"years_in_role":"","seniority":"C-level/Director/Manager"}
        ],
        # --- 第四部分 Org Chart(组织结构)---
        "org_chart": {
            "description": "",            # 文字描述决策链
            "chain": [],                  # ["CFO", "Finance Director", "AP Manager", "Expense Team"]
        },
        # --- 第五部分 Technology Stack(技术栈 / Technographic)---
        "tech_stack": {
            "erp": [],
            "expense_travel": [],
            "procurement": [],
            "hr": [],
            "itsm": [],
            "crm": [],
            "bi_cloud": [],
            "collaboration": [],
            "concur_installed": "unknown",   # yes / no / unknown
            "concur_details": "",            # 上线时间 / partner / 是否 cloud
            "details": [
                # {"category":"ERP","vendor":"SAP","product":"S/4HANA","cloud":True,
                #  "since":"2019","partner":"","confidence":"high/medium/low","source":""}
            ],
        },
        # --- 第六部分 Business Events(商业事件 / Sales Triggers)---
        "business_events": [
            # {"date":"2025-03","type":"ERP升级/收购/CFO变化/扩张/...",
            #  "title":"","summary":"","source":"","sales_trigger":True/False}
        ],
        # --- 第七部分 Hiring Signals(招聘信号)---
        "hiring_signals": [
            # {"title":"","function":"","location":"","keywords":[],
            #  "posted":"","source":"","transformation_signal":True/False}
        ],
        # --- 第九部分 AI Summary(AI总结,中文叙述)---
        "ai_summary_cn": "",
        # --- 元数据 ---
        "sources": [],                    # 主要信息来源 URL
        "data_confidence": "low",         # high / medium / low
    }


def normalize(record: dict | None) -> dict:
    """把任意(可能残缺的)引擎输出补齐到完整结构。深度合并,缺啥补啥。"""
    base = empty_record()
    if not isinstance(record, dict):
        return base
    return _deep_merge(base, record)


def _deep_merge(base: dict, override: dict) -> dict:
    out = copy.deepcopy(base)
    for k, v in override.items():
        if k not in out:
            out[k] = v
        elif isinstance(out[k], dict) and isinstance(v, dict):
            out[k] = _deep_merge(out[k], v)
        elif v is None or v == "":
            continue  # 不要用空值覆盖模板默认
        else:
            out[k] = v
    return out
