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
    """Concise mode includes technical, engine, regions, structured wheels."""
    item = {
        "slug": "abc123",
        "name": "2.0i",
        "trim": "Sport",
        "generation": {
            "name": "G20 [2018 .. 2025]", "platform": "G20",
            "start": 2018, "end": 2025,
        },
        "start_year": 2018,
        "end_year": 2025,
        "regions": ["eudm"],
        "engine": {
            "fuel": "Petrol", "capacity": "2.0", "type": "I4",
            "power": {"kW": 135, "PS": 184, "hp": 181}, "code": "B48",
        },
        "tire_type": "Passenger car",
        "technical": {
            "bolt_pattern": "5x112",
            "centre_bore": "66.5",
            "stud_holes": 5,
            "pcd": 112.0,
            "wheel_fasteners": {"type": "Lug bolts", "thread_size": "M14 x 1.25"},
            "wheel_tightening_torque": "120 Nm",
        },
        "wheels": [
            {
                "is_stock": True,
                "front": {
                    "rim": "7.5Jx18 ET25", "tire": "225/45R18",
                    "load_index": 95, "speed_index": "V",
                    "tire_pressure": {"bar": 2.4, "psi": 35, "kPa": 240},
                },
                "rear": {
                    "rim": "8.5Jx18 ET40", "tire": "255/40R18",
                    "load_index": 99, "speed_index": "V",
                    "tire_pressure": {"bar": 2.6, "psi": 38, "kPa": 260},
                },
            },
            {
                "is_stock": False,
                "front": {"rim": "8Jx19 ET30", "tire": "235/35R19"},
                "rear": None,
            },
        ],
    }
    result = filter_vehicle_fitment(item, "concise")
    assert result["technical"]["bolt_pattern"] == "5x112"
    assert result["technical"]["wheel_fasteners"]["type"] == "Lug bolts"
    assert result["technical"]["wheel_fasteners"]["thread_size"] == "M14 x 1.25"
    assert result["technical"]["wheel_tightening_torque"] == "120 Nm"
    assert result["engine"]["fuel"] == "Petrol"
    assert result["regions"] == ["eudm"]
    assert result["tire_type"] == "Passenger car"
    assert result["wheel_count"] == 2
    assert len(result["stock_wheels"]) == 1
    assert result["stock_wheels"][0]["front"]["rim"] == "7.5Jx18 ET25"
    assert result["stock_wheels"][0]["front"]["tire_pressure"] == {
        "bar": 2.4, "psi": 35, "kPa": 240,
    }
    assert result["stock_wheels"][0]["rear"]["rim"] == "8.5Jx18 ET40"


def test_filter_vehicle_fitment_full():
    """Full mode includes all axle fields and wheel flags."""
    item = {
        "slug": "abc123",
        "name": "2.0i",
        "generation": {"name": "G20"},
        "engine": {
            "fuel": "Petrol", "capacity": "2.0", "type": "I4",
            "power": {"kW": 135}, "code": "B48",
        },
        "technical": {
            "bolt_pattern": "5x112",
            "centre_bore": "66.5",
            "wheel_fasteners": {"type": "Lug bolts", "thread_size": "M14 x 1.25"},
        },
        "wheels": [
            {
                "is_stock": True,
                "showing_fp_only": True,
                "is_extra_load_tires": False,
                "is_recommended_for_winter": False,
                "is_runflat_tires": True,
                "is_pressed_steel_rims": False,
                "front": {
                    "rim": "7Jx17", "tire": "225/50R17",
                    "tire_full": "225/50R17 98V",
                    "rim_diameter": 17, "rim_width": 7, "rim_offset": 40,
                    "load_index": 98, "speed_index": "V",
                    "tire_pressure": {"bar": 2.4},
                    "tire_sizing_system": "metric", "tire_construction": "R",
                    "tire_width": 225, "tire_aspect_ratio": 50,
                    "tire_width_mm": 225, "tire_diameter_mm": 668,
                    "tire_weight_kg": 9.5,
                },
                "rear": None,
            }
        ],
    }
    result = filter_vehicle_fitment(item, "full")
    assert len(result["wheels"]) == 1
    w = result["wheels"][0]
    assert w["front"]["tire_full"] == "225/50R17 98V"
    assert w["front"]["rim_diameter"] == 17
    assert w["front"]["load_index"] == 98
    assert w["front"]["tire_pressure"] == {"bar": 2.4}
    assert w["front"]["tire_width_mm"] == 225
    assert w["is_runflat_tires"] is True
    assert w["showing_fp_only"] is True
    assert result["technical"]["wheel_fasteners"]["type"] == "Lug bolts"


def test_filter_vehicle_fitment_concise_no_rear():
    """Concise mode with rear=None should handle gracefully."""
    item = {
        "slug": "xyz",
        "name": "1.6",
        "generation": {"name": "Gen1"},
        "technical": {"bolt_pattern": "4x100"},
        "wheels": [
            {
                "is_stock": True,
                "front": {"rim": "6Jx15", "tire": "195/65R15"},
                "rear": None,
            }
        ],
    }
    result = filter_vehicle_fitment(item, "concise")
    assert result["stock_wheels"][0]["rear"] is None
