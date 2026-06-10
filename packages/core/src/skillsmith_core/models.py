"""Typed contracts shared across every skillsmith subskill.

These Pydantic v2 models are the *portable* boundary of skillsmith: they emit and
consume JSON Schema (see :mod:`skillsmith_core.schema`) so reports can cross process
and language boundaries (CI artifacts, the eval harness, other ecosystems).
"""

from __future__ import annotations

import enum
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from pydantic import BaseModel, ConfigDict, Field


def _utcnow() -> datetime:
    return datetime.now(UTC)


class _Model(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=False, populate_by_name=True)


# --------------------------------------------------------------------------- #
# Enums
# --------------------------------------------------------------------------- #
class Severity(str, enum.Enum):
    """Ordered so comparisons can gate CI (``info`` < ``warning`` < ``error``)."""

    INFO = "info"
    WARNING = "warning"
    ERROR = "error"

    @property
    def rank(self) -> int:
        return {"info": 0, "warning": 1, "error": 2}[self.value]


class FindingCategory(str, enum.Enum):
    METADATA = "metadata"  # name/description requirements
    DESCRIPTION_QUALITY = "description_quality"
    BODY_LENGTH = "body_length"
    PROGRESSIVE_DISCLOSURE = "progressive_disclosure"
    REFERENCE_INTEGRITY = "reference_integrity"  # referenced files exist
    SCRIPT_EXECUTABLE = "script_executable"
    UNJUSTIFIED_IMPERATIVE = "unjustified_imperative"  # all-caps MUST/ALWAYS/NEVER
    PROMPT_ANTIPATTERN = "prompt_antipattern"  # conflicting instructions, etc.
    FORMAT_CONTRACT = "format_contract"  # integration/format mismatch
    DETERMINISM = "determinism"


class BlockClassification(str, enum.Enum):
    """The central judgement of the audit: can this work be made deterministic?"""

    DETERMINISTIC_CANDIDATE = "deterministic-candidate"
    JUDGMENT_REQUIRED = "judgment-required"


class SandboxBackend(str, enum.Enum):
    FIRECRACKER = "firecracker"
    GVISOR = "gvisor"
    BUBBLEWRAP = "bubblewrap"
    NSJAIL = "nsjail"
    NONE = "none"  # explicit "no isolation available" — refuse to run untrusted code


# --------------------------------------------------------------------------- #
# Source locations & parsed skill documents
# --------------------------------------------------------------------------- #
class Location(_Model):
    path: Path
    line: int | None = None
    end_line: int | None = None

    def __str__(self) -> str:  # pragma: no cover - cosmetic
        return f"{self.path}:{self.line}" if self.line else str(self.path)


class WorkBlock(_Model):
    """A chunk of instruction in a skill body that performs a unit of work."""

    id: str
    location: Location
    excerpt: str
    classification: BlockClassification
    rationale: str = Field(
        description="Why this block was classified the way it was (human-readable)."
    )
    # Confidence in the classification, 0..1. Augment only acts on high-confidence
    # deterministic-candidates; everything else is surfaced for human review.
    confidence: float = Field(ge=0.0, le=1.0, default=0.5)
    signals: list[str] = Field(
        default_factory=list,
        description="The detected signals that drove the classification.",
    )


class SkillDoc(_Model):
    """A parsed SKILL.md: YAML frontmatter + body + discovered companion files."""

    path: Path
    name: str | None = None
    description: str | None = None
    frontmatter: dict[str, Any] = Field(default_factory=dict)
    body: str = ""
    body_line_count: int = 0
    # Files referenced from the body (reference docs, scripts) with existence noted.
    referenced_paths: list[Path] = Field(default_factory=list)
    script_paths: list[Path] = Field(default_factory=list)
    raw: str = ""


# --------------------------------------------------------------------------- #
# Audit
# --------------------------------------------------------------------------- #
class Finding(_Model):
    rule_id: str
    category: FindingCategory
    severity: Severity
    message: str
    location: Location | None = None
    # A concrete, actionable suggestion (may seed an augment/heal proposal).
    suggestion: str | None = None
    # Free-form evidence (matched text, computed metrics) for the audit trail.
    evidence: dict[str, Any] = Field(default_factory=dict)


class AuditReport(_Model):
    schema_version: int = 1
    skill_path: Path
    skill_name: str | None = None
    generated_at: datetime = Field(default_factory=_utcnow)
    findings: list[Finding] = Field(default_factory=list)
    work_blocks: list[WorkBlock] = Field(default_factory=list)
    # True only if there are no error-severity findings.
    passed: bool = True

    def with_computed_pass(self) -> AuditReport:
        self.passed = not any(f.severity is Severity.ERROR for f in self.findings)
        return self

    @property
    def deterministic_candidates(self) -> list[WorkBlock]:
        return [
            b
            for b in self.work_blocks
            if b.classification is BlockClassification.DETERMINISTIC_CANDIDATE
        ]


