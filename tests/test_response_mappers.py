"""Unit tests for shared response mappers in response.py."""

from ws_mcp.response import (
    map_car_search_row,
    map_classified_generation_row,
    map_drilldown_row,
    map_modification_row,
    map_powertrain_summary,
    map_tire_drilldown_row,
)


def test_map_car_search_row_includes_generations():
    item = {
        "make": {"slug": "chevrolet", "name": "Chevrolet"},
        "slug": "blazer",
        "name": "Blazer",
        "year_ranges": ["1997-2005"],
        "regions": ["usdm"],
        "generations": [
            {"slug": "0b96d81f04", "name": "IV Facelift", "year_ranges": ["1997-2005"], "extra": "dropped"},
        ],
    }
    row = map_car_search_row(item)
    assert row["make"] == "chevrolet"
    assert row["generations"] == [
        {"slug": "0b96d81f04", "name": "IV Facelift", "year_ranges": ["1997-2005"]}
    ]


def test_map_car_search_row_tolerates_missing_generations():
    item = {"make": {"slug": "a", "name": "A"}, "slug": "b", "name": "B"}
    assert map_car_search_row(item)["generations"] == []


def test_map_classified_generation_row_base_fields():
    item = {
        "model": {"make": {"slug": "bmw", "name": "BMW"}, "slug": "x5", "name": "X5"},
        "slug": "gen1",
        "name": "G05",
        "year_ranges": ["2018-2023"],
        "min_fs_delta_mm": 1.5,  # endpoint-specific extras are NOT in the base row
    }
    row = map_classified_generation_row(item)
    assert row["generation"] == "gen1"
    assert "min_fs_delta_mm" not in row


def test_map_drilldown_row_open_end_year():
    item = {"slug": "m1", "production_start_year": 2019, "production_end_year": None}
    assert map_drilldown_row(item)["years"] == "2019-present"


def test_map_modification_row_engine_projection():
    item = {
        "slug": "m1",
        "name": "2.0T",
        "engine": {"fuel": "Petrol", "capacity": "2.0", "power": {"hp": 252, "kW": 185}},
    }
    row = map_modification_row(item)
    assert row["engine"] == {"fuel": "Petrol", "capacity": "2.0", "hp": 252}


# ---------------------------------------------------------------------------
# powertrain block (WHEEL-7496 API release, 2026-09-15) — fixtures are live
# production rows quoted in the KT document.
# ---------------------------------------------------------------------------

PHEV_POWERTRAIN = {  # BMW M5 2024, ecda908aa6
    "combustion_engine": "present",
    "electrification_level": "phev",
    "primary_fuel": {"code": "petrol", "title": "Petrol"},
    "secondary_fuel": {"code": "not_applicable", "title": "Not applicable"},
    "engine_power": {"kW": 430.0, "PS": 585, "hp": 577},
    "system_power": {"kW": 535.0, "PS": 727, "hp": 717},
    "engine_power_secondary": None,
    "motors": [{"axle": "front", "power": {"kW": 145.0, "PS": 197, "hp": 194}, "code": "GC1P28M0"}],
}

BEV_POWERTRAIN = {  # Nissan Leaf 2023, ce42361c10 — final null vs not-yet-entered motors
    "combustion_engine": "not_applicable",
    "electrification_level": "bev",
    "primary_fuel": {"code": "electric", "title": "Electric"},
    "secondary_fuel": {"code": "not_applicable", "title": "Not applicable"},
    "engine_power": None,
    "system_power": None,
    "engine_power_secondary": None,
    "motors": [],
}

FLEX_FUEL_POWERTRAIN = {  # Chevrolet Blazer 2.4i, 5919cc509b — two ratings for one engine
    "combustion_engine": "present",
    "electrification_level": "not_applicable",
    "primary_fuel": {"code": "petrol", "title": "Petrol"},
    "secondary_fuel": {"code": "ethanol_blend", "title": "Ethanol blend"},
    "engine_power": {"kW": 104.0, "PS": 141, "hp": 139},
    "system_power": None,
    "engine_power_secondary": {"kW": 108.0, "PS": 147, "hp": 145},
    "motors": [],
}


