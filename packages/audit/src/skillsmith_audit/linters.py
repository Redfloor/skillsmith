"""The generic, data-driven linters.

Each linter reads its thresholds/markers from the :class:`Ruleset` so behavior
tracks Anthropic's spec via YAML, not code. Adapter-specific linters live in their
adapter (e.g. claude-skill format-contract checks); the engine runs both.
"""

from __future__ import annotations

import re
from collections.abc import Iterable
from pathlib import Path
from typing import Any

from skillsmith_audit.ruleset import Rule, Ruleset
from skillsmith_core.models import Finding, FindingCategory, Location, SkillDoc


def run_all(doc: SkillDoc, rs: Ruleset) -> list[Finding]:
    findings: list[Finding] = []
    for linter in _LINTERS:
        findings.extend(linter(doc, rs))
    return findings


def _emit(
    rule: Rule | None,
    doc: SkillDoc,
    *,
    message: str | None = None,
    line: int | None = None,
    suggestion: str | None = None,
    evidence: dict[str, Any] | None = None,
) -> Iterable[Finding]:
    if rule is None or not rule.enabled:
        return
    yield Finding(
        rule_id=rule.id,
        category=FindingCategory(rule.category),
        severity=rule.severity,
        message=message or rule.message,
        location=Location(path=doc.path, line=line),
        suggestion=suggestion,
        evidence=evidence or {},
    )


# --------------------------------------------------------------------------- #
# Metadata
# --------------------------------------------------------------------------- #
def _lint_metadata(doc: SkillDoc, rs: Ruleset) -> Iterable[Finding]:
    if not doc.name:
        yield from _emit(
            rs.rule("metadata.name_required"),
            doc,
            suggestion="Add a `name:` field to the YAML frontmatter.",
        )
    else:
        pattern = rs.limit("name_pattern")
        if pattern and not re.match(pattern, doc.name):
            yield from _emit(rs.rule("metadata.name_format"), doc, evidence={"name": doc.name})
        max_chars = rs.limit("name_max_chars", 64)
        if len(doc.name) > max_chars:
            yield from _emit(
                rs.rule("metadata.name_format"),
                doc,
                message=f"`name` exceeds {max_chars} chars.",
                evidence={"length": len(doc.name)},
            )
    if not doc.description:
        yield from _emit(
            rs.rule("metadata.description_required"),
            doc,
            suggestion="Add a `description:` covering WHAT it does and WHEN to use it.",
        )


# --------------------------------------------------------------------------- #
# Description quality
# --------------------------------------------------------------------------- #
def _lint_description(doc: SkillDoc, rs: Ruleset) -> Iterable[Finding]:
    desc = (doc.description or "").strip()
    if not desc:
        return
    low = desc.lower()
    if len(desc) < rs.limit("description_min_chars", 40):
        yield from _emit(rs.rule("description.too_short"), doc, evidence={"length": len(desc)})
    if len(desc) > rs.limit("description_max_chars", 1024):
        yield from _emit(rs.rule("description.too_long"), doc, evidence={"length": len(desc)})

    when_rule = rs.rule("description.missing_when_to_use")
    if when_rule and when_rule.enabled:
        cues = when_rule.params.get("when_to_use_cues", [])
        if not any(c in low for c in cues):
            yield from _emit(
                when_rule, doc, suggestion="Add a 'use when ...' clause so triggering is accurate."
            )

    fp_rule = rs.rule("description.not_third_person")
    if fp_rule and fp_rule.enabled:
        markers = fp_rule.params.get("first_person_markers", [])
        hit = next((m for m in markers if m in low), None)
        if hit:
            yield from _emit(fp_rule, doc, evidence={"marker": hit.strip()})

    vague_rule = rs.rule("description.too_vague")
    if vague_rule and vague_rule.enabled:
        markers = vague_rule.params.get("vague_markers", [])
        hit = next((m for m in markers if m in low), None)
        if hit:
            yield from _emit(vague_rule, doc, evidence={"marker": hit.strip()})


