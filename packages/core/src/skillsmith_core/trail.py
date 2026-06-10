"""Append-only audit trail.

Every consequential decision (proposed PR, auto-applied low-risk change, a choice
blocked by the autonomy ceiling) is recorded as a JSON line under ``.skillsmith/``.
This is what makes "no silent commits" auditable after the fact.
"""

from __future__ import annotations

from pathlib import Path

from skillsmith_core.models import AuditTrailEntry

TRAIL_DIR = ".skillsmith"
TRAIL_FILE = "audit-trail.jsonl"


def trail_path(repo_root: Path) -> Path:
    return repo_root / TRAIL_DIR / TRAIL_FILE


def record(repo_root: Path, entry: AuditTrailEntry) -> Path:
    path = trail_path(repo_root)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as fh:
        fh.write(entry.model_dump_json() + "\n")
    return path


def read_all(repo_root: Path) -> list[AuditTrailEntry]:
    path = trail_path(repo_root)
    if not path.exists():
        return []
    out: list[AuditTrailEntry] = []
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if line:
            out.append(AuditTrailEntry.model_validate_json(line))
    return out
