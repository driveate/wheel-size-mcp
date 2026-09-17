"""Search tools — fitment lookup by vehicle, rim, or tire.

IMPORTANT: Search tools must be initiated by real users per API Terms of Service.
Do not call these tools in autonomous loops.
"""

from __future__ import annotations

from typing import Annotated, Literal

from fastmcp import FastMCP
from fastmcp.exceptions import ToolError
from pydantic import Field

from ws_mcp.client import DEFAULT_LIMIT, MAX_ITEMS, api
from ws_mcp.response import (
    filter_vehicle_fitment,
    map_car_search_row,
    map_modification_row,
    paginated_response,
)
from ws_mcp.slugify import normalize_regions, normalize_slug
from ws_mcp.tools._annotations import SEARCH_ANNOTATIONS

# Max raw rows fetched from the API when filtering by year MCP-side
# (the search/modifications endpoints expose no year parameter)
_YEAR_FETCH_CAP = 200
_API_PAGE_SIZE = 50

# Max options kept per facet to respect the ~25K token response cap
_FACET_CAP = 50

_SPEED_SYMBOLS = ["L", "M", "N", "P", "Q", "R", "S", "T", "U", "H", "V", "Z", "W", "Y"]
_SpeedSymbol = Literal["L", "M", "N", "P", "Q", "R", "S", "T", "U", "H", "V", "Z", "W", "Y"]


def _compact_facets(meta: dict) -> dict:
    """Compact meta.facets: keep active + value→count options, cap entries per facet."""
    out = {}
    for name, facet in (meta.get("facets") or {}).items():
        options = facet.get("options") or {}
        entry: dict = {"active": facet.get("active", [])}
        if len(options) > _FACET_CAP:
            entry["options"] = dict(list(options.items())[:_FACET_CAP])
            entry["truncated"] = f"top {_FACET_CAP} of {len(options)}"
        else:
            entry["options"] = options
        out[name] = entry
    return out


def _check_dimension(name: str, exact, lo, hi, required: bool = False) -> None:
    """Validate an exact-or-range dimension: exclusive, paired, ordered."""
    if exact is not None and (lo is not None or hi is not None):
        raise ToolError(f"Use either {name} or the {name}_min/{name}_max range, not both.")
    if (lo is None) != (hi is None):
        raise ToolError(f"Range search needs both {name}_min and {name}_max.")
    if lo is not None and lo > hi:
        raise ToolError(f"{name}_min must be <= {name}_max.")
    if required and exact is None and lo is None:
        raise ToolError(f"Provide {name}, or both {name}_min and {name}_max.")


def _year_in_range(item: dict, year: int) -> bool:
    """True if the modification's production range covers the year (open ends pass)."""
    start, end = item.get("start_year"), item.get("end_year")
    return (start is None or start <= year) and (end is None or year <= end)


async def _fitment_check(path: str, params: dict, year: int | None, limit: int, offset: int) -> dict:
    """Run a search/modifications request with optional MCP-side year filtering.

    Without a year the API's own pagination is used. With a year, raw rows are
    fetched (up to _YEAR_FETCH_CAP), filtered by production range, and the
    filtered list is paginated MCP-side.
    """
    if year is None:
        data = await api.get(path, {**params, "limit": limit, "offset": offset})
        items = [map_modification_row(r) for r in data["data"]]
        return paginated_response(items, data["meta"]["count"], offset, limit)

    raw: list[dict] = []
    api_offset = 0
    truncated = False
    while True:
        data = await api.get(path, {**params, "limit": _API_PAGE_SIZE, "offset": api_offset})
        raw.extend(data["data"])
        api_offset += _API_PAGE_SIZE
        if api_offset >= data["meta"]["count"]:
            break
        if api_offset >= _YEAR_FETCH_CAP:
            truncated = True
            break

    matched = [r for r in raw if _year_in_range(r, year)]
    items = [map_modification_row(r) for r in matched[offset : offset + limit]]
    result = paginated_response(items, len(matched), offset, limit)
    if truncated:
        result["note"] = (
            f"Year filter scanned only the first {_YEAR_FETCH_CAP} of "
            f"{data['meta']['count']} matching rows — results may be incomplete. "
            f"Narrow the spec (e.g. add rim_offset) to reduce the candidate set."
        )
    return result


