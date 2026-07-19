# wheel-size-mcp MCP Tools Inventory

21 tools grouped into 4 modules. Each tool wraps a single Wheel Fitment API endpoint (`/v2/...`), except `ws_get_spec_metadata` and `ws_check_*_fitment_for_vehicle`, which add MCP-side logic on top of the API response.

---

## Catalog (`tools/catalog.py`) — 6 tools

Navigation through the vehicle hierarchy. No restrictions — can be called freely.

### Navigation scenarios toward `ws_search_by_vehicle`

The catalog is not a linear chain but a flexible hierarchy. Different MCP clients need different selector orders. All 4 scenarios end the same way: `ws_list_modifications` → `ws_search_by_vehicle`.

```
Scenario 1 (basic):
  ws_list_makes → ws_list_models → ws_list_years → ws_list_modifications → ws_search_by_vehicle

Scenario 2 (year before model):
  ws_list_makes → ws_list_years(make) → ws_list_models(make, year) → ws_list_modifications → ws_search_by_vehicle

Scenario 3 (starting from year):
  ws_list_years → ws_list_makes(year) → ws_list_models(make, year) → ws_list_modifications → ws_search_by_vehicle

Scenario 4 (via generations):
  ws_list_makes → ws_list_models → ws_list_generations → ws_list_modifications(generation) → ws_search_by_vehicle
```

**Why the order differs:**
- Scenario 1 — classic: the user knows the make and model, picks a year
- Scenario 2 — "which Toyota models existed in 2020?": filters models by year
- Scenario 3 — "what was available in 2024?": starts from the year, then picks a make
- Scenario 4 — for models with a long history (BMW 3 Series): generation instead of year

**Key point**: `ws_list_years` accepts all parameters optionally (`make?`, `model?`), so it can be called at any step. `ws_list_generations` requires `make` + `model`, so it always comes after them.

---

### `ws_list_makes`

**API**: `GET /v2/makes/`

**Docstring**:
> List all vehicle manufacturers (makes).
> Returns slugs and names for all car brands in the database.
>
> Common starting point for vehicle fitment lookups, but not the only one —
> ws_list_years can also be called first (without params) to start from year.
>
> After getting a make slug, use ws_list_models to find models.

**Parameters**:
| Parameter | Type | Description |
|----------|-----|----------|
| `year` | `int?` | Filter by year (e.g. 2024) |
| `region` | `list[str]?` | Region slug(s) (e.g. ['usdm', 'jdm']). Filter makes sold in these regions. |
| `brands` | `list[str]?` | Only these make slugs (e.g. ['toyota', 'nissan']). For curated storefronts. |
| `brands_exclude` | `list[str]?` | Exclude these make slugs (e.g. ['geely', 'great-wall']). |
| `lang` | `str?` | Translate names (e.g. 'ru'). name_en keeps the English original. |

---

### `ws_list_models`

**API**: `GET /v2/models/`

**Docstring**:
> List models for a given make.
> Returns model slugs, names, and production year ranges.
>
> Can be filtered by year to narrow results (e.g. "which Toyota models existed in 2020?").
>
> After getting a model slug, use ws_list_years or ws_list_generations next.

**Parameters**:
| Parameter | Type | Description |
|----------|-----|----------|
| `make` | `str` | Make slug (e.g. 'toyota'). Use ws_list_makes to find valid slugs. |
| `year` | `int?` | Filter by year |
| `region` | `list[str]?` | Region slug(s) (e.g. ['usdm']). Filter models sold in these regions. |
| `lang` | `str?` | Translate names (e.g. 'ru'). name_en keeps the English original. |

---

### `ws_list_years`

**API**: `GET /v2/years/`

**Docstring**:
> List available years, optionally filtered by make and model.
>
> Can be called without params to get all years globally — this makes it
> an alternative starting point for navigation (Scenario 3: years first).
> Can also be called with make only to get years for that brand (Scenario 2).
>
> After getting a year, use ws_list_modifications to get trims.

**Parameters**:
| Parameter | Type | Description |
|----------|-----|----------|
| `make` | `str?` | Make slug |
| `model` | `str?` | Model slug |
| `region` | `list[str]?` | Region slug(s) (e.g. ['usdm']). Filter years available in these regions. |

---

### `ws_list_generations`

**API**: `GET /v2/generations/`

