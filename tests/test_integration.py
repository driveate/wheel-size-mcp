"""Integration tests — tools against the live local API.

Requires the local API at http://api.ws.local (see conftest.py).
Skip with: pytest -m "not integration"
"""

import pytest
from fastmcp.exceptions import ToolError

pytestmark = pytest.mark.integration

# ---------------------------------------------------------------------------
# Catalog tools
# ---------------------------------------------------------------------------


async def test_list_makes(call_tool):
    data = await call_tool("list_makes")
    assert data["total"] > 200
    make = data["makes"][0]
    assert "slug" in make
    assert "name" in make
    assert "regions" in make


async def test_list_makes_filter_by_year(call_tool):
    data = await call_tool("list_makes", {"year": 2024})
    assert data["total"] > 0
    assert data["total"] < 300  # filtered subset


async def test_list_models(call_tool):
    data = await call_tool("list_models", {"make": "toyota"})
    assert data["total"] > 100
    model = data["models"][0]
    assert "slug" in model
    assert "name" in model
    assert "year_ranges" in model
    assert "regions" in model


async def test_list_years(call_tool):
    data = await call_tool("list_years", {"make": "toyota", "model": "camry"})
    assert data["total"] > 30
    assert all(isinstance(y, int) for y in data["years"])


async def test_list_generations(call_tool):
    data = await call_tool("list_generations", {"make": "toyota", "model": "camry"})
    assert data["total"] > 10
    gen = data["generations"][0]
    assert "slug" in gen
    assert "name" in gen
    assert "start" in gen
    assert "end" in gen
    assert "bodies" in gen
    assert "regions" in gen
    assert "years" in gen


async def test_list_modifications(call_tool):
    data = await call_tool("list_modifications", {"make": "toyota", "model": "camry", "year": 2024})
    assert data["total"] > 0
    mod = data["modifications"][0]
    assert "slug" in mod
    assert "name" in mod
    assert "engine" in mod
    assert "body" in mod
    assert "trim_levels" in mod
    assert "trim_attributes" in mod
    assert "trim_body_types" in mod



async def test_list_regions(call_tool):
    data = await call_tool("list_regions")
    assert data["total"] == 14
    region = data["regions"][0]
    assert "slug" in region
    assert "name" in region
    assert "abbr" in region


# ---------------------------------------------------------------------------
# Navigation flow (end-to-end chain)
# ---------------------------------------------------------------------------


async def test_navigation_flow(call_tool):
    """Full catalog chain: makes → models → years → modifications → search."""
    # Step 1: find toyota
    makes = await call_tool("list_makes")
    toyota = next(m for m in makes["makes"] if m["slug"] == "toyota")
    assert toyota["name"] == "Toyota"

    # Step 2: find camry
    models = await call_tool("list_models", {"make": toyota["slug"]})
    camry = next(m for m in models["models"] if m["slug"] == "camry")

    # Step 3: pick a year
    years = await call_tool("list_years", {"make": "toyota", "model": camry["slug"]})
    year = years["years"][0]  # most recent

    # Step 4: get modifications
    mods = await call_tool("list_modifications", {"make": "toyota", "model": "camry", "year": year})
    assert mods["total"] > 0

    # Step 5: search fitment (needs region)
    result = await call_tool("search_by_vehicle", {
        "make": "toyota",
        "model": "camry",
        "year": year,
        "region": "usdm",
    })
    assert result["total"] > 0
    item = result["results"][0]
    assert "technical" in item
    assert "bolt_pattern" in item["technical"]
    assert "stock_wheels" in item  # concise detail_level default
    assert "trim_attributes" in item
    assert "body" in item
    assert "slug" in item["generation"]
    assert "bodies" in item["generation"]


# ---------------------------------------------------------------------------
# Search tools
# ---------------------------------------------------------------------------


async def test_search_by_vehicle_concise(call_tool):
    data = await call_tool("search_by_vehicle", {
        "make": "toyota", "model": "camry", "year": 2024, "region": "usdm",
    })
    assert data["total"] > 0
    item = data["results"][0]
    assert "stock_wheels" in item
    assert "wheels" not in item  # concise mode excludes full wheels
    assert "trim_attributes" in item
    assert "trim_body_types" in item
    assert "body" in item
    assert "slug" in item["generation"]
    assert "bodies" in item["generation"]


async def test_search_by_vehicle_full(call_tool):
    data = await call_tool("search_by_vehicle", {
        "make": "toyota", "model": "camry", "year": 2024,
        "region": "usdm", "detail_level": "full",
    })
    assert data["total"] > 0
    item = data["results"][0]
    assert "wheels" in item
    assert "stock_wheels" not in item  # full mode uses wheels key


async def test_search_by_rim(call_tool):
    data = await call_tool("search_by_rim", {
        "bolt_pattern": "5x114.3", "rim_diameter": 18, "rim_width": 8,
    })
    assert data["total"] > 0
    item = data["results"][0]
    assert "make" in item
    assert "model" in item
    assert "year_ranges" in item


