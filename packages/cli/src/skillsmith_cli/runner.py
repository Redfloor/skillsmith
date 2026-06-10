"""Bounded-parallel runners with isolated per-skill context.

- CPU-bound static analysis (audit) runs on a ``ProcessPoolExecutor`` (true
  parallelism, and a crash in one skill's analysis can't take down the batch).
- I/O-bound work (eval/heal, which may call models or spawn sandboxes) runs on
  ``asyncio`` with a bounded semaphore.

Worker entrypoints are module-level so they're picklable on Windows ('spawn').
Each worker re-discovers its own adapter + config, so contexts never leak between
skills.
"""

from __future__ import annotations

import asyncio
from concurrent.futures import ProcessPoolExecutor
from pathlib import Path
from typing import Any

from skillsmith_adapters import detect, get
from skillsmith_audit import audit_doc
from skillsmith_core.config import load_config
from skillsmith_core.models import AuditReport, EvalReport
from skillsmith_eval import eval_doc


def expand_targets(target: str, ecosystem: str | None) -> list[tuple[str, str]]:
    """Resolve a file/dir/glob into ``(skill_path, ecosystem)`` work items."""

    base = Path(target)
    roots: list[Path]
    if any(ch in target for ch in "*?[") and not base.exists():
        # Treat as a glob relative to CWD.
        roots = sorted(Path().glob(target))
    else:
        roots = [base]

    items: list[tuple[str, str]] = []
    for root in roots:
        adapter = get(ecosystem) if ecosystem else detect(root)
        if adapter is None:
            continue
        for ref in adapter.discover(root):
            items.append((str(ref.path), adapter.ecosystem))
    return items


# --------------------------------------------------------------------------- #
# Audit — process pool (CPU-bound)
# --------------------------------------------------------------------------- #
def _audit_one(item: tuple[str, str]) -> tuple[str, dict[str, Any] | None, str | None]:
    path_str, ecosystem = item
    try:
        path = Path(path_str)
        cfg = load_config(path)
        adapter = get(ecosystem)
        ref = next((r for r in adapter.discover(path) if r.path == path), None)
        if ref is None:
            return path_str, None, "skill not found during worker discovery"
        report = audit_doc(adapter.parse(ref), adapter=adapter, config=cfg)
        return path_str, report.model_dump(mode="json"), None
    except Exception as exc:
        return path_str, None, f"{type(exc).__name__}: {exc}"


def run_audits(
    items: list[tuple[str, str]], *, max_parallel: int
) -> tuple[list[AuditReport], dict[str, str]]:
    reports: list[AuditReport] = []
    errors: dict[str, str] = {}
    if not items:
        return reports, errors
    workers = max(1, min(max_parallel, len(items)))
    if workers == 1:
        results = [_audit_one(it) for it in items]
    else:
        with ProcessPoolExecutor(max_workers=workers) as pool:
            results = list(pool.map(_audit_one, items))
    for path_str, payload, err in results:
        if err:
            errors[path_str] = err
        elif payload is not None:
            reports.append(AuditReport.model_validate(payload))
    return reports, errors


# --------------------------------------------------------------------------- #
# Eval — asyncio (I/O-bound), bounded by a semaphore
# --------------------------------------------------------------------------- #
def _eval_one(item: tuple[str, str]) -> tuple[str, EvalReport | None, str | None]:
    path_str, ecosystem = item
    try:
        path = Path(path_str)
        cfg = load_config(path)
        adapter = get(ecosystem)
        ref = next((r for r in adapter.discover(path) if r.path == path), None)
        if ref is None:
            return path_str, None, "skill not found during worker discovery"
        return path_str, eval_doc(adapter.parse(ref), adapter=adapter, config=cfg), None
    except Exception as exc:
        return path_str, None, f"{type(exc).__name__}: {exc}"


async def _run_evals_async(
    items: list[tuple[str, str]], max_parallel: int
) -> list[tuple[str, EvalReport | None, str | None]]:
    sem = asyncio.Semaphore(max(1, max_parallel))
    results: list[tuple[str, EvalReport | None, str | None]] = []

    async def worker(it: tuple[str, str]) -> None:
        async with sem:
            results.append(await asyncio.to_thread(_eval_one, it))

    async with asyncio.TaskGroup() as tg:
        for it in items:
            tg.create_task(worker(it))
    return results


def run_evals(
    items: list[tuple[str, str]], *, max_parallel: int
) -> tuple[list[EvalReport], dict[str, str]]:
    reports: list[EvalReport] = []
    errors: dict[str, str] = {}
    if not items:
        return reports, errors
    for path_str, report, err in asyncio.run(_run_evals_async(items, max_parallel)):
        if err:
            errors[path_str] = err
        elif report is not None:
            reports.append(report)
    return reports, errors