**Docstring**:
> List generations for a make/model.
> Returns generation slugs, names, platform codes, and production spans.
> Alternative to ws_list_years for models with many generations (e.g. BMW 3 Series).
> After getting a generation, use ws_list_modifications with the generation slug.

**Parameters**:
| Parameter | Type | Description |
|----------|-----|----------|
| `make` | `str` | Make slug |
| `model` | `str` | Model slug |
| `year` | `int?` | Filter by year |
| `region` | `list[str]?` | Region slug(s) (e.g. ['eudm']). Filter generations sold in these regions. |

---

### `ws_list_modifications`

**API**: `GET /v2/modifications/`

**Docstring**:
> List modifications (trims) for a specific vehicle.
>
> Returns trim names, engine specs, and production years.
> One of year or generation is required.
> Filter by power via horsepower (exact ±2.7 hp) or horsepower_min/max
> (e.g. "trims over 300 hp" → horsepower_min=300).
> After getting a modification slug, use ws_search_by_vehicle for fitment data.

**Parameters**:
| Parameter | Type | Description |
|----------|-----|----------|
| `make` | `str` | Make slug |
| `model` | `str` | Model slug |
| `year` | `int?` | Model year |
| `generation` | `str?` | Generation slug (alternative to year) |
| `region` | `list[str]?` | Region slug(s) (e.g. ['usdm'] or ['eudm', 'audm']). Multiple regions give a more comprehensive view. |
| `fuel` | `str?` | Fuel type filter (e.g. 'diesel', 'electric', 'hybrid', 'petrol') |
| `trim` | `str?` | Fuzzy engine/trim name search (e.g. '2.0T', 'V6') |
| `trim_level` | `str?` | Case-insensitive trim level (e.g. 'EX-L', 'Touring', 'Sport') |
| `horsepower` | `float?` | Horsepower (±2.7 hp band, e.g. 150) |
| `horsepower_min` | `float?` | Minimum horsepower (e.g. 300) |
| `horsepower_max` | `float?` | Maximum horsepower |
| `lang` | `str?` | Translate names (e.g. 'ru'). name_en keeps the English original. |

---

### `ws_list_regions`

**API**: `GET /v2/regions/`

**Docstring**:
> List all market regions where vehicles are sold.
> Returns region slugs and display names (e.g. usdm=USA, eudm=Europe, jdm=Japan).
> Use region slugs to filter results in other tools.

**Parameters**: none

---

## Search (`tools/search.py`) — 8 tools

Fitment search. All except `ws_calculate_upsteps` are user-initiated only (API ToS) and must not be called in autonomous loops: **ws_search_by_vehicle, ws_search_by_rim, ws_search_by_tire, ws_search_by_hf_tire, ws_check_rim_fitment_for_vehicle, ws_check_tire_fitment_for_vehicle, ws_check_hf_tire_fitment_for_vehicle**.

---

### `ws_search_by_vehicle`

**API**: `GET /v2/search/by_model/`

**Docstring**:
> Get wheel and tire fitment data for a specific vehicle.
>
> REQUIRED parameter combination:
> 1. Either 'modification' OR 'region' (to narrow fitment results)
> 2. Either 'year' OR 'generation' (to identify the vehicle) —
>    not required when 'modification' is provided
>
> PREREQUISITES — you MUST have valid slugs before calling:
> - make: lowercase slug from ws_list_makes (e.g. 'toyota', 'land-rover')
> - model: lowercase slug from ws_list_models (e.g. 'camry', '3-series')
> - modification or region: from ws_list_modifications / ws_list_regions
> - year or generation: from ws_list_years / ws_list_generations
>   (skip when modification is provided)
> - NOTE: this endpoint accepts only ONE region (unlike other tools)
>
> Do NOT guess these values. Call the prerequisite tools first.
>
> Returns OEM and optional wheel/tire specs including rim diameter, width,
> offset, bolt pattern, tire sizes, and tire pressure.
> Each wheel has setup='symmetric' (same front/rear) or 'staggered' (different).
>
> IMPORTANT: This is a Search method — only call when a user explicitly
> requests fitment information. Do not call in autonomous loops.

