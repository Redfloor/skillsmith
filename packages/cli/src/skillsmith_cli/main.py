"""skillsmith CLI (Typer).

skillsmith audit   <glob-or-dir>   parse + lint + classify (parallel)
skillsmith eval    <glob-or-dir>   golden + determinism + triggering (parallel)
skillsmith heal    <glob-or-dir>   snapshot/diff MCP contracts, propose repairs
skillsmith augment <glob-or-dir>   propose deterministic-candidate -> script PRs
skillsmith schema  export          emit JSON Schema for public contracts
skillsmith adapters                list registered ecosystem adapters
"""

from __future__ import annotations

import json
import os
from pathlib import Path

import typer
from rich.console import Console

from skillsmith_cli.runner import expand_targets, run_audits, run_evals
from skillsmith_core.models import AggregateReport, AuditReport, EvalReport

app = typer.Typer(
    name="skillsmith",
    help="Audit, optimize, test, and self-heal agentic skills and prompt-based tools.",
    no_args_is_help=True,
    add_completion=False,
)
schema_app = typer.Typer(help="Emit JSON Schemas for skillsmith's public contracts.")
app.add_typer(schema_app, name="schema")

console = Console()
err_console = Console(stderr=True)

_DEFAULT_PARALLEL = max(2, (os.cpu_count() or 4))


@app.command()
def audit(
    target: str = typer.Argument(..., help="SKILL.md file, directory, or glob."),
    ecosystem: str | None = typer.Option(None, "--ecosystem", "-e", help="Force an adapter."),
    max_parallel: int = typer.Option(_DEFAULT_PARALLEL, "--max-parallel", "-j", min=1),
    as_json: bool = typer.Option(False, "--json", help="Emit the aggregate report as JSON."),
    fail_on: str = typer.Option("error", "--fail-on", help="Exit nonzero at this severity floor."),
) -> None:
    """Audit one or many skills concurrently and aggregate the results."""

    from skillsmith_audit import to_human

    items = expand_targets(target, ecosystem)
    if not items:
        err_console.print(f"[yellow]No skills discovered at[/] {target}")
        raise typer.Exit(code=2)

    reports, errors = run_audits(items, max_parallel=max_parallel)
    agg = AggregateReport(command="audit", audits=reports, errors=errors)

    if as_json:
        console.print_json(agg.model_dump_json())
    else:
        for r in reports:
            # markup=False: report text contains literal [rule_id] brackets, not Rich markup.
            console.print(to_human(r), soft_wrap=True, markup=False)
            console.print()
        _print_errors(errors)
        _print_audit_summary(reports, errors)

    raise typer.Exit(code=0 if _audit_ok(reports, errors, fail_on) else 1)


@app.command("eval")
def eval_cmd(
    target: str = typer.Argument(..., help="Skill file, directory, or glob."),
    ecosystem: str | None = typer.Option(None, "--ecosystem", "-e"),
    max_parallel: int = typer.Option(_DEFAULT_PARALLEL, "--max-parallel", "-j", min=1),
    as_json: bool = typer.Option(False, "--json"),
) -> None:
    """Run golden + determinism/variance + triggering accuracy across skills."""

    items = expand_targets(target, ecosystem)
    if not items:
        err_console.print(f"[yellow]No skills discovered at[/] {target}")
        raise typer.Exit(code=2)

    reports, errors = run_evals(items, max_parallel=max_parallel)
    agg = AggregateReport(command="eval", evals=reports, errors=errors)

    if as_json:
        console.print_json(agg.model_dump_json())
    else:
        for r in reports:
            _print_eval(r)
        _print_errors(errors)

    raise typer.Exit(code=0 if agg.ok else 1)


@app.command()
def heal(
    target: str = typer.Argument(..., help="MCP config / *.mcpc.json / directory / glob."),
    ecosystem: str | None = typer.Option("mcp", "--ecosystem", "-e"),
    update_baseline: bool = typer.Option(False, "--update-baseline", help="Re-record snapshots."),
    as_json: bool = typer.Option(False, "--json"),
) -> None:
    """Snapshot/diff MCP tool contracts and propose repairs (human-in-the-loop)."""

    from skillsmith_heal import heal_path

    outcomes = heal_path(target, ecosystem=ecosystem, update_snapshot=update_baseline)
    if as_json:
        payload = [
            {
                "server": o.server_id,
                "severity": o.diff.severity.value,
                "summary": o.diff.human_summary,
                "decision": o.decision.reason,
                "proposed_pr": bool(o.proposed),
            }
            for o in outcomes
        ]
        console.print_json(json.dumps(payload))
    else:
        if not outcomes:
            console.print("[green]No MCP targets found / no drift.[/]")
        for o in outcomes:
            color = {"info": "green", "warning": "yellow", "error": "red"}[o.diff.severity.value]
            console.print(f"[{color}]*[/] {o.server_id} - {o.diff.human_summary}", soft_wrap=True)
            console.print(f"    decision: {o.decision.reason}", soft_wrap=True)
            if o.proposed:
                console.print(
                    f"    -> proposal ready: {o.proposed.title} "
                    f"({'auto-eligible' if o.decision.may_auto_apply else 'PR for review'})"
                )
    breaking = any(o.diff.severity.value == "error" for o in outcomes)
    raise typer.Exit(code=1 if breaking else 0)


