"""Unit tests for HF (high flotation) tire tools.

No API required — api.get is monkeypatched.
"""

import json

import pytest

from ws_mcp.client import api
from ws_mcp.server import mcp


@pytest.fixture
def captured(monkeypatch):
    state = {"calls": [], "rows": []}

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


def _search_row() -> dict:
    return {
        "make": {"slug": "chevrolet", "name": "Chevrolet"},
        "slug": "blazer",
        "name": "Blazer",
        "year_ranges": ["1997-2005"],
        "regions": ["usdm"],
    }


def _mod_row(start: int, end: int | None) -> dict:
    return {
        "slug": "abc",
        "name": "4.3i",
        "trim": "LS",
        "trim_levels": [],
        "generation": {"slug": "g1", "name": "IV"},
        "start_year": start,
        "end_year": end,
        "engine": {"fuel": "Petrol", "capacity": "4.3", "power": {"hp": 190}},
        "regions": ["usdm"],
    }


HF_SIZE = {"overall_diameter": 31, "section_width": 10.5, "rim_diameter": 15}


async def test_search_by_hf_tire_params_and_projection(captured):
    captured["rows"] = [_search_row()]
    data = await _call("ws_search_by_hf_tire", {**HF_SIZE, "region": ["usdm"]})
    call = captured["calls"][0]
    assert call["path"] == "/v2/by_hf_tire/search/"
    assert call["params"]["overall_diameter"] == 31
    assert call["params"]["section_width"] == 10.5
    assert data["total"] == 1
    row = data["results"][0]
    assert row["make"] == "chevrolet"
    assert row["year_ranges"] == ["1997-2005"]


async def test_search_by_hf_tire_rejects_metric_width():
    """Metric mm widths must not pass — HF section_width is inches (4.5-14)."""
    from pydantic import ValidationError

    with pytest.raises(ValidationError, match="section_width"):
        await mcp.call_tool(
            "ws_search_by_hf_tire",
            {"overall_diameter": 31, "section_width": 225, "rim_diameter": 15},
        )


async def test_check_hf_tire_fitment_year_filter(captured):
    captured["rows"] = [_mod_row(1997, 2005), _mod_row(2006, 2009)]
    data = await _call(
        "ws_check_hf_tire_fitment_for_vehicle",
        {"make": "Chevrolet", "model": "Blazer", **HF_SIZE, "year": 2000},
    )
    call = captured["calls"][0]
    assert call["path"] == "/v2/by_hf_tire/search/modifications/"
    assert call["params"]["make"] == "chevrolet"  # slug-normalized
    assert "year" not in call["params"]  # filtered MCP-side
    assert data["total"] == 1
    assert data["results"][0]["start_year"] == 1997
