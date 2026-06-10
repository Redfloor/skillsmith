"""Triggering-accuracy tester.

Given should-trigger and should-not-trigger query sets, run each query multiple
times against a trigger predicate and report trigger rates. A train/held-out split
prevents overfitting description tweaks: you tune against the train split and report
the held-out numbers as the honest signal.
"""

from __future__ import annotations

import random
from collections.abc import Callable, Sequence

from skillsmith_core.models import TriggeringReport

# A predicate that decides whether a skill would fire for a query. In production this
# wraps a real router/model call; for offline tests a keyword matcher is injected.
TriggerPredicate = Callable[[str], bool]


def _split(items: Sequence[str], frac: float, rng: random.Random) -> tuple[list[str], list[str]]:
    pool = list(items)
    rng.shuffle(pool)
    cut = round(len(pool) * frac)
    return pool[:cut], pool[cut:]


def _rate(
    queries: Sequence[str], predicate: TriggerPredicate, runs: int
) -> tuple[float, dict[str, float]]:
    per_query: dict[str, float] = {}
    if not queries:
        return 0.0, per_query
    for q in queries:
        hits = sum(1 for _ in range(runs) if predicate(q))
        per_query[q] = hits / runs
    return sum(per_query.values()) / len(per_query), per_query


def evaluate(
    predicate: TriggerPredicate,
    *,
    should_trigger: Sequence[str],
    should_not_trigger: Sequence[str],
    runs: int = 5,
    train_frac: float = 0.7,
    seed: int = 1234,
) -> TriggeringReport:
    rng = random.Random(seed)
    train, holdout = _split(should_trigger, train_frac, rng)
    # If the set is tiny, fall back to using all positives for both to avoid empties.
    if not holdout:
        holdout = list(should_trigger)
    if not train:
        train = list(should_trigger)

    train_rate, _ = _rate(train, predicate, runs)
    holdout_rate, per_query = _rate(holdout, predicate, runs)
    false_rate, neg_per = _rate(should_not_trigger, predicate, runs)
    per_query.update({f"[neg] {k}": v for k, v in neg_per.items()})

    return TriggeringReport(
        runs_per_query=runs,
        split_seed=seed,
        train_trigger_rate=round(train_rate, 4),
        holdout_trigger_rate=round(holdout_rate, 4),
        false_trigger_rate=round(false_rate, 4),
        per_query=per_query,
    )


def keyword_predicate(keywords: Sequence[str]) -> TriggerPredicate:
    """A deterministic predicate for offline tests / fixtures."""

    kw = [k.lower() for k in keywords]

    def _pred(query: str) -> bool:
        low = query.lower()
        return any(k in low for k in kw)

    return _pred
