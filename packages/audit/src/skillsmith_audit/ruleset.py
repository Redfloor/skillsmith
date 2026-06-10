"""Load + represent the data-driven audit ruleset.

The ruleset is YAML (``rules/default.yaml``) so thresholds and severities track
Anthropic's evolving spec without code changes. ``rule_overrides`` from the team
config can re-grade or disable individual rules.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from importlib import resources
from pathlib import Path
from typing import Any

import yaml

from skillsmith_core.models import Severity


@dataclass(frozen=True)
class Rule:
    id: str
    category: str
    severity: Severity
    message: str
    enabled: bool = True
    params: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class Ruleset:
    version: int
    spec_revision: str
    limits: dict[str, Any]
    rules: dict[str, Rule]
    classifier: dict[str, Any]

    def rule(self, rule_id: str) -> Rule | None:
        return self.rules.get(rule_id)

    def limit(self, key: str, default: Any = None) -> Any:
        return self.limits.get(key, default)


def load_ruleset(
    name: str = "default",
    *,
    overrides: dict[str, str] | None = None,
    path: Path | None = None,
) -> Ruleset:
    """Load a named ruleset (bundled) or an explicit file, applying severity/disable
    overrides from team config."""

    if path is not None:
        raw = yaml.safe_load(Path(path).read_text(encoding="utf-8"))
    else:
        text = (
            resources.files("skillsmith_audit.rules")
            .joinpath(f"{name}.yaml")
            .read_text(encoding="utf-8")
        )
        raw = yaml.safe_load(text)

    overrides = overrides or {}
    rules: dict[str, Rule] = {}
    for rid, spec in (raw.get("rules") or {}).items():
        severity = Severity(spec.get("severity", "warning"))
        enabled = spec.get("enabled", True)
        ov = overrides.get(rid)
        if ov in {"info", "warning", "error"}:
            severity = Severity(ov)
        elif ov in {"off", "disabled", "false"}:
            enabled = False
        params = {
            k: v for k, v in spec.items() if k not in {"category", "severity", "message", "enabled"}
        }
        rules[rid] = Rule(
            id=rid,
            category=spec.get("category", "metadata"),
            severity=severity,
            message=spec.get("message", rid),
            enabled=enabled,
            params=params,
        )

    return Ruleset(
        version=raw.get("version", 1),
        spec_revision=raw.get("spec_revision", "unknown"),
        limits=raw.get("limits", {}) or {},
        rules=rules,
        classifier=raw.get("classifier", {}) or {},
    )
