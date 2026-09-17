"""Unit tests for classified drill-down tools (rim and package variants).

Covers the shared row mapper — the API returns 'slug' for the modification
id (the former 'vehicle_id' field is gone). No API required.
"""

import json

import pytest

from ws_mcp.client import api
from ws_mcp.server import mcp


def _row(**overrides) -> dict:
    row = {
        "slug": "057191ccec",
        "trim": "1.5Ti DM",
        "body": None,
        "production_start_year": 2019,
        "production_end_year": 2020,
        "regions": ["chdm"],
        "oem_rim": "7Jx17 ET45",
        "oem_tire": "215/55R17",
        "fs_delta_mm": 0.0,
        "bs_delta_mm": 0.0,
        "cb_diff_mm": None,
        "load_kg": None,
    }
    row.update(overrides)
    return row


@pytest.fixture
def captured(monkeypatch):
    state = {"calls": [], "rows": []}

    async def fake_get(path, params=None):
        params = {k: v for k, v in (params or {}).items() if v is not None}
        state["calls"].append({"path": path, "params": params})
        return {"data": state["rows"], "meta": {"count": len(state["rows"])}}

    monkeypatch.setattr(api, "get", fake_get)
    return state


async def _call(name: str, arguments: dict) -> dict:
    result = await mcp.call_tool(name, arguments)
    return json.loads(result.content[0].text)


PACKAGE_ARGS = {
    "make": "byd", "model": "qin-pro", "generation": "773464bf48",
    "bolt_pattern": "5x114.3", "rim_diameter": 17, "rim_width": 7,
    "rim_offset": 45, "section_width": 215, "aspect_ratio": 55,
}


async def test_package_drilldown_path_and_params(captured):
    captured["rows"] = [_row()]
    data = await _call("ws_find_vehicle_modifications_for_package", PACKAGE_ARGS)
    call = captured["calls"][0]
    assert call["path"] == "/v2/classified/by_package/search/modifications/"
    assert call["params"]["section_width"] == 215
    assert call["params"]["aspect_ratio"] == 55
    row = data["results"][0]
    assert row["modification"] == "057191ccec"
    assert row["years"] == "2019-2020"
    assert row["oem_tire"] == "215/55R17"


async def test_rim_drilldown_maps_slug_not_vehicle_id(captured):
    """The API renamed vehicle_id -> slug; the mapper must use slug."""
    captured["rows"] = [_row()]
    data = await _call("ws_find_vehicle_modifications_for_rim", {
        "make": "byd", "model": "qin-pro", "generation": "773464bf48",
        "bolt_pattern": "5x114.3", "rim_diameter": 17, "rim_width": 7,
        "rim_offset": 45,
    })
    row = data["results"][0]
    assert row["modification"] == "057191ccec"
    assert "vehicle_id" not in row


async def test_drilldown_open_end_year_renders_present(captured):
    captured["rows"] = [_row(production_end_year=None)]
    data = await _call("ws_find_vehicle_modifications_for_package", PACKAGE_ARGS)
    assert data["results"][0]["years"] == "2019-present"


RIM_SEARCH_ARGS = {
    "bolt_pattern": "5x114.3", "rim_diameter": 18, "rim_width": 8, "rim_offset": 35,
}


async def test_classified_sends_sort_not_ordering(captured):
    """The classified sort values (name/fitment/load) belong to the 'sort' param;
    sending them as 'ordering' makes the API reject the request."""
    captured["rows"] = []
    await _call("ws_find_vehicles_for_rim", {**RIM_SEARCH_ARGS, "sort": "fitment"})
    params = captured["calls"][0]["params"]
    assert params["sort"] == "fitment"
    assert "ordering" not in params


async def test_classified_geometry_params_passthrough(captured):
    captured["rows"] = []
    await _call("ws_find_tires_for_rim", {
        **RIM_SEARCH_ARGS,
        "fd": 12, "diameter_range": 1, "fs_poke": 10, "bs_push": 5,
        "od_tolerance": 0.02, "sort": "load",
    })
    params = captured["calls"][0]["params"]
    assert params["fd"] == 12
    assert params["diameter_range"] == 1
    assert params["fs_poke"] == 10
    assert params["bs_push"] == 5
    assert params["od_tolerance"] == 0.02
    assert params["sort"] == "load"


async def test_package_search_accepts_geometry_params(captured):
    captured["rows"] = []
    await _call("ws_find_vehicles_for_package", {
        **RIM_SEARCH_ARGS,
        "section_width": 225, "aspect_ratio": 45,
        "fd": 14, "fs_poke": 20, "diameter_range": 2, "sort": "fitment",
    })
    params = captured["calls"][0]["params"]
    assert params["fd"] == 14
    assert params["fs_poke"] == 20
    assert params["diameter_range"] == 2
    assert params["sort"] == "fitment"


# ---------------------------------------------------------------------------
# Tire drill-down (WHEEL-7605 / API WHEEL-7603): /v2/classified/by_tire/search/modifications/
# ---------------------------------------------------------------------------

