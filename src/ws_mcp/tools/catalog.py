"""Catalog tools — vehicle lookup (makes, models, years, generations, modifications)."""

from __future__ import annotations

from typing import Annotated

from fastmcp import FastMCP
from pydantic import Field

from ws_mcp.client import api
from ws_mcp.response import paginated_response


def register(mcp: FastMCP):
    """Register catalog tools with the MCP server."""

    @mcp.tool()
    async def list_makes(
        year: Annotated[int | None, Field(description="Filter by year (e.g. 2024)")] = None,
    ) -> dict:
        """List all vehicle manufacturers (makes).

        Returns slugs and names for all car brands in the database.
        This is the starting point for vehicle fitment lookups.
        After getting a make slug, use list_models to find models.
        """
        params = {"year": year}
        data = await api.get("/v2/makes/", params)
        return {
            "total": data["meta"]["count"],
            "makes": [
                {"slug": m["slug"], "name": m["name"]}
                for m in data["data"]
            ],
        }

    @mcp.tool()
    async def list_models(
        make: Annotated[str, Field(description="Make slug (e.g. 'toyota'). Use list_makes to find valid slugs.")],
        year: Annotated[int | None, Field(description="Filter by year")] = None,
    ) -> dict:
        """List models for a given make.

        Returns model slugs, names, and production year ranges.
        After getting a model slug, use list_years or list_generations next.
        """
        params = {"make": make, "year": year}
        data = await api.get("/v2/models/", params)
        return {
            "total": data["meta"]["count"],
            "models": [
                {"slug": m["slug"], "name": m["name"], "year_ranges": m.get("year_ranges", [])}
                for m in data["data"]
            ],
        }

    @mcp.tool()
    async def list_years(
        make: Annotated[str | None, Field(description="Make slug")] = None,
        model: Annotated[str | None, Field(description="Model slug")] = None,
    ) -> dict:
        """List available years, optionally filtered by make and model.

        Can be called without params to get all years, or with make/model to narrow down.
        After getting a year, use list_modifications to get trims.
        """
        params = {"make": make, "model": model}
        data = await api.get("/v2/years/", params)
        return {
            "total": data["meta"]["count"],
            "years": [y["slug"] for y in data["data"]],
        }

    @mcp.tool()
    async def list_generations(
        make: Annotated[str, Field(description="Make slug")],
        model: Annotated[str, Field(description="Model slug")],
        year: Annotated[int | None, Field(description="Filter by year")] = None,
    ) -> dict:
        """List generations for a make/model.

        Returns generation slugs, names, platform codes, and production spans.
        Alternative to list_years for models with many generations (e.g. BMW 3 Series).
        After getting a generation, use list_modifications with the generation slug.
        """
        params = {"make": make, "model": model, "year": year}
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
                }
                for g in data["data"]
            ],
        }

    @mcp.tool()
    async def list_modifications(
        make: Annotated[str, Field(description="Make slug")],
        model: Annotated[str, Field(description="Model slug")],
        year: Annotated[int | None, Field(description="Model year")] = None,
        generation: Annotated[str | None, Field(description="Generation slug (alternative to year)")] = None,
        region: Annotated[str | None, Field(description="Region slug (e.g. 'usdm'). Use list_regions for valid values.")] = None,
    ) -> dict:
        """List modifications (trims) for a specific vehicle.

        Returns trim names, engine specs, and production years.
        One of year or generation is required.
        After getting a modification slug, use search_by_vehicle for fitment data.
        """
        params = {"make": make, "model": model, "year": year, "generation": generation, "region": region}
        data = await api.get("/v2/modifications/", params)
        return {
            "total": data["meta"]["count"],
            "modifications": [
                {
                    "slug": m["slug"],
                    "name": m["name"],
                    "trim": m.get("trim", ""),
                    "start_year": m.get("start_year"),
                    "end_year": m.get("end_year"),
                    "engine": m.get("engine"),
                    "regions": m.get("regions", []),
                }
                for m in data["data"]
            ],
        }

    @mcp.tool()
    async def list_regions() -> dict:
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
