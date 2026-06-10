"""Determinism harness + triggering + golden/regression."""

from __future__ import annotations

import itertools

from skillsmith_eval import (
    GoldenCase,
    GoldenSuite,
    detect_regressions,
    measure,
    triggering_evaluate,
)
from skillsmith_eval.golden import GoldenResult
from skillsmith_eval.triggering import keyword_predicate


def test_determinism_distinguishes_low_and_high_variance() -> None:
    # Deterministic skill: identical output every run -> variance 0.
    low = measure(lambda q: "always the same", "x", runs=8)
    assert low.normalized_variance == 0.0
    assert low.distinct_outputs == 1

    # Nondeterministic skill: a different output each run -> variance 1.
    counter = itertools.count()
    high = measure(lambda q: f"run-{next(counter)}", "x", runs=8)
    assert high.normalized_variance == 1.0
    assert high.distinct_outputs == 8

    assert high.normalized_variance > low.normalized_variance


def test_triggering_holdout_and_false_rate() -> None:
    predicate = keyword_predicate(["weather", "forecast"])
    report = triggering_evaluate(
        predicate,
        should_trigger=[
            "what's the weather?",
            "give me a forecast",
            "weather today",
            "forecast please",
        ],
        should_not_trigger=["write me a poem", "book a flight"],
        runs=3,
        train_frac=0.5,
    )
    assert report.holdout_trigger_rate == 1.0
    assert report.false_trigger_rate == 0.0


def test_golden_and_regression() -> None:
    suite = GoldenSuite(cases=[GoldenCase(name="c1", input="hi", contains=["HELLO"])])
    results = suite.run(lambda q: "say HELLO world")
    assert results[0].passed

    # Baseline had c1 passing; now it fails -> a regression is reported.
    now_failing = suite.run(lambda q: "no greeting here")
    baseline = [GoldenResult("c1", True, "ok", results[0].fingerprint)]
    regressions = detect_regressions(now_failing, baseline)
    assert regressions and "c1" in regressions[0]
