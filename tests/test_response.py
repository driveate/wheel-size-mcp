"""Tests for response filtering and pagination."""

from ws_mcp.response import filter_vehicle_fitment, paginated_response


def test_paginated_response_with_more():
    result = paginated_response(["a", "b"], total=10, offset=0, limit=2)
    assert result["total"] == 10
    assert result["has_more"] is True
    assert result["next_offset"] == 2
    assert "hint" in result
    assert result["showing"] == "1-2 of 10"


def test_paginated_response_last_page():
    result = paginated_response(["a"], total=3, offset=2, limit=2)
    assert result["has_more"] is False
    assert "next_offset" not in result
    assert "hint" not in result


def test_filter_vehicle_fitment_concise():
    item = {
        "slug": "abc123",
        "name": "2.0i",
        "trim": "Sport",
        "generation": {"name": "G20 [2018 .. 2025]"},
        "start_year": 2018,
        "end_year": 2025,
        "technical": {"bolt_pattern": "5x112", "centre_bore": "66.5"},
        "wheels": [
            {
                "is_stock": True,
                "front": {"rim": "7.5Jx18 ET25", "tire": "225/45R18"},
                "rear": {"rim": "8.5Jx18 ET40", "tire": "255/40R18"},
            },
            {
                "is_stock": False,
                "front": {"rim": "8Jx19 ET30", "tire": "235/35R19"},
                "rear": None,
            },
        ],
    }
    result = filter_vehicle_fitment(item, "concise")
    assert result["bolt_pattern"] == "5x112"
    assert result["wheel_count"] == 2
    assert len(result["stock_wheels"]) == 1  # only stock
    assert result["stock_wheels"][0]["front_rim"] == "7.5Jx18 ET25"


def test_filter_vehicle_fitment_full():
    item = {
        "slug": "abc123",
        "name": "2.0i",
        "generation": {"name": "G20"},
        "technical": {"bolt_pattern": "5x112", "centre_bore": "66.5"},
        "wheels": [
            {
                "is_stock": True,
                "front": {"rim": "7Jx17", "tire": "225/50R17", "tire_full": "225/50R17 98V", "rim_diameter": 17, "rim_width": 7, "rim_offset": 40, "tire_pressure": {"bar": 2.4}},
                "rear": None,
            }
        ],
    }
    result = filter_vehicle_fitment(item, "full")
    assert len(result["wheels"]) == 1
    assert result["wheels"][0]["front_tire"] == "225/50R17 98V"
    assert result["wheels"][0]["front_rim_diameter"] == 17
