"""Determinism / output-variance harness.

Anthropic's API docs state results are not fully deterministic even at
``temperature: 0.0``. So skillsmith *measures* variance empirically: run a skill N
times on the same input, normalize + fingerprint each output, and report how many
distinct outputs resulted. This is the evidence augment uses to claim "equal-or-better
variance", and a signal the audit uses to flag nondeterministic prompt-work.
"""

from __future__ import annotations

import hashlib
import re
from collections.abc import Callable

from skillsmith_core.models import DeterminismReport

_WS_RE = re.compile(r"\s+")


def normalize(text: str) -> str:
    """Canonicalize output so trivial whitespace/case noise isn't counted as variance."""

    return _WS_RE.sub(" ", text.strip()).lower()


def fingerprint(text: str) -> str:
    return hashlib.sha256(normalize(text).encode("utf-8")).hexdigest()[:16]


def measure(
    invoke: Callable[[str], str],
    query: str,
    *,
    runs: int = 8,
) -> DeterminismReport:
    """Run ``invoke(query)`` ``runs`` times and quantify output variance.

    ``normalized_variance`` is ``(distinct - 1) / (runs - 1)``: 0.0 when every run is
    identical, 1.0 when every run differs.
    """

    runs = max(1, runs)
    fingerprints = [fingerprint(invoke(query)) for _ in range(runs)]
    distinct = len(set(fingerprints))
    variance = 0.0 if runs == 1 else (distinct - 1) / (runs - 1)
    return DeterminismReport(
        runs=runs,
        normalized_variance=round(variance, 4),
        distinct_outputs=distinct,
        fingerprints=fingerprints,
        notes=(
            "Identical across all runs — fully reproducible."
            if distinct == 1
            else f"{distinct} distinct outputs across {runs} runs; temperature alone is "
            "insufficient — prefer structured output + a deterministic validator."
        ),
    )
