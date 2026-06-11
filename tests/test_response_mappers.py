"""Unit tests for shared response mappers in response.py."""

from ws_mcp.response import (
    map_car_search_row,
    map_classified_generation_row,
    map_drilldown_row,
    map_modification_row,
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
