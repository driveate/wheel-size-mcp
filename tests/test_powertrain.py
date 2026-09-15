"""Integration tests for the powertrain block and fuel codes (API release 2026-09-15, WHEEL-7496).

Requires the local API at http://api.ws.local (see conftest.py).
"""

import pytest
from fastmcp.exceptions import ToolError

from ws_mcp.server import mcp

pytestmark = pytest.mark.integration

POWERTRAIN_SUMMARY_KEYS = {
    "combustion_engine", "electrification_level", "primary_fuel", "secondary_fuel",
    "engine_power_hp", "system_power_hp", "engine_power_secondary_hp", "motors",
}
POWERTRAIN_FULL_KEYS = [
    "combustion_engine", "electrification_level", "primary_fuel", "secondary_fuel",
    "engine_power", "system_power", "engine_power_secondary", "motors",
]
FUEL_CODES = [
    "biodiesel_blend", "cng", "diesel", "e100", "electric", "ethanol_blend", "flex_fuel",
    "h2", "hybrid", "lpg", "petrol", "petrol_cng", "petrol_lpg",
]


async def test_list_modifications_powertrain_summary_phev(call_tool):
    """BMW M5 2024 PHEV: headline power = system power != engine power; one front motor."""
    data = await call_tool("ws_list_modifications", {"make": "bmw", "model": "m5", "year": 2024})
    rows = {m["slug"]: m for m in data["modifications"]}
    m = rows["ecda908aa6"]
    assert set(m["engine"]) == {"fuel", "capacity", "type", "power", "code"}, "engine block must stay frozen"
    pt = m["powertrain"]
    assert set(pt) == POWERTRAIN_SUMMARY_KEYS
    assert pt["combustion_engine"] == "present"
    assert pt["electrification_level"] == "phev"
    assert pt["primary_fuel"] == "petrol"
    assert pt["secondary_fuel"] == "not_applicable"
    assert pt["system_power_hp"] == m["engine"]["power"]["hp"]
    assert pt["engine_power_hp"] < pt["system_power_hp"]
    assert pt["motors"] == [{"axle": "front", "hp": 194, "code": "GC1P28M0"}]


async def test_list_modifications_powertrain_bev_absence_vocabulary(call_tool):
    """Nissan Leaf: engine_power null is final (no ICE); motors [] means not entered yet."""
    data = await call_tool("ws_list_modifications", {"make": "nissan", "model": "leaf", "year": 2023})
    pt = next(m["powertrain"] for m in data["modifications"] if m["slug"] == "ce42361c10")
    assert pt["combustion_engine"] == "not_applicable"
    assert pt["electrification_level"] == "bev"
    assert pt["primary_fuel"] == "electric"
    assert pt["engine_power_hp"] is None
    assert pt["motors"] == []


async def test_search_by_vehicle_passes_full_powertrain_block(call_tool):
    data = await call_tool(
        "ws_search_by_vehicle",
        {"make": "bmw", "model": "m5", "year": 2024, "region": "eudm", "limit": 5},
    )
    row = next(r for r in data["results"] if r["slug"] == "ecda908aa6")
    pt = row["powertrain"]
    assert list(pt) == POWERTRAIN_FULL_KEYS, "full block, API key order"
    assert pt["primary_fuel"] == {"code": "petrol", "title": "Petrol"}
    assert set(pt["system_power"]) == {"kW", "PS", "hp"}
    assert pt["motors"][0]["power"]["kW"] == 145.0


async def test_fitment_check_rows_carry_powertrain_summary(call_tool):
    data = await call_tool(
        "ws_check_rim_fitment_for_vehicle",
        {"make": "honda", "model": "civic", "bolt_pattern": "5x114.3", "rim_diameter": 17, "rim_width": 7, "limit": 3},
    )
    assert data["results"], "expected at least one documented fitment"
    for row in data["results"]:
        assert set(row["powertrain"]) == POWERTRAIN_SUMMARY_KEYS
        assert row["powertrain"]["combustion_engine"] in ("present", "not_applicable", "unknown")


@pytest.mark.parametrize("fuel", ["cng", "petrol_cng", "natural-gas", "petrol-natural-gas"])
async def test_fuel_filter_accepts_codes_and_legacy_aliases(call_tool, fuel):
    """Fiat Panda 0.9 TwinAir bi-fuel: the four spellings all reach the same row (was dead before)."""
    data = await call_tool("ws_list_modifications", {"make": "fiat", "model": "panda", "year": 2015, "fuel": fuel})
    slugs = {m["slug"] for m in data["modifications"]}
    assert "e5e702e1b7" in slugs
    pt = next(m["powertrain"] for m in data["modifications"] if m["slug"] == "e5e702e1b7")
    assert (pt["primary_fuel"], pt["secondary_fuel"]) == ("petrol", "cng")


async def test_fuel_filter_round_trips_primary_fuel_code(call_tool):
    """A code read from powertrain.primary_fuel can be pasted back into the fuel filter."""
    data = await call_tool("ws_list_modifications", {"make": "nissan", "model": "leaf", "year": 2023})
    code = data["modifications"][0]["powertrain"]["primary_fuel"]
    assert code in FUEL_CODES
    filtered = await call_tool("ws_list_modifications", {"make": "nissan", "model": "leaf", "year": 2023, "fuel": code})
    assert filtered["total"] == data["total"]


@pytest.mark.parametrize("fuel", ["bogus", "not_applicable", "not_reported", "unknown"])
async def test_fuel_filter_rejects_unknown_values_and_absence_words(fuel):
    """Absence words appear in powertrain fuel fields but are not fuel codes: the filter returns 400."""
    with pytest.raises(ToolError, match="fuel"):
        await mcp.call_tool("ws_list_modifications", {"make": "fiat", "model": "panda", "year": 2015, "fuel": fuel})


async def test_flex_fuel_secondary_rating(call_tool):
    """Chevrolet Blazer 2.4i — the row with engine_power_secondary filled."""
    data = await call_tool("ws_list_modifications", {"make": "chevrolet", "model": "blazer", "year": 2010})
    pt = next(m["powertrain"] for m in data["modifications"] if m["slug"] == "5919cc509b")
    assert pt["secondary_fuel"] == "ethanol_blend"
    assert pt["engine_power_secondary_hp"] == 145
    assert pt["engine_power_hp"] == 139