async def test_search_by_tire(call_tool):
    data = await call_tool("search_by_tire", {
        "section_width": 225, "aspect_ratio": 45, "rim_diameter": 18,
    })
    assert data["total"] > 0
    item = data["results"][0]
    assert "make" in item
    assert "model" in item


async def test_check_rim_fitment_for_vehicle(call_tool):
    """Camry on 5x114.3 17x7.5 — known fitment in the local DB."""
    data = await call_tool("check_rim_fitment_for_vehicle", {
        "make": "toyota", "model": "camry",
        "bolt_pattern": "5x114.3", "rim_diameter": 17, "rim_width": 7.5,
    })
    assert data["total"] > 0
    item = data["results"][0]
    assert "modification" in item
    assert "start_year" in item
    assert "end_year" in item
    assert "generation" in item


async def test_check_rim_fitment_for_vehicle_year_filter(call_tool):
    """Year filter keeps only modifications whose production range covers it."""
    unfiltered = await call_tool("check_rim_fitment_for_vehicle", {
        "make": "toyota", "model": "camry",
        "bolt_pattern": "5x114.3", "rim_diameter": 17, "rim_width": 7.5,
    })
    filtered = await call_tool("check_rim_fitment_for_vehicle", {
        "make": "toyota", "model": "camry",
        "bolt_pattern": "5x114.3", "rim_diameter": 17, "rim_width": 7.5,
        "year": 2002,
    })
    assert 0 < filtered["total"] < unfiltered["total"]
    for item in filtered["results"]:
        assert item["start_year"] is None or item["start_year"] <= 2002
        assert item["end_year"] is None or item["end_year"] >= 2002


async def test_check_tire_fitment_for_vehicle(call_tool):
    """215/50R17 on a Civic — known fitment in the local DB."""
    data = await call_tool("check_tire_fitment_for_vehicle", {
        "make": "honda", "model": "civic",
        "section_width": 215, "aspect_ratio": 50, "rim_diameter": 17,
    })
    assert data["total"] > 0
    item = data["results"][0]
    assert "modification" in item
    assert "engine" in item


async def test_search_by_hf_tire(call_tool):
    """31x10.50R15 — classic offroad size, known data in the local DB."""
    data = await call_tool("search_by_hf_tire", {
        "overall_diameter": 31, "section_width": 10.5, "rim_diameter": 15,
    })
    assert data["total"] > 0
    item = data["results"][0]
    assert "make" in item
    assert "year_ranges" in item


async def test_check_hf_tire_fitment_for_vehicle(call_tool):
    """31x10.50R15 on a Chevrolet Blazer — known fitment in the local DB."""
    data = await call_tool("check_hf_tire_fitment_for_vehicle", {
        "make": "chevrolet", "model": "blazer",
        "overall_diameter": 31, "section_width": 10.5, "rim_diameter": 15,
        "year": 2000,
    })
    assert data["total"] > 0
    item = data["results"][0]
    assert item["start_year"] is None or item["start_year"] <= 2000
    assert item["end_year"] is None or item["end_year"] >= 2000


async def test_calculate_upsteps(call_tool):
    data = await call_tool("calculate_upsteps", {
        "rim_diameter": 17, "rim_width": 7, "rim_offset": 40,
        "section_width": 225, "aspect_ratio": 50,
    })
    assert data["total"] > 0
    assert isinstance(data["options"], list)
    opt = data["options"][0]
    assert "tire" in opt
    assert "designation" in opt["tire"]
    assert "section_width" in opt["tire"]
    assert "aspect_ratio" in opt["tire"]
    assert "rim" in opt
    assert "designation" in opt["rim"]
    assert "diameter" in opt["rim"]
    assert "width" in opt["rim"]
    assert "offset" in opt["rim"]
    assert "backspacing" in opt["rim"]
    assert "is_oe" in opt
    assert "difference" in opt


# ---------------------------------------------------------------------------
# Classified tools
# ---------------------------------------------------------------------------

RIM_SPEC = {
    "bolt_pattern": "5x114.3",
    "rim_diameter": 18,
    "rim_width": 8,
    "rim_offset": 35,
}


async def test_find_tires_for_rim(call_tool):
    data = await call_tool("find_tires_for_rim", RIM_SPEC)
    assert data["total"] > 0
    item = data["results"][0]
    assert "tire" in item
    assert "vehicle_count" in item


async def test_find_vehicles_for_rim(call_tool):
    data = await call_tool("find_vehicles_for_rim", RIM_SPEC)
    assert data["total"] > 0
    item = data["results"][0]
    assert "make" in item
    assert "model" in item
    assert "generation" in item


async def test_find_vehicles_for_tire(call_tool):
    data = await call_tool("find_vehicles_for_tire", {
        "section_width": 225, "aspect_ratio": 45, "rim_diameter": 18,
    })
    assert data["total"] > 0
    item = data["results"][0]
    assert "make" in item
    assert "generation" in item


