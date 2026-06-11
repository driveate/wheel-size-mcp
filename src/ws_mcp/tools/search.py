"""Search tools — fitment lookup by vehicle, rim, or tire.

IMPORTANT: Search tools must be initiated by real users per API Terms of Service.
Do not call these tools in autonomous loops.
"""

from __future__ import annotations

from typing import Annotated, Literal

from fastmcp import FastMCP
from fastmcp.exceptions import ToolError
from pydantic import Field

from ws_mcp.client import DEFAULT_LIMIT, api
from ws_mcp.response import filter_vehicle_fitment, paginated_response
from ws_mcp.slugify import normalize_regions, normalize_slug
from ws_mcp.tools._annotations import SEARCH_ANNOTATIONS


def register(mcp: FastMCP):
    """Register search tools with the MCP server."""

    @mcp.tool(annotations=SEARCH_ANNOTATIONS, tags={"search", "user-initiated"})
    async def search_by_vehicle(
        make: Annotated[str, Field(description="Make slug (e.g. 'toyota'). Use list_makes to find valid slugs.")],
        model: Annotated[str, Field(description="Model slug (e.g. 'camry'). Use list_models to find valid slugs.")],
        year: Annotated[int | None, Field(ge=1950, le=2027, description="Model year")] = None,
        generation: Annotated[
            str | None, Field(description="Generation slug (alternative to year). From list_generations.")
        ] = None,
        modification: Annotated[
            str | None, Field(description="Modification slug from list_modifications. Alternative to region.")
        ] = None,
        region: Annotated[
            str | None,
            Field(description="Single region slug (e.g. 'usdm'). Only ONE region allowed here."),
        ] = None,
        detail_level: Annotated[
            Literal["concise", "full"], Field(description="'concise' = key specs only, 'full' = all wheel/tire details")
        ] = "concise",
        limit: Annotated[int, Field(ge=1, le=50, description="Results per page")] = DEFAULT_LIMIT,
        offset: Annotated[int, Field(ge=0, description="Pagination offset")] = 0,
    ) -> dict:
        """Get wheel and tire fitment data for a specific vehicle.

        REQUIRES TWO conditions:
        1. Either 'year' OR 'generation' (to identify the vehicle)
        2. Either 'modification' OR 'region' (to narrow fitment results)

        PREREQUISITES — you MUST have valid slugs before calling:
        - make: lowercase slug from list_makes (e.g. 'toyota', 'land-rover')
        - model: lowercase slug from list_models (e.g. 'camry', '3-series')
        - year or generation: from list_years / list_generations
        - modification or region: from list_modifications / list_regions
        - NOTE: this endpoint accepts only ONE region (unlike other tools)

        Do NOT guess these values. Call the prerequisite tools first.

        Returns OEM and optional wheel/tire specs including rim diameter, width,
        offset, bolt pattern, tire sizes, and tire pressure.
        Each wheel has setup='symmetric' (same front/rear) or 'staggered' (different).

        IMPORTANT: This is a Search method — only call when a user explicitly
        requests fitment information. Do not call in autonomous loops.
        """
        if not year and not generation:
            raise ToolError(
                "Either 'year' or 'generation' is required to identify the vehicle. "
                "Use list_years or list_generations to find valid values."
            )
        if not modification and not region:
            raise ToolError(
                "Either 'modification' or 'region' is required. "
                "Use list_modifications to get modification slugs, "
                "or list_regions for region slugs (e.g. 'usdm', 'eudm')."
            )
        params = {
            "make": normalize_slug(make), "model": normalize_slug(model), "year": year,
            "generation": normalize_slug(generation) if generation else None,
            "modification": normalize_slug(modification) if modification else None,
            "region": normalize_slug(region) if region else None,
            "limit": limit, "offset": offset,
        }
        data = await api.get("/v2/search/by_model/", params)
        total = data["meta"]["count"]
        items = [filter_vehicle_fitment(item, detail_level) for item in data["data"]]
        return paginated_response(items, total, offset, limit)

    @mcp.tool(annotations=SEARCH_ANNOTATIONS, tags={"search", "user-initiated"})
    async def search_by_rim(
        bolt_pattern: Annotated[str, Field(description="Bolt pattern (e.g. '5x114.3')")],
        rim_diameter: Annotated[float, Field(ge=8, le=26, description="Rim diameter in inches (e.g. 18)")],
        rim_width: Annotated[float, Field(ge=2, le=14, description="Rim width in inches (e.g. 8)")],
        rim_offset: Annotated[int | None, Field(ge=-150, le=150, description="Rim offset in mm")] = None,
        region: Annotated[
            list[str] | None,
            Field(description="Region slug(s) (e.g. ['usdm'] or ['eudm', 'audm'])."),
        ] = None,
        mode: Annotated[Literal["both", "front_only", "rear_only"] | None, Field(description="Axle mode")] = None,
        limit: Annotated[int, Field(ge=1, le=50, description="Results per page")] = DEFAULT_LIMIT,
        offset: Annotated[int, Field(ge=0, description="Pagination offset")] = 0,
    ) -> dict:
        """Find vehicles compatible with given rim specs via direct 1:1 wheel pair matching.

        Uses a direct mapping of existing wheel pair data to vehicle specs —
        returns only vehicles where this exact rim (or close offset) appears
        in the database as an OEM or documented fitment. Does NOT calculate
        whether the rim would physically fit based on wheel housing geometry.

        Requires bolt_pattern, rim_diameter, and rim_width.
        Add rim_offset for more precise results.

        IMPORTANT: This is a Search method — only call when a user explicitly
        requests a rim compatibility search. Do not call in autonomous loops.

        For e-commerce product cards, use find_vehicles_for_rim instead —
        it uses geometric backspace calculations for broader, physics-based matching.
        """
        params = {
            "bolt_pattern": bolt_pattern, "rim_diameter": rim_diameter,
            "rim_width": rim_width, "rim_offset": rim_offset,
            "region": normalize_regions(region), "mode": mode,
            "limit": limit, "offset": offset,
        }
        data = await api.get("/v2/by_rim/search/", params)
        total = data["meta"]["count"]
        items = [
            {
                "make": item["make"]["slug"],
                "make_name": item["make"]["name"],
                "model": item["slug"],
                "model_name": item["name"],
                "year_ranges": item.get("year_ranges", []),
                "regions": item.get("regions", []),
            }
            for item in data["data"]
        ]
        return paginated_response(items, total, offset, limit)

    @mcp.tool(annotations=SEARCH_ANNOTATIONS, tags={"search", "user-initiated"})
    async def search_by_tire(
        section_width: Annotated[int, Field(ge=115, le=365, description="Tire section width in mm (e.g. 225)")],
        aspect_ratio: Annotated[int, Field(ge=25, le=95, description="Tire aspect ratio (e.g. 55)")],
        rim_diameter: Annotated[float, Field(ge=8, le=26, description="Rim diameter in inches (e.g. 17)")],
        region: Annotated[
            list[str] | None,
            Field(description="Region slug(s) (e.g. ['usdm'] or ['eudm', 'audm'])."),
        ] = None,
        mode: Annotated[Literal["both", "front_only", "rear_only"] | None, Field(description="Axle mode")] = None,
        limit: Annotated[int, Field(ge=1, le=50, description="Results per page")] = DEFAULT_LIMIT,
        offset: Annotated[int, Field(ge=0, description="Pagination offset")] = 0,
    ) -> dict:
        """Find vehicles compatible with a given tire size (metric).

        IMPORTANT: This is a Search method — only call when a user explicitly
        requests a tire compatibility search. Do not call in autonomous loops.

        This tool accepts metric sizes only. High-flotation (LT) tires with
        inch-based sizing (e.g. 33x12.5R15) are not supported here — use
        get_spec_metadata (HF mode) for spec information.
        """
        params = {
            "section_width": section_width, "aspect_ratio": aspect_ratio,
            "rim_diameter": rim_diameter,
            "region": normalize_regions(region), "mode": mode,
            "limit": limit, "offset": offset,
        }
        data = await api.get("/v2/by_tire/search/", params)
        total = data["meta"]["count"]
        items = [
            {
                "make": item["make"]["slug"],
                "make_name": item["make"]["name"],
                "model": item["slug"],
                "model_name": item["name"],
                "year_ranges": item.get("year_ranges", []),
                "regions": item.get("regions", []),
            }
            for item in data["data"]
        ]
        return paginated_response(items, total, offset, limit)

    @mcp.tool(annotations=SEARCH_ANNOTATIONS, tags={"search"})
    async def calculate_upsteps(
        rim_diameter: Annotated[float, Field(ge=8, le=26, description="OE rim diameter in inches")],
        rim_width: Annotated[float, Field(ge=2, le=14, description="OE rim width in inches")],
        rim_offset: Annotated[int, Field(ge=-150, le=150, description="OE rim offset in mm")],
        section_width: Annotated[int, Field(ge=115, le=365, description="OE tire section width in mm")],
        aspect_ratio: Annotated[int, Field(ge=25, le=95, description="OE tire aspect ratio")],
        steps: Annotated[int | None, Field(ge=-3, le=3, description="Plus/minus steps (default +2)")] = None,
    ) -> dict:
        """Calculate plus/minus sizing alternatives for a wheel/tire combo.

        Given OEM wheel specs, returns safe replacement sizes at different
        plus/minus levels (e.g. +1, +2 = larger rim with lower-profile tire).

        This is a calculator tool — can be called freely without user initiation.
        """
        params = {
            "rim_diameter": rim_diameter, "rim_width": rim_width,
            "rim_offset": rim_offset, "section_width": section_width,
            "aspect_ratio": aspect_ratio, "steps": steps,
        }
        data = await api.get("/v2/upsteps/", params)
        return {
            "total": data["meta"]["count"],
            "options": [
                {
                    "tire": {
                        "designation": opt["tire"]["designation"],
                        "section_width": opt["tire"]["section_width"],
                        "aspect_ratio": opt["tire"]["aspect_ratio"],
                        "weight": opt["tire"].get("weight"),
                    },
                    "rim": {
                        "designation": opt["rim"]["designation"],
                        "diameter": opt["rim"]["diameter"],
                        "width": opt["rim"]["width"],
                        "offset": opt["rim"]["offset"],
                        "backspacing": opt["rim"]["backspacing"],
                        "weight": opt["rim"].get("weight"),
                    },
                    "is_oe": opt.get("is_oe", False),
                    "difference": opt.get("difference", {}),
                }
                for opt in data["data"]
            ],
        }