**Parameters**:
| Parameter | Type | Description |
|----------|-----|----------|
| `make` | `str` | Make slug (e.g. 'toyota'). Use ws_list_makes to find valid slugs. |
| `model` | `str` | Model slug (e.g. 'camry'). Use ws_list_models to find valid slugs. |
| `year` | `int?` | Model year |
| `generation` | `str?` | Generation slug (alternative to year). From ws_list_generations. |
| `modification` | `str?` | Modification slug from ws_list_modifications. Alternative to region. |
| `region` | `str?` | Single region slug (e.g. 'usdm'). Only ONE region allowed here. |
| `detail_level` | `"concise" \| "full"` | 'concise' = key specs only, 'full' = all wheel/tire details |
| `lang` | `str?` | Translate make/model/region names (e.g. 'ru'). |
| `limit` | `int` | Results per page |
| `offset` | `int` | Pagination offset |

**In-code validation**: Raises `ToolError` if modification/region is missing, or if year/generation is missing while modification is not provided — with a hint about which tools to call.

---

### `ws_search_by_rim`

**API**: `GET /v2/by_rim/search/`

**Docstring**:
> Find vehicles compatible with given rim specs via direct 1:1 wheel pair matching.
>
> Uses a direct mapping of existing wheel pair data to vehicle specs —
> returns only vehicles where this exact rim (or close offset) appears
> in the database as an OEM or documented fitment. Does NOT calculate
> whether the rim would physically fit based on wheel housing geometry.
>
> Diameter and width accept either an exact value (rim_diameter,
> rim_width) or a min/max range pair — e.g. "18-19 inch, ET30-45" →
> rim_diameter_min=18, rim_diameter_max=19, rim_offset_min=30,
> rim_offset_max=45. One of exact or range is required per dimension.
>
> IMPORTANT: This is a Search method — only call when a user explicitly
> requests a rim compatibility search. Do not call in autonomous loops.
>
> For e-commerce product cards, use ws_find_vehicles_for_rim instead —
> it uses geometric backspace calculations for broader, physics-based matching.

**Parameters**:
| Parameter | Type | Description |
|----------|-----|----------|
| `bolt_pattern` | `str` | Bolt pattern (e.g. '5x114.3') |
| `rim_diameter` | `float?` | Exact rim diameter in inches (e.g. 18) |
| `rim_width` | `float?` | Exact rim width in inches (e.g. 8) |
| `rim_offset` | `int?` | Rim offset in mm |
| `rim_diameter_min` | `float?` | Range search: min diameter (use with _max) |
| `rim_diameter_max` | `float?` | Range search: max diameter |
| `rim_width_min` | `float?` | Range search: min width (use with _max) |
| `rim_width_max` | `float?` | Range search: max width |
| `rim_offset_min` | `int?` | Range search: min offset |
| `rim_offset_max` | `int?` | Range search: max offset |
| `cb` | `float?` | Centre bore in mm (e.g. 64.1) |
| `cb_min` | `float?` | Range search: min centre bore |
| `cb_max` | `float?` | Range search: max centre bore |
| `fd` | `float?` | Wheel fastener thread diameter in mm (e.g. 12 for M12) |
| `region` | `list[str]?` | Region slug(s) (e.g. ['usdm'] or ['eudm', 'audm']). |
| `mode` | `"both" \| "front_only" \| "rear_only"?` | Axle mode |
| `limit` | `int` | Results per page |
| `offset` | `int` | Pagination offset |

**In-code validation**: for each dimension (diameter/width required, offset/cb optional) — either an exact value or a complete min+max pair (not both at once, min ≤ max); otherwise `ToolError` with a hint.

---

### `ws_search_by_tire`

**API**: `GET /v2/by_tire/search/`

**Docstring**:
> Find vehicles compatible with a given tire size (metric).
>
> The response includes 'facets' (per-value car counts for speed_symbol,
> load_index, region, fitment — use them to offer refinements) and
> 'summary' (feature counts like runflat/winter + physical tire data).
> Echo a facet value back as a filter to drill down.
>
> IMPORTANT: This is a Search method — only call when a user explicitly
> requests a tire compatibility search. Do not call in autonomous loops.
>
> This tool accepts metric sizes only. For high-flotation (LT) tires
> with inch-based sizing (e.g. 31x10.50R15), use ws_search_by_hf_tire.