def test_map_powertrain_summary_phev_split():
    assert map_powertrain_summary(PHEV_POWERTRAIN) == {
        "combustion_engine": "present",
        "electrification_level": "phev",
        "primary_fuel": "petrol",
        "secondary_fuel": "not_applicable",
        "engine_power_hp": 577,
        "system_power_hp": 717,
        "engine_power_secondary_hp": None,
        "motors": [{"axle": "front", "hp": 194, "code": "GC1P28M0"}],
    }


def test_map_powertrain_summary_bev_keeps_absence_words_and_nulls():
    """null power members and empty motors stay in the summary — the enums give them meaning."""
    row = map_powertrain_summary(BEV_POWERTRAIN)
    assert row["combustion_engine"] == "not_applicable"
    assert row["electrification_level"] == "bev"
    assert row["primary_fuel"] == "electric"
    assert row["engine_power_hp"] is None
    assert row["system_power_hp"] is None
    assert row["motors"] == []
    assert set(row) == {
        "combustion_engine", "electrification_level", "primary_fuel", "secondary_fuel",
        "engine_power_hp", "system_power_hp", "engine_power_secondary_hp", "motors",
    }


def test_map_powertrain_summary_flex_fuel_secondary_rating():
    row = map_powertrain_summary(FLEX_FUEL_POWERTRAIN)
    assert row["secondary_fuel"] == "ethanol_blend"
    assert row["engine_power_hp"] == 139
    assert row["engine_power_secondary_hp"] == 145


def test_map_powertrain_summary_not_reported_row():
    """Editorial-in-progress row: absence words pass through verbatim, never coerced."""
    row = map_powertrain_summary({
        "combustion_engine": "present",
        "electrification_level": "not_reported",
        "primary_fuel": {"code": "not_reported", "title": "Not reported"},
        "secondary_fuel": {"code": "not_reported", "title": "Not reported"},
        "engine_power": None, "system_power": None, "engine_power_secondary": None, "motors": [],
    })
    assert row["electrification_level"] == "not_reported"
    assert row["primary_fuel"] == "not_reported"


def test_map_powertrain_summary_absent_block_is_none():
    """Rows without the block (classified endpoints, pre-release API) map to None, not a crash."""
    assert map_powertrain_summary(None) is None
    assert map_powertrain_summary({}) is None


def test_map_modification_row_includes_powertrain_summary():
    item = {
        "slug": "m1", "name": "M5",
        "engine": {"fuel": "Hybrid", "capacity": "4.4", "power": {"hp": 717, "kW": 535.0}},
        "powertrain": PHEV_POWERTRAIN,
    }
    row = map_modification_row(item)
    assert row["engine"] == {"fuel": "Hybrid", "capacity": "4.4", "hp": 717}
    assert row["powertrain"]["system_power_hp"] == 717
    assert row["powertrain"]["engine_power_hp"] == 577


def test_map_modification_row_without_powertrain():
    row = map_modification_row({"slug": "m1", "name": "x", "engine": {"fuel": "Petrol"}})
    assert row["powertrain"] is None


def test_map_tire_drilldown_row_keeps_full_field_set_and_no_rim_geometry():
    item = {
        "slug": "fcad99f8fe", "trim": "1.5T HEV", "body": None,
        "production_start_year": 2026, "production_end_year": None, "regions": ["cdm", "usdm"],
        "oem_rim": "7.5Jx18 ET35", "oem_tire": "235/60R18", "oem_rim_diameter": 18, "oem_rim_width": 7.5,
        "oem_rim_offset": 35, "oem_tire_width_mm": 235, "oem_tire_diameter_mm": 739, "oem_tire_aspect_ratio": 60,
        "ow_delta_mm": 0, "od_delta_mm": 0.2, "od_delta_percent": 0.03, "ar_delta": 0, "load_kg": 875,
        "load_index": 103,
        "cb_diff_mm": "must not leak",
    }
    row = map_tire_drilldown_row(item)
    assert row["modification"] == "fcad99f8fe"
    assert row["years"] == "2026-present"
    assert row["od_delta_percent"] == 0.03
    assert "cb_diff_mm" not in row
    assert len(row) == 19
