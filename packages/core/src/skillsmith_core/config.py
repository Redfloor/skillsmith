"""Two-layer configuration with an enforced autonomy ceiling.

Layer 1 (committed ``skillsmith.config.yaml``): team policy — the *ceiling*.
Layer 2 (gitignored ``skillsmith.local.yaml``): per-developer preferences and
remembered "auto-fix vs propose" answers. Layer 2 may only ever *tighten* autonomy;
:func:`load_config` clamps every local value to the committed ceiling so a developer
can never grant themselves more agency than the team sanctioned.
"""

from __future__ import annotations

from fnmatch import fnmatch
from pathlib import Path
from typing import Any

import yaml
from pydantic import BaseModel, ConfigDict, Field

from skillsmith_core.autonomy import ActionClass, AutonomyTier, clamp

COMMITTED_NAME = "skillsmith.config.yaml"
LOCAL_NAME = "skillsmith.local.yaml"

_DEFAULT_AUTONOMY: dict[ActionClass, AutonomyTier] = {
    ActionClass.AUDIT: AutonomyTier.AUTO,
    ActionClass.AUGMENT: AutonomyTier.PROPOSE,
    ActionClass.HEAL_ADDITIVE: AutonomyTier.AUTO_IF_TESTS_PASS,
    ActionClass.HEAL_BREAKING: AutonomyTier.PROPOSE,
    ActionClass.HEAL_WARNING: AutonomyTier.PROPOSE,
}


class SandboxLimits(BaseModel):
    model_config = ConfigDict(extra="ignore")
    cpu_seconds: int = 30
    memory_mb: int = 512
    wall_seconds: int = 60
    max_processes: int = 64


class SandboxConfig(BaseModel):
    model_config = ConfigDict(extra="ignore")
    profile: str = "strict"
    backend_preference: list[str] = Field(
        default_factory=lambda: ["firecracker", "gvisor", "bubblewrap", "nsjail"]
    )
    deny_network: bool = True
    read_only_fs: bool = True
    limits: SandboxLimits = Field(default_factory=SandboxLimits)


class GitConfig(BaseModel):
    model_config = ConfigDict(extra="ignore")
    branch_prefix: str = "skillsmith/"
    open_pr: bool = True
    pr_labels: list[str] = Field(default_factory=lambda: ["skillsmith"])
    commit_trailer: str = "Co-Authored-By: skillsmith <noreply@skillsmith.dev>"


class EvalPolicy(BaseModel):
    model_config = ConfigDict(extra="ignore")
    regression: str = "block-on-regression"
    determinism_runs: int = 8
    max_normalized_variance: float = 0.15
    triggering_runs: int = 5
    train_holdout_split: float = 0.7
    llm_judge_enabled: bool = True
    llm_judge_sole_gate: bool = False


class EffectiveConfig(BaseModel):
    """The merged, clamped configuration the rest of skillsmith consumes."""

    model_config = ConfigDict(extra="ignore", frozen=False)

    autonomy: dict[ActionClass, AutonomyTier]
    require_human: frozenset[ActionClass]
    forbid: frozenset[str]
    allowed_paths: list[str]
    read_only_paths: list[str]
    sandbox: SandboxConfig
    git: GitConfig
    eval: EvalPolicy
    ruleset: str = "default"
    rule_overrides: dict[str, str] = Field(default_factory=dict)
    # Where the local file lives, so remembered choices can be persisted back.
    local_path: Path | None = None

    # --- queries ----------------------------------------------------------- #
    def tier(self, action: ActionClass) -> AutonomyTier:
        return self.autonomy.get(action, AutonomyTier.PROPOSE)

    def path_allowed(self, target: Path) -> bool:
        s = target.as_posix()
        if not any(fnmatch(s, pat) for pat in self.allowed_paths):
            return False
        return not any(fnmatch(s, pat) for pat in self.read_only_paths)

    def is_forbidden(self, capability: str) -> bool:
        return capability in self.forbid

    # --- remembered choices ------------------------------------------------ #
    def remember_choice(self, action: ActionClass, tier: AutonomyTier) -> AutonomyTier:
        """Persist a developer's answer to skillsmith.local.yaml, clamped to ceiling.

        Returns the *effective* (clamped) tier actually stored.
        """

        ceiling = self.autonomy.get(action, AutonomyTier.PROPOSE)
        effective = clamp(tier, ceiling)
        if self.local_path is None:
            return effective
        data: dict[str, Any] = {}
        if self.local_path.exists():
            data = yaml.safe_load(self.local_path.read_text(encoding="utf-8")) or {}
        data.setdefault("version", 1)
        data.setdefault("remembered_choices", {})
        data["remembered_choices"][action.value] = effective.value
        self.local_path.write_text(yaml.safe_dump(data, sort_keys=False), encoding="utf-8")
        self.autonomy[action] = effective
        return effective


