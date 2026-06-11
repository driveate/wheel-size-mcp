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
    data = await _call("find_vehicle_modifications_for_package", PACKAGE_ARGS)
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
    data = await _call("find_vehicle_modifications_for_rim", {
        "make": "byd", "model": "qin-pro", "generation": "773464bf48",
        "bolt_pattern": "5x114.3", "rim_diameter": 17, "rim_width": 7,
        "rim_offset": 45,
    })
    row = data["results"][0]
    assert row["modification"] == "057191ccec"
    assert "vehicle_id" not in row


async def test_drilldown_open_end_year_renders_present(captured):
    captured["rows"] = [_row(production_end_year=None)]
    data = await _call("find_vehicle_modifications_for_package", PACKAGE_ARGS)
    assert data["results"][0]["years"] == "2019-present"


RIM_SEARCH_ARGS = {
    "bolt_pattern": "5x114.3", "rim_diameter": 18, "rim_width": 8, "rim_offset": 35,
}


async def test_classified_sends_sort_not_ordering(captured):
    """The classified sort values (name/fitment/load) belong to the 'sort' param;
    sending them as 'ordering' makes the API reject the request."""
    captured["rows"] = []
    await _call("find_vehicles_for_rim", {**RIM_SEARCH_ARGS, "sort": "fitment"})
    params = captured["calls"][0]["params"]
    assert params["sort"] == "fitment"
    assert "ordering" not in params


async def test_classified_geometry_params_passthrough(captured):
    captured["rows"] = []
    await _call("find_tires_for_rim", {
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
    await _call("find_vehicles_for_package", {
        **RIM_SEARCH_ARGS,
        "section_width": 225, "aspect_ratio": 45,
        "fd": 14, "fs_poke": 20, "diameter_range": 2, "sort": "fitment",
    })
    params = captured["calls"][0]["params"]
    assert params["fd"] == 14
    assert params["fs_poke"] == 20
    assert params["diameter_range"] == 2
    assert params["sort"] == "fitment"
