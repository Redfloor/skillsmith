"""Meta-evals: assert skillsmith catches the issues SEEDED into the fixture corpus,
and that the determinism harness distinguishes high- vs low-variance skills.

Each fixture ships an ``expected.yaml`` manifest of seeded issues; this test is the
ground-truth check that the auditor actually finds them.
"""

from __future__ import annotations

from pathlib import Path

import pytest
import yaml

from skillsmith_adapters import ClaudeSkillAdapter
from skillsmith_audit import audit_doc
from skillsmith_core.config import load_config
from skillsmith_core.models import BlockClassification

SKILLS = Path(__file__).parent / "fixtures" / "skills"
CASES = sorted(SKILLS.glob("*/expected.yaml"))


@pytest.mark.parametrize("expected_path", CASES, ids=lambda p: p.parent.name)
def test_seeded_issues_are_caught(expected_path: Path) -> None:
    expected = yaml.safe_load(expected_path.read_text(encoding="utf-8"))
    skill = expected_path.parent / "SKILL.md"

    adapter = ClaudeSkillAdapter()
    ref = adapter.discover(skill)[0]
    report = audit_doc(adapter.parse(ref), adapter=adapter, config=load_config(skill))

    found = {f.rule_id for f in report.findings}

    for rid in expected.get("must_find_rules", []) or []:
        assert rid in found, f"{skill.parent.name}: expected to catch {rid}, got {sorted(found)}"

    for rid in expected.get("forbid_rules", []) or []:
        assert rid not in found, f"{skill.parent.name}: false positive {rid}"

    det = sum(
        1
        for b in report.work_blocks
        if b.classification is BlockClassification.DETERMINISTIC_CANDIDATE
    )
    jud = sum(
        1 for b in report.work_blocks if b.classification is BlockClassification.JUDGMENT_REQUIRED
    )
    assert det >= expected.get("deterministic_candidate_min", 0)
    assert jud >= expected.get("judgment_required_min", 0)

    if "must_pass" in expected:
        assert report.passed is expected["must_pass"]


def test_determinism_harness_separates_variance() -> None:
    import itertools

    from skillsmith_eval import measure

    low = measure(lambda q: "constant", "p", runs=6)
    counter = itertools.count()
    high = measure(lambda q: f"v{next(counter)}", "p", runs=6)
    # The harness must rank the flaky skill strictly above the deterministic one.
    assert high.normalized_variance > low.normalized_variance
    assert low.normalized_variance == 0.0
