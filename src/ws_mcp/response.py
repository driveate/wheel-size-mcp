"""Response filtering and pagination helpers.

Claude Code warns at 10,000 tokens and caps at 25,000 tokens.
All responses must be filtered to essential fields and paginated.
"""

from __future__ import annotations


def paginated_response(items: list, total: int, offset: int, limit: int) -> dict:
    """Wrap items in a paginated response with navigation hints."""
    has_more = offset + limit < total
    result = {
        "results": items,
        "total": total,
        "showing": f"{offset + 1}-{min(offset + limit, total)} of {total}",
        "has_more": has_more,
    }
    if has_more:
        result["next_offset"] = offset + limit
        result["hint"] = f"Call again with offset={offset + limit} to see more results."
    return result


def _filter_technical(tech: dict) -> dict:
    """Extract all technical fields from API response."""
    return {
        "bolt_pattern": tech.get("bolt_pattern"),
        "centre_bore": tech.get("centre_bore"),
        "stud_holes": tech.get("stud_holes"),
        "pcd": tech.get("pcd"),
        "wheel_fasteners": tech.get("wheel_fasteners"),
        "wheel_tightening_torque": tech.get("wheel_tightening_torque"),
        "rear_axis_bolt_pattern": tech.get("rear_axis_bolt_pattern"),
        "rear_axis_centre_bore": tech.get("rear_axis_centre_bore"),
        "rear_axis_stud_holes": tech.get("rear_axis_stud_holes"),
        "rear_axis_pcd": tech.get("rear_axis_pcd"),
    }


def _filter_axle(axle: dict | None) -> dict | None:
    """Extract all fields from a front/rear axle dict."""
    if not axle:
        return None
    return {
        "rim": axle.get("rim"),
        "rim_diameter": axle.get("rim_diameter"),
        "rim_width": axle.get("rim_width"),
        "rim_offset": axle.get("rim_offset"),
        "tire": axle.get("tire"),
        "tire_full": axle.get("tire_full"),
        "load_index": axle.get("load_index"),
        "speed_index": axle.get("speed_index"),
        "tire_pressure": axle.get("tire_pressure"),
        "tire_sizing_system": axle.get("tire_sizing_system"),
        "tire_construction": axle.get("tire_construction"),
        "tire_width": axle.get("tire_width"),
        "tire_aspect_ratio": axle.get("tire_aspect_ratio"),
        "tire_diameter": axle.get("tire_diameter"),
        "tire_section_width": axle.get("tire_section_width"),
        "tire_is_82series": axle.get("tire_is_82series"),
        "tire_alpha_numeric": axle.get("tire_alpha_numeric"),
        "tire_width_mm": axle.get("tire_width_mm"),
        "tire_diameter_mm": axle.get("tire_diameter_mm"),
        "tire_weight_kg": axle.get("tire_weight_kg"),
    }


def filter_vehicle_fitment(item: dict, detail_level: str = "concise") -> dict:
    """Filter a search_by_model result item to essential fields.

    Args:
        item: Raw API response item from /search/by_model/
        detail_level: 'concise' = key specs, 'full' = all wheel/tire details
    """
    tech = item.get("technical", {})
    gen = item.get("generation", {})

    result = {
        "slug": item.get("slug"),
        "name": item.get("name"),
        "trim": item.get("trim", ""),
        "trim_levels": item.get("trim_levels") or [],
        "generation": {
            "name": gen.get("name", ""),
            "platform": gen.get("platform"),
            "start": gen.get("start"),
            "end": gen.get("end"),
        },
        "start_year": item.get("start_year"),
        "end_year": item.get("end_year"),
        "regions": item.get("regions", []),
        "engine": item.get("engine"),
        "tire_type": item.get("tire_type"),
        "technical": _filter_technical(tech),
        "wheel_count": len(item.get("wheels", [])),
    }

    wheels = item.get("wheels", [])
    if detail_level == "concise":
        stock = [w for w in wheels if w.get("is_stock")]
        result["stock_wheels"] = [
            {
                "front": {
                    "rim": w.get("front", {}).get("rim"),
                    "tire": w.get("front", {}).get("tire"),
                    "tire_pressure": w.get("front", {}).get("tire_pressure"),
                    "load_index": w.get("front", {}).get("load_index"),
                    "speed_index": w.get("front", {}).get("speed_index"),
                },
                "rear": {
                    "rim": w.get("rear", {}).get("rim"),
                    "tire": w.get("rear", {}).get("tire"),
                    "tire_pressure": w.get("rear", {}).get("tire_pressure"),
                    "load_index": w.get("rear", {}).get("load_index"),
                    "speed_index": w.get("rear", {}).get("speed_index"),
                } if w.get("rear") else None,
            }
            for w in stock[:5]
        ]
    elif detail_level == "full":
        result["wheels"] = [
            {
                "is_stock": w.get("is_stock"),
                "showing_fp_only": w.get("showing_fp_only"),
                "is_extra_load_tires": w.get("is_extra_load_tires"),
                "is_recommended_for_winter": w.get("is_recommended_for_winter"),
                "is_runflat_tires": w.get("is_runflat_tires"),
                "is_pressed_steel_rims": w.get("is_pressed_steel_rims"),
                "front": _filter_axle(w.get("front")),
                "rear": _filter_axle(w.get("rear")),
            }
            for w in wheels
        ]

    return result