async def test_find_vehicles_for_package(call_tool):
    data = await call_tool("find_vehicles_for_package", {
        **RIM_SPEC,
        "section_width": 225, "aspect_ratio": 45,
    })
    assert data["total"] > 0
    item = data["results"][0]
    assert "make" in item
    assert "generation" in item


async def test_classified_drill_down_flow(call_tool):
    """Chain: find_vehicles_for_rim → pick first generation → drill into modifications."""
    # Step 1: find vehicles for rim
    vehicles = await call_tool("find_vehicles_for_rim", RIM_SPEC)
    assert vehicles["total"] > 0

    first = vehicles["results"][0]

    # Step 2: drill down into modifications for that generation
    mods = await call_tool("find_vehicle_modifications_for_rim", {
        "make": first["make"],
        "model": first["model"],
        "generation": first["generation"],
        **RIM_SPEC,
    })
    assert mods["total"] > 0
    item = mods["results"][0]
    assert "vehicle_id" in item
    assert "trim" in item
    assert "oem_rim" in item


# ---------------------------------------------------------------------------
# Utility tools
# ---------------------------------------------------------------------------


async def test_get_spec_metadata_rim_mode(call_tool):
    data = await call_tool("get_spec_metadata", {
        "rim_diameter": 18, "rim_width": 8,
    })
    assert data["mode"] == "rim"
    assert "rim" in data
    assert "population" in data
    assert "hints" in data
    assert isinstance(data["hints"], list)
    assert data["population"]["total_wheelpairs"] > 0
    # MCP generates hints — should mention bolt patterns for common size
    assert any("bolt pattern" in h.lower() for h in data["hints"])


async def test_get_spec_metadata_rim_with_offset(call_tool):
    data = await call_tool("get_spec_metadata", {
        "rim_diameter": 18, "rim_width": 8, "rim_offset": 45,
    })
    assert data["mode"] == "rim"
    assert "geometry" in data
    assert "frontspace" in data["geometry"]
    assert "match_estimates" in data["population"]
    # Should have offset percentile hint
    assert any("percentile" in h for h in data["hints"])


async def test_get_spec_metadata_tire_mode(call_tool):
    data = await call_tool("get_spec_metadata", {
        "section_width": 225, "aspect_ratio": 45, "rim_diameter": 18,
    })
    assert data["mode"] == "tire"
    assert "tire_geometry" in data
    assert "tire_population" in data
    assert any("225/45R18" in h for h in data["hints"])


async def test_get_spec_metadata_package_mode(call_tool):
    data = await call_tool("get_spec_metadata", {
        "rim_diameter": 18, "rim_width": 8, "rim_offset": 40,
        "section_width": 245, "aspect_ratio": 45,
    })
    assert data["mode"] == "package"
    assert "geometry" in data
    assert "package" in data
    assert "tire_geometry" in data
    # Should have both rim and tire hints
    assert any("bolt pattern" in h.lower() for h in data["hints"])
    assert any("245/45R18" in h for h in data["hints"])


async def test_get_spec_metadata_validation_error(call_tool):
    """Missing required param combos should raise ToolError."""
    from ws_mcp.server import mcp

    with pytest.raises(ToolError):
        await mcp.call_tool("get_spec_metadata", {"rim_diameter": 18})


# ---------------------------------------------------------------------------
# Edge cases
# ---------------------------------------------------------------------------


async def test_search_by_vehicle_requires_region_or_generation(call_tool):
    """search_by_vehicle must reject calls without region or generation."""
    from ws_mcp.server import mcp

    with pytest.raises(ToolError, match="region.*generation"):
        await mcp.call_tool("search_by_vehicle", {
            "make": "toyota", "model": "camry", "year": 2024,
        })


async def test_validation_error_actionable_message(call_tool):
    """API validation errors should include actionable hints."""
    from ws_mcp.server import mcp

    with pytest.raises(ToolError, match="bolt_pattern") as exc_info:
        await mcp.call_tool("search_by_rim", {
            "bolt_pattern": "invalid", "rim_diameter": 18, "rim_width": 8,
        })
    assert "NxDDD.D" in str(exc_info.value) or "5x114.3" in str(exc_info.value)


async def test_empty_results_invalid_make(call_tool):
    data = await call_tool("list_models", {"make": "nonexistent_brand_xyz"})
    assert data["total"] == 0
    assert data["models"] == []


async def test_pagination(call_tool):
    rim_params = {"bolt_pattern": "5x114.3", "rim_diameter": 18, "rim_width": 8}

    # Fetch with small limit
    page1 = await call_tool("search_by_rim", {**rim_params, "limit": 2, "offset": 0})
    assert page1["has_more"] is True
    assert page1["next_offset"] == 2
    assert "hint" in page1
    assert len(page1["results"]) == 2
    assert page1["showing"] == "1-2 of " + str(page1["total"])

    # Fetch next page
    page2 = await call_tool("search_by_rim", {**rim_params, "limit": 2, "offset": 2})
    assert len(page2["results"]) == 2
    assert page2["showing"].startswith("3-4 of ")
