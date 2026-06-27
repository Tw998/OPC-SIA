"""引擎 A:Manual / Claude Code 调研引擎。

读取 data/enriched/<slug>.json —— 这些 JSON 由人工或 Claude Code Agent(用内置 WebSearch)
预先调研产出。适合:高价值客户、样本验证、需要人盯质量的场景。

找不到对应 JSON 时不报错,返回一条带提示的空记录(管线照常跑、报告里标注"待调研")。
"""

from __future__ import annotations

import json
import os

from engines.base import ResearchEngine
from util import slugify

ENRICHED_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), "data", "enriched")


class ManualEngine(ResearchEngine):
    name = "manual"

    def __init__(self, enriched_dir: str = ENRICHED_DIR):
        self.enriched_dir = enriched_dir

    def research(self, company_name: str) -> dict:
        path = os.path.join(self.enriched_dir, f"{slugify(company_name)}.json")
        if os.path.exists(path):
            with open(path, "r", encoding="utf-8") as f:
                raw = json.load(f)
            return self._wrap(raw, company_name)

        # 没有预调研数据 —— 返回带提示的空记录
        rec = self._wrap(None, company_name)
        rec["ai_summary_cn"] = (
            f"⚠️ 尚无 {company_name} 的调研数据。请用 Claude Code(内置搜索)按 prompts/research_prompt.py "
            f"调研后,把 JSON 存到 {path};或改用 --engine api 自动调研。"
        )
        rec["data_confidence"] = "none"
        return rec
