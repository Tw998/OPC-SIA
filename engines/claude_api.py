"""引擎 B:Claude API + Web Search(无人值守批量)。

这是真正能让独立脚本无人值守跑 1000 家公司的引擎。用 Claude API 的服务端
web_search 工具(claude-opus-4-8 + adaptive thinking),让模型自己联网调研并产出 JSON。

需要环境变量 ANTHROPIC_API_KEY。依赖:pip install anthropic
"""

from __future__ import annotations

import json
import re

import config
from engines.base import ResearchEngine
from prompts.research_prompt import SYSTEM_PROMPT, build_research_prompt


class ClaudeAPIEngine(ResearchEngine):
    name = "claude_api"

    def __init__(self, model: str = config.MODEL, max_searches: int = 8,
                 max_continuations: int = 6):
        try:
            import anthropic
        except ImportError as e:  # pragma: no cover
            raise RuntimeError("缺少依赖:pip install anthropic") from e
        self._anthropic = anthropic
        self.client = anthropic.Anthropic()  # 从 ANTHROPIC_API_KEY 读取
        self.model = model
        self.max_searches = max_searches
        self.max_continuations = max_continuations

    def research(self, company_name: str) -> dict:
        prompt = build_research_prompt(company_name)
        messages = [{"role": "user", "content": prompt}]
        all_sources: list[str] = []
        final_text = ""

        # 服务端 web_search 循环可能返回 stop_reason=pause_turn(到达迭代上限),
        # 需把 assistant 内容回填并续跑,直到模型给出最终答案。
        for _ in range(self.max_continuations):
            # 流式 + get_final_message(),避免大 max_tokens 触发 HTTP 超时
            with self.client.messages.stream(
                model=self.model,
                max_tokens=16000,
                system=SYSTEM_PROMPT,
                thinking={"type": "adaptive"},
                tools=[{
                    "type": "web_search_20260209",
                    "name": "web_search",
                    "max_uses": self.max_searches,
                }],
                messages=messages,
            ) as stream:
                message = stream.get_final_message()

            all_sources.extend(_collect_sources(message))
            final_text = "".join(b.text for b in message.content if getattr(b, "type", "") == "text")

            if message.stop_reason == "pause_turn":
                messages.append({"role": "assistant", "content": message.content})
                continue
            break

        sources = list(dict.fromkeys(all_sources))
        raw = _extract_json(final_text)
        if raw is None:
            rec = self._wrap(None, company_name)
            rec["ai_summary_cn"] = f"⚠️ {company_name}:模型未返回可解析 JSON。原始输出片段:{final_text[:300]}"
            rec["data_confidence"] = "none"
            return rec

        # 合并模型自报来源 + web_search 实际访问的来源
        merged = list(dict.fromkeys((raw.get("sources") or []) + sources))
        raw["sources"] = merged
        return self._wrap(raw, company_name)


def _extract_json(text: str) -> dict | None:
    """从模型输出里抠出 JSON。优先 ```json 围栏,退化为第一个 {...}。"""
    if not text:
        return None
    fence = re.search(r"```(?:json)?\s*(\{.*?\})\s*```", text, re.DOTALL)
    candidate = fence.group(1) if fence else None
    if candidate is None:
        start = text.find("{")
        end = text.rfind("}")
        candidate = text[start:end + 1] if start != -1 and end > start else None
    if candidate is None:
        return None
    try:
        return json.loads(candidate)
    except json.JSONDecodeError:
        return None


def _collect_sources(message) -> list[str]:
    """从 web_search_tool_result 块里收集实际访问过的 URL。"""
    urls = []
    for block in message.content:
        if getattr(block, "type", "") == "web_search_tool_result":
            content = getattr(block, "content", None)
            if isinstance(content, list):
                for item in content:
                    url = getattr(item, "url", None)
                    if url:
                        urls.append(url)
    return list(dict.fromkeys(urls))
