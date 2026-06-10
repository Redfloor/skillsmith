"""Audit engine on real fixtures (parser + linters + classifier)."""

from __future__ import annotations

from pathlib import Path

from skillsmith_adapters import ClaudeSkillAdapter
from skillsmith_adapters.claude_skill import parse_skill_md
from skillsmith_audit import audit_doc
from skillsmith_core.config import load_config
from skillsmith_core.models import BlockClassification


def _audit(path: Path):
    adapter = ClaudeSkillAdapter()
    ref = adapter.discover(path)[0]
    doc = adapter.parse(ref)
    return audit_doc(doc, adapter=adapter, config=load_config(path))


def test_parse_frontmatter(skills_dir: Path) -> None:
    doc = parse_skill_md(skills_dir / "good-csv-cleaner" / "SKILL.md")
    assert doc.name == "csv-cleaner"
    assert "Cleans messy CSV" in (doc.description or "")
    assert any(p.name == "schema.json" for p in doc.referenced_paths)
    assert any(p.name == "normalize.py" for p in doc.script_paths)


def test_flawed_skill_findings(skills_dir: Path) -> None:
    report = _audit(skills_dir / "flawed-summarizer" / "SKILL.md")
    rule_ids = {f.rule_id for f in report.findings}
    for expected in (
        "metadata.name_format",
        "description.too_vague",
        "description.missing_when_to_use",
        "imperative.unjustified",
        "antipattern.conflicting_instructions",
        "antipattern.missing_error_handling",
    ):
        assert expected in rule_ids, f"expected {expected} in {sorted(rule_ids)}"


def test_missing_metadata_is_error(skills_dir: Path) -> None:
    report = _audit(skills_dir / "missing-metadata" / "SKILL.md")
    rule_ids = {f.rule_id for f in report.findings}
    assert "metadata.name_required" in rule_ids
    assert "metadata.description_required" in rule_ids
    assert "references.missing_file" in rule_ids
    assert report.passed is False  # hard fail on error-severity findings


def test_good_skill_passes(skills_dir: Path) -> None:
    report = _audit(skills_dir / "good-csv-cleaner" / "SKILL.md")
    assert report.passed is True
    rule_ids = {f.rule_id for f in report.findings}
    assert "metadata.name_required" not in rule_ids
    assert "description.too_vague" not in rule_ids


def test_classification_splits_blocks(skills_dir: Path) -> None:
    report = _audit(skills_dir / "flawed-summarizer" / "SKILL.md")
    det = [
        b
        for b in report.work_blocks
        if b.classification is BlockClassification.DETERMINISTIC_CANDIDATE
    ]
    jud = [
        b for b in report.work_blocks if b.classification is BlockClassification.JUDGMENT_REQUIRED
    ]
    assert len(det) >= 2  # word-count + email-extract
    assert len(jud) >= 1  # summarize-in-your-own-words/tone
