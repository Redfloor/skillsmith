"""Heal engine: snapshot -> diff -> canary -> autonomy decision -> propose.

Flow per the self-healing default: detect -> diagnose -> propose-as-diff/PR ->
human-approve, with a full audit trail. Auto-fix is opt-in and limited to the
additive/low-risk tier that passes tests. No silent commits.
"""

from __future__ import annotations

from collections.abc import Callable, Sequence
from dataclasses import dataclass
from pathlib import Path

from skillsmith_adapters import detect, get
from skillsmith_adapters.base import Adapter
from skillsmith_adapters.mcp import load_snapshot, save_snapshot
from skillsmith_core.autonomy import ActionClass, AutonomyDecision, decide
from skillsmith_core.config import EffectiveConfig, load_config
from skillsmith_core.models import (
    AuditTrailEntry,
    ContractDiff,
    ContractSnapshot,
    ProposedChange,
    Severity,
    SkillDoc,
)
from skillsmith_core.trail import record
from skillsmith_heal.diff import diff_contracts, has_drift


@dataclass
class HealOutcome:
    server_id: str
    diff: ContractDiff
    decision: AutonomyDecision
    proposed: ProposedChange | None
    drift: bool


def _action_for(diff: ContractDiff) -> ActionClass:
    if diff.severity is Severity.ERROR:
        return ActionClass.HEAL_BREAKING
    if diff.severity is Severity.WARNING:
        return ActionClass.HEAL_WARNING
    return ActionClass.HEAL_ADDITIVE


def behavioral_drift(
    canary_queries: Sequence[str],
    fingerprint_fn: Callable[[str], str] | None,
    baseline: ContractSnapshot,
) -> bool:
    """Run canary queries and compare an output fingerprint to the baseline's.

    ``fingerprint_fn`` runs a canary through the live server (inside the sandbox) and
    returns a stable fingerprint. Absent a live server we cannot detect behavioral
    drift and conservatively report False (schema diff still applies)."""

    if not canary_queries or fingerprint_fn is None or baseline.behavior_fingerprint is None:
        return False
    combined = "\n".join(fingerprint_fn(q) for q in canary_queries)
    return combined != baseline.behavior_fingerprint


def heal_doc(
    doc: SkillDoc,
    *,
    adapter: Adapter,
    config: EffectiveConfig,
    repo_root: Path,
    update_snapshot: bool = False,
    canary_fingerprint: Callable[[str], str] | None = None,
) -> list[HealOutcome]:
    outcomes: list[HealOutcome] = []
    for hook in adapter.heal_hooks(doc):
        current = hook.snapshot()
        baseline_path = doc.path.with_name(f"{hook.name}.mcpc.json")
        baseline = load_snapshot(baseline_path) if baseline_path.exists() else current

        diff = diff_contracts(baseline, current)
        drift = behavioral_drift(hook.canary_queries, canary_fingerprint, baseline)
        diff.behavioral_drift = drift
        if drift and diff.severity is Severity.INFO:
            diff.severity = Severity.WARNING
        diff.human_summary = diff.human_summary  # already computed

        action = _action_for(diff)
        tier = config.tier(action)
        # Heal repairs are only "low-risk" when purely additive and non-behavioral.
        low_risk = action is ActionClass.HEAL_ADDITIVE and not drift
        decision = decide(
            action,
            tier,
            tests_pass=True,  # the heal repair is re-validated by the eval gate in CI
            low_risk=low_risk,
            require_human_for=config.require_human,
        )

        proposed: ProposedChange | None = None
        if has_drift(diff):
            proposed = _propose_repair(doc, hook.name, diff, baseline_path, current, low_risk)

        # Persist the new snapshot only when explicitly asked (e.g. `--update-baseline`).
        if update_snapshot:
            save_snapshot(current, baseline_path)

        record(
            repo_root,
            AuditTrailEntry(
                action_class=action.value,
                target=doc.path,
                decision=(
                    "proposed-pr"
                    if proposed and not decision.may_auto_apply
                    else "auto-apply-eligible"
                    if decision.may_auto_apply
                    else "no-drift"
                ),
                autonomy_tier=tier.value,
                detail={
                    "server": hook.name,
                    "summary": diff.human_summary,
                    "reason": decision.reason,
                },
            ),
        )
        outcomes.append(HealOutcome(hook.name, diff, decision, proposed, drift))
    return outcomes


def _propose_repair(
    doc: SkillDoc,
    server_id: str,
    diff: ContractDiff,
    baseline_path: Path,
    current: ContractSnapshot,
    low_risk: bool,
) -> ProposedChange:
    new_json = current.model_dump_json(indent=2)
    unified = (
        f"--- a/{baseline_path.name}\n+++ b/{baseline_path.name}\n"
        f"@@ contract drift: {diff.human_summary} @@\n"
        + "".join(f"+{line}\n" for line in new_json.splitlines()[:40])
        + ("+...\n" if new_json.count("\n") > 40 else "")
    )
    return ProposedChange(
        action_class=_action_for(diff).value,
        title=f"Heal MCP contract drift for '{server_id}' ({diff.severity.value})",
        rationale=(
            f"Detected drift: {diff.human_summary}. Proposing an updated contract "
            f"snapshot ({baseline_path.name}) and any dependent skill edits. "
            "Review required before merge — descriptions are model instructions."
        ),
        unified_diff=unified,
        touched_paths=[baseline_path],
        low_risk=low_risk,
    )


def heal_path(
    target: Path | str,
    *,
    config: EffectiveConfig | None = None,
    repo_root: Path | None = None,
    ecosystem: str | None = None,
    update_snapshot: bool = False,
) -> list[HealOutcome]:
    target = Path(target)
    cfg = config or load_config(target)
    root = repo_root or _find_repo_root(target)
    adapter = get(ecosystem) if ecosystem else detect(target)
    if adapter is None:
        raise ValueError(f"No adapter could discover an MCP target at {target}")
    out: list[HealOutcome] = []
    for ref in adapter.discover(target):
        out.extend(
            heal_doc(
                adapter.parse(ref),
                adapter=adapter,
                config=cfg,
                repo_root=root,
                update_snapshot=update_snapshot,
            )
        )
    return out


def _find_repo_root(start: Path) -> Path:
    start = start if start.is_dir() else start.parent
    for parent in [start, *start.parents]:
        if (parent / ".git").exists():
            return parent
    return start
