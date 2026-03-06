"""Search tools — fitment lookup by vehicle, rim, or tire.

IMPORTANT: Search tools must be initiated by real users per API Terms of Service.
Do not call these tools in autonomous loops.
"""

from __future__ import annotations

from typing import Annotated, Literal

from fastmcp import FastMCP
from pydantic import Field

from ws_mcp.client import DEFAULT_LIMIT, api
from ws_mcp.response import filter_vehicle_fitment, paginated_response


def register(mcp: FastMCP):
    """Register search tools with the MCP server."""

    @mcp.tool()
    async def search_by_vehicle(
        make: Annotated[str, Field(description="Make slug (e.g. 'toyota'). Use list_makes to find valid slugs.")],
        model: Annotated[str, Field(description="Model slug (e.g. 'camry'). Use list_models to find valid slugs.")],
        year: Annotated[int | None, Field(ge=1950, le=2027, description="Model year")] = None,
        generation: Annotated[str | None, Field(description="Generation slug (alternative to year)")] = None,
        region: Annotated[str | None, Field(description="Region slug (e.g. 'usdm')")] = None,
        detail_level: Annotated[
            Literal["concise", "full"], Field(description="'concise' = key specs only, 'full' = all wheel/tire details")
        ] = "concise",
        limit: Annotated[int, Field(ge=1, le=50, description="Results per page")] = DEFAULT_LIMIT,
        offset: Annotated[int, Field(ge=0, description="Pagination offset")] = 0,
    ) -> dict:
        """Get wheel and tire fitment data for a specific vehicle.

        Returns OEM and optional wheel/tire specs including rim diameter, width,
        offset, bolt pattern, tire sizes, and tire pressure.

        IMPORTANT: This is a Search method — only call when a user explicitly
        requests fitment information. Do not call in autonomous loops.

        Use list_makes -> list_models -> list_years -> list_modifications first
        if you don't have exact make/model/year values.
        """
        params = {
            "make": make, "model": model, "year": year,
            "generation": generation, "region": region,
            "limit": limit, "offset": offset,
        }
        data = await api.get("/v2/search/by_model/", params)
        total = data["meta"]["count"]
        items = [filter_vehicle_fitment(item, detail_level) for item in data["data"]]
        return paginated_response(items, total, offset, limit)

    @mcp.tool()
    async def search_by_rim(
        bolt_pattern: Annotated[str, Field(description="Bolt pattern (e.g. '5x114.3')")],
        rim_diameter: Annotated[float | None, Field(ge=8, le=26, description="Rim diameter in inches")] = None,
        rim_width: Annotated[float | None, Field(ge=2, le=14, description="Rim width in inches")] = None,
        rim_offset: Annotated[int | None, Field(ge=-150, le=150, description="Rim offset in mm")] = None,
        region: Annotated[str | None, Field(description="Region slug")] = None,
        mode: Annotated[Literal["both", "front_only", "rear_only"] | None, Field(description="Axle mode")] = None,
        limit: Annotated[int, Field(ge=1, le=50, description="Results per page")] = DEFAULT_LIMIT,
        offset: Annotated[int, Field(ge=0, description="Pagination offset")] = 0,
    ) -> dict:
        """Find vehicles compatible with given rim specs.

        Pass bolt_pattern alone to get a list of matching vehicles.
        Add rim_diameter, rim_width, rim_offset for more precise results.

        IMPORTANT: This is a Search method — only call when a user explicitly
        requests a rim compatibility search. Do not call in autonomous loops.

        For product card generation (e-commerce), use find_vehicles_for_rim instead.
        """
        params = {
            "bolt_pattern": bolt_pattern, "rim_diameter": rim_diameter,
            "rim_width": rim_width, "rim_offset": rim_offset,
            "region": region, "mode": mode,
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

    @mcp.tool()
    async def search_by_tire(
        section_width: Annotated[int, Field(ge=115, le=365, description="Tire section width in mm (e.g. 225)")],
        aspect_ratio: Annotated[int, Field(ge=25, le=95, description="Tire aspect ratio (e.g. 55)")],
        rim_diameter: Annotated[float, Field(ge=8, le=26, description="Rim diameter in inches (e.g. 17)")],
        region: Annotated[str | None, Field(description="Region slug")] = None,
        mode: Annotated[Literal["both", "front_only", "rear_only"] | None, Field(description="Axle mode")] = None,
        limit: Annotated[int, Field(ge=1, le=50, description="Results per page")] = DEFAULT_LIMIT,
        offset: Annotated[int, Field(ge=0, description="Pagination offset")] = 0,
    ) -> dict:
        """Find vehicles compatible with a given tire size (metric).

        IMPORTANT: This is a Search method — only call when a user explicitly
        requests a tire compatibility search. Do not call in autonomous loops.

        For high-flotation (LT) tires with inch-based sizing (e.g. 33x12.5R15),
        use search_by_hf_tire instead.
        """
        params = {
            "section_width": section_width, "aspect_ratio": aspect_ratio,
            "rim_diameter": rim_diameter, "region": region, "mode": mode,
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

    @mcp.tool()
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
            "options": data["data"],
        }
