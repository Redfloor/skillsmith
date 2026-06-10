"""MCP contract diff severity classification + adapter snapshot loading."""

from __future__ import annotations

from pathlib import Path

from skillsmith_adapters.mcp import McpAdapter, load_snapshot
from skillsmith_core.models import ContractSnapshot, Severity, ToolContract
from skillsmith_heal import diff_contracts, has_drift


def _snap(tools: list[ToolContract], server="weather", fp=None) -> ContractSnapshot:
    return ContractSnapshot(server_id=server, tools=tools, behavior_fingerprint=fp)


def _forecast(required=("location",), days_type="integer", desc="Forecast.") -> ToolContract:
    return ToolContract(
        name="get_forecast",
        description=desc,
        input_schema={
            "type": "object",
            "properties": {"location": {"type": "string"}, "days": {"type": days_type}},
            "required": list(required),
        },
    )


def test_added_tool_is_info() -> None:
    old = _snap([_forecast()])
    new = _snap([_forecast(), ToolContract(name="list_stations")])
    d = diff_contracts(old, new)
    assert d.severity is Severity.INFO
    assert d.added_tools == ["list_stations"]
    assert has_drift(d)


def test_removed_tool_is_breaking() -> None:
    old = _snap([_forecast(), ToolContract(name="list_stations")])
    new = _snap([_forecast()])
    d = diff_contracts(old, new)
    assert d.severity is Severity.ERROR
    assert d.removed_tools == ["list_stations"]


def test_required_added_is_breaking() -> None:
    old = _snap([_forecast(required=("location",))])
    new = _snap([_forecast(required=("location", "days"))])
    d = diff_contracts(old, new)
    assert d.severity is Severity.ERROR
    assert "get_forecast" in d.required_added


def test_type_change_is_breaking() -> None:
    old = _snap([_forecast(days_type="integer")])
    new = _snap([_forecast(days_type="string")])
    d = diff_contracts(old, new)
    assert d.severity is Severity.ERROR
    assert "get_forecast" in d.type_changed


def test_description_change_is_warning() -> None:
    old = _snap([_forecast(desc="Forecast.")])
    new = _snap([_forecast(desc="Forecast, now with humidity.")])
    d = diff_contracts(old, new)
    assert d.severity is Severity.WARNING
    assert "get_forecast" in d.description_changed


def test_no_change_is_info_no_drift() -> None:
    d = diff_contracts(_snap([_forecast()]), _snap([_forecast()]))
    assert d.severity is Severity.INFO
    assert not has_drift(d)


def test_adapter_loads_committed_snapshot(mcp_dir: Path) -> None:
    snap = load_snapshot(mcp_dir / "weather.mcpc.json")
    assert snap.server_id == "weather"
    assert {t.name for t in snap.tools} == {"get_forecast", "list_stations"}
    refs = McpAdapter().discover(mcp_dir)
    assert any(r.identifier == "weather" for r in refs)
