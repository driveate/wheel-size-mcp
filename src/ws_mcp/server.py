"""MCP server entry point."""

from fastmcp import FastMCP

from ws_mcp import prompts
from ws_mcp.tools import catalog, classified, search, utility

mcp = FastMCP(
    "wheel-size-api",
    instructions="""\
Wheel Fitment API — vehicle wheel and tire compatibility data from wheel-size.com.

## WORKFLOW — Vehicle Fitment Lookup (4 navigation flows)

All flows end at list_modifications → search_by_vehicle.

**Flow 1 — Make → Model → Year** (default):
  list_makes → list_models(make) → list_years(make, model)
  → list_modifications(make, model, year) → search_by_vehicle

**Flow 2 — Make → Year → Model** (user knows brand + year):
  list_makes → list_years(make) → list_models(make, year)
  → list_modifications(make, model, year) → search_by_vehicle

**Flow 3 — Year → Make → Model** (year-first, common for tire shops):
  list_years → list_makes(year) → list_models(make, year)
  → list_modifications(make, model, year) → search_by_vehicle

**Flow 4 — Make → Model → Generation** (long-running models):
  list_makes → list_models(make) → list_generations(make, model)
  → list_modifications(make, model, generation) → search_by_vehicle

## WORKFLOW — Reverse Fitment (by rim/tire)
1. get_spec_metadata(...) → understand if this spec is common/unusual
2. find_vehicles_for_rim/tire/package(...) → vehicles fitting this spec
3. find_vehicle_modifications_for_rim(make, model, generation, ...) → drill into trims

## CRITICAL RULES
- ALL slug params (make, model, generation) are lowercase-hyphenated.
  NEVER guess — always call list_* first.
  Examples: 'bmw' not 'BMW', '3-series' not '3 Series', 'land-rover' not 'Land Rover'
- ALL flows pass through list_modifications before search_by_vehicle.
  The modification slug ensures accurate fitment for the exact vehicle trim.
- search_by_vehicle REQUIRES TWO conditions:
  1. Either 'year' OR 'generation' (to identify the vehicle)
  2. Either 'modification' OR 'region' (to narrow fitment results)
- Common region slugs: 'usdm' (USA), 'eudm' (Europe), 'jdm' (Japan),
  'cdm' (Canada), 'chdm' (China), 'audm' (Oceania). Full list: list_regions()
- Most tools accept multiple regions for broader coverage (e.g. ['eudm', 'audm']).
  EXCEPTION: search_by_vehicle accepts only ONE region.
- Common multi-region combos: Canada=['cdm','usdm'], Australia=['audm','eudm'],
  Russia=['russia','eudm','usdm','jdm'], Israel=['medm','eudm']
- Catalog tools (list_*) and utility tools: call freely, no restrictions
- Search tools (search_by_*): user-initiated only per API Terms of Service
- Classified tools (find_*): for e-commerce product cards, call freely
- search_by_rim vs find_vehicles_for_rim:
  search_by_rim = direct 1:1 wheel pair matching (exact OEM/documented fitments)
  find_vehicles_for_rim = geometric backspace calculations (physics-based, broader results)
  Use search_by_rim for "does this exact spec exist as OEM?";
  use find_vehicles_for_rim for "will this rim physically fit?"
""",
)

# Register tool modules
catalog.register(mcp)
search.register(mcp)
classified.register(mcp)
utility.register(mcp)

# Register workflow prompts
prompts.register(mcp)


@mcp.resource("config://status")
async def server_status():
    """Server configuration status."""
    from ws_mcp.client import API_BASE_URL, API_KEY

    return {
        "api_base_url": API_BASE_URL,
        "api_key_configured": bool(API_KEY),
        "version": "0.1.0",
    }


def main():
    """Run the MCP server (stdio transport)."""
    mcp.run()


if __name__ == "__main__":
    main()
