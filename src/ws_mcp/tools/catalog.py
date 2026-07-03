"""Catalog tools — vehicle lookup (makes, models, years, generations, modifications)."""

from __future__ import annotations

from typing import Annotated

from fastmcp import FastMCP
from pydantic import Field

from ws_mcp.client import api
from ws_mcp.slugify import normalize_regions, normalize_slug
from ws_mcp.tools._annotations import CATALOG_ANNOTATIONS


def register(mcp: FastMCP):
    """Register catalog tools with the MCP server."""

    @mcp.tool(annotations=CATALOG_ANNOTATIONS, tags={"catalog"})
    async def ws_list_makes(
        year: Annotated[int | None, Field(description="Filter by year (e.g. 2024)")] = None,
        region: Annotated[
            list[str] | None,
            Field(description="Region slug(s) (e.g. ['usdm', 'jdm']). Filter makes sold in these regions."),
        ] = None,
        brands: Annotated[
            list[str] | None,
            Field(description="Only these make slugs (e.g. ['toyota', 'nissan']). For curated storefronts."),
        ] = None,
        brands_exclude: Annotated[
            list[str] | None,
            Field(description="Exclude these make slugs (e.g. ['geely', 'great-wall'])."),
        ] = None,
        lang: Annotated[
            str | None,
            Field(description="Translate names (e.g. 'ru'). name_en keeps the English original."),
        ] = None,
    ) -> dict:
        """List all vehicle manufacturers (makes).

        Returns slugs and names for all car brands in the database.

        Common starting point for vehicle fitment lookups, but not the only one —
        ws_list_years can also be called first (without params) to start from year.

        After getting a make slug, use ws_list_models to find models.
        """
        params = {
            "year": year, "region": normalize_regions(region),
            "brands": ",".join(normalize_slug(b) for b in brands) if brands else None,
            "brands_exclude": ",".join(normalize_slug(b) for b in brands_exclude) if brands_exclude else None,
            "lang": lang,
        }
        data = await api.get("/v2/makes/", params)
        return {
            "total": data["meta"]["count"],
            "makes": [
                {
                    "slug": m["slug"],
                    "name": m["name"],
                    **({"name_en": m.get("name_en")} if lang else {}),
                    "regions": m.get("regions", []),
                }
                for m in data["data"]
            ],
        }

    @mcp.tool(annotations=CATALOG_ANNOTATIONS, tags={"catalog"})
    async def ws_list_models(
        make: Annotated[str, Field(description="Make slug (e.g. 'toyota'). Use ws_list_makes to find valid slugs.")],
        year: Annotated[int | None, Field(description="Filter by year")] = None,
        region: Annotated[
            list[str] | None,
            Field(description="Region slug(s) (e.g. ['usdm']). Filter models sold in these regions."),
        ] = None,
        lang: Annotated[
            str | None,
            Field(description="Translate names (e.g. 'ru'). name_en keeps the English original."),
        ] = None,
    ) -> dict:
        """List models for a given make.

        Returns model slugs, names, and production year ranges.

        Can be filtered by year to narrow results (e.g. "which Toyota models existed in 2020?").

        After getting a model slug, use ws_list_years or ws_list_generations next.
        """
        params = {
            "make": normalize_slug(make), "year": year,
            "region": normalize_regions(region), "lang": lang,
        }
        data = await api.get("/v2/models/", params)
        return {
            "total": data["meta"]["count"],
            "models": [
                {
                    "slug": m["slug"],
                    "name": m["name"],
                    **({"name_en": m.get("name_en")} if lang else {}),
                    "year_ranges": m.get("year_ranges", []),
                    "regions": m.get("regions", []),
                }
                for m in data["data"]
            ],
        }

    @mcp.tool(annotations=CATALOG_ANNOTATIONS, tags={"catalog"})
    async def ws_list_years(
        make: Annotated[str | None, Field(description="Make slug")] = None,
        model: Annotated[str | None, Field(description="Model slug")] = None,
        region: Annotated[
            list[str] | None,
            Field(description="Region slug(s) (e.g. ['usdm']). Filter years available in these regions."),
        ] = None,
    ) -> dict:
        """List available years, optionally filtered by make and model.

        Can be called without params to get all years globally — this makes it
        an alternative starting point for navigation (Scenario 3: years first).
        Can also be called with make only to get years for that brand (Scenario 2).

        After getting a year, use ws_list_modifications to get trims.
        """
        params = {
            "make": normalize_slug(make) if make else None,
            "model": normalize_slug(model) if model else None,
            "region": normalize_regions(region),
        }
        data = await api.get("/v2/years/", params)
        return {
            "total": data["meta"]["count"],
            "years": [y["slug"] for y in data["data"]],
        }

    @mcp.tool(annotations=CATALOG_ANNOTATIONS, tags={"catalog"})
    async def ws_list_generations(
        make: Annotated[str, Field(description="Make slug")],
        model: Annotated[str, Field(description="Model slug")],
        year: Annotated[int | None, Field(description="Filter by year")] = None,
        region: Annotated[
            list[str] | None,
            Field(description="Region slug(s) (e.g. ['eudm']). Filter generations sold in these regions."),
        ] = None,
    ) -> dict:
        """List generations for a make/model.

        Returns generation slugs, names, platform codes, and production spans.
        Alternative to ws_list_years for models with many generations (e.g. BMW 3 Series).
        After getting a generation, use ws_list_modifications with the generation slug.
        """
        params = {
            "make": normalize_slug(make), "model": normalize_slug(model),
            "year": year, "region": normalize_regions(region),
        }
        data = await api.get("/v2/generations/", params)
        return {
            "total": data["meta"]["count"],
            "generations": [
                {
                    "slug": g["slug"],
                    "name": g["name"],
                    "platform": g.get("platform", ""),
                    "start": g["start"],
                    "end": g["end"],
                    "year_ranges": g.get("year_ranges", []),
                    "bodies": g.get("bodies", []),
                    "regions": g.get("regions", []),
                    "years": g.get("years", []),
                }
                for g in data["data"]
            ],
        }

    @mcp.tool(annotations=CATALOG_ANNOTATIONS, tags={"catalog"})
    async def ws_list_modifications(
        make: Annotated[str, Field(description="Make slug")],
        model: Annotated[str, Field(description="Model slug")],
        year: Annotated[int | None, Field(description="Model year")] = None,
        generation: Annotated[str | None, Field(description="Generation slug (alternative to year)")] = None,
        region: Annotated[
            list[str] | None,
            Field(
                description="Region slug(s) (e.g. ['usdm'] or ['eudm', 'audm']). "
                "Multiple regions give a more comprehensive view."
            ),
        ] = None,
        fuel: Annotated[
            str | None,
            Field(description="Fuel type filter (e.g. 'diesel', 'electric', 'hybrid', 'petrol')"),
        ] = None,
        trim: Annotated[
            str | None,
            Field(description="Fuzzy engine/trim name search (e.g. '2.0T', 'V6')"),
        ] = None,
        trim_level: Annotated[
            str | None,
            Field(description="Case-insensitive trim level (e.g. 'EX-L', 'Touring', 'Sport')"),
        ] = None,
        horsepower: Annotated[
            float | None,
            Field(ge=0, le=2000, description="Horsepower (±2.7 hp band, e.g. 150)"),
        ] = None,
        horsepower_min: Annotated[
            float | None, Field(ge=0, le=2000, description="Minimum horsepower (e.g. 300)")
        ] = None,
        horsepower_max: Annotated[
            float | None, Field(ge=0, le=2000, description="Maximum horsepower")
        ] = None,
        lang: Annotated[
            str | None,
            Field(description="Translate names (e.g. 'ru'). name_en keeps the English original."),
        ] = None,
    ) -> dict:
        """List modifications (trims) for a specific vehicle.

        Returns trim names, engine specs, and production years.
        One of year or generation is required.
        Filter by power via horsepower (exact ±2.7 hp) or horsepower_min/max
        (e.g. "trims over 300 hp" → horsepower_min=300).
        After getting a modification slug, use ws_search_by_vehicle for fitment data.
        """
        params = {
            "make": normalize_slug(make),
            "model": normalize_slug(model),
            "year": year,
            "generation": normalize_slug(generation) if generation else None,
            "region": normalize_regions(region),
            "fuel": fuel,
            "trim": trim,
            "trim_level": trim_level,
            "horsepower": horsepower,
            "horsepower_min": horsepower_min,
            "horsepower_max": horsepower_max,
            "lang": lang,
        }
        data = await api.get("/v2/modifications/", params)
        return {
            "total": data["meta"]["count"],
            "modifications": [
                {
                    "slug": m["slug"],
                    "name": m["name"],
                    "trim": m.get("trim", ""),
                    "body": m.get("body"),
                    "start_year": m.get("start_year"),
                    "end_year": m.get("end_year"),
                    "engine": m.get("engine"),
                    "regions": m.get("regions", []),
                    "trim_levels": m.get("trim_levels", []),
                    "trim_attributes": m.get("trim_attributes", []),
                    "trim_body_types": m.get("trim_body_types", []),
                }
                for m in data["data"]
            ],
        }

    @mcp.tool(annotations=CATALOG_ANNOTATIONS, tags={"catalog"})
    async def ws_list_regions() -> dict:
        """List all market regions where vehicles are sold.

        Returns region slugs and display names (e.g. usdm=USA, eudm=Europe, jdm=Japan).
        Use region slugs to filter results in other tools.
        """
        data = await api.get("/v2/regions/")
        return {
            "total": data["meta"]["count"],
            "regions": [
                {"slug": r["slug"], "name": r["display"], "abbr": r["abbr"]}
                for r in data["data"]
            ],
        }
