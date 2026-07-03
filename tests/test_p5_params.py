"""Unit tests for P5 parameter additions across existing tools.

No API required — api.get is monkeypatched.
"""

import json

import pytest
from fastmcp.exceptions import ToolError

from ws_mcp.client import api
from ws_mcp.server import mcp


@pytest.fixture
def captured(monkeypatch):
    state = {"calls": [], "response": {"data": [], "meta": {"count": 0}}}

    async def fake_get(path, params=None):
        params = {k: v for k, v in (params or {}).items() if v is not None}
        state["calls"].append({"path": path, "params": params})
        return state["response"]

    monkeypatch.setattr(api, "get", fake_get)
    return state


async def _call(name: str, arguments: dict) -> dict:
    result = await mcp.call_tool(name, arguments)
    return json.loads(result.content[0].text)


TIRE_ARGS = {"section_width": 225, "aspect_ratio": 45, "rim_diameter": 17}


async def test_search_by_tire_filter_passthrough(captured):
    await _call("ws_search_by_tire", {
        **TIRE_ARGS,
        "speed_symbol": ["V", "W"], "load_index_min": 91, "fitment": "staggered",
    })
    params = captured["calls"][0]["params"]
    assert params["speed_symbol"] == ["V", "W"]
    assert params["load_index_min"] == 91
    assert params["fitment"] == "staggered"


async def test_search_by_tire_returns_summary_and_facets(captured):
    captured["response"] = {
        "data": [],
        "meta": {
            "count": 0,
            "summary": {"features": {"runflat": 8}},
            "facets": {
                "speed_symbol": {"active": ["V"], "options": {"V": 180, "W": 147}},
            },
        },
    }
    data = await _call("ws_search_by_tire", TIRE_ARGS)
    assert data["summary"]["features"]["runflat"] == 8
    assert data["facets"]["speed_symbol"]["options"]["V"] == 180
    assert data["facets"]["speed_symbol"]["active"] == ["V"]


async def test_facets_truncated_at_cap(captured):
    captured["response"] = {
        "data": [],
        "meta": {
            "count": 0,
            "facets": {"load_index": {"active": [], "options": {str(i): 1 for i in range(80)}}},
        },
    }
    data = await _call("ws_search_by_tire", TIRE_ARGS)
    facet = data["facets"]["load_index"]
    assert len(facet["options"]) == 50
    assert facet["truncated"] == "top 50 of 80"


async def test_search_by_rim_range_params(captured):
    await _call("ws_search_by_rim", {
        "bolt_pattern": "5x114.3",
        "rim_diameter_min": 18, "rim_diameter_max": 19,
        "rim_width_min": 8, "rim_width_max": 9,
        "rim_offset_min": 30, "rim_offset_max": 45,
        "cb": 64.1, "fd": 12,
    })
    params = captured["calls"][0]["params"]
    assert params["rim_diameter_min"] == 18
    assert params["rim_offset_max"] == 45
    assert params["cb"] == 64.1
    assert params["fd"] == 12
    assert "rim_diameter" not in params


async def test_search_by_rim_requires_exact_or_range():
    with pytest.raises(ToolError, match="rim_diameter"):
        await mcp.call_tool("ws_search_by_rim", {"bolt_pattern": "5x114.3", "rim_width": 8})
    with pytest.raises(ToolError, match="rim_width"):
        await mcp.call_tool("ws_search_by_rim", {"bolt_pattern": "5x114.3", "rim_diameter": 18})


async def test_search_by_rim_rejects_exact_plus_range():
    with pytest.raises(ToolError, match="not both"):
        await mcp.call_tool("ws_search_by_rim", {
            "bolt_pattern": "5x114.3", "rim_width": 8,
            "rim_diameter": 18, "rim_diameter_min": 18, "rim_diameter_max": 19,
        })


async def test_search_by_rim_rejects_one_sided_range():
    with pytest.raises(ToolError, match="both rim_diameter_min and rim_diameter_max"):
        await mcp.call_tool("ws_search_by_rim", {
            "bolt_pattern": "5x114.3", "rim_width": 8, "rim_diameter_min": 18,
        })


async def test_search_by_rim_rejects_inverted_range():
    with pytest.raises(ToolError, match="must be <="):
        await mcp.call_tool("ws_search_by_rim", {
            "bolt_pattern": "5x114.3", "rim_width": 8,
            "rim_diameter_min": 19, "rim_diameter_max": 18,
        })


async def test_search_by_rim_validates_optional_dimensions():
    """offset/cb are optional, but their ranges must still be paired/exclusive/ordered."""
    base = {"bolt_pattern": "5x114.3", "rim_diameter": 18, "rim_width": 8}
    with pytest.raises(ToolError, match="rim_offset_min and rim_offset_max"):
        await mcp.call_tool("ws_search_by_rim", {**base, "rim_offset_min": 30})
    with pytest.raises(ToolError, match="not both"):
        await mcp.call_tool("ws_search_by_rim", {**base, "cb": 64.1, "cb_min": 60, "cb_max": 70})
    with pytest.raises(ToolError, match="cb_min must be <="):
        await mcp.call_tool("ws_search_by_rim", {**base, "cb_min": 70, "cb_max": 60})


async def test_unfiltered_facet_keeps_empty_active(captured):
    captured["response"] = {
        "data": [],
        "meta": {"count": 0, "facets": {"fitment": {"active": [], "options": {"square": 10}}}},
    }
    data = await _call("ws_search_by_tire", TIRE_ARGS)
    assert data["facets"]["fitment"]["active"] == []


async def test_calculate_upsteps_tolerances(captured):
    captured["response"] = {"data": [], "meta": {"count": 0}}
    await _call("ws_calculate_upsteps", {
        "rim_diameter": 17, "rim_width": 7, "rim_offset": 40,
        "section_width": 225, "aspect_ratio": 50,
        "s_max": 5, "do_max": 2,
    })
    params = captured["calls"][0]["params"]
    assert params["s_max"] == 5
    assert params["do_max"] == 2


async def test_list_modifications_horsepower(captured):
    await _call("ws_list_modifications", {
        "make": "bmw", "model": "x5", "year": 2022, "horsepower_min": 300,
    })
    params = captured["calls"][0]["params"]
    assert params["horsepower_min"] == 300


async def test_list_makes_brands_and_lang(captured):
    captured["response"] = {
        "data": [{"slug": "toyota", "name": "Тойота", "name_en": "Toyota", "regions": []}],
        "meta": {"count": 1},
    }
    data = await _call("ws_list_makes", {"brands": ["Toyota", "nissan"], "lang": "ru"})
    params = captured["calls"][0]["params"]
    assert params["brands"] == "toyota,nissan"  # CSV, slug-normalized
    assert params["lang"] == "ru"
    assert data["makes"][0]["name"] == "Тойота"
    assert data["makes"][0]["name_en"] == "Toyota"


async def test_list_makes_no_lang_omits_name_en(captured):
    captured["response"] = {
        "data": [{"slug": "toyota", "name": "Toyota", "name_en": "Toyota", "regions": []}],
        "meta": {"count": 1},
    }
    data = await _call("ws_list_makes", {})
    assert "name_en" not in data["makes"][0]


async def test_get_spec_metadata_cb_passthrough(captured):
    captured["response"] = {"mode": "rim"}
    await _call("ws_get_spec_metadata", {"rim_diameter": 18, "rim_width": 8, "cb": 71.6})
    assert captured["calls"][0]["params"]["cb"] == 71.6
