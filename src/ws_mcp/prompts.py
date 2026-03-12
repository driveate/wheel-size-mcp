"""MCP prompts for common wheel fitment workflows."""

from __future__ import annotations

from fastmcp import FastMCP


def register(mcp: FastMCP):
    """Register workflow prompts with the MCP server."""

    @mcp.prompt()
    def vehicle_fitment_lookup(vehicle_description: str) -> str:
        """Guide through a complete vehicle fitment lookup.

        Supports 4 navigation flows depending on what info the user provides.
        All flows end at list_modifications -> search_by_vehicle.
        """
        return f"""Look up wheel and tire fitment for: {vehicle_description}

Pick the best navigation flow based on what info the user provided.
ALL slug params are lowercase-hyphenated — NEVER guess, always call list_* first.

## Flow 1: Make → Model → Year (default — user names a vehicle)
1. list_makes() → find make slug
2. list_models(make) → find model slug
3. list_years(make, model) → find year
4. list_modifications(make, model, year) → find modification slug
5. search_by_vehicle(make, model, year, modification=<slug>)

## Flow 2: Make → Year → Model (user knows brand + year, not model)
1. list_makes() → find make slug
2. list_years(make) → find year
3. list_models(make, year) → find model slug
4. list_modifications(make, model, year) → find modification slug
5. search_by_vehicle(make, model, year, modification=<slug>)

## Flow 3: Year → Make → Model (year-first — common for tire shops)
1. list_years() → confirm year exists
2. list_makes(year) → find make slug
3. list_models(make, year) → find model slug
4. list_modifications(make, model, year) → find modification slug
5. search_by_vehicle(make, model, year, modification=<slug>)

## Flow 4: Make → Model → Generation (long-running models like BMW 3 Series)
1. list_makes() → find make slug
2. list_models(make) → find model slug
3. list_generations(make, model) → find generation slug
4. list_modifications(make, model, generation=<slug>) → find modification
5. search_by_vehicle(make, model, generation=<slug>, modification=<slug>)

## Tips
- If the user says a specific year, use Flow 1 (most common).
- If the user says just a make + year, use Flow 2.
- For models with many generations (BMW 3 Series, Toyota Corolla), prefer
  Flow 4 — generation is more precise than year alone.
- All flows pass through list_modifications before search_by_vehicle.
  The modification slug ensures accurate fitment for the exact trim.
- search_by_vehicle REQUIRES TWO conditions:
  1. Either 'year' OR 'generation' (to identify the vehicle)
  2. Either 'modification' OR 'region' (to narrow fitment results)
- Common region slugs: 'usdm' (USA), 'eudm' (Europe), 'jdm' (Japan),
  'cdm' (Canada), 'chdm' (China), 'audm' (Oceania). Full list: list_regions()
- Most tools accept multiple regions for broader results (e.g. ['eudm','audm']).
  EXCEPTION: search_by_vehicle accepts only ONE region.
- Common multi-region combos: Canada=['cdm','usdm'],
  Australia=['audm','eudm'], Russia=['russia','eudm','usdm','jdm'],
  Israel=['medm','eudm']

Present the results clearly: rim size, tire size, bolt pattern, offset, \
and tire pressure."""

    @mcp.prompt()
    def rim_compatibility_check(
        bolt_pattern: str,
        rim_diameter: str,
        rim_width: str,
        rim_offset: str,
    ) -> str:
        """Check what vehicles are compatible with a specific rim.

        Uses metadata + classified flow for accurate geometric fitment.
        """
        spec = f"{bolt_pattern} {rim_diameter}x{rim_width} ET{rim_offset}"
        return f"""Check vehicle compatibility for this rim: {spec}

Follow this workflow:

1. Call get_spec_metadata(
     bolt_pattern='{bolt_pattern}', rim_diameter={rim_diameter},
     rim_width={rim_width}, rim_offset={rim_offset}
   ) to understand how common this spec is and get recommended tolerances.
2. Review the hints — they tell you about offset percentile, common bolt
   patterns, and suggested tolerance values.
3. Call find_vehicles_for_rim(
     bolt_pattern='{bolt_pattern}', rim_diameter={rim_diameter},
     rim_width={rim_width}, rim_offset={rim_offset}
   ) to get compatible vehicles with geometric fitment data.
   If the hints suggested fs_poke/bs_push values, use those.
4. For any interesting generation, drill down with
   find_vehicle_modifications_for_rim to see per-trim fitment deltas.

Present results as a compatibility list with fitment confidence \
(based on frontspace/backspace deltas)."""

    @mcp.prompt()
    def product_card_generation(
        bolt_pattern: str,
        rim_diameter: str,
        rim_width: str,
        rim_offset: str,
        section_width: str | None = None,
        aspect_ratio: str | None = None,
    ) -> str:
        """Generate an e-commerce product card for a wheel or package.

        Uses classified endpoints for accurate geometric fitment filtering.
        """
        spec = f"{bolt_pattern} {rim_diameter}x{rim_width} ET{rim_offset}"
        if section_width and aspect_ratio:
            tire = f"{section_width}/{aspect_ratio}R{rim_diameter}"
            spec += f" with {tire}"

        steps = f"""Generate an e-commerce product card for: {spec}

Follow this workflow:

1. Call get_spec_metadata with all available params to get geometry,
   population stats, and hints.
"""
        if section_width and aspect_ratio:
            steps += (
                f"2. Call find_vehicles_for_package(\n"
                f"     bolt_pattern='{bolt_pattern}',\n"
                f"     rim_diameter={rim_diameter},\n"
                f"     rim_width={rim_width},\n"
                f"     rim_offset={rim_offset},\n"
                f"     section_width={section_width},\n"
                f"     aspect_ratio={aspect_ratio}\n"
                f"   ) for compatible vehicles.\n"
            )
        else:
            steps += (
                f"2. Call find_vehicles_for_rim(\n"
                f"     bolt_pattern='{bolt_pattern}',\n"
                f"     rim_diameter={rim_diameter},\n"
                f"     rim_width={rim_width},\n"
                f"     rim_offset={rim_offset}\n"
                f"   ) for compatible vehicles.\n"
                f"3. Call find_tires_for_rim with the same rim params\n"
                f"   to get compatible tire sizes.\n"
            )

        steps += """
Format the output as a product card with:
- Wheel specifications (diameter, width, offset, bolt pattern, geometry)
- Compatible vehicles grouped by make (with year ranges)
- Compatible tire sizes (if applicable)
- Any fitment notes from the metadata hints"""

        return steps
