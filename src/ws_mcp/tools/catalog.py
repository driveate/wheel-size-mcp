"""Catalog tools — vehicle lookup (makes, models, years, generations, modifications)."""

from __future__ import annotations

from typing import Annotated

from fastmcp import FastMCP
from pydantic import Field

from ws_mcp.client import api
from ws_mcp.response import map_powertrain_summary
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
            Field(
                description=(
                    "Fuel code — one of: biodiesel_blend, cng, diesel, e100, electric, ethanol_blend, "
                    "flex_fuel, h2, hybrid, lpg, petrol, petrol_cng, petrol_lpg. One value matches the legacy "
                    "engine.fuel OR powertrain.primary_fuel OR powertrain.secondary_fuel (e.g. 'lpg' returns "
                    "dedicated-LPG and petrol/LPG bi-fuel cars alike). Old spellings such as 'natural-gas', "
                    "'flex-fuel' or 'e85' are still accepted; any other value is a 400 error. "
                    "A real fuel code read from powertrain.primary_fuel / secondary_fuel can be passed straight "
                    "back here; the absence words not_applicable, not_reported and unknown are not fuel codes "
                    "and are rejected."
                )
            ),
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
            Field(
                ge=0, le=2000,
                description=(
                    "Horsepower, ±2.7 hp band (e.g. 150). Matches the headline engine.power figure, whose "
                    "source depends on the electrification level — not always the system total, not always "
                    "the combustion engine."
                ),
            ),
        ] = None,
        horsepower_min: Annotated[
            float | None,
            Field(ge=0, le=2000, description="Minimum horsepower (e.g. 300). Same headline figure as horsepower."),
        ] = None,
        horsepower_max: Annotated[
            float | None,
            Field(ge=0, le=2000, description="Maximum horsepower. Same headline figure as horsepower."),
        ] = None,
        lang: Annotated[
            str | None,
            Field(description="Translate names (e.g. 'ru'). name_en keeps the English original."),
        ] = None,
    ) -> dict:
        """List modifications (trims) for a specific vehicle.

        Returns trim names, engine and powertrain specs, and production years.
        One of year or generation is required.
        Filter by power via horsepower (exact ±2.7 hp) or horsepower_min/max
        (e.g. "trims over 300 hp" → horsepower_min=300).
        After getting a modification slug, use ws_search_by_vehicle for fitment data.

        Each row carries two sibling blocks:
        - engine: legacy {fuel, capacity, type, power, code}. engine.power is the
          headline figure whose source depends on the electrification level:
          the combustion engine for combustion-only cars and mild hybrids;
          system power (else sum of motors, else engine) for full and plug-in
          hybrids; sum of motors (else engine) for range-extenders; system
          power (else sum of motors) for BEV/FCEV. engine.fuel is a display string (renamed
          without notice, e.g. 'Natural gas' → 'CNG'); group on powertrain fuel
          codes instead.
        - powertrain: combustion_engine, electrification_level, primary_fuel and
          secondary_fuel (fuel codes — a real code can be passed back as the
          fuel filter; the absence words cannot),
          engine_power_hp, system_power_hp, engine_power_secondary_hp, and
          motors [{axle, hp, code}]. The full block with kW/PS/hp and fuel
          titles is returned by ws_search_by_vehicle.

        Powertrain semantics:
        - engine_power_hp = the combustion engine alone on its primary fuel,
          excluding any electric motor. This is what most other vehicle-data
          providers publish as "power"; use it to reconcile hybrids against
          other datasets. On bi-fuel vehicles it may still be the higher of the
          engine's two ratings rather than the primary-fuel one (splitting them
          into engine_power_secondary is editorial work in progress).
        - system_power_hp = manufacturer-declared total of the whole powertrain.
          A distinct quantity only on full hybrids, plug-in hybrids and EVs with
          a motor on each axle; normally null on a single-motor EV, a mild
          hybrid, a range-extender and a pure combustion vehicle. NEVER
          reconstruct it by adding engine_power and motors — the declared total
          is normally lower than their sum.
        - engine_power_secondary_hp = the same engine's rating on its secondary
          fuel (bi-fuel / flex-fuel only). Not a second engine; never add it.
        - motors = one entry per driven axle. 'front' also holds an aggregated
          figure with no front/rear split, or a mild hybrid's starter-generator.
        - electrification_level: mild_hybrid, full_hybrid, phev, erev, bev, fcev,
          or not_applicable (combustion-only), not_reported, unknown.

        Absence words in enums and fuel codes are data, not errors:
        not_applicable = cannot apply to this vehicle (a BEV has no engine, a
        single-fuel car has no secondary fuel) — final. not_reported = applies
        but not recorded yet — may fill in later. unknown = neither
        electrification tier nor fuel recorded. So a null engine_power_hp means
        "no combustion engine" when combustion_engine is not_applicable and
        "not yet recorded" when it is present; motors: [] on an electrified
        vehicle means motor data not entered yet; a null
        engine_power_secondary_hp on a bi-fuel car means the second rating is
        not recorded yet, not that the engine has a single rating.
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
                    "powertrain": map_powertrain_summary(m.get("powertrain")),
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