**Parameters**:
| Parameter | Type | Description |
|----------|-----|----------|
| `section_width` | `int` | Tire section width in mm (e.g. 225) |
| `aspect_ratio` | `int` | Tire aspect ratio (e.g. 55) |
| `rim_diameter` | `float` | Rim diameter in inches (e.g. 17) |
| `speed_symbol` | `list[str]?` | Speed rating(s), OR-combined (e.g. ['V', 'W']). Counts in facets.speed_symbol. |
| `speed_symbol_min` | `str?` | Minimum speed rating (e.g. 'V' = V or faster) |
| `speed_symbol_max` | `str?` | Maximum speed rating |
| `load_index` | `list[int]?` | Load index(es), OR-combined (e.g. [91, 94]). Counts in facets.load_index. |
| `load_index_min` | `int?` | Minimum load index (e.g. 91) |
| `load_index_max` | `int?` | Maximum load index |
| `fitment` | `"square" \| "staggered"?` | square = same size all around, staggered = rear differs from front |
| `region` | `list[str]?` | Region slug(s) (e.g. ['usdm'] or ['eudm', 'audm']). |
| `mode` | `"both" \| "front_only" \| "rear_only"?` | Axle mode |
| `limit` | `int` | Results per page |
| `offset` | `int` | Pagination offset |

