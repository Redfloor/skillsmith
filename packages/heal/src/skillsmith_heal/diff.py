"""Diff two MCP contract snapshots and classify drift severity.

Severity rules (descriptions are model instructions, so wording changes are NOT
cosmetic):
    added tool / added-optional param      -> info
    removed tool / renamed param           -> breaking
    required param added / type changed    -> breaking
    description changed                     -> warning

NOTE (future): SEP-1575 / SEP-1400 propose native MCP capability/contract versioning.
When servers can declare a contract version, skillsmith would compare versions
directly instead of structurally diffing snapshots. Until then, snapshot+diff is the
source of truth.
"""

from __future__ import annotations

from typing import Any

from skillsmith_core.models import ContractDiff, ContractSnapshot, Severity, ToolContract


def _by_name(snapshot: ContractSnapshot) -> dict[str, ToolContract]:
    return {t.name: t for t in snapshot.tools}


def _props(tool: ToolContract) -> dict[str, dict[str, Any]]:
    schema = tool.input_schema or {}
    return schema.get("properties", {}) or {}


def _required(tool: ToolContract) -> set[str]:
    return set((tool.input_schema or {}).get("required", []) or [])


def diff_contracts(old: ContractSnapshot, new: ContractSnapshot) -> ContractDiff:
    old_tools, new_tools = _by_name(old), _by_name(new)

    added_tools = sorted(set(new_tools) - set(old_tools))
    removed_tools = sorted(set(old_tools) - set(new_tools))

    renamed_params: dict[str, list[str]] = {}
    required_added: dict[str, list[str]] = {}
    type_changed: dict[str, list[str]] = {}
    description_changed: list[str] = []

    for name in sorted(set(old_tools) & set(new_tools)):
        o, n = old_tools[name], new_tools[name]
        o_props, n_props = _props(o), _props(n)

        # Removed params surface as "renamed/removed" (breaking either way).
        removed_params = sorted(set(o_props) - set(n_props))
        if removed_params:
            renamed_params[name] = removed_params

        # Newly-required params (either brand-new required, or optional->required).
        new_required = sorted(_required(n) - _required(o))
        if new_required:
            required_added[name] = new_required

        # Type changes on shared params.
        changed_types = sorted(
            p
            for p in (set(o_props) & set(n_props))
            if o_props[p].get("type") != n_props[p].get("type")
        )
        if changed_types:
            type_changed[name] = changed_types

        if (o.description or "") != (n.description or ""):
            description_changed.append(name)

    severity = _classify(
        removed_tools, renamed_params, required_added, type_changed, description_changed
    )
    diff = ContractDiff(
        server_id=new.server_id or old.server_id,
        severity=severity,
        added_tools=added_tools,
        removed_tools=removed_tools,
        renamed_params=renamed_params,
        required_added=required_added,
        type_changed=type_changed,
        description_changed=description_changed,
    )
    diff.human_summary = _summarize(diff)
    return diff


def _classify(
    removed_tools: list[str],
    renamed_params: dict[str, list[str]],
    required_added: dict[str, list[str]],
    type_changed: dict[str, list[str]],
    description_changed: list[str],
) -> Severity:
    if removed_tools or renamed_params or required_added or type_changed:
        return Severity.ERROR  # breaking
    if description_changed:
        return Severity.WARNING  # descriptions are model instructions
    return Severity.INFO


def _summarize(d: ContractDiff) -> str:
    parts: list[str] = []
    if d.added_tools:
        parts.append(f"+{len(d.added_tools)} tool(s) (info)")
    if d.removed_tools:
        parts.append(f"-{len(d.removed_tools)} tool(s) (BREAKING)")
    if d.renamed_params:
        parts.append(
            f"{sum(len(v) for v in d.renamed_params.values())} removed/renamed param(s) (BREAKING)"
        )
    if d.required_added:
        parts.append(
            f"{sum(len(v) for v in d.required_added.values())} newly-required param(s) (BREAKING)"
        )
    if d.type_changed:
        parts.append(f"{sum(len(v) for v in d.type_changed.values())} type change(s) (BREAKING)")
    if d.description_changed:
        parts.append(f"{len(d.description_changed)} description change(s) (warning)")
    if d.behavioral_drift:
        parts.append("behavioral drift detected via canary fingerprints")
    return "; ".join(parts) if parts else "no contract drift"


def has_drift(d: ContractDiff) -> bool:
    return d.severity is not Severity.INFO or bool(d.added_tools) or d.behavioral_drift
