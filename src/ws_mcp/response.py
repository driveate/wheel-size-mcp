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


def filter_vehicle_fitment(item: dict, detail_level: str = "concise") -> dict:
    """Filter a search_by_model result item to essential fields.

    Args:
        item: Raw API response item from /search/by_model/
        detail_level: 'concise' = key specs, 'full' = all wheel/tire details
    """
    result = {
        "slug": item.get("slug"),
        "name": item.get("name"),
        "trim": item.get("trim", ""),
        "generation": item.get("generation", {}).get("name", ""),
        "start_year": item.get("start_year"),
        "end_year": item.get("end_year"),
        "bolt_pattern": item.get("technical", {}).get("bolt_pattern"),
        "centre_bore": item.get("technical", {}).get("centre_bore"),
        "wheel_count": len(item.get("wheels", [])),
    }

    wheels = item.get("wheels", [])
    if detail_level == "concise":
        # Just stock wheel summary
        stock = [w for w in wheels if w.get("is_stock")]
        result["stock_wheels"] = [
            {
                "front_rim": w.get("front", {}).get("rim"),
                "front_tire": w.get("front", {}).get("tire"),
                "rear_rim": w.get("rear", {}).get("rim") if w.get("rear") else None,
                "rear_tire": w.get("rear", {}).get("tire") if w.get("rear") else None,
            }
            for w in stock[:5]
        ]
    elif detail_level == "full":
        result["wheels"] = [
            {
                "is_stock": w.get("is_stock"),
                "front_rim": w.get("front", {}).get("rim"),
                "front_tire": w.get("front", {}).get("tire_full") or w.get("front", {}).get("tire"),
                "front_rim_diameter": w.get("front", {}).get("rim_diameter"),
                "front_rim_width": w.get("front", {}).get("rim_width"),
                "front_rim_offset": w.get("front", {}).get("rim_offset"),
                "front_tire_pressure": w.get("front", {}).get("tire_pressure"),
                "rear_rim": w.get("rear", {}).get("rim") if w.get("rear") else None,
                "rear_tire": (w["rear"].get("tire_full") or w["rear"].get("tire")) if w.get("rear") else None,
            }
            for w in wheels
        ]

    return result
