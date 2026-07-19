"""Classified tools — product card generation for e-commerce.

IMPORTANT: Classified tools must be initiated by real users per API Terms of Service.
Do not call these tools in autonomous loops or for bulk data generation.
"""

from __future__ import annotations

from typing import Annotated, Literal

from fastmcp import FastMCP
from pydantic import Field

from ws_mcp.client import DEFAULT_LIMIT, api
from ws_mcp.response import map_classified_generation_row, map_drilldown_row, paginated_response
from ws_mcp.slugify import normalize_slug
from ws_mcp.tools._annotations import CLASSIFIED_ANNOTATIONS

# Shared parameter types — the classified rim/package endpoints accept an
# identical geometric filter set (see /v2/classified/* in the OpenAPI spec)
_BoltPattern = Annotated[str, Field(description="Bolt pattern (e.g. '5x114.3')")]
_RimDiameter = Annotated[float, Field(ge=8, le=26, description="Rim diameter in inches")]
_RimWidth = Annotated[float, Field(ge=2, le=14, description="Rim width in inches")]
_RimOffset = Annotated[float, Field(ge=-150, le=150, description="Rim offset in mm")]
_SectionWidth = Annotated[int, Field(ge=115, le=365, description="Tire section width in mm")]
_AspectRatio = Annotated[int, Field(ge=25, le=95, description="Tire aspect ratio")]
_Cb = Annotated[float | None, Field(ge=52.1, le=225, description="Centre bore diameter in mm")]
_Fd = Annotated[
    float | None,
    Field(ge=9.525, le=18, description="Wheel fastener thread diameter in mm (e.g. 12 for M12)"),
]
_FsPoke = Annotated[
    int | None, Field(ge=0, le=150, description="Frontspace poke tolerance in mm (default 2)")
]
_BsPush = Annotated[
    int | None, Field(ge=0, le=150, description="Backspace push tolerance in mm (default 2)")
]
_RimBstFrom = Annotated[
    int | None, Field(ge=1, le=8, description="Backspace tolerance lower bound in mm (default 2)")
]
_RimBstTo = Annotated[
    int | None, Field(ge=1, le=8, description="Backspace tolerance upper bound in mm (default 2)")
]
_OdTolerance = Annotated[
    float | None, Field(ge=0, le=0.05, description="Overall diameter tolerance fraction (default 0.01)")
]
_OwTolerance = Annotated[
    float | None, Field(ge=0, le=0.03, description="Overall width tolerance fraction (default 0)")
]
_DiameterRange = Annotated[
    int | None,
    Field(ge=0, le=3, description="Widen rim diameter search ±N inches (0 = exact match)"),
]
_Sort = Annotated[
    Literal["name", "fitment", "load"] | None,
    Field(description="Sort: name (A-Z), fitment (closest FS delta first), load (heaviest first)"),
]
_Limit = Annotated[int, Field(ge=1, le=50, description="Results per page")]
_Offset = Annotated[int, Field(ge=0, description="Pagination offset")]


def _geometry_params(
    cb, fd, fs_poke, bs_push, rim_bst_from, rim_bst_to, od_tolerance, ow_tolerance, diameter_range, sort
) -> dict:
    """Common geometric filter params shared by classified rim/package endpoints."""
    return {
        "cb": cb, "fd": fd, "fs_poke": fs_poke, "bs_push": bs_push,
        "rim_bst_from": rim_bst_from, "rim_bst_to": rim_bst_to,
        "od_tolerance": od_tolerance, "ow_tolerance": ow_tolerance,
        "diameter_range": diameter_range, "sort": sort,
    }


