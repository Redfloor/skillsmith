"""Autonomy policy: the rules that decide whether skillsmith may act unattended.

This is the safety core. It encodes OWASP LLM06:2025 (Excessive Agency): high-impact
actions require human approval, and open-ended capabilities are forbidden. The team
policy (``skillsmith.config.yaml``) sets the *ceiling*; per-developer config may only
tighten it. :func:`decide` is the single chokepoint every actuator must call.
"""

from __future__ import annotations

import enum
from dataclasses import dataclass


class ActionClass(str, enum.Enum):
    """What skillsmith is about to do. Maps 1:1 to a config autonomy key."""

    AUDIT = "audit"  # read-only analysis
    AUGMENT = "augment"  # generate + wire a script into a skill
    HEAL_ADDITIVE = "heal_additive"  # additive/non-breaking MCP repair (low-risk)
    HEAL_BREAKING = "heal_breaking"  # removed/renamed/required-added/type-changed
    HEAL_WARNING = "heal_warning"  # description change (descriptions are model instructions)


class AutonomyTier(str, enum.Enum):
    """How much latitude an action class has. Ordered least → most autonomous."""

    OFF = "off"
    PROPOSE = "propose"
    AUTO_IF_TESTS_PASS = "auto-if-tests-pass"
    AUTO = "auto"

    @property
    def rank(self) -> int:
        return {
            "off": 0,
            "propose": 1,
            "auto-if-tests-pass": 2,
            "auto": 3,
        }[self.value]


def clamp(requested: AutonomyTier, ceiling: AutonomyTier) -> AutonomyTier:
    """Return the *more restrictive* of two tiers. Per-dev config can never exceed
    the committed team ceiling."""

    return requested if requested.rank <= ceiling.rank else ceiling


@dataclass(frozen=True)
class AutonomyDecision:
    action: ActionClass
    tier: AutonomyTier
    may_auto_apply: bool
    requires_human: bool
    reason: str

    @property
    def must_propose_only(self) -> bool:
        return not self.may_auto_apply


def decide(
    action: ActionClass,
    tier: AutonomyTier,
    *,
    tests_pass: bool,
    low_risk: bool,
    require_human_for: frozenset[ActionClass] = frozenset(),
) -> AutonomyDecision:
    """The single decision chokepoint.

    Parameters
    ----------
    action:
        The action class being attempted.
    tier:
        The *already-clamped* effective tier (team ceiling ∧ local preference).
    tests_pass:
        Whether all golden tests passed for the proposed change.
    low_risk:
        Whether the change is additive/non-breaking (the only auto-apply-eligible tier).
    require_human_for:
        Action classes the team policy pins to human approval regardless of tier
        (``approval_gates.require_human``). These can never be auto-applied.
    """

    if action in require_human_for:
        return AutonomyDecision(
            action,
            tier,
            may_auto_apply=False,
            requires_human=True,
            reason=f"{action.value} is pinned to human approval by approval_gates.require_human.",
        )

    if tier is AutonomyTier.OFF:
        return AutonomyDecision(
            action,
            tier,
            may_auto_apply=False,
            requires_human=True,
            reason=f"{action.value} autonomy is off; no action will be taken.",
        )

    if tier is AutonomyTier.AUTO:
        return AutonomyDecision(
            action,
            tier,
            may_auto_apply=True,
            requires_human=False,
            reason=f"{action.value} is set to auto.",
        )

    if tier is AutonomyTier.AUTO_IF_TESTS_PASS:
        ok = tests_pass and low_risk
        return AutonomyDecision(
            action,
            tier,
            may_auto_apply=ok,
            requires_human=not ok,
            reason=(
                f"{action.value} auto-applied: tests passed and change is low-risk."
                if ok
                else f"{action.value} held for review: "
                + ("tests failed" if not tests_pass else "change is not low-risk/non-breaking.")
            ),
        )

    # PROPOSE
    return AutonomyDecision(
        action,
        tier,
        may_auto_apply=False,
        requires_human=True,
        reason=f"{action.value} is set to propose; opening a PR for human approval.",
    )
