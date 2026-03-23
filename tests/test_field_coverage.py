"""Parameterized field coverage tests — validates all catalog tools return expected fields.

Requires the local API at http://api.ws.local (see conftest.py).
"""

import pytest

pytestmark = pytest.mark.integration

# Expected fields per catalog tool, keyed by the response list key.
EXPECTED_FIELDS = {
    "list_makes": {
        "key": "makes",
        "args": {},
        "fields": ["slug", "name", "regions"],
    },
    "list_models": {
        "key": "models",
        "args": {"make": "toyota"},
        "fields": ["slug", "name", "year_ranges", "regions"],
    },
    "list_years": {
        "key": "years",
        "args": {"make": "toyota", "model": "camry"},
        "fields": None,  # years is a flat list of ints, not dicts
    },
    "list_generations": {
        "key": "generations",
        "args": {"make": "toyota", "model": "camry"},
        "fields": ["slug", "name", "platform", "start", "end", "year_ranges", "bodies", "regions", "years"],
    },
    "list_modifications": {
        "key": "modifications",
        "args": {"make": "toyota", "model": "camry", "year": 2024},
        "fields": [
            "slug", "name", "trim", "body", "start_year", "end_year",
            "engine", "regions", "trim_levels", "trim_attributes",
            "trim_body_types",
        ],
    },
    "calculate_upsteps": {
        "key": "options",
        "args": {
            "rim_diameter": 17, "rim_width": 7, "rim_offset": 40,
            "section_width": 225, "aspect_ratio": 50,
        },
        "fields": ["tire", "rim", "is_oe", "difference"],
    },
    "search_by_vehicle": {
        "key": "results",
        "args": {"make": "toyota", "model": "camry", "year": 2024, "region": "usdm"},
        "fields": [
            "slug", "name", "trim", "trim_levels",
            "trim_attributes", "trim_body_types", "body",
            "generation", "start_year", "end_year", "regions",
            "engine", "tire_type", "technical", "wheel_count", "stock_wheels",
        ],
    },
}


@pytest.mark.parametrize(
    "tool_name,spec",
    EXPECTED_FIELDS.items(),
    ids=EXPECTED_FIELDS.keys(),
)
async def test_catalog_field_coverage(call_tool, tool_name, spec):
    """Verify every expected field is present in the first item of each catalog tool."""
    data = await call_tool(tool_name, spec["args"])
    assert data["total"] > 0, f"{tool_name} returned no results"

    if spec["fields"] is None:
        # Flat list (e.g. years) — just check it's non-empty
        assert len(data[spec["key"]]) > 0
        return

    item = data[spec["key"]][0]
    missing = [f for f in spec["fields"] if f not in item]
    assert not missing, f"{tool_name} missing fields: {missing}"
