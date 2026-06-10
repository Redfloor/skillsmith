"""skillsmith adapters: the Adapter protocol and per-ecosystem implementations."""

from __future__ import annotations

from skillsmith_adapters.base import (
    Adapter,
    AuditHook,
    BaseAdapter,
    EvalHook,
    HealHook,
    SkillRef,
)
from skillsmith_adapters.claude_agent_sdk import ClaudeAgentSdkAdapter
from skillsmith_adapters.claude_skill import ClaudeSkillAdapter, parse_skill_md
from skillsmith_adapters.mcp import McpAdapter
from skillsmith_adapters.registry import all_adapters, detect, get, register
from skillsmith_adapters.stubs import (
    CrewAIAdapter,
    CursorAdapter,
    LangGraphAdapter,
    OpenAIAdapter,
)

__all__ = [
    "Adapter",
    "AuditHook",
    "BaseAdapter",
    "ClaudeAgentSdkAdapter",
    "ClaudeSkillAdapter",
    "CrewAIAdapter",
    "CursorAdapter",
    "EvalHook",
    "HealHook",
    "LangGraphAdapter",
    "McpAdapter",
    "OpenAIAdapter",
    "SkillRef",
    "all_adapters",
    "detect",
    "get",
    "parse_skill_md",
    "register",
]
