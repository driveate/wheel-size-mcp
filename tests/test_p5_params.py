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


# ---------------------------------------------------------------------------
# ws_calculate_upsteps — asymmetric diameter range (WHEEL-7609 / API WHEEL-7604 step A)
# ---------------------------------------------------------------------------

OE_ARGS = {"rim_diameter": 18, "rim_width": 7.5, "rim_offset": 35, "section_width": 235, "aspect_ratio": 60}


def _upsteps_response() -> dict:
    """Shape per spec §3.6: step on every row, by_diameter with an empty diameter."""
    return {
        "data": [
            {"tire": {"designation": "225/75 R 17", "section_width": 225, "aspect_ratio": 75, "weight": 14.91},
             "rim": {"designation": "17 ⨯ 6J", "diameter": 17.0, "width": 6.0, "offset": 29, "backspacing": 118,
                     "weight": 8.03},
             "is_oe": False, "step": -1,
             "difference": {"s_relative": -7.08, "s_absolute": -17.0, "do_relative": 4.19, "do_absolute": 31.0}},
            {"tire": {"designation": "235/60 R 18", "section_width": 235, "aspect_ratio": 60, "weight": 13.2},
             "rim": {"designation": "18 ⨯ 7.5J", "diameter": 18.0, "width": 7.5, "offset": 35, "backspacing": 130,
                     "weight": 9.1},
             "is_oe": True, "step": 0,
             "difference": {"s_relative": 0, "s_absolute": 0, "do_relative": 0, "do_absolute": 0}},
        ],
        "meta": {
            "count": 2,
            "by_rim": {"17 ⨯ 6J": 1, "18 ⨯ 7.5J": 1},
            "by_diameter": {"17": {"step": -1, "count": 1}, "18": {"step": 0, "count": 1},
                            "19": {"step": 1, "count": 0}},
        },
    }


async def test_calculate_upsteps_steps_range_passthrough(captured):
    captured["response"] = _upsteps_response()
    await _call("ws_calculate_upsteps", {**OE_ARGS, "steps_min": -1, "steps_max": 2})
    params = captured["calls"][0]["params"]
    assert params["steps_min"] == -1
    assert params["steps_max"] == 2
    assert "steps" not in params


async def test_calculate_upsteps_deprecated_steps_still_sent(captured):
    captured["response"] = _upsteps_response()
    await _call("ws_calculate_upsteps", {**OE_ARGS, "steps": -1})
    params = captured["calls"][0]["params"]
    assert params["steps"] == -1
    assert "steps_min" not in params and "steps_max" not in params


@pytest.mark.parametrize("extra", [{"steps_min": -1}, {"steps_max": 1}, {"steps_min": -1, "steps_max": 1}])
async def test_calculate_upsteps_rejects_steps_with_range_before_calling_api(captured, extra):
    with pytest.raises(ToolError, match="not both"):
        await mcp.call_tool("ws_calculate_upsteps", {**OE_ARGS, "steps": 1, **extra})
    assert captured["calls"] == []


async def test_calculate_upsteps_exposes_step_and_by_diameter(captured):
    captured["response"] = _upsteps_response()
    data = await _call("ws_calculate_upsteps", OE_ARGS)
    assert data["total"] == 2
    assert data["by_diameter"] == {"17": {"step": -1, "count": 1}, "18": {"step": 0, "count": 1},
                                   "19": {"step": 1, "count": 0}}
    assert data["by_rim"] == {"17 ⨯ 6J": 1, "18 ⨯ 7.5J": 1}
    assert [o["step"] for o in data["results"]] == [-1, 0]
    oe = [o for o in data["results"] if o["is_oe"]]
    assert len(oe) == 1 and oe[0]["step"] == 0
    assert oe[0]["rim"]["designation"] == "18 ⨯ 7.5J"


async def test_calculate_upsteps_accepts_api_ranges(captured):
    """Types/ranges follow the API: float offset from -50, widths to 13 in, catalog diameters up to 30."""
    captured["response"] = _upsteps_response()
    await _call("ws_calculate_upsteps", {
        "rim_diameter": 30, "rim_width": 13, "rim_offset": -49.5, "section_width": 265, "aspect_ratio": 40,
    })
    params = captured["calls"][0]["params"]
    assert params["rim_offset"] == -49.5
    assert params["rim_diameter"] == 30
    assert "limit" not in params and "offset" not in params, "pagination is MCP-side, the API has none"


async def test_calculate_upsteps_paginates_options_mcp_side(captured):
    """Option rows are paged; by_diameter / by_rim / total always describe the whole list."""
    resp = _upsteps_response()
    captured["response"] = resp
    page1 = await _call("ws_calculate_upsteps", {**OE_ARGS, "limit": 1})
    assert page1["total"] == 2 and len(page1["results"]) == 1 and page1["has_more"] is True
    assert page1["next_offset"] == 1
    assert page1["by_diameter"] == resp["meta"]["by_diameter"]
    page2 = await _call("ws_calculate_upsteps", {**OE_ARGS, "limit": 1, "offset": 1})
    assert page2["results"][0]["is_oe"] is True and page2["has_more"] is False
