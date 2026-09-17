"""Integration tests for ws_calculate_upsteps invariants (API WHEEL-7604, spec §3.6).

Requires the local API at http://api.ws.local (see conftest.py) with ws-django-automobile >= 4.22.0.
"""

import pytest

pytestmark = pytest.mark.integration

OE = {"rim_diameter": 18, "rim_width": 7.5, "rim_offset": 35, "section_width": 235, "aspect_ratio": 60}


async def test_upsteps_asymmetric_range_invariants(call_tool):
    data = await call_tool("ws_calculate_upsteps", {**OE, "steps_min": -1, "steps_max": 2})
    by_diameter = data["by_diameter"]
    diameters = [float(d) for d in by_diameter]
    assert diameters == sorted(diameters), "keys ordered by numeric diameter"
    assert {"17", "18", "19", "20"} <= set(by_diameter), "every whole inch of the -1..+2 range is enumerated"
    assert all(17 <= d <= 20 for d in diameters)
    for d, v in by_diameter.items():
        assert v["step"] == int(float(d)) - 18
        assert v["count"] >= 0
    options = data["results"]
    assert data["total"] == len(options), "one page holds the whole default-tolerance list"
    assert data["total"] == sum(v["count"] for v in by_diameter.values())
    assert data["total"] == sum(data["by_rim"].values())
    oe_rows = [o for o in options if o["is_oe"]]
    assert len(oe_rows) == 1 and oe_rows[0]["step"] == 0
    for o in options:
        assert o["step"] == int(o["rim"]["diameter"]) - 18
        assert -1 <= o["step"] <= 2


async def test_upsteps_default_range_is_oe_to_plus_two(call_tool):
    data = await call_tool("ws_calculate_upsteps", OE)
    assert {"18", "19", "20"} <= set(data["by_diameter"])
    assert all(18 <= float(d) <= 20 for d in data["by_diameter"])
    assert min(o["step"] for o in data["results"]) == 0


async def test_upsteps_deprecated_steps_negative_equals_min_range(call_tool):
    old = await call_tool("ws_calculate_upsteps", {**OE, "steps": -1})
    new = await call_tool("ws_calculate_upsteps", {**OE, "steps_min": -1, "steps_max": 0})
    assert old["by_diameter"] == new["by_diameter"]
    assert old["total"] == new["total"]
