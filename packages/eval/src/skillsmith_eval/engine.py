"""Eval engine: drive an adapter's eval hooks through golden + determinism + triggering.

Discovers an optional ``eval/`` sidecar next to the skill:
    <skill_dir>/eval/golden.yaml      golden cases
    <skill_dir>/eval/baseline.yaml    recorded baseline (for block-on-regression)
"""

from __future__ import annotations

from pathlib import Path

from skillsmith_adapters import detect, get
from skillsmith_adapters.base import Adapter, EvalHook
from skillsmith_core.config import EffectiveConfig, load_config
from skillsmith_core.models import EvalReport, SkillDoc
from skillsmith_eval.determinism import measure
from skillsmith_eval.golden import (
    GoldenSuite,
    detect_regressions,
    load_baseline,
)
from skillsmith_eval.triggering import evaluate as eval_triggering
from skillsmith_eval.triggering import keyword_predicate


def eval_doc(doc: SkillDoc, *, adapter: Adapter, config: EffectiveConfig) -> EvalReport:
    report = EvalReport(skill_path=doc.path)
    hooks = adapter.eval_hooks(doc)
    if not hooks:
        report.passed = True
        return report
    primary: EvalHook = hooks[0]

    skill_dir = doc.path.parent
    golden_path = skill_dir / "eval" / "golden.yaml"
    baseline_path = skill_dir / "eval" / "baseline.yaml"

    # --- golden + regression ------------------------------------------------ #
    if golden_path.exists():
        suite = GoldenSuite.from_file(golden_path)
        results = suite.run(primary.invoke)
        report.golden_passed = sum(1 for r in results if r.passed)
        report.golden_failed = sum(1 for r in results if not r.passed)
        if config.eval.regression == "block-on-regression":
            report.regressions = detect_regressions(results, load_baseline(baseline_path))

    # --- determinism / variance -------------------------------------------- #
    probe = primary.should_trigger[0] if primary.should_trigger else doc.name or "probe"
    report.determinism = measure(primary.invoke, probe, runs=config.eval.determinism_runs)

    # --- triggering accuracy ------------------------------------------------ #
    if primary.should_trigger or primary.should_not_trigger:
        # Offline predicate: derive keywords from the skill name/description.
        kws = [w for w in (doc.name or "").replace("-", " ").split() if len(w) > 3]
        predicate = keyword_predicate(kws or [doc.name or ""])
        report.triggering = eval_triggering(
            predicate,
            should_trigger=list(primary.should_trigger),
            should_not_trigger=list(primary.should_not_trigger),
            runs=config.eval.triggering_runs,
            train_frac=config.eval.train_holdout_split,
        )

    report.passed = report.golden_failed == 0 and not report.regressions
    return report


def eval_path(
    target: Path | str,
    *,
    config: EffectiveConfig | None = None,
    ecosystem: str | None = None,
) -> list[EvalReport]:
    target = Path(target)
    cfg = config or load_config(target)
    adapter = get(ecosystem) if ecosystem else detect(target)
    if adapter is None:
        raise ValueError(f"No adapter could discover a skill at {target}")
    out: list[EvalReport] = []
    for ref in adapter.discover(target):
        out.append(eval_doc(adapter.parse(ref), adapter=adapter, config=cfg))
    return out
