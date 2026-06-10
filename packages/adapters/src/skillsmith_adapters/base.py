"""The Adapter protocol — skillsmith's extension point for new ecosystems.

An adapter teaches skillsmith how to *discover*, *parse*, *audit*, *eval*, and
*heal* a particular kind of skill/tool. core defines the shared models; an adapter
maps a concrete ecosystem onto them. Audit/eval/heal *engines* live in their own
packages and call adapter-provided hooks — the engines never hard-code an ecosystem.
"""

from __future__ import annotations

from collections.abc import Callable, Iterable, Sequence
from dataclasses import dataclass, field
from pathlib import Path
from typing import Protocol, runtime_checkable

from skillsmith_core.config import EffectiveConfig
from skillsmith_core.models import (
    AuditReport,
    ContractSnapshot,
    Finding,
    SkillDoc,
)


@dataclass(frozen=True)
class SkillRef:
    """A pointer to a discoverable target, before it is parsed."""

    ecosystem: str
    path: Path
    identifier: str  # stable id (usually the skill name or server id)


# An audit hook inspects a parsed SkillDoc and yields findings. Engines run the
# generic, data-driven linters AND every adapter audit hook.
AuditHook = Callable[[SkillDoc, EffectiveConfig], Iterable[Finding]]


@dataclass(frozen=True)
class EvalHook:
    """How to invoke a skill once, for the determinism/golden harness.

    ``invoke`` returns the skill's textual output for a given input. Implementations
    are expected to run inside the sandbox; the eval engine handles N-run variance,
    fingerprinting, and scoring on top.
    """

    name: str
    invoke: Callable[[str], str]
    # Optional queries for triggering-accuracy tests.
    should_trigger: Sequence[str] = field(default_factory=tuple)
    should_not_trigger: Sequence[str] = field(default_factory=tuple)


@dataclass(frozen=True)
class HealHook:
    """Provides the current contract snapshot for drift detection."""

    name: str
    snapshot: Callable[[], ContractSnapshot]
    canary_queries: Sequence[str] = field(default_factory=tuple)


@runtime_checkable
class Adapter(Protocol):
    """Implement this (structurally) to add an ecosystem. Register via the
    ``skillsmith.adapters`` entry-point group or :func:`register`."""

    ecosystem: str

    def discover(self, root: Path) -> list[SkillRef]: ...

    def parse(self, ref: SkillRef) -> SkillDoc: ...

    def audit_hooks(self) -> list[AuditHook]: ...

    def eval_hooks(self, doc: SkillDoc) -> list[EvalHook]: ...

    def heal_hooks(self, doc: SkillDoc) -> list[HealHook]: ...


class BaseAdapter:
    """Convenience base with no-op hooks; concrete adapters override what they need."""

    ecosystem: str = "base"

    def discover(self, root: Path) -> list[SkillRef]:  # pragma: no cover - abstract
        raise NotImplementedError

    def parse(self, ref: SkillRef) -> SkillDoc:  # pragma: no cover - abstract
        raise NotImplementedError

    def audit_hooks(self) -> list[AuditHook]:
        return []

    def eval_hooks(self, doc: SkillDoc) -> list[EvalHook]:
        return []

    def heal_hooks(self, doc: SkillDoc) -> list[HealHook]:
        return []


def empty_audit_report(doc: SkillDoc) -> AuditReport:
    return AuditReport(skill_path=doc.path, skill_name=doc.name)
