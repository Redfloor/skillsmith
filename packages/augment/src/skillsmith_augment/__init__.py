"""skillsmith augment: deterministic-candidate -> tested script (proposed as a PR)."""

from __future__ import annotations

from skillsmith_augment.engine import (
    AugmentOutcome,
    augment_block,
    select_candidates,
)
from skillsmith_augment.generator import (
    GeneratedScript,
    Generator,
    TemplateGenerator,
)

__all__ = [
    "AugmentOutcome",
    "GeneratedScript",
    "Generator",
    "TemplateGenerator",
    "augment_block",
    "select_candidates",
]
