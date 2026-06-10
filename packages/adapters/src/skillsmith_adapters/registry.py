"""Adapter discovery & registration.

Adapters register via the ``skillsmith.adapters`` entry-point group (see each
package's pyproject) or imperatively with :func:`register`. The CLI resolves an
adapter by ecosystem name or auto-detects from a target path.
"""

from __future__ import annotations

from importlib.metadata import entry_points
from pathlib import Path

from skillsmith_adapters.base import Adapter

_REGISTRY: dict[str, Adapter] = {}
_LOADED = False


def register(adapter: Adapter) -> None:
    _REGISTRY[adapter.ecosystem] = adapter


def _load_entrypoints() -> None:
    global _LOADED
    if _LOADED:
        return
    for ep in entry_points(group="skillsmith.adapters"):
        try:
            cls = ep.load()
            register(cls())
        except Exception:
            continue
    _LOADED = True


def all_adapters() -> dict[str, Adapter]:
    _load_entrypoints()
    # Ensure the built-ins are present even if entry points aren't installed (e.g.
    # editable dev runs before `uv sync`).
    _ensure_builtins()
    return dict(_REGISTRY)


def get(ecosystem: str) -> Adapter:
    adapters = all_adapters()
    if ecosystem not in adapters:
        raise KeyError(f"No adapter for ecosystem {ecosystem!r}. Known: {sorted(adapters)}")
    return adapters[ecosystem]


def detect(path: Path) -> Adapter | None:
    """Pick the first adapter that can discover something at ``path``."""

    for adapter in all_adapters().values():
        try:
            if adapter.discover(path):
                return adapter
        except Exception:
            continue
    return None


def _ensure_builtins() -> None:
    from skillsmith_adapters.claude_agent_sdk import ClaudeAgentSdkAdapter
    from skillsmith_adapters.claude_skill import ClaudeSkillAdapter
    from skillsmith_adapters.mcp import McpAdapter

    for cls in (ClaudeSkillAdapter, ClaudeAgentSdkAdapter, McpAdapter):
        inst = cls()
        _REGISTRY.setdefault(inst.ecosystem, inst)
