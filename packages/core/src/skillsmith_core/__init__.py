"""skillsmith core: models, config, autonomy, sandbox, git plumbing.

Nothing here knows about a specific ecosystem (Claude skill, MCP, etc.); adapters
depend on core, never the reverse.
"""

from __future__ import annotations

from skillsmith_core.autonomy import ActionClass, AutonomyDecision, AutonomyTier, decide
from skillsmith_core.config import EffectiveConfig, load_config
from skillsmith_core.models import (
    AggregateReport,
    AuditReport,
    AuditTrailEntry,
    BlockClassification,
    ContractDiff,
    ContractSnapshot,
    DeterminismReport,
    EvalReport,
    Finding,
    FindingCategory,
    Location,
    ProposedChange,
    Severity,
    SkillDoc,
    ToolContract,
    TriggeringReport,
    WorkBlock,
)

__version__ = "0.1.0"

__all__ = [
    "ActionClass",
    "AggregateReport",
    "AuditReport",
    "AuditTrailEntry",
    "AutonomyDecision",
    "AutonomyTier",
    "BlockClassification",
    "ContractDiff",
    "ContractSnapshot",
    "DeterminismReport",
    "EffectiveConfig",
    "EvalReport",
    "Finding",
    "FindingCategory",
    "Location",
    "ProposedChange",
    "Severity",
    "SkillDoc",
    "ToolContract",
    "TriggeringReport",
    "WorkBlock",
    "__version__",
    "decide",
    "load_config",
]
