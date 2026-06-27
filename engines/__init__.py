"""研究引擎(可插拔):manual(人工/Claude Code 调研) 或 claude_api(无人值守批量)。"""

from engines.base import ResearchEngine, get_engine

__all__ = ["ResearchEngine", "get_engine"]
