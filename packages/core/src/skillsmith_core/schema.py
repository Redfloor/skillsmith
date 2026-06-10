"""Emit JSON Schema for the public contracts, for portability across ecosystems.

Other tools (CI gates, dashboards, non-Python adapters) consume these schemas
rather than importing the Pydantic models.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from pydantic import BaseModel

from skillsmith_core.models import (
    AggregateReport,
    AuditReport,
    ContractSnapshot,
    EvalReport,
    ProposedChange,
)

PUBLIC_MODELS: dict[str, type[BaseModel]] = {
    "audit_report": AuditReport,
    "eval_report": EvalReport,
    "aggregate_report": AggregateReport,
    "contract_snapshot": ContractSnapshot,
    "proposed_change": ProposedChange,
}


def export_schemas(out_dir: Path) -> list[Path]:
    """Write one ``<name>.schema.json`` per public model. Returns written paths."""

    out_dir.mkdir(parents=True, exist_ok=True)
    written: list[Path] = []
    for name, model in PUBLIC_MODELS.items():
        schema: dict[str, Any] = model.model_json_schema()
        schema["$id"] = f"https://skillsmith.dev/schemas/{name}.schema.json"
        schema["$schema"] = "https://json-schema.org/draft/2020-12/schema"
        path = out_dir / f"{name}.schema.json"
        path.write_text(json.dumps(schema, indent=2, sort_keys=True), encoding="utf-8")
        written.append(path)
    return written
