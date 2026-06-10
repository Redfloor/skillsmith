"""Thin wrapper around promptfoo for declarative golden/regression/triggering configs.

promptfoo is CI-native and declarative; we shell out to it (via ``npx promptfoo``)
rather than re-implementing its config surface. This wrapper is optional: if
promptfoo isn't installed, callers fall back to the native harness in this package.

Deterministic scorers remain ground truth; any LLM-as-judge assertions configured in
promptfoo are advisory and never the sole gate (enforced in :func:`run`).
"""

from __future__ import annotations

import json
import shutil
import subprocess
from dataclasses import dataclass
from pathlib import Path
from typing import Any


class PromptfooUnavailable(RuntimeError):
    pass


@dataclass
class PromptfooResult:
    passed: int
    failed: int
    raw: dict[str, Any]


def available() -> bool:
    return shutil.which("promptfoo") is not None or shutil.which("npx") is not None


def _binary() -> list[str]:
    if shutil.which("promptfoo"):
        return ["promptfoo"]
    if shutil.which("npx"):
        return ["npx", "--yes", "promptfoo@latest"]
    raise PromptfooUnavailable("promptfoo not found (install it or use the native harness).")


def run(config_path: Path, *, allow_llm_judge_sole_gate: bool = False) -> PromptfooResult:
    """Run ``promptfoo eval`` for a config and parse its JSON output."""

    if not allow_llm_judge_sole_gate:
        _assert_not_sole_llm_judge(config_path)
    cmd = [*_binary(), "eval", "-c", str(config_path), "--output", "-", "--no-progress-bar"]
    proc = subprocess.run(cmd, capture_output=True, text=True, check=False)
    if proc.returncode not in (0, 100):  # 100 == some assertions failed
        raise PromptfooUnavailable(f"promptfoo failed: {proc.stderr.strip()[:400]}")
    try:
        data = json.loads(proc.stdout or "{}")
    except json.JSONDecodeError:
        data = {}
    results = data.get("results", {})
    stats = results.get("stats", {}) if isinstance(results, dict) else {}
    return PromptfooResult(
        passed=stats.get("successes", 0),
        failed=stats.get("failures", 0),
        raw=data,
    )


def _assert_not_sole_llm_judge(config_path: Path) -> None:
    """Refuse a config whose only assertions are LLM-graded — policy says LLM-as-judge
    is never the sole gate."""

    try:
        import yaml

        cfg = yaml.safe_load(Path(config_path).read_text(encoding="utf-8")) or {}
    except Exception:
        return
    asserts: list[dict[str, Any]] = []
    for test in cfg.get("tests", []) or []:
        asserts.extend(test.get("assert", []) or [])
    if asserts and all(
        str(a.get("type", "")).startswith(("llm-rubric", "model-graded")) for a in asserts
    ):
        raise PromptfooUnavailable(
            "Config relies solely on LLM-as-judge assertions. Add at least one "
            "deterministic assertion (equals/contains/is-json/javascript) — LLM-judge "
            "is never the sole gate."
        )
