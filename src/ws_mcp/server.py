"""MCP server entry point."""

from fastmcp import FastMCP

from ws_mcp import prompts
from ws_mcp.tools import catalog, classified, search, utility

mcp = FastMCP(
    "wheel-size-api",
    instructions="""\
Wheel Fitment API — vehicle wheel and tire compatibility data from wheel-size.com.

## WORKFLOW — Vehicle Fitment Lookup (4 navigation flows)

All flows end at ws_list_modifications → ws_search_by_vehicle.

**Flow 1 — Make → Model → Year** (default):
  ws_list_makes → ws_list_models(make) → ws_list_years(make, model)
  → ws_list_modifications(make, model, year) → ws_search_by_vehicle

**Flow 2 — Make → Year → Model** (user knows brand + year):
  ws_list_makes → ws_list_years(make) → ws_list_models(make, year)
  → ws_list_modifications(make, model, year) → ws_search_by_vehicle

**Flow 3 — Year → Make → Model** (year-first, common for tire shops):
  ws_list_years → ws_list_makes(year) → ws_list_models(make, year)
  → ws_list_modifications(make, model, year) → ws_search_by_vehicle

**Flow 4 — Make → Model → Generation** (long-running models):
  ws_list_makes → ws_list_models(make) → ws_list_generations(make, model)
  → ws_list_modifications(make, model, generation) → ws_search_by_vehicle

## WORKFLOW — Direct Fitment Check ("will X fit my car?")
When the user names a SPECIFIC vehicle and a rim/tire spec, answer in ONE call:
  ws_check_rim_fitment_for_vehicle(make, model, bolt_pattern, rim_diameter, rim_width, year?)
  ws_check_tire_fitment_for_vehicle(make, model, section_width, aspect_ratio, rim_diameter, year?)
  ws_check_hf_tire_fitment_for_vehicle(make, model, overall_diameter, section_width, rim_diameter, year?)
An EMPTY result = no documented fitment. Rows echo start_year/end_year so
near-misses can be explained. Prefer these over fetching OEM specs and
comparing manually.

## WORKFLOW — Reverse Fitment (by rim/tire)
1. ws_get_spec_metadata(...) → understand if this spec is common/unusual
2. ws_find_vehicles_for_rim/tire/package(...) → vehicles fitting this spec
   (sort='fitment' puts closest matches first; diameter_range widens ±N inch)
3. ws_find_vehicle_modifications_for_rim/package(make, model, generation, ...) → drill into trims

## TIRE SIZE SYSTEMS
- Metric (225/45R17): ws_search_by_tire, ws_check_tire_fitment_for_vehicle
- High-flotation inches (31x10.50R15 — trucks/offroad): ws_search_by_hf_tire,
  ws_check_hf_tire_fitment_for_vehicle
- ws_search_by_tire responses include 'facets' (car counts per speed_symbol /
  load_index / region / fitment) — use them to answer follow-ups and offer
  refinements without extra calls, and 'summary' (runflat/winter counts etc.)

## CRITICAL RULES
- ALL slug params (make, model, generation) are lowercase-hyphenated.
  NEVER guess — always call ws_list_* first.
  Examples: 'bmw' not 'BMW', '3-series' not '3 Series', 'land-rover' not 'Land Rover'
- ALL flows pass through ws_list_modifications before ws_search_by_vehicle.
  The modification slug ensures accurate fitment for the exact vehicle trim.
- ws_search_by_vehicle REQUIRES:
  1. Either 'modification' OR 'region' (to narrow fitment results)
  2. Either 'year' OR 'generation' (to identify the vehicle) —
     not required when 'modification' is provided
- Common region slugs: 'usdm' (USA), 'eudm' (Europe), 'jdm' (Japan),
  'cdm' (Canada), 'chdm' (China), 'audm' (Oceania). Full list: ws_list_regions()
- Most tools accept multiple regions for broader coverage (e.g. ['eudm', 'audm']).
  EXCEPTION: ws_search_by_vehicle accepts only ONE region.
- Common multi-region combos: Canada=['cdm','usdm'], Australia=['audm','eudm'],
  Russia=['russia','eudm','usdm','jdm'], Israel=['medm','eudm']
- Catalog tools (ws_list_*) and utility tools: call freely, no restrictions
- Search tools (ws_search_by_*, ws_check_*_fitment_for_vehicle): user-initiated only
  per API Terms of Service (ws_calculate_upsteps is exempt)
- Classified tools (ws_find_*): for e-commerce product cards, call freely
- ws_search_by_rim vs ws_find_vehicles_for_rim:
  ws_search_by_rim = direct 1:1 wheel pair matching (exact OEM/documented fitments)
  ws_find_vehicles_for_rim = geometric backspace calculations (physics-based, broader results)
  Use ws_search_by_rim for "does this exact spec exist as OEM?";
  use ws_find_vehicles_for_rim for "will this rim physically fit?"
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
    from importlib.metadata import version

    from ws_mcp.client import API_BASE_URL, API_KEY

    return {
        "api_base_url": API_BASE_URL,
        "api_key_configured": bool(API_KEY),
        "version": version("wheel-size-mcp"),
    }


def main():
    """Run the MCP server (stdio transport)."""
    mcp.run()


if __name__ == "__main__":
    main()
