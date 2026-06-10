"""Golden/snapshot tests and regression-vs-baseline.

Regression policy is *block-on-regression*: we compare current results to a recorded
baseline and fail only when a case that previously passed now fails (or an output
fingerprint changed). We deliberately do NOT block on an absolute score threshold —
skills legitimately evolve, and absolute gates rot.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass, field
from pathlib import Path

import yaml

from skillsmith_eval.determinism import fingerprint, normalize


@dataclass
class GoldenCase:
    name: str
    input: str
    expected: str | None = None  # exact-ish expected output (normalized compare)
    expected_fingerprint: str | None = None
    contains: list[str] = field(default_factory=list)  # substrings that must appear


@dataclass
class GoldenResult:
    name: str
    passed: bool
    detail: str
    fingerprint: str


@dataclass
class GoldenSuite:
    cases: list[GoldenCase]

    @classmethod
    def from_file(cls, path: Path) -> GoldenSuite:
        data = yaml.safe_load(Path(path).read_text(encoding="utf-8")) or {}
        cases = [
            GoldenCase(
                name=c.get("name", f"case{i}"),
                input=c.get("input", ""),
                expected=c.get("expected"),
                expected_fingerprint=c.get("expected_fingerprint"),
                contains=c.get("contains", []) or [],
            )
            for i, c in enumerate(data.get("cases", []))
        ]
        return cls(cases=cases)

    def run(self, invoke: Callable[[str], str]) -> list[GoldenResult]:
        results: list[GoldenResult] = []
        for case in self.cases:
            out = invoke(case.input)
            fp = fingerprint(out)
            ok, detail = _check(case, out, fp)
            results.append(GoldenResult(case.name, ok, detail, fp))
        return results


def _check(case: GoldenCase, out: str, fp: str) -> tuple[bool, str]:
    if case.expected_fingerprint is not None:
        if fp != case.expected_fingerprint:
            return False, f"fingerprint {fp} != expected {case.expected_fingerprint}"
        return True, "fingerprint match"
    if case.expected is not None:
        if normalize(out) != normalize(case.expected):
            return False, "normalized output != expected"
        return True, "output match"
    missing = [s for s in case.contains if s.lower() not in out.lower()]
    if missing:
        return False, f"missing substrings: {missing}"
    return True, "all `contains` present"


def detect_regressions(
    current: list[GoldenResult],
    baseline: list[GoldenResult],
) -> list[str]:
    """Block-on-regression: a case that passed in baseline but fails now, OR whose
    output fingerprint changed, is a regression. New failures of new cases are not
    counted as regressions (they're reported by the suite itself)."""

    base = {r.name: r for r in baseline}
    regressions: list[str] = []
    for cur in current:
        prev = base.get(cur.name)
        if prev is None:
            continue
        if prev.passed and not cur.passed:
            regressions.append(f"{cur.name}: passed in baseline, now failing ({cur.detail})")
        elif prev.passed and cur.passed and prev.fingerprint != cur.fingerprint:
            regressions.append(
                f"{cur.name}: output changed vs baseline ({prev.fingerprint} -> {cur.fingerprint})"
            )
    return regressions


def load_baseline(path: Path) -> list[GoldenResult]:
    if not Path(path).exists():
        return []
    data = yaml.safe_load(Path(path).read_text(encoding="utf-8")) or {}
    return [
        GoldenResult(r["name"], r["passed"], r.get("detail", ""), r.get("fingerprint", ""))
        for r in data.get("results", [])
    ]


def save_baseline(path: Path, results: list[GoldenResult]) -> None:
    payload = {
        "results": [
            {"name": r.name, "passed": r.passed, "detail": r.detail, "fingerprint": r.fingerprint}
            for r in results
        ]
    }
    Path(path).write_text(yaml.safe_dump(payload, sort_keys=False), encoding="utf-8")
