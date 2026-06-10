"""Adapter for MCP (Model Context Protocol) servers.

Discovers MCP server declarations (``.mcp.json`` / ``mcp.json`` and committed
``*.mcpc.json`` contract snapshots) and exposes heal hooks that snapshot a server's
tool contract (names, params, input schemas, descriptions) for drift detection.

Live introspection (spawning the server and calling ``tools/list``) is wired through
:func:`live_snapshot`, kept behind the sandbox by the heal engine. When a server
cannot be reached, the committed ``*.mcpc.json`` snapshot is used as the source of truth.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from skillsmith_adapters.base import BaseAdapter, HealHook, SkillRef
from skillsmith_core.models import ContractSnapshot, SkillDoc, ToolContract

MCP_CONFIG_NAMES = (".mcp.json", "mcp.json")
SNAPSHOT_SUFFIX = ".mcpc.json"


class McpAdapter(BaseAdapter):
    ecosystem = "mcp"

    def discover(self, root: Path) -> list[SkillRef]:
        root = Path(root)
        refs: list[SkillRef] = []
        candidates: list[Path] = []
        if root.is_file() and (
            root.name in MCP_CONFIG_NAMES or root.name.endswith(SNAPSHOT_SUFFIX)
        ):
            candidates = [root]
        elif root.is_dir():
            for name in MCP_CONFIG_NAMES:
                candidates += list(root.rglob(name))
            candidates += list(root.rglob(f"*{SNAPSHOT_SUFFIX}"))
        for c in sorted(set(candidates)):
            for server_id in _server_ids(c):
                refs.append(SkillRef(ecosystem=self.ecosystem, path=c, identifier=server_id))
        return refs

    def parse(self, ref: SkillRef) -> SkillDoc:
        # MCP "skills" are servers; we model the config file as the SkillDoc body.
        text = ref.path.read_text(encoding="utf-8")
        return SkillDoc(path=ref.path, name=ref.identifier, body=text, raw=text)

    def heal_hooks(self, doc: SkillDoc) -> list[HealHook]:
        hooks: list[HealHook] = []
        if doc.path.name.endswith(SNAPSHOT_SUFFIX):
            snap = load_snapshot(doc.path)

            def _committed(s: ContractSnapshot = snap) -> ContractSnapshot:
                return s

            hooks.append(HealHook(name=snap.server_id, snapshot=_committed))
        else:
            for server_id in _server_ids(doc.path):

                def _live(sid: str = server_id, p: Path = doc.path) -> ContractSnapshot:
                    return live_snapshot(p, sid)

                hooks.append(HealHook(name=server_id, snapshot=_live))
        return hooks


# --------------------------------------------------------------------------- #
# Snapshot I/O
# --------------------------------------------------------------------------- #
def load_snapshot(path: Path) -> ContractSnapshot:
    return ContractSnapshot.model_validate_json(Path(path).read_text(encoding="utf-8"))


def save_snapshot(snapshot: ContractSnapshot, path: Path) -> Path:
    path = Path(path)
    path.write_text(snapshot.model_dump_json(indent=2), encoding="utf-8")
    return path


def snapshot_from_tools_list(server_id: str, tools_list: list[dict[str, Any]]) -> ContractSnapshot:
    """Build a snapshot from a raw MCP ``tools/list`` response."""

    tools = [
        ToolContract(
            name=t.get("name", ""),
            description=t.get("description", "") or "",
            input_schema=t.get("inputSchema") or t.get("input_schema") or {},
        )
        for t in tools_list
    ]
    return ContractSnapshot(server_id=server_id, tools=sorted(tools, key=lambda x: x.name))


def live_snapshot(config_path: Path, server_id: str) -> ContractSnapshot:
    """Best-effort live introspection.

    TODO: spawn the configured server inside the sandbox and issue ``tools/list`` over
    stdio. For now we fall back to a committed snapshot beside the config, or an empty
    contract if none exists, so the heal engine degrades gracefully offline.
    """

    sibling = config_path.with_name(f"{server_id}{SNAPSHOT_SUFFIX}")
    if sibling.exists():
        return load_snapshot(sibling)
    return ContractSnapshot(server_id=server_id, tools=[])


def _server_ids(path: Path) -> list[str]:
    if path.name.endswith(SNAPSHOT_SUFFIX):
        try:
            return [load_snapshot(path).server_id]
        except Exception:
            return [path.name[: -len(SNAPSHOT_SUFFIX)]]
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return []
    servers = data.get("mcpServers") or data.get("servers") or {}
    return sorted(servers.keys())
