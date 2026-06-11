"""Response filtering and pagination helpers.

Claude Code warns at 10,000 tokens and caps at 25,000 tokens.
All responses must be filtered to essential fields and paginated.
"""

from __future__ import annotations


def map_car_search_row(item: dict) -> dict:
    """Project a by_rim/by_tire/by_hf_tire search row (model-level) to essential fields.

    Includes generations so the LLM can drill down without a second search.
    """
    return {
        "make": item["make"]["slug"],
        "make_name": item["make"]["name"],
        "model": item["slug"],
        "model_name": item["name"],
        "year_ranges": item.get("year_ranges", []),
        "regions": item.get("regions", []),
        "generations": [
            {"slug": g["slug"], "name": g["name"], "year_ranges": g.get("year_ranges", [])}
            for g in item.get("generations") or []
        ],
    }


def map_modification_row(item: dict) -> dict:
    """Project a search .../modifications/ row (fitment check) to essential fields."""
    gen = item.get("generation") or {}
    engine = item.get("engine") or {}
    return {
        "modification": item["slug"],
        "name": item["name"],
        "trim": item.get("trim"),
        "trim_levels": item.get("trim_levels", []),
        "generation": gen.get("slug"),
        "generation_name": gen.get("name"),
        "start_year": item.get("start_year"),
        "end_year": item.get("end_year"),
        "engine": {
            "fuel": engine.get("fuel"),
            "capacity": engine.get("capacity"),
            "hp": (engine.get("power") or {}).get("hp"),
        },
        "regions": item.get("regions", []),
    }


def map_classified_generation_row(item: dict) -> dict:
    """Project a classified generation-level row to its common base fields.

    Tools merge endpoint-specific extras (fitment deltas, load, regions) on top.
    """
    return {
        "make": item["model"]["make"]["slug"],
        "make_name": item["model"]["make"]["name"],
        "model": item["model"]["slug"],
        "model_name": item["model"]["name"],
        "generation": item["slug"],
        "generation_name": item["name"],
        "year_ranges": item.get("year_ranges", []),
    }


def map_drilldown_row(item: dict) -> dict:
    """Project a classified .../search/modifications/ row to essential fields."""
    end = item.get("production_end_year") or "present"
    return {
        "modification": item["slug"],
        "trim": item.get("trim"),
        "body": item.get("body"),
        "years": f"{item['production_start_year']}-{end}",
        "regions": item.get("regions", []),
        "oem_rim": item.get("oem_rim"),
        "oem_tire": item.get("oem_tire"),
        "fs_delta_mm": item.get("fs_delta_mm"),
        "bs_delta_mm": item.get("bs_delta_mm"),
        "cb_diff_mm": item.get("cb_diff_mm"),
        "load_kg": item.get("load_kg"),
    }


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


def _resolve_rear(w: dict) -> dict | None:
    """Resolve rear axle data, falling back to front when symmetric.

    When the API sets showing_fp_only=true, front and rear specs are identical
    but only front is populated. This copies front data to rear so the LLM
    always sees complete axle data.
    """
    rear = w.get("rear")
    if w.get("showing_fp_only") and not rear:
        return w.get("front")
    return rear


def _wheel_setup(w: dict) -> str:
    """Return 'symmetric' or 'staggered' based on axle configuration."""
    return "symmetric" if w.get("showing_fp_only") else "staggered"


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
        "trim_attributes": item.get("trim_attributes") or [],
        "trim_body_types": item.get("trim_body_types") or [],
        "body": item.get("body"),
        "generation": {
            "slug": gen.get("slug", ""),
            "name": gen.get("name", ""),
            "platform": gen.get("platform"),
            "start": gen.get("start"),
            "end": gen.get("end"),
            "bodies": gen.get("bodies", []),
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
            _concise_wheel(w) for w in stock[:5]
        ]
    elif detail_level == "full":
        result["wheels"] = [
            {
                "is_stock": w.get("is_stock"),
                "setup": _wheel_setup(w),
                "is_extra_load_tires": w.get("is_extra_load_tires"),
                "is_recommended_for_winter": w.get("is_recommended_for_winter"),
                "is_runflat_tires": w.get("is_runflat_tires"),
                "is_pressed_steel_rims": w.get("is_pressed_steel_rims"),
                "front": _filter_axle(w.get("front")),
                "rear": _filter_axle(_resolve_rear(w)),
            }
            for w in wheels
        ]

    return result


def _concise_wheel(w: dict) -> dict:
    """Build a concise wheel entry with resolved rear axle."""
    front = w.get("front", {})
    rear_src = _resolve_rear(w) or {}
    rear_data = {
        "rim": rear_src.get("rim"),
        "tire": rear_src.get("tire"),
        "tire_pressure": rear_src.get("tire_pressure"),
        "load_index": rear_src.get("load_index"),
        "speed_index": rear_src.get("speed_index"),
    } if rear_src else None
    return {
        "setup": _wheel_setup(w),
        "front": {
            "rim": front.get("rim"),
            "tire": front.get("tire"),
            "tire_pressure": front.get("tire_pressure"),
            "load_index": front.get("load_index"),
            "speed_index": front.get("speed_index"),
        },
        "rear": rear_data,
    }