TIRE_DRILLDOWN_ARGS = {
    "make": "mitsubishi", "model": "outlander", "generation": "a65f0f2858",
    "section_width": 235, "aspect_ratio": 60, "rim_diameter": 18,
}


def _tire_row(**overrides) -> dict:
    """Live production row, Mitsubishi Outlander 1.5T HEV 2026 (KT WHEEL-7603)."""
    row = {
        "slug": "fcad99f8fe", "trim": "1.5T HEV", "body": None,
        "production_start_year": 2026, "production_end_year": 2026,
        "regions": ["cdm", "usdm"], "oem_rim": "7.5Jx18 ET35", "oem_tire": "235/60R18",
        "oem_rim_diameter": 18, "oem_rim_width": 7.5, "oem_rim_offset": 35,
        "oem_tire_width_mm": 235, "oem_tire_diameter_mm": 739, "oem_tire_aspect_ratio": 60,
        "ow_delta_mm": 0, "od_delta_mm": 0.2, "od_delta_percent": 0.03, "ar_delta": 0,
        "load_kg": 875, "load_index": 103,
    }
    row.update(overrides)
    return row


async def test_tire_drilldown_path_and_params(captured):
    captured["rows"] = [_tire_row()]
    data = await _call("ws_find_vehicle_modifications_for_tire", TIRE_DRILLDOWN_ARGS)
    call = captured["calls"][0]
    assert call["path"] == "/v2/classified/by_tire/search/modifications/"
    assert call["params"] == {
        "make": "mitsubishi", "model": "outlander", "generation": "a65f0f2858",
        "section_width": 235, "aspect_ratio": 60, "rim_diameter": 18,
        "limit": 20, "offset": 0,
    }
    assert data["total"] == 1


async def test_tire_drilldown_row_fields(captured):
    """Full API field set, and none of the rim-geometry fields the endpoint does not compute."""
    captured["rows"] = [_tire_row()]
    data = await _call("ws_find_vehicle_modifications_for_tire", TIRE_DRILLDOWN_ARGS)
    row = data["results"][0]
    assert row == {
        "modification": "fcad99f8fe", "trim": "1.5T HEV", "body": None, "years": "2026-2026",
        "regions": ["cdm", "usdm"], "oem_rim": "7.5Jx18 ET35", "oem_tire": "235/60R18",
        "oem_rim_diameter": 18, "oem_rim_width": 7.5, "oem_rim_offset": 35,
        "oem_tire_width_mm": 235, "oem_tire_diameter_mm": 739, "oem_tire_aspect_ratio": 60,
        "ow_delta_mm": 0, "od_delta_mm": 0.2, "od_delta_percent": 0.03, "ar_delta": 0,
        "load_kg": 875, "load_index": 103,
    }
    for absent in ("cb_diff_mm", "fs_delta_mm", "bs_delta_mm", "oem_frontspace_mm", "oem_backspace_mm"):
        assert absent not in row


async def test_tire_drilldown_null_aspect_ratio_for_flotation_oem_tire(captured):
    captured["rows"] = [_tire_row(oem_tire="37x12.50R17LT", oem_tire_aspect_ratio=None, ar_delta=None,
                                  production_end_year=None)]
    data = await _call("ws_find_vehicle_modifications_for_tire", TIRE_DRILLDOWN_ARGS)
    row = data["results"][0]
    assert row["oem_tire_aspect_ratio"] is None
    assert row["ar_delta"] is None
    assert row["years"] == "2026-present"


async def test_tire_drilldown_rejects_rim_geometry_params(captured):
    """The API has no tolerance/sort params for this endpoint; the tool must not accept them."""
    from fastmcp.exceptions import ValidationError

    with pytest.raises(ValidationError, match="sort"):
        await mcp.call_tool("ws_find_vehicle_modifications_for_tire", {**TIRE_DRILLDOWN_ARGS, "sort": "fitment"})
    assert captured["calls"] == []


@pytest.mark.parametrize("tool,args,parent", [
    ("ws_find_vehicle_modifications_for_tire", TIRE_DRILLDOWN_ARGS, "ws_find_vehicles_for_tire"),
    ("ws_find_vehicle_modifications_for_package", PACKAGE_ARGS, "ws_find_vehicles_for_package"),
    ("ws_find_vehicle_modifications_for_rim", {k: v for k, v in PACKAGE_ARGS.items()
                                               if k not in ("section_width", "aspect_ratio")},
     "ws_find_vehicles_for_rim"),
])
async def test_drilldown_empty_result_carries_hint(captured, tool, args, parent):
    """All three drill-downs answer a wrong slug with an empty 200 — the hint is the only signal."""
    captured["rows"] = []
    data = await _call(tool, args)
    assert data["total"] == 0 and data["results"] == []
    assert "slugs" in data["hint"] and parent in data["hint"]


async def test_drilldown_non_empty_result_has_no_hint(captured):
    captured["rows"] = [_row()]
    data = await _call("ws_find_vehicle_modifications_for_package", PACKAGE_ARGS)
    assert "hint" not in data
