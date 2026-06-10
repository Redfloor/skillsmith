"""Stub adapters for ecosystems on the roadmap. Each implements the Adapter
interface but raises ``NotImplementedError`` with a TODO until built out. They are
intentionally importable so the registry and docs can enumerate planned coverage.

See docs/future-extensions.md for the roadmap and docs/extending.md for how to
turn one of these into a real adapter.
"""

from __future__ import annotations

from pathlib import Path

from skillsmith_adapters.base import BaseAdapter, SkillRef
from skillsmith_core.models import SkillDoc


class _NotYet(BaseAdapter):
    ecosystem = "stub"
    note = "TODO: implement this adapter."

    def discover(self, root: Path) -> list[SkillRef]:
        return []  # discovers nothing until implemented

    def parse(self, ref: SkillRef) -> SkillDoc:  # pragma: no cover - stub
        raise NotImplementedError(f"{self.ecosystem} adapter: {self.note}")


class OpenAIAdapter(_NotYet):
    ecosystem = "openai"
    # TODO: parse OpenAI Assistants / function-tool definitions + system instructions.
    note = "Map OpenAI Assistants/tool schemas onto core models."


class LangGraphAdapter(_NotYet):
    ecosystem = "langgraph"
    # TODO: parse LangGraph graph node prompts + tool bindings.
    note = "Discover LangGraph nodes and their prompts/tools."


class CrewAIAdapter(_NotYet):
    ecosystem = "crewai"
    # TODO: parse CrewAI Agent/Task definitions (role, goal, backstory, tools).
    note = "Map CrewAI Agent/Task definitions onto core models."


class CursorAdapter(_NotYet):
    ecosystem = "cursor"
    # TODO: parse .cursor/rules and Cursor command/prompt files.
    note = "Discover Cursor rules/commands and audit them."


STUB_ADAPTERS = (OpenAIAdapter, LangGraphAdapter, CrewAIAdapter, CursorAdapter)
