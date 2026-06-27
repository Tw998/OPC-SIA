"""研究引擎接口 + 工厂。

引擎的唯一职责:给一个公司名,返回一份 normalize 过的 Company Intelligence 记录。
怎么拿到数据由各引擎自己决定 —— 这就是"研究引擎可插拔"的关键。
"""

from __future__ import annotations

from abc import ABC, abstractmethod

import schema


class ResearchEngine(ABC):
    name = "base"

    @abstractmethod
    def research(self, company_name: str) -> dict:
        """返回 normalize 过的记录。子类实现具体取数逻辑。"""
        raise NotImplementedError

    def _wrap(self, raw: dict | None, company_name: str) -> dict:
        rec = schema.normalize(raw)
        # 保证至少有个英文名
        if not rec["company_profile"].get("name_en"):
            rec["company_profile"]["name_en"] = company_name
        rec["_engine"] = self.name
        return rec


def get_engine(name: str, **kwargs) -> ResearchEngine:
    name = (name or "manual").lower()
    if name == "manual":
        from engines.manual import ManualEngine
        return ManualEngine(**kwargs)
    if name in ("api", "claude", "claude_api"):
        from engines.claude_api import ClaudeAPIEngine
        return ClaudeAPIEngine(**kwargs)
    raise ValueError(f"未知引擎: {name}(可选 manual / api)")