@app.command()
def augment(
    target: str = typer.Argument(..., help="SKILL.md file, directory, or glob."),
    ecosystem: str | None = typer.Option(None, "--ecosystem", "-e"),
    as_json: bool = typer.Option(False, "--json"),
) -> None:
    """Propose converting high-confidence deterministic-candidate blocks to scripts.

    Never auto-commits: prints the proposals that would become PRs."""

    from skillsmith_adapters import detect, get
    from skillsmith_audit import audit_doc
    from skillsmith_augment import augment_block, select_candidates
    from skillsmith_core.config import load_config

    path = Path(target)
    cfg = load_config(path)
    adapter = get(ecosystem) if ecosystem else detect(path)
    if adapter is None:
        err_console.print(f"[yellow]No adapter for[/] {target}")
        raise typer.Exit(code=2)

    proposals = []
    for ref in adapter.discover(path):
        doc = adapter.parse(ref)
        report = audit_doc(doc, adapter=adapter, config=cfg)
        for block in select_candidates(report.work_blocks):
            try:
                outcome = augment_block(doc, block, config=cfg)
            except Exception as exc:
                err_console.print(f"[red]augment skipped[/] {block.id}: {exc}")
                continue
            if outcome.proposed:
                proposals.append(outcome.proposed)
            elif not as_json:
                console.print(f"[dim]· {block.id}: skipped ({outcome.skipped_reason})[/]")

    if as_json:
        console.print_json(json.dumps([p.model_dump(mode="json") for p in proposals]))
    else:
        console.print(f"\n[bold]{len(proposals)} proposal(s) ready for PR[/] (no changes applied):")
        for p in proposals:
            console.print(f"  * {p.title}  (tokens {p.token_delta:+d})", soft_wrap=True)
    raise typer.Exit(code=0)


@schema_app.command("export")
def schema_export(
    out: Path = typer.Option(Path("docs/schemas"), "--out", help="Output directory."),
) -> None:
    """Write JSON Schema for AuditReport / EvalReport / etc."""

    from skillsmith_core.schema import export_schemas

    written = export_schemas(out)
    for p in written:
        console.print(f"[green]wrote[/] {p}")


@app.command()
def adapters() -> None:
    """List registered ecosystem adapters."""

    from skillsmith_adapters import all_adapters
    from skillsmith_adapters.stubs import STUB_ADAPTERS

    stub_names = {a.ecosystem for a in (cls() for cls in STUB_ADAPTERS)}
    for name in sorted(all_adapters()):
        tag = "[dim](stub)[/]" if name in stub_names else "[green](active)[/]"
        console.print(f"  {name} {tag}")
    for cls in STUB_ADAPTERS:
        eco = cls().ecosystem
        console.print(f"  {eco} [dim](stub — see docs/extending.md)[/]")


# --------------------------------------------------------------------------- #
# helpers
# --------------------------------------------------------------------------- #
def _print_errors(errors: dict[str, str]) -> None:
    for path, msg in errors.items():
        err_console.print(f"[red]error[/] {path}: {msg}", soft_wrap=True)


def _print_audit_summary(reports: list[AuditReport], errors: dict[str, str]) -> None:
    passed = sum(1 for r in reports if r.passed)
    cand = sum(len(r.deterministic_candidates) for r in reports)
    console.print(
        f"[bold]summary:[/] {passed}/{len(reports)} skills passed, "
        f"{cand} deterministic-candidate block(s), {len(errors)} error(s)."
    )


def _print_eval(r: EvalReport) -> None:
    status = "[green]PASS[/]" if r.passed else "[red]FAIL[/]"
    console.print(f"{status} {r.skill_path}")
    if r.determinism:
        console.print(
            f"    determinism: variance={r.determinism.normalized_variance} "
            f"({r.determinism.distinct_outputs}/{r.determinism.runs} distinct)"
        )
    if r.triggering:
        console.print(
            f"    triggering: holdout={r.triggering.holdout_trigger_rate} "
            f"false={r.triggering.false_trigger_rate}"
        )
    if r.regressions:
        for reg in r.regressions:
            console.print(f"    [red]regression:[/] {reg}")


def _audit_ok(reports: list[AuditReport], errors: dict[str, str], fail_on: str) -> bool:
    from skillsmith_core.models import Severity

    if errors:
        return False
    floor = Severity(fail_on).rank
    return all(not any(f.severity.rank >= floor for f in r.findings) for r in reports)


if __name__ == "__main__":  # pragma: no cover
    app()
