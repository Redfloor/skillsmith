"""Two-layer config: local preferences may only TIGHTEN the team ceiling."""

from __future__ import annotations

import textwrap
from pathlib import Path

from skillsmith_core.autonomy import ActionClass, AutonomyTier
from skillsmith_core.config import load_config


def _write(p: Path, body: str) -> None:
    p.write_text(textwrap.dedent(body), encoding="utf-8")


def test_local_cannot_exceed_ceiling(tmp_path: Path) -> None:
    _write(
        tmp_path / "skillsmith.config.yaml",
        """
        version: 1
        autonomy:
          augment: propose
          heal_additive: auto-if-tests-pass
    """,
    )
    # Local tries to ESCALATE augment to auto — must be clamped back to propose.
    _write(
        tmp_path / "skillsmith.local.yaml",
        """
        version: 1
        autonomy:
          augment: auto
    """,
    )
    cfg = load_config(tmp_path)
    assert cfg.tier(ActionClass.AUGMENT) is AutonomyTier.PROPOSE


def test_local_may_tighten(tmp_path: Path) -> None:
    _write(
        tmp_path / "skillsmith.config.yaml",
        """
        version: 1
        autonomy:
          heal_additive: auto-if-tests-pass
    """,
    )
    _write(
        tmp_path / "skillsmith.local.yaml",
        """
        version: 1
        autonomy:
          heal_additive: propose
    """,
    )
    cfg = load_config(tmp_path)
    assert cfg.tier(ActionClass.HEAL_ADDITIVE) is AutonomyTier.PROPOSE


def test_remember_choice_persists_clamped(tmp_path: Path) -> None:
    _write(
        tmp_path / "skillsmith.config.yaml",
        """
        version: 1
        autonomy:
          augment: propose
    """,
    )
    cfg = load_config(tmp_path)
    effective = cfg.remember_choice(ActionClass.AUGMENT, AutonomyTier.AUTO)
    assert effective is AutonomyTier.PROPOSE  # clamped
    # Re-load: the remembered (clamped) choice is read back, still <= ceiling.
    cfg2 = load_config(tmp_path)
    assert cfg2.tier(ActionClass.AUGMENT) is AutonomyTier.PROPOSE


def test_defaults_when_no_files(tmp_path: Path) -> None:
    cfg = load_config(tmp_path)
    assert cfg.tier(ActionClass.AUDIT) is AutonomyTier.AUTO
    assert cfg.tier(ActionClass.HEAL_BREAKING) is AutonomyTier.PROPOSE