def register(mcp: FastMCP):
    """Register search tools with the MCP server."""

    @mcp.tool(annotations=SEARCH_ANNOTATIONS, tags={"search", "user-initiated"})
    async def ws_search_by_vehicle(
        make: Annotated[str, Field(description="Make slug (e.g. 'toyota'). Use ws_list_makes to find valid slugs.")],
        model: Annotated[str, Field(description="Model slug (e.g. 'camry'). Use ws_list_models to find valid slugs.")],
        year: Annotated[int | None, Field(ge=1950, le=2027, description="Model year")] = None,
        generation: Annotated[
            str | None, Field(description="Generation slug (alternative to year). From ws_list_generations.")
        ] = None,
        modification: Annotated[
            str | None, Field(description="Modification slug from ws_list_modifications. Alternative to region.")
        ] = None,
        region: Annotated[
            str | None,
            Field(description="Single region slug (e.g. 'usdm'). Only ONE region allowed here."),
        ] = None,
        detail_level: Annotated[
            Literal["concise", "full"], Field(description="'concise' = key specs only, 'full' = all wheel/tire details")
        ] = "concise",
        lang: Annotated[
            str | None,
            Field(description="Translate make/model/region names (e.g. 'ru')."),
        ] = None,
        limit: Annotated[int, Field(ge=1, le=50, description="Results per page")] = DEFAULT_LIMIT,
        offset: Annotated[int, Field(ge=0, description="Pagination offset")] = 0,
    ) -> dict:
        """Get wheel and tire fitment data for a specific vehicle.

        REQUIRED parameter combination:
        1. Either 'modification' OR 'region' (to narrow fitment results)
        2. Either 'year' OR 'generation' (to identify the vehicle) —
           not required when 'modification' is provided

        PREREQUISITES — you MUST have valid slugs before calling:
        - make: lowercase slug from ws_list_makes (e.g. 'toyota', 'land-rover')
        - model: lowercase slug from ws_list_models (e.g. 'camry', '3-series')
        - modification or region: from ws_list_modifications / ws_list_regions
        - year or generation: from ws_list_years / ws_list_generations
          (skip when modification is provided)
        - NOTE: this endpoint accepts only ONE region (unlike other tools)

        Do NOT guess these values. Call the prerequisite tools first.

        Returns OEM and optional wheel/tire specs including rim diameter, width,
        offset, bolt pattern, tire sizes, and tire pressure.
        Each wheel has setup='symmetric' (same front/rear) or 'staggered' (different).

        Each row also carries the legacy engine block and the full powertrain
        block as the API returns them: combustion_engine, electrification_level,
        primary_fuel / secondary_fuel as {code, title}, engine_power /
        system_power / engine_power_secondary as {kW, PS, hp} or null, and
        motors [{axle, power, code}]. The field vocabulary, the absence words
        (not_applicable / not_reported / unknown) and the power semantics are
        described in ws_list_modifications.

        IMPORTANT: This is a Search method — only call when a user explicitly
        requests fitment information. Do not call in autonomous loops.
        """
        if not modification and not region:
            raise ToolError(
                "Either 'modification' or 'region' is required. "
                "Use ws_list_modifications to get modification slugs, "
                "or ws_list_regions for region slugs (e.g. 'usdm', 'eudm')."
            )
        if not modification and not year and not generation:
            raise ToolError(
                "Either 'year' or 'generation' is required to identify the vehicle "
                "(not needed when 'modification' is provided). "
                "Use ws_list_years or ws_list_generations to find valid values."
            )
        params = {
            "make": normalize_slug(make), "model": normalize_slug(model), "year": year,
            "generation": normalize_slug(generation) if generation else None,
            "modification": normalize_slug(modification) if modification else None,
            "region": normalize_slug(region) if region else None,
            "lang": lang, "limit": limit, "offset": offset,
        }
        data = await api.get("/v2/search/by_model/", params)
        total = data["meta"]["count"]
        items = [filter_vehicle_fitment(item, detail_level) for item in data["data"]]
        return paginated_response(items, total, offset, limit)

    @mcp.tool(annotations=SEARCH_ANNOTATIONS, tags={"search", "user-initiated"})
    async def ws_search_by_rim(
        bolt_pattern: Annotated[str, Field(description="Bolt pattern (e.g. '5x114.3')")],
        rim_diameter: Annotated[
            float | None, Field(ge=8, le=26, description="Exact rim diameter in inches (e.g. 18)")
        ] = None,
        rim_width: Annotated[
            float | None, Field(ge=2, le=14, description="Exact rim width in inches (e.g. 8)")
        ] = None,
        rim_offset: Annotated[int | None, Field(ge=-150, le=150, description="Rim offset in mm")] = None,
        rim_diameter_min: Annotated[
            float | None, Field(ge=8, le=26, description="Range search: min diameter (use with _max)")
        ] = None,
        rim_diameter_max: Annotated[float | None, Field(ge=8, le=26, description="Range search: max diameter")] = None,
        rim_width_min: Annotated[
            float | None, Field(ge=2, le=14, description="Range search: min width (use with _max)")
        ] = None,
        rim_width_max: Annotated[float | None, Field(ge=2, le=14, description="Range search: max width")] = None,
        rim_offset_min: Annotated[int | None, Field(ge=-150, le=150, description="Range search: min offset")] = None,
        rim_offset_max: Annotated[int | None, Field(ge=-150, le=150, description="Range search: max offset")] = None,
        cb: Annotated[float | None, Field(ge=52.1, le=225, description="Centre bore in mm (e.g. 64.1)")] = None,
        cb_min: Annotated[float | None, Field(ge=52.1, le=225, description="Range search: min centre bore")] = None,
        cb_max: Annotated[float | None, Field(ge=52.1, le=225, description="Range search: max centre bore")] = None,
        fd: Annotated[
            float | None,
            Field(ge=9.525, le=18, description="Wheel fastener thread diameter in mm (e.g. 12 for M12)"),
        ] = None,
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

        Diameter and width accept either an exact value (rim_diameter,
        rim_width) or a min/max range pair — e.g. "18-19 inch, ET30-45" →
        rim_diameter_min=18, rim_diameter_max=19, rim_offset_min=30,
        rim_offset_max=45. One of exact or range is required per dimension.

        IMPORTANT: This is a Search method — only call when a user explicitly
        requests a rim compatibility search. Do not call in autonomous loops.

        For e-commerce product cards, use ws_find_vehicles_for_rim instead —
        it uses geometric backspace calculations for broader, physics-based matching.
        """
        _check_dimension("rim_diameter", rim_diameter, rim_diameter_min, rim_diameter_max, required=True)
        _check_dimension("rim_width", rim_width, rim_width_min, rim_width_max, required=True)
        _check_dimension("rim_offset", rim_offset, rim_offset_min, rim_offset_max)
        _check_dimension("cb", cb, cb_min, cb_max)
        params = {
            "bolt_pattern": bolt_pattern, "rim_diameter": rim_diameter,
            "rim_width": rim_width, "rim_offset": rim_offset,
            "rim_diameter_min": rim_diameter_min, "rim_diameter_max": rim_diameter_max,
            "rim_width_min": rim_width_min, "rim_width_max": rim_width_max,
            "rim_offset_min": rim_offset_min, "rim_offset_max": rim_offset_max,
            "cb": cb, "cb_min": cb_min, "cb_max": cb_max, "fd": fd,
            "region": normalize_regions(region), "mode": mode,
            "limit": limit, "offset": offset,
        }
        data = await api.get("/v2/by_rim/search/", params)
        total = data["meta"]["count"]
        items = [map_car_search_row(item) for item in data["data"]]
        return paginated_response(items, total, offset, limit)

    @mcp.tool(annotations=SEARCH_ANNOTATIONS, tags={"search", "user-initiated"})
    async def ws_search_by_tire(
        section_width: Annotated[int, Field(ge=115, le=365, description="Tire section width in mm (e.g. 225)")],
        aspect_ratio: Annotated[int, Field(ge=25, le=95, description="Tire aspect ratio (e.g. 55)")],
        rim_diameter: Annotated[float, Field(ge=8, le=26, description="Rim diameter in inches (e.g. 17)")],
        speed_symbol: Annotated[
            list[_SpeedSymbol] | None,
            Field(description="Speed rating(s), OR-combined (e.g. ['V', 'W']). Counts in facets.speed_symbol."),
        ] = None,
        speed_symbol_min: Annotated[
            _SpeedSymbol | None, Field(description="Minimum speed rating (e.g. 'V' = V or faster)")
        ] = None,
        speed_symbol_max: Annotated[_SpeedSymbol | None, Field(description="Maximum speed rating")] = None,
        load_index: Annotated[
            list[int] | None,
            Field(description="Load index(es), OR-combined (e.g. [91, 94]). Counts in facets.load_index."),
        ] = None,
        load_index_min: Annotated[
            int | None, Field(ge=0, le=200, description="Minimum load index (e.g. 91)")
        ] = None,
        load_index_max: Annotated[int | None, Field(ge=0, le=200, description="Maximum load index")] = None,
        fitment: Annotated[
            Literal["square", "staggered"] | None,
            Field(description="square = same size all around, staggered = rear differs from front"),
        ] = None,
        region: Annotated[
            list[str] | None,
            Field(description="Region slug(s) (e.g. ['usdm'] or ['eudm', 'audm'])."),
        ] = None,
        mode: Annotated[Literal["both", "front_only", "rear_only"] | None, Field(description="Axle mode")] = None,
        limit: Annotated[int, Field(ge=1, le=50, description="Results per page")] = DEFAULT_LIMIT,
        offset: Annotated[int, Field(ge=0, description="Pagination offset")] = 0,
    ) -> dict:
        """Find vehicles compatible with a given tire size (metric).

        The response includes 'facets' (per-value car counts for speed_symbol,
        load_index, region, fitment — use them to offer refinements) and
        'summary' (feature counts like runflat/winter + physical tire data).
        Echo a facet value back as a filter to drill down.

        IMPORTANT: This is a Search method — only call when a user explicitly
        requests a tire compatibility search. Do not call in autonomous loops.

        This tool accepts metric sizes only. For high-flotation (LT) tires
        with inch-based sizing (e.g. 31x10.50R15), use ws_search_by_hf_tire.
        """
        params = {
            "section_width": section_width, "aspect_ratio": aspect_ratio,
            "rim_diameter": rim_diameter,
            "speed_symbol": speed_symbol, "speed_symbol_min": speed_symbol_min,
            "speed_symbol_max": speed_symbol_max,
            "load_index": load_index, "load_index_min": load_index_min,
            "load_index_max": load_index_max, "fitment": fitment,
            "region": normalize_regions(region), "mode": mode,
            "limit": limit, "offset": offset,
        }
        data = await api.get("/v2/by_tire/search/", params)
        total = data["meta"]["count"]
        items = [map_car_search_row(item) for item in data["data"]]
        result = paginated_response(items, total, offset, limit)
        if data["meta"].get("summary"):
            result["summary"] = data["meta"]["summary"]
        facets = _compact_facets(data["meta"])
        if facets:
            result["facets"] = facets
        return result

    @mcp.tool(annotations=SEARCH_ANNOTATIONS, tags={"search", "user-initiated"})
    async def ws_search_by_hf_tire(
        overall_diameter: Annotated[
            float, Field(ge=27, le=38, description="Overall tire diameter in inches (e.g. 31 for 31x10.50R15)")
        ],
        section_width: Annotated[
            float, Field(ge=4.5, le=14, description="Tire section width in inches (e.g. 10.5)")
        ],
        rim_diameter: Annotated[float, Field(ge=8, le=26, description="Rim diameter in inches (e.g. 15)")],
        region: Annotated[
            list[str] | None,
            Field(description="Region slug(s) (e.g. ['usdm'] or ['eudm', 'audm'])."),
        ] = None,
        mode: Annotated[Literal["both", "front_only", "rear_only"] | None, Field(description="Axle mode")] = None,
        limit: Annotated[int, Field(ge=1, le=50, description="Results per page")] = DEFAULT_LIMIT,
        offset: Annotated[int, Field(ge=0, description="Pagination offset")] = 0,
    ) -> dict:
        """Find vehicles compatible with a high-flotation (LT) tire size.

        HF tires use inch-based sizing like 31x10.50R15: overall diameter x
        section width R rim diameter, all in inches. Common on trucks, SUVs,
        and offroad vehicles. For metric sizes (e.g. 225/45R17) use
        ws_search_by_tire instead.

        IMPORTANT: This is a Search method — only call when a user explicitly
        requests a tire compatibility search. Do not call in autonomous loops.
        """
        params = {
            "overall_diameter": overall_diameter, "section_width": section_width,
            "rim_diameter": rim_diameter,
            "region": normalize_regions(region), "mode": mode,
            "limit": limit, "offset": offset,
        }
        data = await api.get("/v2/by_hf_tire/search/", params)
        total = data["meta"]["count"]
        items = [map_car_search_row(item) for item in data["data"]]
        return paginated_response(items, total, offset, limit)

    @mcp.tool(annotations=SEARCH_ANNOTATIONS, tags={"search", "user-initiated"})
    async def ws_check_hf_tire_fitment_for_vehicle(
        make: Annotated[str, Field(description="Make slug (e.g. 'chevrolet'). Use ws_list_makes to find valid slugs.")],
        model: Annotated[str, Field(description="Model slug (e.g. 'blazer'). Use ws_list_models to find valid slugs.")],
        overall_diameter: Annotated[
            float, Field(ge=27, le=38, description="Overall tire diameter in inches (e.g. 31 for 31x10.50R15)")
        ],
        section_width: Annotated[
            float, Field(ge=4.5, le=14, description="Tire section width in inches (e.g. 10.5)")
        ],
        rim_diameter: Annotated[float, Field(ge=8, le=26, description="Rim diameter in inches (e.g. 15)")],
        year: Annotated[
            int | None,
            Field(ge=1950, le=2027, description="Model year — filters to modifications in production that year"),
        ] = None,
        region: Annotated[
            list[str] | None,
            Field(description="Region slug(s) (e.g. ['usdm'] or ['eudm', 'audm'])."),
        ] = None,
        mode: Annotated[Literal["both", "front_only", "rear_only"] | None, Field(description="Axle mode")] = None,
        limit: Annotated[int, Field(ge=1, le=50, description="Results per page")] = DEFAULT_LIMIT,
        offset: Annotated[int, Field(ge=0, description="Pagination offset")] = 0,
    ) -> dict:
        """Check whether a high-flotation (LT) tire size fits a specific vehicle.

        Answers "do 31x10.50R15 tires fit my 2000 Chevy Blazer?" in one call:
        returns the vehicle's modifications (trims) where this HF tire size
        appears as a documented fitment. An EMPTY result means no documented
        fitment for that combination. Inch-based HF sizes only — for metric
        sizes use ws_check_tire_fitment_for_vehicle.

        The API has no year parameter, so 'year' is filtered MCP-side against
        each modification's production range (start_year/end_year); each row
        echoes its range so near-misses can be explained. Each row carries
        engine {fuel, capacity, hp} and a powertrain summary (field vocabulary
        in ws_list_modifications).

        IMPORTANT: This is a Search method — only call when a user explicitly
        requests a fitment check. Do not call in autonomous loops.
        """
        params = {
            "make": normalize_slug(make), "model": normalize_slug(model),
            "overall_diameter": overall_diameter, "section_width": section_width,
            "rim_diameter": rim_diameter,
            "region": normalize_regions(region), "mode": mode,
        }
        return await _fitment_check("/v2/by_hf_tire/search/modifications/", params, year, limit, offset)

    @mcp.tool(annotations=SEARCH_ANNOTATIONS, tags={"search", "user-initiated"})
    async def ws_check_rim_fitment_for_vehicle(
        make: Annotated[str, Field(description="Make slug (e.g. 'honda'). Use ws_list_makes to find valid slugs.")],
        model: Annotated[str, Field(description="Model slug (e.g. 'civic'). Use ws_list_models to find valid slugs.")],
        bolt_pattern: Annotated[str, Field(description="Bolt pattern of the rim (e.g. '5x114.3')")],
        rim_diameter: Annotated[float, Field(ge=8, le=26, description="Rim diameter in inches (e.g. 17)")],
        rim_width: Annotated[float, Field(ge=2, le=14, description="Rim width in inches (e.g. 7)")],
        rim_offset: Annotated[int | None, Field(ge=-150, le=150, description="Rim offset ET in mm (e.g. 40)")] = None,
        cb: Annotated[float | None, Field(ge=52.1, le=225, description="Centre bore in mm (e.g. 64.1)")] = None,
        year: Annotated[
            int | None,
            Field(ge=1950, le=2027, description="Model year — filters to modifications in production that year"),
        ] = None,
        region: Annotated[
            list[str] | None,
            Field(description="Region slug(s) (e.g. ['usdm'] or ['eudm', 'audm'])."),
        ] = None,
        mode: Annotated[Literal["both", "front_only", "rear_only"] | None, Field(description="Axle mode")] = None,
        limit: Annotated[int, Field(ge=1, le=50, description="Results per page")] = DEFAULT_LIMIT,
        offset: Annotated[int, Field(ge=0, description="Pagination offset")] = 0,
    ) -> dict:
        """Check whether specific rims fit a specific vehicle (make + model, optionally year).

        Answers "will 5x114.3 17x7 ET40 rims fit my 2020 Honda Civic?" in one
        call: returns the vehicle's modifications (trims) where this rim appears
        as a documented fitment. An EMPTY result means no documented fitment for
        that combination — the rim is likely incompatible or undocumented.

        The API has no year parameter, so 'year' is filtered MCP-side against
        each modification's production range (start_year/end_year); each row
        echoes its range so near-misses can be explained. Each row carries
        engine {fuel, capacity, hp} and a powertrain summary (field vocabulary
        in ws_list_modifications).

        Prefer this over ws_search_by_rim + ws_search_by_vehicle comparison when the
        user names a specific vehicle.

        IMPORTANT: This is a Search method — only call when a user explicitly
        requests a fitment check. Do not call in autonomous loops.
        """
        params = {
            "make": normalize_slug(make), "model": normalize_slug(model),
            "bolt_pattern": bolt_pattern, "rim_diameter": rim_diameter,
            "rim_width": rim_width, "rim_offset": rim_offset, "cb": cb,
            "region": normalize_regions(region), "mode": mode,
        }
        return await _fitment_check("/v2/by_rim/search/modifications/", params, year, limit, offset)

    @mcp.tool(annotations=SEARCH_ANNOTATIONS, tags={"search", "user-initiated"})
    async def ws_check_tire_fitment_for_vehicle(
        make: Annotated[str, Field(description="Make slug (e.g. 'honda'). Use ws_list_makes to find valid slugs.")],
        model: Annotated[str, Field(description="Model slug (e.g. 'civic'). Use ws_list_models to find valid slugs.")],
        section_width: Annotated[int, Field(ge=115, le=365, description="Tire section width in mm (e.g. 225)")],
        aspect_ratio: Annotated[int, Field(ge=25, le=95, description="Tire aspect ratio (e.g. 45)")],
        rim_diameter: Annotated[float, Field(ge=8, le=26, description="Rim diameter in inches (e.g. 17)")],
        year: Annotated[
            int | None,
            Field(ge=1950, le=2027, description="Model year — filters to modifications in production that year"),
        ] = None,
        region: Annotated[
            list[str] | None,
            Field(description="Region slug(s) (e.g. ['usdm'] or ['eudm', 'audm'])."),
        ] = None,
        mode: Annotated[Literal["both", "front_only", "rear_only"] | None, Field(description="Axle mode")] = None,
        limit: Annotated[int, Field(ge=1, le=50, description="Results per page")] = DEFAULT_LIMIT,
        offset: Annotated[int, Field(ge=0, description="Pagination offset")] = 0,
    ) -> dict:
        """Check whether a specific tire size fits a specific vehicle (make + model, optionally year).

        Answers "do 225/45R17 tires fit my 2020 Honda Civic?" in one call:
        returns the vehicle's modifications (trims) where this tire size appears
        as a documented fitment. An EMPTY result means no documented fitment for
        that combination. Metric sizes only.

        The API has no year parameter, so 'year' is filtered MCP-side against
        each modification's production range (start_year/end_year); each row
        echoes its range so near-misses can be explained. Each row carries
        engine {fuel, capacity, hp} and a powertrain summary (field vocabulary
        in ws_list_modifications).

        Prefer this over ws_search_by_tire + ws_search_by_vehicle comparison when the
        user names a specific vehicle.

        IMPORTANT: This is a Search method — only call when a user explicitly
        requests a fitment check. Do not call in autonomous loops.
        """
        params = {
            "make": normalize_slug(make), "model": normalize_slug(model),
            "section_width": section_width, "aspect_ratio": aspect_ratio,
            "rim_diameter": rim_diameter,
            "region": normalize_regions(region), "mode": mode,
        }
        return await _fitment_check("/v2/by_tire/search/modifications/", params, year, limit, offset)

    @mcp.tool(annotations=SEARCH_ANNOTATIONS, tags={"search"})
    async def ws_calculate_upsteps(
        rim_diameter: Annotated[
            float,
            Field(
                ge=10, le=30,
                description="OE rim diameter in inches — a catalog diameter (10, 12-26 incl. 16.5/17.5/19.5/22.5, "
                "28, 30); other values are a 400 that lists the valid ones.",
            ),
        ],
        rim_width: Annotated[float, Field(ge=2, le=13, description="OE rim width in inches (e.g. 7.5)")],
        rim_offset: Annotated[float, Field(ge=-50, le=150, description="OE rim offset (ET) in mm")],
        section_width: Annotated[
            int,
            Field(
                ge=95, le=525,
                description="OE tire nominal section width in mm; must end in 5 (ISO 4000-1, e.g. 235). "
                "The size must exist in the metric tire catalog for that rim diameter.",
            ),
        ],
        aspect_ratio: Annotated[
            int,
            Field(
                ge=20, le=95,
                description="OE tire nominal aspect ratio, %; a multiple of 5 (82 for legacy 82-series sizes).",
            ),
        ],
        steps_min: Annotated[
            int | None,
            Field(
                ge=-3, le=0,
                description="Lowest rim diameter step below OE, 1-inch steps (default 0 = OE only downwards). "
                "E.g. -1 with an 18-inch OE starts the range at 17 inches.",
            ),
        ] = None,
        steps_max: Annotated[
            int | None,
            Field(
                ge=0, le=3,
                description="Highest rim diameter step above OE, 1-inch steps (default 2). "
                "Defaults are independent: steps_min=-1 alone means -1..+2.",
            ),
        ] = None,
        steps: Annotated[
            int | None,
            Field(
                ge=-3, le=3,
                description="DEPRECATED — use steps_min/steps_max. steps=n (n>0) = steps_max=n; "
                "steps=-n = steps_min=-n and steps_max=0; steps=0 = OE diameter only. "
                "Cannot be combined with steps_min/steps_max.",
            ),
        ] = None,
        s_max: Annotated[
            int | None,
            Field(
                ge=0, le=25,
                description="Max relative difference of the design section width from OE, % (default 10)",
            ),
        ] = None,
        do_max: Annotated[
            int | None,
            Field(
                ge=0, le=15,
                description="Max relative difference of the overall diameter from OE, % (default 5). "
                "Use 2-3 to keep the speedometer accurate.",
            ),
        ] = None,
        limit: Annotated[int, Field(ge=1, le=MAX_ITEMS, description="Options per page (default 50)")] = MAX_ITEMS,
        offset: Annotated[int, Field(ge=0, description="Pagination offset into the option list")] = 0,
    ) -> dict:
        """Calculate plus/minus sizing candidates for an OE wheel/tire combo.

        Given the OE rim and tire, enumerates rim diameters from steps_min to
        steps_max around OE (e.g. steps_min=-1, steps_max=2 with an 18-inch OE
        covers 17-20 inches in one call; the OE diameter is always included)
        and returns the tire/rim combinations whose design section width and
        overall diameter stay within s_max / do_max of OE. Tighten do_max for
        "without changing the overall diameter" requests.

        Each option carries step = rim diameter minus OE diameter in whole
        inches (0 = OE diameter; 17.5 counts as 17). Exactly one option has
        is_oe=true (step 0) — it echoes the requested OE combo.
        by_diameter lists every enumerated diameter in order, including those
        with count 0, as {"17": {"step": -1, "count": 12}, ...} — use it to
        build -1 / OE / +1 tabs. by_rim counts options per rim designation.
        Both summarise the WHOLE candidate list; total counts tire-rim
        combinations. The option rows are paginated MCP-side (limit/offset,
        API order: by diameter, then rim width) — a wide range with loose
        tolerances can exceed 300 options, so page through has_more.

        This is a geometric calculator only: it does not check load or speed
        ratings, brake/arch clearance, staggered setups or high-flotation
        sizes. Can be called freely without user initiation.
        """
        if steps is not None and (steps_min is not None or steps_max is not None):
            raise ToolError(
                "Use either steps_min/steps_max or the deprecated steps, not both. "
                "steps=n equals steps_max=n; steps=-n equals steps_min=-n with steps_max=0."
            )
        params = {
            "rim_diameter": rim_diameter, "rim_width": rim_width,
            "rim_offset": rim_offset, "section_width": section_width,
            "aspect_ratio": aspect_ratio,
            "steps_min": steps_min, "steps_max": steps_max, "steps": steps,
            "s_max": s_max, "do_max": do_max,
        }
        data = await api.get("/v2/upsteps/", params)
        meta = data["meta"]
        options = [
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
                "step": opt.get("step"),
                "difference": opt.get("difference", {}),
            }
            for opt in data["data"]
        ]
        result = paginated_response(options[offset : offset + limit], meta["count"], offset, limit)
        result["by_diameter"] = meta.get("by_diameter", {})
        result["by_rim"] = meta.get("by_rim", {})
        return result