**The response additionally contains** `facets` (vehicle counts by speed_symbol/load_index/region/fitment — a ready-made refinement menu; each facet's options are truncated to 50 entries with a `truncated` flag) and `summary` (runflat/winter/extra_load features + physical tire data).

---

### `ws_search_by_hf_tire`

**API**: `GET /v2/by_hf_tire/search/`

**Docstring**:
> Find vehicles compatible with a high-flotation (LT) tire size.
>
> HF tires use inch-based sizing like 31x10.50R15: overall diameter x
> section width R rim diameter, all in inches. Common on trucks, SUVs,
> and offroad vehicles. For metric sizes (e.g. 225/45R17) use
> ws_search_by_tire instead.
>
> IMPORTANT: This is a Search method — only call when a user explicitly
> requests a tire compatibility search. Do not call in autonomous loops.

**Parameters**:
| Parameter | Type | Description |
|----------|-----|----------|
| `overall_diameter` | `float` | Overall tire diameter in inches (e.g. 31 for 31x10.50R15) |
| `section_width` | `float` | Tire section width in inches (e.g. 10.5) |
| `rim_diameter` | `float` | Rim diameter in inches (e.g. 15) |
| `region` | `list[str]?` | Region slug(s) (e.g. ['usdm'] or ['eudm', 'audm']). |
| `mode` | `"both" \| "front_only" \| "rear_only"?` | Axle mode |
| `limit` | `int` | Results per page |
| `offset` | `int` | Pagination offset |

---

### `ws_check_hf_tire_fitment_for_vehicle` (composite)

**API**: `GET /v2/by_hf_tire/search/modifications/` + MCP-side year filtering

**Docstring**:
> Check whether a high-flotation (LT) tire size fits a specific vehicle.
>
> Answers "do 31x10.50R15 tires fit my 2000 Chevy Blazer?" in one call:
> returns the vehicle's modifications (trims) where this HF tire size
> appears as a documented fitment. An EMPTY result means no documented
> fitment for that combination. Inch-based HF sizes only — for metric
> sizes use ws_check_tire_fitment_for_vehicle.
>
> The API has no year parameter, so 'year' is filtered MCP-side against
> each modification's production range (start_year/end_year); each row
> echoes its range so near-misses can be explained.
>
> IMPORTANT: This is a Search method — only call when a user explicitly
> requests a fitment check. Do not call in autonomous loops.

**Parameters**:
| Parameter | Type | Description |
|----------|-----|----------|
| `make` | `str` | Make slug (e.g. 'chevrolet'). Use ws_list_makes to find valid slugs. |
| `model` | `str` | Model slug (e.g. 'blazer'). Use ws_list_models to find valid slugs. |
| `overall_diameter` | `float` | Overall tire diameter in inches (e.g. 31 for 31x10.50R15) |
| `section_width` | `float` | Tire section width in inches (e.g. 10.5) |
| `rim_diameter` | `float` | Rim diameter in inches (e.g. 15) |
| `year` | `int?` | Model year — filters to modifications in production that year |
| `region` | `list[str]?` | Region slug(s) (e.g. ['usdm'] or ['eudm', 'audm']). |
| `mode` | `"both" \| "front_only" \| "rear_only"?` | Axle mode |
| `limit` | `int` | Results per page |
| `offset` | `int` | Pagination offset |

**MCP-side logic**: the same year filtering as `ws_check_rim_fitment_for_vehicle`.

---

### `ws_check_rim_fitment_for_vehicle` (composite)

**API**: `GET /v2/by_rim/search/modifications/` + MCP-side year filtering

**Docstring**:
> Check whether specific rims fit a specific vehicle (make + model, optionally year).
>
> Answers "will 5x114.3 17x7 ET40 rims fit my 2020 Honda Civic?" in one
> call: returns the vehicle's modifications (trims) where this rim appears
> as a documented fitment. An EMPTY result means no documented fitment for
> that combination — the rim is likely incompatible or undocumented.
>
> The API has no year parameter, so 'year' is filtered MCP-side against
> each modification's production range (start_year/end_year); each row
> echoes its range so near-misses can be explained.
>
> Prefer this over ws_search_by_rim + ws_search_by_vehicle comparison when the
> user names a specific vehicle.
>
> IMPORTANT: This is a Search method — only call when a user explicitly
> requests a fitment check. Do not call in autonomous loops.

**Parameters**:
| Parameter | Type | Description |
|----------|-----|----------|
| `make` | `str` | Make slug (e.g. 'honda'). Use ws_list_makes to find valid slugs. |
| `model` | `str` | Model slug (e.g. 'civic'). Use ws_list_models to find valid slugs. |
| `bolt_pattern` | `str` | Bolt pattern of the rim (e.g. '5x114.3') |
| `rim_diameter` | `float` | Rim diameter in inches (e.g. 17) |
| `rim_width` | `float` | Rim width in inches (e.g. 7) |
| `rim_offset` | `int?` | Rim offset ET in mm (e.g. 40) |
| `cb` | `float?` | Centre bore in mm (e.g. 64.1) |
| `year` | `int?` | Model year — filters to modifications in production that year |
| `region` | `list[str]?` | Region slug(s) (e.g. ['usdm'] or ['eudm', 'audm']). |
| `mode` | `"both" \| "front_only" \| "rear_only"?` | Axle mode |
| `limit` | `int` | Results per page |
| `offset` | `int` | Pagination offset |

**MCP-side logic**: the API endpoint has no `year` parameter — filtering is done MCP-side against the modification's production range (`start_year`/`end_year`; open bounds pass). When `year` is given, rows are fetched in pages of 50 (200 max), filtered and paginated MCP-side; if the limit is exceeded, a `note` about incompleteness is added to the response.

---

### `ws_check_tire_fitment_for_vehicle` (composite)

**API**: `GET /v2/by_tire/search/modifications/` + MCP-side year filtering

**Docstring**:
> Check whether a specific tire size fits a specific vehicle (make + model, optionally year).
>
> Answers "do 225/45R17 tires fit my 2020 Honda Civic?" in one call:
> returns the vehicle's modifications (trims) where this tire size appears
> as a documented fitment. An EMPTY result means no documented fitment for
> that combination. Metric sizes only.
>
> The API has no year parameter, so 'year' is filtered MCP-side against
> each modification's production range (start_year/end_year); each row
> echoes its range so near-misses can be explained.
>
> Prefer this over ws_search_by_tire + ws_search_by_vehicle comparison when the
> user names a specific vehicle.
>
> IMPORTANT: This is a Search method — only call when a user explicitly
> requests a fitment check. Do not call in autonomous loops.

**Parameters**:
| Parameter | Type | Description |
|----------|-----|----------|
| `make` | `str` | Make slug (e.g. 'honda'). Use ws_list_makes to find valid slugs. |
| `model` | `str` | Model slug (e.g. 'civic'). Use ws_list_models to find valid slugs. |
| `section_width` | `int` | Tire section width in mm (e.g. 225) |
| `aspect_ratio` | `int` | Tire aspect ratio (e.g. 45) |
| `rim_diameter` | `float` | Rim diameter in inches (e.g. 17) |
| `year` | `int?` | Model year — filters to modifications in production that year |
| `region` | `list[str]?` | Region slug(s) (e.g. ['usdm'] or ['eudm', 'audm']). |
| `mode` | `"both" \| "front_only" \| "rear_only"?` | Axle mode |
| `limit` | `int` | Results per page |
| `offset` | `int` | Pagination offset |

**MCP-side logic**: the same year filtering as `ws_check_rim_fitment_for_vehicle`.

---

### `ws_calculate_upsteps`

**API**: `GET /v2/upsteps/`

**Docstring**:
> Calculate plus/minus sizing alternatives for a wheel/tire combo.
>
> Given OEM wheel specs, returns safe replacement sizes at different
> plus/minus levels (e.g. +1, +2 = larger rim with lower-profile tire).
> Tighten do_max for "without changing the overall diameter" requests.
>
> This is a calculator tool — can be called freely without user initiation.

**Parameters**:
| Parameter | Type | Description |
|----------|-----|----------|
| `rim_diameter` | `float` | OE rim diameter in inches |
| `rim_width` | `float` | OE rim width in inches |
| `rim_offset` | `int` | OE rim offset in mm |
| `section_width` | `int` | OE tire section width in mm |
| `aspect_ratio` | `int` | OE tire aspect ratio |
| `steps` | `int?` | Plus/minus steps (default +2) |
| `s_max` | `int?` | Max section width difference, % (default 10) |
| `do_max` | `int?` | Max overall diameter difference, % (default 5). Use 2-3 to keep speedo accurate. |

---

## Classified (`tools/classified.py`) — 6 tools

### Shared geometric parameters

All rim/package classified tools (except `ws_find_vehicles_for_tire`) accept a shared set of geometric filters — in the tool tables it is marked with the row "+ shared geometric parameters":

| Parameter | Type | Description |
|----------|-----|----------|
| `cb` | `float?` | Centre bore diameter in mm |
| `fd` | `float?` | Wheel fastener thread diameter in mm (e.g. 12 for M12) |
| `fs_poke` | `int?` | Frontspace poke tolerance in mm (default 2) |
| `bs_push` | `int?` | Backspace push tolerance in mm (default 2) |
| `rim_bst_from` | `int?` | Backspace tolerance lower bound in mm (default 2) |
| `rim_bst_to` | `int?` | Backspace tolerance upper bound in mm (default 2) |
| `od_tolerance` | `float?` | Overall diameter tolerance fraction (default 0.01) |
| `ow_tolerance` | `float?` | Overall width tolerance fraction (default 0) |
| `diameter_range` | `int?` | Widen rim diameter search ±N inches (0 = exact match) |
| `sort` | `"name" \| "fitment" \| "load"?` | Sort: name (A-Z), fitment (closest FS delta first), load (heaviest first) |

> Note (2026-06): sorting is passed via the **`sort`** parameter — previously the tools sent the name/fitment/load values in `ordering`, which the API rejected with VALIDATION_ERROR. The `region` parameter was removed from the drill-down tools: the endpoints silently ignore it (it is not in the spec).

E-commerce product card generation. Geometric 2D fitment (backspace/frontspace). User-initiated only (API ToS) — must not be called in autonomous loops or for bulk data generation.

---

### `ws_find_tires_for_rim`

**API**: `GET /v2/classified/by_rim/`

**Docstring**:
> Find compatible tire sizes for a given rim specification.
>
> Returns tire sizes (e.g. '245/70R17') with the number of vehicle
> generations that use each tire on this rim. Set diameter_range to
> also include tires for ±N inch rim diameters.
>
> Useful for tire product recommendations on wheel product pages.

**Parameters**:
| Parameter | Type | Description |
|----------|-----|----------|
| `bolt_pattern` | `str` | Bolt pattern (e.g. '5x114.3') |
| `rim_diameter` | `float` | Rim diameter in inches |
| `rim_width` | `float` | Rim width in inches |
| `rim_offset` | `float` | Rim offset in mm |
| *+ shared geometric parameters* | | see block above |
| `limit` | `int` | Results per page |
| `offset` | `int` | Pagination offset |

---

### `ws_find_vehicles_for_rim`

**API**: `GET /v2/classified/by_rim/search/`

**Docstring**:
> Find vehicle generations compatible with a given rim via geometric backspace calculations.
>
> Unlike ws_search_by_rim (which does direct 1:1 wheel pair matching),
> this endpoint uses advanced 2D geometric filtering based on
> frontspace/backspace calculations to determine physical fitment.
> This yields broader results — any vehicle where the rim physically
> fits the wheel housing, even if this exact spec isn't in the OEM database.
>
> Returns make/model/generation with fitment deltas (frontspace/backspace),
> load capacity, and OEM ratio ranges. Use sort='fitment' to put the
> closest matches first on product pages.
>
> Note: in some cases spacers or special bolts/nuts may be required.
> Always verify rims don't interfere with brake calipers or extend
> beyond the wheel arch.
>
> For e-commerce product pages: "This wheel fits: BMW X5, Audi Q7..."
> To drill into a specific generation, use ws_find_vehicle_modifications_for_rim.

**Parameters**:
| Parameter | Type | Description |
|----------|-----|----------|
| `bolt_pattern` | `str` | Bolt pattern (e.g. '5x114.3') |
| `rim_diameter` | `float` | Rim diameter in inches |
| `rim_width` | `float` | Rim width in inches |
| `rim_offset` | `float` | Rim offset in mm |
| *+ shared geometric parameters* | | see block above |
| `limit` | `int` | Results per page |
| `offset` | `int` | Pagination offset |

---

### `ws_find_vehicle_modifications_for_rim`

**API**: `GET /v2/classified/by_rim/search/modifications/`

**Docstring**:
> Drill down into individual trims for a generation from ws_find_vehicles_for_rim.
>
> PREREQUISITES — call ws_find_vehicles_for_rim first to get:
> - make, model, generation slugs (from the results)
> - Use the same rim parameters and tolerances as the parent search
>
> Returns per-vehicle rows with OEM wheel specs (rim, tire, frontspace,
> backspace) and fitment deltas vs the searched rim.

**Parameters**:
| Parameter | Type | Description |
|----------|-----|----------|
| `make` | `str` | Make slug from ws_find_vehicles_for_rim results |
| `model` | `str` | Model slug from ws_find_vehicles_for_rim results |
| `generation` | `str` | Generation slug from ws_find_vehicles_for_rim results |
| `bolt_pattern` | `str` | Bolt pattern (e.g. '5x114.3') |
| `rim_diameter` | `float` | Rim diameter in inches |
| `rim_width` | `float` | Rim width in inches |
| `rim_offset` | `float` | Rim offset in mm |
| *+ shared geometric parameters* | | see block above |
| `limit` | `int` | Results per page |
| `offset` | `int` | Pagination offset |

---

### `ws_find_vehicle_modifications_for_package`

**API**: `GET /v2/classified/by_package/search/modifications/`

**Docstring**:
> Drill down into individual trims for a generation from ws_find_vehicles_for_package.
>
> PREREQUISITES — call ws_find_vehicles_for_package first to get:
> - make, model, generation slugs (from the results)
> - Use the same rim AND tire parameters and tolerances as the parent search
>
> Returns per-vehicle rows with OEM wheel specs (rim, tire) and fitment
> deltas vs the searched rim + tire package. Completes the e-commerce
> chain: package search → generations → specific trims.

**Parameters**:
| Parameter | Type | Description |
|----------|-----|----------|
| `make` | `str` | Make slug from ws_find_vehicles_for_package results |
| `model` | `str` | Model slug from ws_find_vehicles_for_package results |
| `generation` | `str` | Generation slug from ws_find_vehicles_for_package results |
| `bolt_pattern` | `str` | Bolt pattern (e.g. '5x114.3') |
| `rim_diameter` | `float` | Rim diameter in inches |
| `rim_width` | `float` | Rim width in inches |
| `rim_offset` | `float` | Rim offset in mm |
| `section_width` | `int` | Tire section width in mm |
| `aspect_ratio` | `int` | Tire aspect ratio |
| *+ shared geometric parameters* | | see block above |
| `limit` | `int` | Results per page |
| `offset` | `int` | Pagination offset |

---

### `ws_find_vehicles_for_tire`

**API**: `GET /v2/classified/by_tire/search/`

**Docstring**:
> Find vehicle generations that use a specific tire size.
>
> Simplest classified search — matches tire dimensions only,
> no bolt pattern or backspace filtering.
>
> For e-commerce: "This tire fits: Honda Civic, Toyota Camry..."

**Parameters**:
| Parameter | Type | Description |
|----------|-----|----------|
| `section_width` | `int` | Tire section width in mm |
| `aspect_ratio` | `int` | Tire aspect ratio |
| `rim_diameter` | `float` | Rim diameter in inches |
| `limit` | `int` | Results per page |
| `offset` | `int` | Pagination offset |

---

### `ws_find_vehicles_for_package`

**API**: `GET /v2/classified/by_package/search/`

**Docstring**:
> Find vehicles compatible with a rim + tire package.
>
> Most precise classified search — considers both physical wheel
> fitment (backspace) and tire size compatibility simultaneously.
> Use sort='fitment' to put the closest matches first.
>
> For e-commerce combo/bundle product pages.
> To drill into a specific generation, use ws_find_vehicle_modifications_for_package.

**Parameters**:
| Parameter | Type | Description |
|----------|-----|----------|
| `bolt_pattern` | `str` | Bolt pattern (e.g. '5x114.3') |
| `rim_diameter` | `float` | Rim diameter in inches |
| `rim_width` | `float` | Rim width in inches |
| `rim_offset` | `float` | Rim offset in mm |
| `section_width` | `int` | Tire section width in mm |
| `aspect_ratio` | `int` | Tire aspect ratio |
| *+ shared geometric parameters* | | see block above |
| `limit` | `int` | Results per page |
| `offset` | `int` | Pagination offset |

---

## Utility (`tools/utility.py`) — 1 tool

---

### `ws_get_spec_metadata` (composite)

**API**: `GET /v2/spec/metadata/?hints=true` + MCP-side routing hint

**Docstring**:
> Get computed geometry, population stats, and hints for a wheel/tire spec.
>
> Auto-detects mode from parameters:
> - rim: rim_diameter + rim_width (optionally rim_offset)
> - tire: section_width [mm] + aspect_ratio + rim_diameter
> - hf_tire: overall_diameter + section_width [inches] + rim_diameter
> - package: rim + tire params combined
>
> Use before search or classified calls to understand whether a spec
> is common or unusual, what tolerances to use, and what to expect.
>
> This is a utility tool — can be called freely without user initiation.

**Parameters**:
| Parameter | Type | Description |
|----------|-----|----------|
| `rim_diameter` | `float?` | Rim diameter in inches (e.g. 18) |
| `rim_width` | `float?` | Rim width in inches (e.g. 8.0) |
| `rim_offset` | `float?` | Offset ET in mm (e.g. 45). Enables geometry. |
| `bolt_pattern` | `str?` | Bolt pattern (e.g. '5x114.3'). Narrows population stats. |
| `section_width` | `float?` | Tire section width. Metric tires: mm (95-405, e.g. 225). HF tires (when overall_diameter is set): inches (4.5-14, e.g. 12.5). |
| `aspect_ratio` | `int?` | Tire aspect ratio (e.g. 45) |
| `cb` | `float?` | Centre bore in mm (e.g. 71.6). Passed to suggested classified params. |
| `overall_diameter` | `float?` | Overall tire diameter in inches (e.g. 33). HF mode. |

**Hints** are generated server-side (the tool always calls the API with `hints=true`; `suggested_classified_params` is also computed server-side). They cover:
- Offset (ET) percentile within the given rim size
- Estimated match counts when widening tolerances
- Warning when backspace is close to the database minimum
- Top 3 bolt patterns
- Primary axle usage (front/rear) and stock fitment percentage
- Stagger pairs (what is most often mounted on the other axle)
- Rim/tire weight estimate
- Rim width to tire compatibility (for package mode)

**MCP-side logic (`_mcp_routing_hints`)** adds the one hint the API cannot generate because it references MCP tool names: when an offset search yields no matches at any tolerance, it recommends `ws_find_vehicles_for_rim` with the server-suggested `fs_poke`/`bs_push` values.

---

## Summary


| Module     | Tool count   | API endpoints  | Restrictions        |
| ---------- | ------------ | -------------- | ------------------- |
| Catalog    | 6            | 6              | None                |
| Search     | 8            | 8              | ToS (except upsteps)|
| Classified | 6            | 6              | None                |
| Utility    | 1            | 1              | None                |
| **Total**  | **21**       | **21**         | —                   |


**Simple tools (1:1 with API)**: 16
**Composite tools (API + MCP-side logic)**: 4 (`ws_get_spec_metadata`, `ws_check_rim_fitment_for_vehicle`, `ws_check_tire_fitment_for_vehicle`, `ws_check_hf_tire_fitment_for_vehicle`)
