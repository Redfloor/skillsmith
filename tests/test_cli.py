"""CLI integration via Typer's CliRunner (exercises the parallel runner end-to-end)."""

from __future__ import annotations

import json
from pathlib import Path

from typer.testing import CliRunner

from skillsmith_cli.main import app

runner = CliRunner()
SKILLS = Path(__file__).parent / "fixtures" / "skills"


def test_audit_good_skill_exit_zero() -> None:
    result = runner.invoke(app, ["audit", str(SKILLS / "good-csv-cleaner" / "SKILL.md"), "-j", "1"])
    assert result.exit_code == 0, result.output
    assert "PASS" in result.output


def test_audit_missing_metadata_exit_nonzero() -> None:
    result = runner.invoke(app, ["audit", str(SKILLS / "missing-metadata" / "SKILL.md"), "-j", "1"])
    assert result.exit_code == 1
    assert "metadata.name_required" in result.output


def test_audit_json_aggregate() -> None:
    result = runner.invoke(
        app, ["audit", str(SKILLS / "flawed-summarizer" / "SKILL.md"), "--json", "-j", "1"]
    )
    payload = json.loads(result.output)
    assert payload["command"] == "audit"
    assert payload["audits"]
    assert payload["audits"][0]["findings"]


def test_audit_directory_runs_many() -> None:
    # Pass the whole corpus dir; the runner should discover + audit every SKILL.md.
    result = runner.invoke(app, ["audit", str(SKILLS), "--json", "-j", "2"])
    payload = json.loads(result.output)
    assert len(payload["audits"]) >= 3


def test_adapters_lists_active_and_stubs() -> None:
    result = runner.invoke(app, ["adapters"])
    assert result.exit_code == 0
    assert "claude-skill" in result.output
    assert "openai" in result.output  # stub listed
