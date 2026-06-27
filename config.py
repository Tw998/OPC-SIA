"""Hitpoint Sales Intelligence Agent — 配置中枢 (ICP / 评分权重 / 目标技术栈)

Hitpoint 的核心定位:在中国为跨国企业(MNC)提供 SAP Concur / 差旅与费用(T&E)、
费控与采购数字化落地。因此 ICP 偏向:
  - 在中国有实体(WFOE / JV / 工厂 / R&D / 共享服务中心)
  - 有一定规模的中国员工
  - 已经在跑 SAP / Oracle 等大型 ERP
  - 设有共享服务中心(Shared Service Center)

调这个文件 = 调整整个 Agent 的"销售嗅觉"。
"""

# --- 模型 ---
MODEL = "claude-opus-4-8"

# --- ICP:中国员工规模 -> 基础分 (人数下限, 分数) 从高到低匹配 ---
CHINA_EMPLOYEE_TIERS = [
    (2000, 100),
    (1000, 92),
    (500, 82),
    (200, 68),
    (50, 48),
    (0, 28),
]

# 我们最关心的 ERP(装了这些 = 与 Concur / 费控天然契合)
TARGET_ERP = [
    "sap s/4hana", "sap s4", "s/4hana", "sap ecc", "sap erp", "sap",
    "oracle fusion", "oracle ebs", "oracle", "netsuite",
    "microsoft dynamics", "dynamics 365", "dynamics", "ifs", "infor",
]

# 我们卖的 / 可交叉销售的 T&E + 费控 + 采购系统(及主要竞品)
TARGET_TE_SPEND = [
    "sap concur", "concur",            # 我们的主力
    "coupa", "ariba", "sap ariba", "basware", "expensify",  # 国际竞品/相邻
    "kingdee", "yonyou", "用友", "金蝶", "fenbeitong", "分贝通",
    "maycur", "每刻", "汇联易", "hosting", "易快报",          # 本土费控竞品
]

CONCUR_KEYWORDS = ["concur"]

# 招聘信号里代表"正在做转型"的关键词
TRANSFORMATION_JOB_KEYWORDS = [
    "finance transformation", "财务转型", "财务共享", "shared service",
    "concur", "sap", "s/4hana", "erp", "oracle", "netsuite",
    "digital transformation", "数字化转型", "procurement", "采购数字化",
    "travel manager", "差旅", "expense", "费控", "ap manager", "应付",
    "transformation office", "process excellence",
]

# 商业事件里代表"采购触发点"的关键词
TRIGGER_EVENT_KEYWORDS = [
    "erp", "sap", "s/4hana", "oracle", "上线", "升级", "implementation",
    "shared service", "共享中心", "共享服务", "ssc",
    "cfo", "首席财务官", "财务负责人",
    "中国投资", "investment in china", "新工厂", "factory", "扩张", "expansion",
    "acquisition", "收购", "merger", "ipo", "funding", "融资",
    "digital transformation", "数字化",
]

# --- Overall 评分权重(四个核心维度,加权求和)---
SCORE_WEIGHTS = {
    "icp_fit": 0.35,
    "cross_sell": 0.30,
    "buying_intent": 0.25,
    "relationship": 0.10,
}

# Relationship 维度:真实数据应来自 Salesforce。未接入前用此默认值。
DEFAULT_RELATIONSHIP_SCORE = 50
RELATIONSHIP_NOTE = "默认值 — 接入 Salesforce 后按真实客户关系自动更新"

# 分级阈值
TIER_THRESHOLDS = [("A", 80), ("B", 60), ("C", 0)]
