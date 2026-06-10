"""The decision chokepoint enforces human-in-the-loop / Excessive Agency limits."""

from __future__ import annotations

from skillsmith_core.autonomy import ActionClass, AutonomyTier, clamp, decide


def test_clamp_picks_more_restrictive() -> None:
    assert clamp(AutonomyTier.AUTO, AutonomyTier.PROPOSE) is AutonomyTier.PROPOSE
    assert clamp(AutonomyTier.OFF, AutonomyTier.AUTO) is AutonomyTier.OFF


def test_propose_never_auto_applies() -> None:
    d = decide(ActionClass.AUGMENT, AutonomyTier.PROPOSE, tests_pass=True, low_risk=True)
    assert not d.may_auto_apply
    assert d.requires_human


def test_auto_if_tests_pass_requires_both() -> None:
    ok = decide(
        ActionClass.HEAL_ADDITIVE, AutonomyTier.AUTO_IF_TESTS_PASS, tests_pass=True, low_risk=True
    )
    assert ok.may_auto_apply
    no_tests = decide(
        ActionClass.HEAL_ADDITIVE, AutonomyTier.AUTO_IF_TESTS_PASS, tests_pass=False, low_risk=True
    )
    assert not no_tests.may_auto_apply
    not_low = decide(
        ActionClass.HEAL_ADDITIVE, AutonomyTier.AUTO_IF_TESTS_PASS, tests_pass=True, low_risk=False
    )
    assert not not_low.may_auto_apply


def test_require_human_pin_overrides_auto() -> None:
    d = decide(
        ActionClass.HEAL_BREAKING,
        AutonomyTier.AUTO,
        tests_pass=True,
        low_risk=True,
        require_human_for=frozenset({ActionClass.HEAL_BREAKING}),
    )
    assert not d.may_auto_apply
    assert d.requires_human


def test_off_takes_no_action() -> None:
    d = decide(ActionClass.AUGMENT, AutonomyTier.OFF, tests_pass=True, low_risk=True)
    assert not d.may_auto_apply
