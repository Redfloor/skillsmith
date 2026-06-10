"""Augment gating: validate-in-sandbox + variance + token-reduction, never auto-commit."""

from __future__ import annotations

from pathlib import Path

import pytest

from skillsmith_augment import augment_block, select_candidates
from skillsmith_core.config import SandboxConfig, load_config
from skillsmith_core.models import (
    BlockClassification,
    Location,
    SkillDoc,
    WorkBlock,
)
from skillsmith_core.sandbox import Sandbox


@pytest.fixture
def dev_sandbox() -> Sandbox:
    # 'dev' profile runs locally without requiring gVisor/Firecracker on the CI box,
    # so the gating pipeline is exercised even where no isolating backend exists.
    return Sandbox(SandboxConfig(profile="dev", deny_network=True))


def _doc(tmp_path: Path) -> SkillDoc:
    p = tmp_path / "SKILL.md"
    p.write_text("---\nname: t\n---\nbody\n", encoding="utf-8")
    return SkillDoc(path=p, name="t", body="body")


def _det_block(excerpt: str, conf: float) -> WorkBlock:
    return WorkBlock(
        id="t#b0",
        location=Location(path=Path("SKILL.md")),
        excerpt=excerpt,
        classification=BlockClassification.DETERMINISTIC_CANDIDATE,
        rationale="test",
        confidence=conf,
    )


def test_select_candidates_requires_high_confidence() -> None:
    high = _det_block("x", 0.9)
    low = _det_block("x", 0.6)
    judg = WorkBlock(
        id="t#b1",
        location=Location(path=Path("SKILL.md")),
        excerpt="x",
        classification=BlockClassification.JUDGMENT_REQUIRED,
        rationale="t",
        confidence=0.99,
    )
    selected = select_candidates([high, low, judg])
    assert selected == [high]


def test_meaningful_block_produces_proposal(tmp_path: Path, dev_sandbox: Sandbox) -> None:
    cfg = load_config(tmp_path)
    long_excerpt = (
        "Parse the input log file, extract every IPv4 address with a regex, "
        "deduplicate them, sort numerically, and write the unique sorted list to output. "
        "This is purely mechanical string processing with no judgement involved at all."
    )
    block = _det_block(long_excerpt, 0.9)
    outcome = augment_block(_doc(tmp_path), block, config=cfg, sandbox=dev_sandbox)
    assert outcome.proposed is not None
    assert outcome.proposed.action_class == "augment"
    assert outcome.proposed.token_delta is not None and outcome.proposed.token_delta < 0
    assert outcome.proposed.low_risk is True


def test_tiny_block_skipped_no_token_win(tmp_path: Path, dev_sandbox: Sandbox) -> None:
    cfg = load_config(tmp_path)
    outcome = augment_block(
        _doc(tmp_path), _det_block("count words", 0.9), config=cfg, sandbox=dev_sandbox
    )
    assert outcome.proposed is None
    assert outcome.skipped_reason is not None