# --------------------------------------------------------------------------- #
# Body length / progressive disclosure
# --------------------------------------------------------------------------- #
def _lint_body(doc: SkillDoc, rs: Ruleset) -> Iterable[Finding]:
    max_lines = rs.limit("body_max_lines", 500)
    if doc.body_line_count > max_lines:
        yield from _emit(
            rs.rule("body.too_long"),
            doc,
            message=f"Body is {doc.body_line_count} lines (> {max_lines}).",
            evidence={"lines": doc.body_line_count, "limit": max_lines},
            suggestion="Move detail into reference files and link them.",
        )
        if not doc.referenced_paths:
            yield from _emit(rs.rule("progressive_disclosure.no_references"), doc)


# --------------------------------------------------------------------------- #
# Reference + script integrity
# --------------------------------------------------------------------------- #
def _lint_references(doc: SkillDoc, rs: Ruleset) -> Iterable[Finding]:
    for ref in doc.referenced_paths:
        if not ref.exists():
            yield from _emit(
                rs.rule("references.missing_file"),
                doc,
                message=f"Referenced file is missing: {ref}",
                evidence={"path": str(ref)},
            )
    for script in doc.script_paths:
        if script.exists() and not _is_executable(script):
            yield from _emit(
                rs.rule("scripts.not_executable"),
                doc,
                message=f"Script is not executable: {script}",
                evidence={"path": str(script)},
                suggestion=f"chmod +x {script}",
            )


def _is_executable(path: Path) -> bool:
    import os
    import stat

    try:
        mode = path.stat().st_mode
    except OSError:
        return False
    # On Windows the x-bit is not meaningful; treat .py/.sh as runnable via interpreter.
    if os.name == "nt":
        return path.suffix in {".py", ".sh", ".ps1", ".bat", ".cmd"}
    return bool(mode & (stat.S_IXUSR | stat.S_IXGRP | stat.S_IXOTH))


# --------------------------------------------------------------------------- #
# Unjustified imperatives
# --------------------------------------------------------------------------- #
def _lint_imperatives(doc: SkillDoc, rs: Ruleset) -> Iterable[Finding]:
    rule = rs.rule("imperative.unjustified")
    if rule is None or not rule.enabled:
        return
    tokens = rule.params.get("tokens", [])
    rationale_cues = rule.params.get("rationale_cues", [])
    token_re = re.compile(r"\b(" + "|".join(re.escape(t) for t in tokens) + r")\b")
    for i, line in enumerate(doc.body.splitlines(), start=1):
        if token_re.search(line):
            low = line.lower()
            if not any(c in low for c in rationale_cues):
                yield from _emit(
                    rule,
                    doc,
                    line=i,
                    message=f"Imperative without rationale: {line.strip()[:80]!r}",
                    evidence={"line_text": line.strip()},
                )


# --------------------------------------------------------------------------- #
# Prompt anti-patterns
# --------------------------------------------------------------------------- #
def _lint_antipatterns(doc: SkillDoc, rs: Ruleset) -> Iterable[Finding]:
    body_low = doc.body.lower()

    conflict = rs.rule("antipattern.conflicting_instructions")
    if conflict and conflict.enabled:
        # crude but useful: "always <verb>" paired with "never <verb>"
        always = set(re.findall(r"always (\w+)", body_low))
        never = set(re.findall(r"never (\w+)", body_low))
        clash = always & never
        if clash:
            yield from _emit(
                conflict,
                doc,
                message=f"Conflicting 'always'/'never' on: {', '.join(sorted(clash))}",
                evidence={"verbs": sorted(clash)},
            )

    err = rs.rule("antipattern.missing_error_handling")
    if err and err.enabled:
        invoke_cues = err.params.get("invoke_cues", [])
        error_cues = err.params.get("error_cues", [])
        if any(c in body_low for c in invoke_cues) and not any(c in body_low for c in error_cues):
            yield from _emit(
                err, doc, suggestion="Describe what to do when an invoked command/script fails."
            )


_LINTERS = (
    _lint_metadata,
    _lint_description,
    _lint_body,
    _lint_references,
    _lint_imperatives,
    _lint_antipatterns,
)
