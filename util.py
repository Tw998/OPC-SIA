"""通用工具函数 / Shared utilities."""

from __future__ import annotations

import re
import unicodedata


def slugify(name: str) -> str:
    """公司名 -> 文件名安全的 slug。Medtronic plc -> medtronic-plc"""
    name = unicodedata.normalize("NFKD", name)
    name = name.encode("ascii", "ignore").decode("ascii")  # 去掉非 ASCII (中文等)
    name = name.lower().strip()
    name = re.sub(r"[^a-z0-9]+", "-", name)
    name = re.sub(r"-+", "-", name).strip("-")
    return name or "company"


def parse_int(value) -> int | None:
    """把 '约 5,000 人' / '5000' / '5K' / 12000 解析成整数;解析不出返回 None。"""
    if value is None:
        return None
    if isinstance(value, (int, float)):
        return int(value)
    s = str(value).strip().lower().replace(",", "")
    if not s:
        return None
    # 处理 5k / 1.2k / 10万
    m = re.search(r"(\d+(?:\.\d+)?)\s*([km万])?", s)
    if not m:
        return None
    num = float(m.group(1))
    unit = m.group(2)
    if unit == "k":
        num *= 1_000
    elif unit == "m":
        num *= 1_000_000
    elif unit == "万":
        num *= 10_000
    return int(num)


def clamp(value: float, low: float = 0, high: float = 100) -> int:
    """限制在 [low, high] 并取整。"""
    return int(round(max(low, min(high, value))))


def safe_get(d: dict, *keys, default=None):
    """嵌套安全取值:safe_get(data, 'company_profile', 'name_en')"""
    cur = d
    for k in keys:
        if not isinstance(cur, dict) or k not in cur or cur[k] is None:
            return default
        cur = cur[k]
    return cur
