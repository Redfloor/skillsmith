"""Reference integrity resolves against the repo root, and treats bare names softly.

Regression test for the false positives skillsmith produced on real repos whose
SKILL.md points at repo-relative paths (``data/…``, ``docs/…``) or conceptual bare
names (``robots.txt``) rather than files sitting beside the skill.
"""

from __future__ import annotations

from pathlib import Path

from skillsmith_adapters.claude_skill import parse_skill_md
from skillsmith_audit.linters import run_all
from skillsmith_audit.ruleset import load_ruleset
from skillsmith_core.models import Severity


def _refs(skill: Path) -> list:
    findings = run_all(parse_skill_md(skill), load_ruleset())
    return [f for f in findings if f.rule_id == "references.missing_file"]


def _make_repo(tmp: Path, body: str) -> Path:
    (tmp / ".git").mkdir()
    skill_dir = tmp / "skills" / "demo"
    skill_dir.mkdir(parents=True)
    skill = skill_dir / "SKILL.md"
    skill.write_text(f"---\nname: demo\ndescription: x\n---\n{body}\n", encoding="utf-8")
    return skill


def test_repo_root_relative_reference_resolves(tmp_path: Path) -> None:
    (tmp_path / "data").mkdir()
    (tmp_path / "data" / "sources.json").write_text("{}", encoding="utf-8")
    skill = _make_repo(tmp_path, "See [sources](data/sources.json) for the registry.")
    assert _refs(skill) == []  # resolved via repo root, not a missing-file error


def test_slashed_missing_reference_is_error(tmp_path: Path) -> None:
    skill = _make_repo(tmp_path, "See [gone](docs/legal/nope.md).")
    findings = _refs(skill)
    assert findings and findings[0].severity is Severity.ERROR


def test_bare_conceptual_name_is_warning_not_error(tmp_path: Path) -> None:
    # "fetch `robots.txt`" is a concept/remote artifact, not a shipped file.
    skill = _make_repo(tmp_path, "Fetch `robots.txt` and read the site's terms.")
    findings = _refs(skill)
    assert findings and all(f.severity is Severity.WARNING for f in findings)


def test_reference_beside_skill_still_resolves(tmp_path: Path) -> None:
    skill = _make_repo(tmp_path, "See [ref](reference/guide.md).")
    (skill.parent / "reference").mkdir()
    (skill.parent / "reference" / "guide.md").write_text("x", encoding="utf-8")
    assert _refs(skill) == []
