"""Adapter for Claude Agent SDK projects.

Discovers agent definitions built with the Claude Agent SDK (Python/TypeScript),
where "skills" are the system prompt + tool definitions an agent ships. Parsing
focuses on the agent's instruction text and declared tools so the same audit/eval
machinery applies; MCP tools an agent consumes are healed via the ``mcp`` adapter.
"""

from __future__ import annotations

import json
import re
from pathlib import Path

from skillsmith_adapters.base import BaseAdapter, EvalHook, SkillRef
from skillsmith_core.models import SkillDoc

# Markers that identify an Agent SDK agent definition without importing the SDK.
_PY_MARKERS = (
    re.compile(r"from\s+claude_agent_sdk\b"),
    re.compile(r"ClaudeSDKClient|create_agent\("),
)
_TS_MARKERS = (re.compile(r"@anthropic-ai/claude-agent-sdk"),)
_SYS_PROMPT_RE = re.compile(
    r"""system_prompt\s*=\s*(?P<q>['"]{1,3})(?P<body>.*?)(?P=q)""", re.DOTALL
)


class ClaudeAgentSdkAdapter(BaseAdapter):
    ecosystem = "claude-agent-sdk"

    def discover(self, root: Path) -> list[SkillRef]:
        root = Path(root)
        files: list[Path] = []
        if root.is_file():
            files = [root]
        elif root.is_dir():
            files = [*root.rglob("*.py"), *root.rglob("*.ts"), *root.rglob("agent.json")]
        refs: list[SkillRef] = []
        for f in files:
            try:
                text = f.read_text(encoding="utf-8", errors="ignore")
            except OSError:
                continue
            if self._looks_like_agent(f, text):
                refs.append(SkillRef(ecosystem=self.ecosystem, path=f, identifier=f.stem))
        return refs

    def parse(self, ref: SkillRef) -> SkillDoc:
        text = ref.path.read_text(encoding="utf-8", errors="ignore")
        body = text
        name = ref.identifier
        if ref.path.name == "agent.json":
            try:
                data = json.loads(text)
                name = data.get("name", name)
                body = data.get("system_prompt") or data.get("instructions") or text
            except json.JSONDecodeError:
                pass
        else:
            m = _SYS_PROMPT_RE.search(text)
            if m:
                body = m.group("body")
        return SkillDoc(
            path=ref.path,
            name=name,
            description=_first_sentence(body),
            body=body,
            body_line_count=body.count("\n") + 1,
            raw=text,
        )

    def eval_hooks(self, doc: SkillDoc) -> list[EvalHook]:
        def _render(_q: str) -> str:
            return doc.body

        return [EvalHook(name="system-prompt", invoke=_render)]

    @staticmethod
    def _looks_like_agent(path: Path, text: str) -> bool:
        if path.name == "agent.json":
            return '"system_prompt"' in text or '"instructions"' in text
        markers = _PY_MARKERS if path.suffix == ".py" else _TS_MARKERS
        return any(m.search(text) for m in markers)


def _first_sentence(text: str) -> str | None:
    stripped = text.strip()
    if not stripped:
        return None
    end = stripped.find(".")
    return stripped[: end + 1] if end != -1 else stripped[:160]
