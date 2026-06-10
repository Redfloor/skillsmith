"""Adapter for the Claude Code ``SKILL.md`` format.

Parses YAML frontmatter + Markdown body into a :class:`SkillDoc`, discovers
companion reference docs and scripts, and exposes ecosystem-specific audit hooks
that complement the generic data-driven linter in ``skillsmith_audit``.
"""

from __future__ import annotations

import re
from collections.abc import Iterable
from pathlib import Path
from typing import Any

import yaml

from skillsmith_adapters.base import AuditHook, BaseAdapter, EvalHook, HealHook, SkillRef
from skillsmith_core.config import EffectiveConfig
from skillsmith_core.models import (
    Finding,
    FindingCategory,
    Location,
    Severity,
    SkillDoc,
)

_FRONTMATTER_RE = re.compile(r"^---\s*\n(.*?)\n---\s*\n", re.DOTALL)
# Markdown links / inline code that look like companion file paths.
_PATH_RE = re.compile(r"(?:\]\(|`)([A-Za-z0-9_./\-]+\.(?:md|py|sh|json|ya?ml|txt))(?:\)|`)")
_SCRIPT_INVOKE_RE = re.compile(
    r"(?:^|\s)(?:python3?|bash|sh|node|\./)?\s*(scripts/[A-Za-z0-9_./\-]+)"
)


class ClaudeSkillAdapter(BaseAdapter):
    ecosystem = "claude-skill"

    # ----------------------------------------------------------- discover --- #
    def discover(self, root: Path) -> list[SkillRef]:
        root = Path(root)
        if root.is_file() and root.name == "SKILL.md":
            files = [root]
        else:
            files = sorted(root.rglob("SKILL.md")) if root.is_dir() else []
        refs: list[SkillRef] = []
        for f in files:
            name = self._peek_name(f) or f.parent.name
            refs.append(SkillRef(ecosystem=self.ecosystem, path=f, identifier=name))
        return refs

    # -------------------------------------------------------------- parse --- #
    def parse(self, ref: SkillRef) -> SkillDoc:
        return parse_skill_md(ref.path)

    # -------------------------------------------------------- audit hooks --- #
    def audit_hooks(self) -> list[AuditHook]:
        return [_hook_format_contract, _hook_progressive_disclosure]

    # --------------------------------------------------------- eval hooks --- #
    def eval_hooks(self, doc: SkillDoc) -> list[EvalHook]:
        # The real invocation path is provided by the host (Claude Code / SDK). For
        # the MVP harness we expose a deterministic "render" invoke so the variance
        # harness has something to measure on skills that ship pure scripts.
        def _render(_query: str) -> str:
            return doc.body

        triggers = _extract_examples(doc, positive=True)
        anti = _extract_examples(doc, positive=False)
        return [
            EvalHook(
                name="render", invoke=_render, should_trigger=triggers, should_not_trigger=anti
            )
        ]

    # --------------------------------------------------------- heal hooks --- #
    def heal_hooks(self, doc: SkillDoc) -> list[HealHook]:
        # A SKILL.md may declare MCP servers it depends on; the mcp adapter provides
        # the actual contract snapshots. Nothing skill-local to snapshot here.
        return []

    # ------------------------------------------------------------ helpers --- #
    @staticmethod
    def _peek_name(path: Path) -> str | None:
        try:
            doc = parse_skill_md(path)
        except Exception:
            return None
        return doc.name


# --------------------------------------------------------------------------- #
# Parsing
# --------------------------------------------------------------------------- #
def parse_skill_md(path: Path) -> SkillDoc:
    """Parse a SKILL.md file into a :class:`SkillDoc`. Tolerant of missing frontmatter."""

    path = Path(path)
    raw = path.read_text(encoding="utf-8")
    m = _FRONTMATTER_RE.match(raw)
    frontmatter: dict[str, Any] = {}
    body = raw
    if m:
        try:
            frontmatter = yaml.safe_load(m.group(1)) or {}
        except yaml.YAMLError:
            frontmatter = {}
        body = raw[m.end() :]

    referenced: list[Path] = []
    for rel in _PATH_RE.findall(body):
        referenced.append(path.parent / rel)
    scripts: list[Path] = []
    for rel in _SCRIPT_INVOKE_RE.findall(body):
        scripts.append(path.parent / rel)

    return SkillDoc(
        path=path,
        name=frontmatter.get("name"),
        description=frontmatter.get("description"),
        frontmatter=frontmatter,
        body=body,
        body_line_count=body.count("\n") + 1 if body else 0,
        referenced_paths=_dedupe(referenced),
        script_paths=_dedupe(scripts),
        raw=raw,
    )


def _dedupe(paths: list[Path]) -> list[Path]:
    seen: set[str] = set()
    out: list[Path] = []
    for p in paths:
        key = p.as_posix()
        if key not in seen:
            seen.add(key)
            out.append(p)
    return out


def _extract_examples(doc: SkillDoc, *, positive: bool) -> list[str]:
    # Heuristic: lines under a "when to use"/"do not use" cue become trigger queries.
    cue = (
        ("when to use", "use this when", "triggers")
        if positive
        else ("do not use", "don't use", "skip when")
    )
    out: list[str] = []
    for line in doc.body.splitlines():
        low = line.lower()
        if any(c in low for c in cue) and len(line.strip()) > 12:
            out.append(line.strip("-* ").strip())
    return out[:10]


# --------------------------------------------------------------------------- #
# Ecosystem-specific audit hooks
# --------------------------------------------------------------------------- #
def _hook_format_contract(doc: SkillDoc, _cfg: EffectiveConfig) -> Iterable[Finding]:
    """Flag integration/format-contract mismatches: the body promises an output
    format but no script or schema enforces it."""

    promises_json = "```json" in doc.body or "return json" in doc.body.lower()
    has_schema = any(p.suffix in {".json"} and "schema" in p.name for p in doc.referenced_paths)
    if promises_json and not has_schema and not doc.script_paths:
        yield Finding(
            rule_id="claude.format_contract.unenforced_json",
            category=FindingCategory.FORMAT_CONTRACT,
            severity=Severity.WARNING,
            message="Body specifies a JSON output format but nothing validates it "
            "(no JSON schema, no script). Consider a deterministic validator.",
            location=Location(path=doc.path),
            suggestion="Add a JSON Schema reference file and a validate step, or a "
            "script that emits/validates the contract.",
        )


def _hook_progressive_disclosure(doc: SkillDoc, _cfg: EffectiveConfig) -> Iterable[Finding]:
    """Heavy how-to content inline (long fenced blocks) should move to reference files."""

    fenced = sum(1 for line in doc.body.splitlines() if line.strip().startswith("```"))
    if doc.body_line_count > 200 and fenced >= 6 and not doc.referenced_paths:
        yield Finding(
            rule_id="claude.progressive_disclosure.inline_heavy",
            category=FindingCategory.PROGRESSIVE_DISCLOSURE,
            severity=Severity.WARNING,
            message="Large body with many inline code blocks and no reference files. "
            "Move heavy content into companion reference docs (progressive disclosure).",
            location=Location(path=doc.path),
            suggestion="Extract long examples/snippets into reference/*.md and link them.",
        )
