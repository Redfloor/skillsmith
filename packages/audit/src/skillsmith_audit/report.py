"""Render audit results: structured JSON (the model itself) + a human summary."""

from __future__ import annotations

from skillsmith_core.models import AuditReport, BlockClassification, Finding, Severity

# ASCII-safe markers: skillsmith must render on legacy Windows consoles (cp1252) too.
_SEV_ICON = {Severity.INFO: ".", Severity.WARNING: "!", Severity.ERROR: "x"}


def to_json(report: AuditReport, *, indent: int = 2) -> str:
    return report.model_dump_json(indent=indent)


def to_human(report: AuditReport) -> str:
    lines: list[str] = []
    status = "PASS" if report.passed else "FAIL"
    lines.append(f"# audit: {report.skill_name or report.skill_path}  [{status}]")
    lines.append(f"  {report.skill_path}")
    lines.append("")

    if report.findings:
        by_sev: dict[Severity, list[Finding]] = {
            Severity.ERROR: [],
            Severity.WARNING: [],
            Severity.INFO: [],
        }
        for f in report.findings:
            by_sev[f.severity].append(f)
        lines.append(
            f"  findings: {len(by_sev[Severity.ERROR])} error, "
            f"{len(by_sev[Severity.WARNING])} warning, {len(by_sev[Severity.INFO])} info"
        )
        for sev in (Severity.ERROR, Severity.WARNING, Severity.INFO):
            for f in by_sev[sev]:
                loc = f":{f.location.line}" if f.location and f.location.line else ""
                lines.append(f"    {_SEV_ICON[sev]} [{f.rule_id}]{loc} {f.message}")
                if f.suggestion:
                    lines.append(f"        -> {f.suggestion}")
    else:
        lines.append("  findings: none")

    lines.append("")
    det = report.deterministic_candidates
    lines.append(
        f"  work-blocks: {len(report.work_blocks)} total, {len(det)} deterministic-candidate"
    )
    for b in det:
        lines.append(f"    * {b.id} (conf {b.confidence:.2f}) - {b.excerpt[:70]!r}")
    judgment = [
        b for b in report.work_blocks if b.classification is BlockClassification.JUDGMENT_REQUIRED
    ]
    if judgment:
        lines.append(f"    ({len(judgment)} judgment-required block(s) left to the model)")
    return "\n".join(lines)