# --------------------------------------------------------------------------- #
# Eval
# --------------------------------------------------------------------------- #
class DeterminismReport(_Model):
    """Empirical output-variance over N runs — the heart of 'temp 0 is not enough'."""

    runs: int
    # 0.0 == identical every run; 1.0 == every run distinct.
    normalized_variance: float = Field(ge=0.0, le=1.0)
    distinct_outputs: int
    # Fingerprints (hashes) of each run's normalized output, for the audit trail.
    fingerprints: list[str] = Field(default_factory=list)
    notes: str | None = None


class TriggeringReport(_Model):
    """Should-trigger / should-not-trigger accuracy with a train/held-out split."""

    runs_per_query: int
    split_seed: int
    train_trigger_rate: float = Field(ge=0.0, le=1.0)
    holdout_trigger_rate: float = Field(ge=0.0, le=1.0)
    false_trigger_rate: float = Field(ge=0.0, le=1.0)
    per_query: dict[str, float] = Field(default_factory=dict)


class EvalReport(_Model):
    schema_version: int = 1
    skill_path: Path
    generated_at: datetime = Field(default_factory=_utcnow)
    golden_passed: int = 0
    golden_failed: int = 0
    # Regression vs a recorded baseline (block-on-regression, not absolute threshold).
    regressions: list[str] = Field(default_factory=list)
    determinism: DeterminismReport | None = None
    triggering: TriggeringReport | None = None
    passed: bool = True


# --------------------------------------------------------------------------- #
# Heal — MCP contract snapshot/diff
# --------------------------------------------------------------------------- #
class ToolContract(_Model):
    """A single MCP tool's externally-observable contract."""

    name: str
    description: str = ""
    input_schema: dict[str, Any] = Field(default_factory=dict)


class ContractSnapshot(_Model):
    """Committed *.mcpc.json artifact: the snapshot of a server's tool contracts."""

    schema_version: int = 1
    server_id: str
    captured_at: datetime = Field(default_factory=_utcnow)
    tools: list[ToolContract] = Field(default_factory=list)
    # Fingerprint over canary-query outputs, to catch behavioral (not just schema) drift.
    behavior_fingerprint: str | None = None


class ContractDiff(_Model):
    server_id: str
    severity: Severity
    added_tools: list[str] = Field(default_factory=list)
    removed_tools: list[str] = Field(default_factory=list)
    renamed_params: dict[str, list[str]] = Field(default_factory=dict)
    required_added: dict[str, list[str]] = Field(default_factory=dict)
    type_changed: dict[str, list[str]] = Field(default_factory=dict)
    description_changed: list[str] = Field(default_factory=list)
    behavioral_drift: bool = False
    human_summary: str = ""


# --------------------------------------------------------------------------- #
# Proposals & audit trail (shared by augment + heal)
# --------------------------------------------------------------------------- #
class ProposedChange(_Model):
    """A repair/optimization proposed as a reviewable diff. NEVER auto-committed
    unless the autonomy policy + tests explicitly permit the low-risk tier."""

    action_class: str  # ActionClass value (kept as str to avoid a core import cycle)
    title: str
    rationale: str
    unified_diff: str
    # Files touched, for allowed-path enforcement.
    touched_paths: list[Path] = Field(default_factory=list)
    # True only for additive/non-breaking changes that passed all golden tests.
    low_risk: bool = False
    token_delta: int | None = None  # negative == savings


class AuditTrailEntry(_Model):
    """One append-only record of a decision skillsmith made. Persisted to .skillsmith/."""

    at: datetime = Field(default_factory=_utcnow)
    action_class: str
    target: Path
    decision: str  # e.g. "proposed-pr", "auto-applied", "blocked-by-ceiling"
    autonomy_tier: str
    sandbox_backend: SandboxBackend | None = None
    detail: dict[str, Any] = Field(default_factory=dict)


# --------------------------------------------------------------------------- #
# Aggregation across many skills (parallel runs)
# --------------------------------------------------------------------------- #
class AggregateReport(_Model):
    schema_version: int = 1
    generated_at: datetime = Field(default_factory=_utcnow)
    command: str
    audits: list[AuditReport] = Field(default_factory=list)
    evals: list[EvalReport] = Field(default_factory=list)
    errors: dict[str, str] = Field(default_factory=dict)  # path -> error message

    @property
    def ok(self) -> bool:
        return (
            not self.errors
            and all(a.passed for a in self.audits)
            and all(e.passed for e in self.evals)
        )
