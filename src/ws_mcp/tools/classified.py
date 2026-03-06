"""Classified tools — product card generation for e-commerce."""

from __future__ import annotations

from typing import Annotated, Literal

from fastmcp import FastMCP
from pydantic import Field

from ws_mcp.client import DEFAULT_LIMIT, api
from ws_mcp.response import paginated_response


def register(mcp: FastMCP):
    """Register classified tools with the MCP server."""

    @mcp.tool()
    async def find_tires_for_rim(
        bolt_pattern: Annotated[str, Field(description="Bolt pattern (e.g. '5x114.3')")],
        rim_diameter: Annotated[float, Field(ge=8, le=26, description="Rim diameter in inches")],
        rim_width: Annotated[float, Field(ge=2, le=14, description="Rim width in inches")],
        rim_offset: Annotated[float, Field(ge=-150, le=150, description="Rim offset in mm")],
        cb: Annotated[float | None, Field(ge=52.1, le=225, description="Centre bore diameter in mm")] = None,
        limit: Annotated[int, Field(ge=1, le=50, description="Results per page")] = DEFAULT_LIMIT,
        offset: Annotated[int, Field(ge=0, description="Pagination offset")] = 0,
    ) -> dict:
        """Find compatible tire sizes for a given rim specification.

        Returns tire sizes (e.g. '245/70R17') with the number of vehicle
        generations that use each tire on this rim.

        Useful for tire product recommendations on wheel product pages.
        """
        params = {
            "bolt_pattern": bolt_pattern, "rim_diameter": rim_diameter,
            "rim_width": rim_width, "rim_offset": rim_offset,
            "cb": cb, "limit": limit, "offset": offset,
        }
        data = await api.get("/v2/classified/by_rim/", params)
        total = data["meta"]["count"]
        items = [
            {
                "tire": item["value"],
                "vehicle_count": item["total"],
                "params": item.get("params"),
            }
            for item in data["data"]
        ]
        return paginated_response(items, total, offset, limit)

    @mcp.tool()
    async def find_vehicles_for_rim(
        bolt_pattern: Annotated[str, Field(description="Bolt pattern (e.g. '5x114.3')")],
        rim_diameter: Annotated[float, Field(ge=8, le=26, description="Rim diameter in inches")],
        rim_width: Annotated[float, Field(ge=2, le=14, description="Rim width in inches")],
        rim_offset: Annotated[float, Field(ge=-150, le=150, description="Rim offset in mm")],
        cb: Annotated[float | None, Field(ge=52.1, le=225, description="Centre bore diameter in mm")] = None,
        fs_poke: Annotated[int | None, Field(ge=0, le=150, description="Frontspace poke tolerance in mm (default 2)")] = None,
        bs_push: Annotated[int | None, Field(ge=0, le=150, description="Backspace push tolerance in mm (default 2)")] = None,
        sort: Annotated[Literal["name", "fitment", "load"] | None, Field(description="Sort: A-Z name, closest fitment delta, heaviest load")] = None,
        limit: Annotated[int, Field(ge=1, le=50, description="Results per page")] = DEFAULT_LIMIT,
        offset: Annotated[int, Field(ge=0, description="Pagination offset")] = 0,
    ) -> dict:
        """Find vehicle generations compatible with a given rim.

        Returns make/model/generation with fitment deltas (frontspace/backspace),
        load capacity, and OEM ratio ranges. Uses 2D geometric filtering for
        accurate physical fitment.

        For e-commerce product pages: "This wheel fits: BMW X5, Audi Q7..."
        To drill into a specific generation, use find_vehicle_modifications_for_rim.
        """
        params = {
            "bolt_pattern": bolt_pattern, "rim_diameter": rim_diameter,
            "rim_width": rim_width, "rim_offset": rim_offset,
            "cb": cb, "fs_poke": fs_poke, "bs_push": bs_push,
            "sort": sort, "limit": limit, "offset": offset,
        }
        data = await api.get("/v2/classified/by_rim/search/", params)
        total = data["meta"]["count"]
        items = [
            {
                "make": item["model"]["make"]["slug"],
                "make_name": item["model"]["make"]["name"],
                "model": item["model"]["slug"],
                "model_name": item["model"]["name"],
                "generation": item["slug"],
                "generation_name": item["name"],
                "year_ranges": item.get("year_ranges", []),
                "regions": item.get("regions", []),
                "min_fs_delta_mm": item.get("min_fs_delta_mm"),
                "max_fs_delta_mm": item.get("max_fs_delta_mm"),
                "max_load_kg": item.get("max_load_kg"),
                "cb_diff_mm": item.get("cb_diff_mm"),
            }
            for item in data["data"]
        ]
        return paginated_response(items, total, offset, limit)

    @mcp.tool()
    async def find_vehicle_modifications_for_rim(
        make: Annotated[str, Field(description="Make slug from find_vehicles_for_rim results")],
        model: Annotated[str, Field(description="Model slug from find_vehicles_for_rim results")],
        generation: Annotated[str, Field(description="Generation slug from find_vehicles_for_rim results")],
        bolt_pattern: Annotated[str, Field(description="Bolt pattern (e.g. '5x114.3')")],
        rim_diameter: Annotated[float, Field(ge=8, le=26, description="Rim diameter in inches")],
        rim_width: Annotated[float, Field(ge=2, le=14, description="Rim width in inches")],
        rim_offset: Annotated[float, Field(ge=-150, le=150, description="Rim offset in mm")],
        cb: Annotated[float | None, Field(ge=52.1, le=225, description="Centre bore diameter in mm")] = None,
        limit: Annotated[int, Field(ge=1, le=50, description="Results per page")] = DEFAULT_LIMIT,
        offset: Annotated[int, Field(ge=0, description="Pagination offset")] = 0,
    ) -> dict:
        """Drill down into individual trims for a generation from find_vehicles_for_rim.

        Returns per-vehicle rows with OEM wheel specs (rim, tire, frontspace,
        backspace) and fitment deltas vs the searched rim.

        Call find_vehicles_for_rim first to get make/model/generation slugs.
        """
        params = {
            "make": make, "model": model, "generation": generation,
            "bolt_pattern": bolt_pattern, "rim_diameter": rim_diameter,
            "rim_width": rim_width, "rim_offset": rim_offset,
            "cb": cb, "limit": limit, "offset": offset,
        }
        data = await api.get("/v2/classified/by_rim/search/modifications/", params)
        total = data["meta"]["count"]
        items = [
            {
                "vehicle_id": item["vehicle_id"],
                "trim": item["trim"],
                "body": item.get("body"),
                "years": f"{item['production_start_year']}-{item['production_end_year']}",
                "oem_rim": item.get("oem_rim"),
                "oem_tire": item.get("oem_tire"),
                "fs_delta_mm": item.get("fs_delta_mm"),
                "bs_delta_mm": item.get("bs_delta_mm"),
                "load_kg": item.get("load_kg"),
            }
            for item in data["data"]
        ]
        return paginated_response(items, total, offset, limit)

    @mcp.tool()
    async def find_vehicles_for_tire(
        section_width: Annotated[int, Field(ge=115, le=365, description="Tire section width in mm")],
        aspect_ratio: Annotated[int, Field(ge=25, le=95, description="Tire aspect ratio")],
        rim_diameter: Annotated[float, Field(ge=8, le=26, description="Rim diameter in inches")],
        limit: Annotated[int, Field(ge=1, le=50, description="Results per page")] = DEFAULT_LIMIT,
        offset: Annotated[int, Field(ge=0, description="Pagination offset")] = 0,
    ) -> dict:
        """Find vehicle generations that use a specific tire size.

        Simplest classified search — matches tire dimensions only,
        no bolt pattern or backspace filtering.

        For e-commerce: "This tire fits: Honda Civic, Toyota Camry..."
        """
        params = {
            "section_width": section_width, "aspect_ratio": aspect_ratio,
            "rim_diameter": rim_diameter, "limit": limit, "offset": offset,
        }
        data = await api.get("/v2/classified/by_tire/search/", params)
        total = data["meta"]["count"]
        items = [
            {
                "make": item["model"]["make"]["slug"],
                "make_name": item["model"]["make"]["name"],
                "model": item["model"]["slug"],
                "model_name": item["model"]["name"],
                "generation": item["slug"],
                "generation_name": item["name"],
                "year_ranges": item.get("year_ranges", []),
                "regions": item.get("regions", []),
            }
            for item in data["data"]
        ]
        return paginated_response(items, total, offset, limit)

    @mcp.tool()
    async def find_vehicles_for_package(
        bolt_pattern: Annotated[str, Field(description="Bolt pattern (e.g. '5x114.3')")],
        rim_diameter: Annotated[float, Field(ge=8, le=26, description="Rim diameter in inches")],
        rim_width: Annotated[float, Field(ge=2, le=14, description="Rim width in inches")],
        rim_offset: Annotated[float, Field(ge=-150, le=150, description="Rim offset in mm")],
        section_width: Annotated[int, Field(ge=115, le=365, description="Tire section width in mm")],
        aspect_ratio: Annotated[int, Field(ge=25, le=95, description="Tire aspect ratio")],
        cb: Annotated[float | None, Field(ge=52.1, le=225, description="Centre bore diameter in mm")] = None,
        sort: Annotated[Literal["name", "fitment", "load"] | None, Field(description="Sort order")] = None,
        limit: Annotated[int, Field(ge=1, le=50, description="Results per page")] = DEFAULT_LIMIT,
        offset: Annotated[int, Field(ge=0, description="Pagination offset")] = 0,
    ) -> dict:
        """Find vehicles compatible with a rim + tire package.

        Most precise classified search — considers both physical wheel
        fitment (backspace) and tire size compatibility simultaneously.

        For e-commerce combo/bundle product pages.
        """
        params = {
            "bolt_pattern": bolt_pattern, "rim_diameter": rim_diameter,
            "rim_width": rim_width, "rim_offset": rim_offset,
            "section_width": section_width, "aspect_ratio": aspect_ratio,
            "cb": cb, "sort": sort, "limit": limit, "offset": offset,
        }
        data = await api.get("/v2/classified/by_package/search/", params)
        total = data["meta"]["count"]
        items = [
            {
                "make": item["model"]["make"]["slug"],
                "make_name": item["model"]["make"]["name"],
                "model": item["model"]["slug"],
                "model_name": item["model"]["name"],
                "generation": item["slug"],
                "generation_name": item["name"],
                "year_ranges": item.get("year_ranges", []),
                "max_load_kg": item.get("max_load_kg"),
                "cb_diff_mm": item.get("cb_diff_mm"),
            }
            for item in data["data"]
        ]
        return paginated_response(items, total, offset, limit)
