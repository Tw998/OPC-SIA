# Hitpoint Sales Intelligence Agent (MVP)

把"一个公司名 / 一份 Excel / 一份 CSV"变成一份**完整的 Company Intelligence + 机会评分排名**。
不是只给联系人,而是公司画像、中国业务、采购委员会、技术栈、商业事件、招聘信号、AI 总结、
机会评分、下一步建议 —— 一份能直接给销售用的 Account Copilot 简报。

面向 Hitpoint 的定位:在中国为跨国企业做 **SAP Concur / 差旅费用(T&E) / 费控采购数字化**。
评分天然偏向"有中国实体、跑 SAP/Oracle、有共享中心、还没上 Concur"的公司。

---

## 架构:研究引擎可插拔

数据流是统一的:`公司名 → 研究引擎 → 标准记录(schema.py) → 评分(scoring.py) → 报告(report.py)`。
变的只是"研究引擎"这一块:

| 引擎 | 怎么取数 | 适合 | 现状 |
|---|---|---|---|
| **manual** | 读 `data/enriched/<slug>.json`(人工 / Claude Code 内置搜索预调研) | 高价值客户、样本验证、人盯质量 | 现在就能用,零配置 |
| **api** | Claude API + `web_search` 自动联网调研 | 无人值守批量跑 1000 家 | 需 `ANTHROPIC_API_KEY` |

> 现在用内置搜索调研的结果,以后填个 API key 就能切到 `api` 引擎规模化 —— 代码不用改。

---

## 安装

```bash
pip install -r requirements.txt        # 只用 manual 引擎其实只需 openpyxl
```

## 用法

```bash
# 单公司(用已调研好的 JSON)
python pipeline.py --company Medtronic --engine manual

# 批量 CSV(1000家)/ Excel(100家)
python pipeline.py --input data/input_sample.csv --engine manual --out output

# 自动联网调研(无人值守,需 API key)
export ANTHROPIC_API_KEY=sk-...
python pipeline.py --input accounts.xlsx --engine api --workers 4 --top 100
```

输入文件认 `company` / `name` / `公司` 列名;找不到就用第一列。

## 输出

```
output/
├── sales_intelligence.xlsx     # 排名 Top-N + 公司画像/联系人/技术栈/信号 多个 sheet
├── reports/<company>.md        # 每家公司一份完整情报(Account Copilot 简报)
└── enriched/<company>.json     # 标准化后的原始数据
```

---

## 七大 MVP 模块(覆盖 ~80% 销售价值)

1. Company Profile 公司画像 ｜ 2. China Footprint 中国业务 ｜ 3. Buying Committee 采购委员会
4. Technology Stack 技术栈 ｜ 5. AI Summary 总结 ｜ 6. Opportunity Score 机会评分 ｜ 7. Next Best Action

(schema 里还预留了 Org Chart / Business Events / Hiring Signals,报告已渲染。)

## 机会评分(可解释、可调)

`Overall = ICP Fit×0.35 + Cross-Sell×0.30 + Buying Intent×0.25 + Relationship×0.10`
另含 `Concur Installed (Yes/No/Unknown)`。每个分都带文字理由。改 `config.py` 即可调整"销售嗅觉"。

- **ICP Fit**:中国员工规模 + 是否跑目标 ERP + 是否有共享中心
- **Cross-Sell**:跑 SAP 但没上 Concur = 95 分(黄金交叉销售)
- **Buying Intent**:转型招聘信号 + ERP/共享中心/CFO 变动等事件
- **Relationship**:占位 50 分,接入 Salesforce 后自动更新

## 文件结构

```
config.py      ICP 阈值 / 评分权重 / 目标技术栈(调"销售嗅觉"的地方)
schema.py      标准数据结构 + normalize()
prompts/       主调研 prompt(两种引擎共用)
engines/       base / manual / claude_api
scoring.py     机会评分(纯 Python,确定性可解释)
report.py      Excel + Markdown 渲染
pipeline.py    CLI 入口
```

## Roadmap → Account Copilot

接入 Salesforce(真实 Relationship + 持续更新)、LinkedIn(联系人/换岗)、招聘/新闻 API,
并自动生成开场邮件 / LinkedIn 连接语 / Demo 议程。