def _parse_autonomy(raw: dict[str, Any] | None) -> dict[ActionClass, AutonomyTier]:
    out: dict[ActionClass, AutonomyTier] = {}
    for key, val in (raw or {}).items():
        try:
            out[ActionClass(key)] = AutonomyTier(val)
        except ValueError:
            continue  # unknown keys are ignored (forward-compat with spec evolution)
    return out


def _load_yaml(path: Path | None) -> dict[str, Any]:
    if path is None or not path.exists():
        return {}
    return yaml.safe_load(path.read_text(encoding="utf-8")) or {}


def find_config(start: Path) -> tuple[Path | None, Path | None]:
    """Walk up from ``start`` looking for the committed + local config files."""

    start = start if start.is_dir() else start.parent
    committed: Path | None = None
    local: Path | None = None
    for parent in [start, *start.parents]:
        if committed is None and (parent / COMMITTED_NAME).exists():
            committed = parent / COMMITTED_NAME
        if local is None and (parent / LOCAL_NAME).exists():
            local = parent / LOCAL_NAME
        if committed is not None:
            # Local must live alongside (or above) the committed policy.
            if local is None and (parent / LOCAL_NAME).exists():
                local = parent / LOCAL_NAME
            break
    return committed, local


def load_config(start: Path | str = ".") -> EffectiveConfig:
    """Load + merge + clamp the two layers. Missing files fall back to defaults."""

    start_path = Path(start).resolve()
    committed_path, local_path = find_config(start_path)
    committed = _load_yaml(committed_path)
    local = _load_yaml(local_path)

    # --- autonomy: team ceiling, then clamp local + remembered choices ------ #
    ceiling = {**_DEFAULT_AUTONOMY, **_parse_autonomy(committed.get("autonomy"))}
    effective_autonomy = dict(ceiling)

    local_autonomy = _parse_autonomy(local.get("autonomy"))
    remembered = _parse_autonomy(local.get("remembered_choices"))
    for action, requested in {**local_autonomy, **remembered}.items():
        effective_autonomy[action] = clamp(requested, ceiling.get(action, AutonomyTier.PROPOSE))

    gates = committed.get("approval_gates", {}) or {}
    require_human = frozenset(
        ActionClass(a)
        for a in gates.get("require_human", [])
        if a in ActionClass._value2member_map_
    )
    forbid = frozenset(gates.get("forbid", []))

    targets = committed.get("targets", {}) or {}
    sandbox = _merge_sandbox(committed.get("sandbox"), local.get("sandbox"))
    git = GitConfig(**(committed.get("git", {}) or {}))
    eval_cfg = _parse_eval(committed.get("eval"))
    audit_cfg = committed.get("audit", {}) or {}

    return EffectiveConfig(
        autonomy=effective_autonomy,
        require_human=require_human,
        forbid=forbid,
        allowed_paths=targets.get("allowed_paths", ["**/SKILL.md"]),
        read_only_paths=targets.get("read_only_paths", []),
        sandbox=sandbox,
        git=git,
        eval=eval_cfg,
        ruleset=audit_cfg.get("ruleset", "default"),
        rule_overrides=audit_cfg.get("rule_overrides", {}) or {},
        local_path=local_path or (committed_path.parent / LOCAL_NAME if committed_path else None),
    )


def _merge_sandbox(committed: dict[str, Any] | None, local: dict[str, Any] | None) -> SandboxConfig:
    base = SandboxConfig(**(committed or {}))
    if not local:
        return base
    # Local may only tighten: it can switch to a more restrictive profile or keep
    # deny_network true, but never enable network if the team disabled it.
    merged = base.model_dump()
    if "profile" in local:
        merged["profile"] = local["profile"]
    if local.get("deny_network") is True:
        merged["deny_network"] = True
    return SandboxConfig(**merged)


def _parse_eval(raw: dict[str, Any] | None) -> EvalPolicy:
    raw = raw or {}
    det = raw.get("determinism", {}) or {}
    trig = raw.get("triggering", {}) or {}
    judge = raw.get("llm_judge", {}) or {}
    return EvalPolicy(
        regression=raw.get("regression", "block-on-regression"),
        determinism_runs=det.get("runs", 8),
        max_normalized_variance=det.get("max_normalized_variance", 0.15),
        triggering_runs=trig.get("runs", 5),
        train_holdout_split=trig.get("train_holdout_split", 0.7),
        llm_judge_enabled=judge.get("enabled", True),
        llm_judge_sole_gate=judge.get("sole_gate", False),
    )