def register(mcp: FastMCP):
    """Register classified tools with the MCP server."""

    @mcp.tool(annotations=CLASSIFIED_ANNOTATIONS, tags={"classified", "e-commerce", "user-initiated"})
    async def ws_find_tires_for_rim(
        bolt_pattern: _BoltPattern,
        rim_diameter: _RimDiameter,
        rim_width: _RimWidth,
        rim_offset: _RimOffset,
        cb: _Cb = None,
        fd: _Fd = None,
        fs_poke: _FsPoke = None,
        bs_push: _BsPush = None,
        rim_bst_from: _RimBstFrom = None,
        rim_bst_to: _RimBstTo = None,
        od_tolerance: _OdTolerance = None,
        ow_tolerance: _OwTolerance = None,
        diameter_range: _DiameterRange = None,
        sort: _Sort = None,
        limit: _Limit = DEFAULT_LIMIT,
        offset: _Offset = 0,
    ) -> dict:
        """Find compatible tire sizes for a given rim specification.

        Returns tire sizes (e.g. '245/70R17') with the number of vehicle
        generations that use each tire on this rim. Set diameter_range to
        also include tires for ±N inch rim diameters.

        Useful for tire product recommendations on wheel product pages.
        """
        params = {
            "bolt_pattern": bolt_pattern, "rim_diameter": rim_diameter,
            "rim_width": rim_width, "rim_offset": rim_offset,
            **_geometry_params(cb, fd, fs_poke, bs_push, rim_bst_from, rim_bst_to,
                               od_tolerance, ow_tolerance, diameter_range, sort),
            "limit": limit, "offset": offset,
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

    @mcp.tool(annotations=CLASSIFIED_ANNOTATIONS, tags={"classified", "e-commerce", "user-initiated"})
    async def ws_find_vehicles_for_rim(
        bolt_pattern: _BoltPattern,
        rim_diameter: _RimDiameter,
        rim_width: _RimWidth,
        rim_offset: _RimOffset,
        cb: _Cb = None,
        fd: _Fd = None,
        fs_poke: _FsPoke = None,
        bs_push: _BsPush = None,
        rim_bst_from: _RimBstFrom = None,
        rim_bst_to: _RimBstTo = None,
        od_tolerance: _OdTolerance = None,
        ow_tolerance: _OwTolerance = None,
        diameter_range: _DiameterRange = None,
        sort: _Sort = None,
        limit: _Limit = DEFAULT_LIMIT,
        offset: _Offset = 0,
    ) -> dict:
        """Find vehicle generations compatible with a given rim via geometric backspace calculations.

        Unlike ws_search_by_rim (which does direct 1:1 wheel pair matching),
        this endpoint uses advanced 2D geometric filtering based on
        frontspace/backspace calculations to determine physical fitment.
        This yields broader results — any vehicle where the rim physically
        fits the wheel housing, even if this exact spec isn't in the OEM database.

        Returns make/model/generation with fitment deltas (frontspace/backspace),
        load capacity, and OEM ratio ranges. Use sort='fitment' to put the
        closest matches first on product pages.

        Note: in some cases spacers or special bolts/nuts may be required.
        Always verify rims don't interfere with brake calipers or extend
        beyond the wheel arch.

        For e-commerce product pages: "This wheel fits: BMW X5, Audi Q7..."
        To drill into a specific generation, use ws_find_vehicle_modifications_for_rim.
        """
        params = {
            "bolt_pattern": bolt_pattern, "rim_diameter": rim_diameter,
            "rim_width": rim_width, "rim_offset": rim_offset,
            **_geometry_params(cb, fd, fs_poke, bs_push, rim_bst_from, rim_bst_to,
                               od_tolerance, ow_tolerance, diameter_range, sort),
            "limit": limit, "offset": offset,
        }
        data = await api.get("/v2/classified/by_rim/search/", params)
        total = data["meta"]["count"]
        items = [
            {
                **map_classified_generation_row(item),
                "regions": item.get("regions", []),
                "min_fs_delta_mm": item.get("min_fs_delta_mm"),
                "max_fs_delta_mm": item.get("max_fs_delta_mm"),
                "max_load_kg": item.get("max_load_kg"),
                "cb_diff_mm": item.get("cb_diff_mm"),
            }
            for item in data["data"]
        ]
        return paginated_response(items, total, offset, limit)

    @mcp.tool(annotations=CLASSIFIED_ANNOTATIONS, tags={"classified", "e-commerce", "user-initiated"})
    async def ws_find_vehicle_modifications_for_rim(
        make: Annotated[str, Field(description="Make slug from ws_find_vehicles_for_rim results")],
        model: Annotated[str, Field(description="Model slug from ws_find_vehicles_for_rim results")],
        generation: Annotated[str, Field(description="Generation slug from ws_find_vehicles_for_rim results")],
        bolt_pattern: _BoltPattern,
        rim_diameter: _RimDiameter,
        rim_width: _RimWidth,
        rim_offset: _RimOffset,
        cb: _Cb = None,
        fd: _Fd = None,
        fs_poke: _FsPoke = None,
        bs_push: _BsPush = None,
        rim_bst_from: _RimBstFrom = None,
        rim_bst_to: _RimBstTo = None,
        od_tolerance: _OdTolerance = None,
        ow_tolerance: _OwTolerance = None,
        diameter_range: _DiameterRange = None,
        sort: _Sort = None,
        limit: _Limit = DEFAULT_LIMIT,
        offset: _Offset = 0,
    ) -> dict:
        """Drill down into individual trims for a generation from ws_find_vehicles_for_rim.

        PREREQUISITES — call ws_find_vehicles_for_rim first to get:
        - make, model, generation slugs (from the results)
        - Use the same rim parameters and tolerances as the parent search

        Returns per-vehicle rows with OEM wheel specs (rim, tire, frontspace,
        backspace) and fitment deltas vs the searched rim.
        """
        params = {
            "make": normalize_slug(make), "model": normalize_slug(model),
            "generation": normalize_slug(generation),
            "bolt_pattern": bolt_pattern, "rim_diameter": rim_diameter,
            "rim_width": rim_width, "rim_offset": rim_offset,
            **_geometry_params(cb, fd, fs_poke, bs_push, rim_bst_from, rim_bst_to,
                               od_tolerance, ow_tolerance, diameter_range, sort),
            "limit": limit, "offset": offset,
        }
        data = await api.get("/v2/classified/by_rim/search/modifications/", params)
        total = data["meta"]["count"]
        items = [map_drilldown_row(item) for item in data["data"]]
        return paginated_response(items, total, offset, limit)

    @mcp.tool(annotations=CLASSIFIED_ANNOTATIONS, tags={"classified", "e-commerce", "user-initiated"})
    async def ws_find_vehicle_modifications_for_package(
        make: Annotated[str, Field(description="Make slug from ws_find_vehicles_for_package results")],
        model: Annotated[str, Field(description="Model slug from ws_find_vehicles_for_package results")],
        generation: Annotated[str, Field(description="Generation slug from ws_find_vehicles_for_package results")],
        bolt_pattern: _BoltPattern,
        rim_diameter: _RimDiameter,
        rim_width: _RimWidth,
        rim_offset: _RimOffset,
        section_width: _SectionWidth,
        aspect_ratio: _AspectRatio,
        cb: _Cb = None,
        fd: _Fd = None,
        fs_poke: _FsPoke = None,
        bs_push: _BsPush = None,
        rim_bst_from: _RimBstFrom = None,
        rim_bst_to: _RimBstTo = None,
        od_tolerance: _OdTolerance = None,
        ow_tolerance: _OwTolerance = None,
        diameter_range: _DiameterRange = None,
        sort: _Sort = None,
        limit: _Limit = DEFAULT_LIMIT,
        offset: _Offset = 0,
    ) -> dict:
        """Drill down into individual trims for a generation from ws_find_vehicles_for_package.

        PREREQUISITES — call ws_find_vehicles_for_package first to get:
        - make, model, generation slugs (from the results)
        - Use the same rim AND tire parameters and tolerances as the parent search

        Returns per-vehicle rows with OEM wheel specs (rim, tire) and fitment
        deltas vs the searched rim + tire package. Completes the e-commerce
        chain: package search → generations → specific trims.
        """
        params = {
            "make": normalize_slug(make), "model": normalize_slug(model),
            "generation": normalize_slug(generation),
            "bolt_pattern": bolt_pattern, "rim_diameter": rim_diameter,
            "rim_width": rim_width, "rim_offset": rim_offset,
            "section_width": section_width, "aspect_ratio": aspect_ratio,
            **_geometry_params(cb, fd, fs_poke, bs_push, rim_bst_from, rim_bst_to,
                               od_tolerance, ow_tolerance, diameter_range, sort),
            "limit": limit, "offset": offset,
        }
        data = await api.get("/v2/classified/by_package/search/modifications/", params)
        total = data["meta"]["count"]
        items = [map_drilldown_row(item) for item in data["data"]]
        return paginated_response(items, total, offset, limit)

    @mcp.tool(annotations=CLASSIFIED_ANNOTATIONS, tags={"classified", "e-commerce", "user-initiated"})
    async def ws_find_vehicles_for_tire(
        section_width: _SectionWidth,
        aspect_ratio: _AspectRatio,
        rim_diameter: _RimDiameter,
        limit: _Limit = DEFAULT_LIMIT,
        offset: _Offset = 0,
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
            {**map_classified_generation_row(item), "regions": item.get("regions", [])}
            for item in data["data"]
        ]
        return paginated_response(items, total, offset, limit)

    @mcp.tool(annotations=CLASSIFIED_ANNOTATIONS, tags={"classified", "e-commerce", "user-initiated"})
    async def ws_find_vehicles_for_package(
        bolt_pattern: _BoltPattern,
        rim_diameter: _RimDiameter,
        rim_width: _RimWidth,
        rim_offset: _RimOffset,
        section_width: _SectionWidth,
        aspect_ratio: _AspectRatio,
        cb: _Cb = None,
        fd: _Fd = None,
        fs_poke: _FsPoke = None,
        bs_push: _BsPush = None,
        rim_bst_from: _RimBstFrom = None,
        rim_bst_to: _RimBstTo = None,
        od_tolerance: _OdTolerance = None,
        ow_tolerance: _OwTolerance = None,
        diameter_range: _DiameterRange = None,
        sort: _Sort = None,
        limit: _Limit = DEFAULT_LIMIT,
        offset: _Offset = 0,
    ) -> dict:
        """Find vehicles compatible with a rim + tire package.

        Most precise classified search — considers both physical wheel
        fitment (backspace) and tire size compatibility simultaneously.
        Use sort='fitment' to put the closest matches first.

        For e-commerce combo/bundle product pages.
        To drill into a specific generation, use ws_find_vehicle_modifications_for_package.
        """
        params = {
            "bolt_pattern": bolt_pattern, "rim_diameter": rim_diameter,
            "rim_width": rim_width, "rim_offset": rim_offset,
            "section_width": section_width, "aspect_ratio": aspect_ratio,
            **_geometry_params(cb, fd, fs_poke, bs_push, rim_bst_from, rim_bst_to,
                               od_tolerance, ow_tolerance, diameter_range, sort),
            "limit": limit, "offset": offset,
        }
        data = await api.get("/v2/classified/by_package/search/", params)
        total = data["meta"]["count"]
        items = [
            {
                **map_classified_generation_row(item),
                "max_load_kg": item.get("max_load_kg"),
                "cb_diff_mm": item.get("cb_diff_mm"),
            }
            for item in data["data"]
        ]
        return paginated_response(items, total, offset, limit)
