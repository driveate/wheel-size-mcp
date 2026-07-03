"""Unit tests for ws_check_rim_fitment_for_vehicle / ws_check_tire_fitment_for_vehicle.

The search/modifications API endpoints expose no year parameter, so year
filtering happens MCP-side. No API required — api.get is monkeypatched.
"""

import json

import pytest

from ws_mcp.client import api
from ws_mcp.server import mcp


def _row(slug: str, start: int | None, end: int | None) -> dict:
    return {
        "slug": slug,
        "name": f"mod-{slug}",
        "trim": "LE",
        "trim_levels": [],
        "model": {"make": {"slug": "toyota"}, "slug": "camry"},
        "generation": {"slug": "gen1", "name": "V (XV30)"},
        "start_year": start,
        "end_year": end,
        "engine": {"fuel": "Petrol", "capacity": "2.5", "power": {"hp": 203}},
        "regions": ["usdm"],
    }


@pytest.fixture
def fake_api(monkeypatch):
    """Monkeypatch api.get to serve synthetic paginated rows and record calls."""
    state = {"rows": [], "calls": []}

    async def fake_get(path, params=None):
        params = {k: v for k, v in (params or {}).items() if v is not None}
        state["calls"].append({"path": path, "params": params})
        offset, limit = params.get("offset", 0), params.get("limit", 50)
        return {
            "data": state["rows"][offset : offset + limit],
            "meta": {"count": len(state["rows"])},
        }

    monkeypatch.setattr(api, "get", fake_get)
    return state


async def _call(name: str, arguments: dict) -> dict:
    result = await mcp.call_tool(name, arguments)
    return json.loads(result.content[0].text)


RIM_ARGS = {
    "make": "Toyota",
    "model": "Camry",
    "bolt_pattern": "5x114.3",
    "rim_diameter": 17,
    "rim_width": 7.5,
}


async def test_no_year_passes_pagination_to_api(fake_api):
    fake_api["rows"] = [_row(f"m{i}", 2001, 2004) for i in range(30)]
    data = await _call(
        "ws_check_rim_fitment_for_vehicle", {**RIM_ARGS, "limit": 5, "offset": 10}
    )
    assert data["total"] == 30
    assert len(data["results"]) == 5
    call = fake_api["calls"][0]
    assert call["path"] == "/v2/by_rim/search/modifications/"
    assert call["params"]["make"] == "toyota"  # slug-normalized
    assert call["params"]["limit"] == 5
    assert call["params"]["offset"] == 10


async def test_year_filters_by_production_range(fake_api):
    fake_api["rows"] = [
        _row("hit-exact", 2001, 2004),
        _row("miss-before", 1995, 2000),
        _row("miss-after", 2005, 2010),
        _row("hit-open-end", 2001, None),  # still in production
        _row("hit-open-start", None, 2004),  # unknown start — not excluded
        _row("hit-boundary", 2002, 2002),
    ]
    data = await _call("ws_check_rim_fitment_for_vehicle", {**RIM_ARGS, "year": 2002})
    slugs = [i["modification"] for i in data["results"]]
    assert slugs == ["hit-exact", "hit-open-end", "hit-open-start", "hit-boundary"]
    assert data["total"] == 4
    # year must never reach the API — the endpoint has no such parameter
    assert all("year" not in c["params"] for c in fake_api["calls"])


async def test_year_paginates_filtered_list(fake_api):
    fake_api["rows"] = [
        _row(f"hit{i}", 2000, 2010) if i % 2 == 0 else _row(f"miss{i}", 1980, 1985)
        for i in range(40)
    ]
    data = await _call(
        "ws_check_rim_fitment_for_vehicle",
        {**RIM_ARGS, "year": 2005, "limit": 5, "offset": 15},
    )
    assert data["total"] == 20  # 20 hits out of 40
    assert len(data["results"]) == 5
    assert data["results"][0]["modification"] == "hit30"  # 16th hit = row 30


async def test_year_fetch_cap_adds_truncation_note(fake_api):
    fake_api["rows"] = [_row(f"m{i}", 2000, 2010) for i in range(260)]
    data = await _call("ws_check_rim_fitment_for_vehicle", {**RIM_ARGS, "year": 2005})
    assert "note" in data
    # scanned exactly the cap: 4 API pages of 50
    fetch_offsets = [c["params"]["offset"] for c in fake_api["calls"]]
    assert fetch_offsets == [0, 50, 100, 150]
    assert data["total"] == 200


async def test_tire_variant_path_and_params(fake_api):
    fake_api["rows"] = [_row("m1", 2016, 2021)]
    data = await _call(
        "ws_check_tire_fitment_for_vehicle",
        {
            "make": "Honda",
            "model": "Civic",
            "section_width": 215,
            "aspect_ratio": 50,
            "rim_diameter": 17,
            "year": 2020,
        },
    )
    call = fake_api["calls"][0]
    assert call["path"] == "/v2/by_tire/search/modifications/"
    assert call["params"]["section_width"] == 215
    assert data["total"] == 1
    row = data["results"][0]
    assert row["start_year"] == 2016 and row["end_year"] == 2021
    assert row["engine"]["hp"] == 203


async def test_cb_above_120_passes_through(fake_api):
    """API allows cb 52.1-225 mm — values above 120 must not be rejected MCP-side."""
    fake_api["rows"] = [_row("m1", 2001, 2004)]
    data = await _call("ws_check_rim_fitment_for_vehicle", {**RIM_ARGS, "cb": 130})
    assert data["total"] == 1
    assert fake_api["calls"][0]["params"]["cb"] == 130


async def test_empty_result_is_valid_no_fitment_answer(fake_api):
    fake_api["rows"] = []
    data = await _call("ws_check_rim_fitment_for_vehicle", {**RIM_ARGS, "year": 2020})
    assert data["total"] == 0
    assert data["results"] == []
