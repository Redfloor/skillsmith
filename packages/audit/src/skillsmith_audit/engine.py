"""Audit engine: parse -> generic linters + adapter audit hooks -> classify.

The engine is ecosystem-agnostic; it gets parsing + extra lint hooks from whichever
adapter owns the target.
"""

from __future__ import annotations

from pathlib import Path

from skillsmith_adapters import detect, get
from skillsmith_adapters.base import Adapter
from skillsmith_audit.classifier import classify
from skillsmith_audit.linters import run_all
from skillsmith_audit.ruleset import load_ruleset
from skillsmith_core.config import EffectiveConfig, load_config
from skillsmith_core.models import AuditReport, SkillDoc


def audit_doc(
    doc: SkillDoc,
    *,
    adapter: Adapter,
    config: EffectiveConfig,
) -> AuditReport:
    rs = load_ruleset(config.ruleset, overrides=config.rule_overrides)
    findings = run_all(doc, rs)
    for hook in adapter.audit_hooks():
        findings.extend(hook(doc, config))
    blocks = classify(doc, rs.classifier)
    report = AuditReport(
        skill_path=doc.path,
        skill_name=doc.name,
        findings=findings,
        work_blocks=blocks,
    )
    return report.with_computed_pass()


def audit_path(
    target: Path | str,
    *,
    config: EffectiveConfig | None = None,
    ecosystem: str | None = None,
) -> list[AuditReport]:
    """Audit every skill discoverable at ``target`` (file, dir, or glob root)."""

    target = Path(target)
    cfg = config or load_config(target)
    adapter = get(ecosystem) if ecosystem else detect(target)
    if adapter is None:
        raise ValueError(f"No adapter could discover a skill at {target}")
    reports: list[AuditReport] = []
    for ref in adapter.discover(target):
        doc = adapter.parse(ref)
        reports.append(audit_doc(doc, adapter=adapter, config=cfg))
    return reports
