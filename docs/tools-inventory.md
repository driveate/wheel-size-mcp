# Инвентарь MCP-тулов wheel-size-mcp

18 тулов, сгруппированных по 4 модулям. Каждый тул — обёртка над одним API-эндпоинтом Wheel Fitment API (`/v2/...`), кроме `get_spec_metadata` и `check_*_fitment_for_vehicle`, которые добавляют MCP-side логику поверх API-ответа.

---

## Catalog (`tools/catalog.py`) — 6 тулов

Навигация по иерархии автомобилей. Без ограничений — можно вызывать свободно.

### Сценарии навигации к `search_by_vehicle`

Каталог — не линейная цепочка, а гибкая иерархия. Разным MCP-клиентам нужен разный порядок селекторов. Все 4 сценария заканчиваются одинаково: `list_modifications` → `search_by_vehicle`.

```
Сценарий 1 (базовый):
  list_makes → list_models → list_years → list_modifications → search_by_vehicle

Сценарий 2 (год раньше модели):
  list_makes → list_years(make) → list_models(make, year) → list_modifications → search_by_vehicle

Сценарий 3 (начинаем с года):
  list_years → list_makes(year) → list_models(make, year) → list_modifications → search_by_vehicle

Сценарий 4 (через поколения):
  list_makes → list_models → list_generations → list_modifications(generation) → search_by_vehicle
```

**Почему разный порядок:**
- Сценарий 1 — классический: пользователь знает марку и модель, выбирает год
- Сценарий 2 — "какие модели Toyota были в 2020?": фильтрует модели по году
- Сценарий 3 — "что было в 2024?": начинает с года, потом выбирает марку
- Сценарий 4 — для моделей с долгой историей (BMW 3 Series): поколение вместо года

**Ключевое**: `list_years` принимает все параметры опционально (`make?`, `model?`), поэтому может быть вызван на любом шаге. `list_generations` требует `make` + `model`, поэтому всегда идёт после них.

---

### `list_makes`

**API**: `GET /v2/makes/`

**Docstring**:
> List all vehicle manufacturers (makes).
> Returns slugs and names for all car brands in the database.
>
> Common starting point for vehicle fitment lookups, but not the only one —
> list_years can also be called first (without params) to start from year.
>
> After getting a make slug, use list_models to find models.

**Параметры**:
| Параметр | Тип | Описание |
|----------|-----|----------|
| `year` | `int?` | Filter by year (e.g. 2024) |
| `region` | `list[str]?` | Region slug(s) (e.g. ['usdm', 'jdm']). Filter makes sold in these regions. |

---

### `list_models`

**API**: `GET /v2/models/`

**Docstring**:
> List models for a given make.
> Returns model slugs, names, and production year ranges.
>
> Can be filtered by year to narrow results (e.g. "which Toyota models existed in 2020?").
>
> After getting a model slug, use list_years or list_generations next.

**Параметры**:
| Параметр | Тип | Описание |
|----------|-----|----------|
| `make` | `str` | Make slug (e.g. 'toyota'). Use list_makes to find valid slugs. |
| `year` | `int?` | Filter by year |
| `region` | `list[str]?` | Region slug(s) (e.g. ['usdm']). Filter models sold in these regions. |

---

### `list_years`

**API**: `GET /v2/years/`

**Docstring**:
> List available years, optionally filtered by make and model.
>
> Can be called without params to get all years globally — this makes it
> an alternative starting point for navigation (Scenario 3: years first).
> Can also be called with make only to get years for that brand (Scenario 2).
>
> After getting a year, use list_modifications to get trims.

**Параметры**:
| Параметр | Тип | Описание |
|----------|-----|----------|
| `make` | `str?` | Make slug |
| `model` | `str?` | Model slug |
| `region` | `list[str]?` | Region slug(s) (e.g. ['usdm']). Filter years available in these regions. |

---

### `list_generations`

**API**: `GET /v2/generations/`

**Docstring**:
> List generations for a make/model.
> Returns generation slugs, names, platform codes, and production spans.
> Alternative to list_years for models with many generations (e.g. BMW 3 Series).
> After getting a generation, use list_modifications with the generation slug.

**Параметры**:
| Параметр | Тип | Описание |
|----------|-----|----------|
| `make` | `str` | Make slug |
| `model` | `str` | Model slug |
| `year` | `int?` | Filter by year |
| `region` | `list[str]?` | Region slug(s) (e.g. ['eudm']). Filter generations sold in these regions. |

---

### `list_modifications`

**API**: `GET /v2/modifications/`

**Docstring**:
> List modifications (trims) for a specific vehicle.
> Returns trim names, engine specs, and production years.
> One of year or generation is required.
> After getting a modification slug, use search_by_vehicle for fitment data.

**Параметры**:
| Параметр | Тип | Описание |
|----------|-----|----------|
| `make` | `str` | Make slug |
| `model` | `str` | Model slug |
| `year` | `int?` | Model year |
| `generation` | `str?` | Generation slug (alternative to year) |
| `region` | `list[str]?` | Region slug(s) (e.g. ['usdm'] or ['eudm', 'audm']). Multiple regions give a more comprehensive view. |
| `fuel` | `str?` | Fuel type filter (e.g. 'diesel', 'electric', 'hybrid', 'petrol') |
| `trim` | `str?` | Fuzzy engine/trim name search (e.g. '2.0T', 'V6') |
| `trim_level` | `str?` | Case-insensitive trim level (e.g. 'EX-L', 'Touring', 'Sport') |

---

### `list_regions`

**API**: `GET /v2/regions/`

**Docstring**:
> List all market regions where vehicles are sold.
> Returns region slugs and display names (e.g. usdm=USA, eudm=Europe, jdm=Japan).
> Use region slugs to filter results in other tools.

**Параметры**: нет

---

## Search (`tools/search.py`) — 6 тулов

Поиск фитмента. **search_by_vehicle, search_by_rim, search_by_tire, check_rim_fitment_for_vehicle, check_tire_fitment_for_vehicle** — только по запросу пользователя (API ToS), нельзя вызывать в автономных циклах. `calculate_upsteps` — без ограничений.

---

### `search_by_vehicle`

**API**: `GET /v2/search/by_model/`

**Docstring**:
> Get wheel and tire fitment data for a specific vehicle.
>
> REQUIRES TWO conditions:
> 1. Either 'year' OR 'generation' (to identify the vehicle)
> 2. Either 'modification' OR 'region' (to narrow fitment results)
>
> PREREQUISITES — you MUST have valid slugs before calling:
> - make: lowercase slug from list_makes (e.g. 'toyota', 'land-rover')
> - model: lowercase slug from list_models (e.g. 'camry', '3-series')
> - year or generation: from list_years / list_generations
> - modification or region: from list_modifications / list_regions
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

**Параметры**:
| Параметр | Тип | Описание |
|----------|-----|----------|
| `make` | `str` | Make slug (e.g. 'toyota'). Use list_makes to find valid slugs. |
| `model` | `str` | Model slug (e.g. 'camry'). Use list_models to find valid slugs. |
| `year` | `int?` | Model year (1950–2027) |
| `generation` | `str?` | Generation slug (alternative to year). From list_generations. |
| `modification` | `str?` | Modification slug from list_modifications. Alternative to region. |
| `region` | `str?` | Single region slug (e.g. 'usdm'). Only ONE region allowed here. |
| `detail_level` | `"concise" \| "full"` | 'concise' = key specs only, 'full' = all wheel/tire details (default: concise) |
| `limit` | `int` | Results per page (1–50, default 20) |
| `offset` | `int` | Pagination offset (default 0) |

**Валидация в коде**: Бросает `ToolError` если не указан year/generation или modification/region — с подсказкой какие тулы вызвать.

---

### `search_by_rim`

**API**: `GET /v2/by_rim/search/`

**Docstring**:
> Find vehicles compatible with given rim specs via direct 1:1 wheel pair matching.
>
> Uses a direct mapping of existing wheel pair data to vehicle specs —
> returns only vehicles where this exact rim (or close offset) appears
> in the database as an OEM or documented fitment. Does NOT calculate
> whether the rim would physically fit based on wheel housing geometry.
>
> Requires bolt_pattern, rim_diameter, and rim_width.
> Add rim_offset for more precise results.
>
> IMPORTANT: This is a Search method — only call when a user explicitly
> requests a rim compatibility search. Do not call in autonomous loops.
>
> For e-commerce product cards, use find_vehicles_for_rim instead —
> it uses geometric backspace calculations for broader, physics-based matching.

**Параметры**:
| Параметр | Тип | Описание |
|----------|-----|----------|
| `bolt_pattern` | `str` | Bolt pattern (e.g. '5x114.3') |
| `rim_diameter` | `float` | Rim diameter in inches (8–26) |
| `rim_width` | `float` | Rim width in inches (2–14) |
| `rim_offset` | `int?` | Rim offset in mm (-150–150) |
| `region` | `list[str]?` | Region slug(s) |
| `mode` | `"both" \| "front_only" \| "rear_only"?` | Axle mode |
| `limit` | `int` | Results per page (default 20) |
| `offset` | `int` | Pagination offset |

---

### `search_by_tire`

**API**: `GET /v2/by_tire/search/`

**Docstring**:
> Find vehicles compatible with a given tire size (metric).
>
> IMPORTANT: This is a Search method — only call when a user explicitly
> requests a tire compatibility search. Do not call in autonomous loops.
>
> This tool accepts metric sizes only. High-flotation (LT) tires with
> inch-based sizing (e.g. 33x12.5R15) are not supported here — use
> get_spec_metadata (HF mode) for spec information.

**Параметры**:
| Параметр | Тип | Описание |
|----------|-----|----------|
| `section_width` | `int` | Tire section width in mm (115–365, e.g. 225) |
| `aspect_ratio` | `int` | Tire aspect ratio (25–95, e.g. 55) |
| `rim_diameter` | `float` | Rim diameter in inches (8–26) |
| `region` | `list[str]?` | Region slug(s) |
| `mode` | `"both" \| "front_only" \| "rear_only"?` | Axle mode |
| `limit` | `int` | Results per page (default 20) |
| `offset` | `int` | Pagination offset |

---

### `check_rim_fitment_for_vehicle` (составной)

**API**: `GET /v2/by_rim/search/modifications/` + MCP-side фильтрация по году

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
> Prefer this over search_by_rim + search_by_vehicle comparison when the
> user names a specific vehicle.
>
> IMPORTANT: This is a Search method — only call when a user explicitly
> requests a fitment check. Do not call in autonomous loops.

**Параметры**:
| Параметр | Тип | Описание |
|----------|-----|----------|
| `make` | `str` | Make slug (e.g. 'honda') |
| `model` | `str` | Model slug (e.g. 'civic') |
| `bolt_pattern` | `str` | Bolt pattern of the rim (e.g. '5x114.3') |
| `rim_diameter` | `float` | Rim diameter in inches (8–26) |
| `rim_width` | `float` | Rim width in inches (2–14) |
| `rim_offset` | `int?` | Rim offset ET in mm (-150–150) |
| `cb` | `float?` | Centre bore in mm (52.1–225) |
| `year` | `int?` | Model year — MCP-side фильтр по start_year/end_year |
| `region` | `list[str]?` | Region slug(s) |
| `mode` | `"both" \| "front_only" \| "rear_only"?` | Axle mode |
| `limit` | `int` | Results per page (default 20) |
| `offset` | `int` | Pagination offset |

**MCP-side логика**: у API-эндпоинта нет параметра `year` — фильтрация выполняется на стороне MCP по диапазону выпуска модификации (`start_year`/`end_year`, открытые границы проходят). При заданном `year` строки выбираются страницами по 50 (максимум 200), фильтруются и пагинируются MCP-side; при превышении лимита в ответ добавляется `note` о неполноте.

---

### `check_tire_fitment_for_vehicle` (составной)

**API**: `GET /v2/by_tire/search/modifications/` + MCP-side фильтрация по году

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
> Prefer this over search_by_tire + search_by_vehicle comparison when the
> user names a specific vehicle.
>
> IMPORTANT: This is a Search method — only call when a user explicitly
> requests a fitment check. Do not call in autonomous loops.

**Параметры**:
| Параметр | Тип | Описание |
|----------|-----|----------|
| `make` | `str` | Make slug (e.g. 'honda') |
| `model` | `str` | Model slug (e.g. 'civic') |
| `section_width` | `int` | Tire section width in mm (115–365) |
| `aspect_ratio` | `int` | Tire aspect ratio (25–95) |
| `rim_diameter` | `float` | Rim diameter in inches (8–26) |
| `year` | `int?` | Model year — MCP-side фильтр по start_year/end_year |
| `region` | `list[str]?` | Region slug(s) |
| `mode` | `"both" \| "front_only" \| "rear_only"?` | Axle mode |
| `limit` | `int` | Results per page (default 20) |
| `offset` | `int` | Pagination offset |

**MCP-side логика**: та же year-фильтрация, что у `check_rim_fitment_for_vehicle`.

---

### `calculate_upsteps`

**API**: `GET /v2/upsteps/`

**Docstring**:
> Calculate plus/minus sizing alternatives for a wheel/tire combo.
>
> Given OEM wheel specs, returns safe replacement sizes at different
> plus/minus levels (e.g. +1, +2 = larger rim with lower-profile tire).
>
> This is a calculator tool — can be called freely without user initiation.

**Параметры**:
| Параметр | Тип | Описание |
|----------|-----|----------|
| `rim_diameter` | `float` | OE rim diameter in inches (8–26) |
| `rim_width` | `float` | OE rim width in inches (2–14) |
| `rim_offset` | `int` | OE rim offset in mm (-150–150) |
| `section_width` | `int` | OE tire section width in mm (115–365) |
| `aspect_ratio` | `int` | OE tire aspect ratio (25–95) |
| `steps` | `int?` | Plus/minus steps (-3–3, default +2) |

---

## Classified (`tools/classified.py`) — 5 тулов

Генерация e-commerce карточек товаров. Геометрический 2D-фитмент (backspace/frontspace). Без ограничений.

---

### `find_tires_for_rim`

**API**: `GET /v2/classified/by_rim/`

**Docstring**:
> Find compatible tire sizes for a given rim specification.
>
> Returns tire sizes (e.g. '245/70R17') with the number of vehicle
> generations that use each tire on this rim.
>
> Useful for tire product recommendations on wheel product pages.

**Параметры**:
| Параметр | Тип | Описание |
|----------|-----|----------|
| `bolt_pattern` | `str` | Bolt pattern (e.g. '5x114.3') |
| `rim_diameter` | `float` | Rim diameter in inches (8–26) |
| `rim_width` | `float` | Rim width in inches (2–14) |
| `rim_offset` | `float` | Rim offset in mm (-150–150) |
| `cb` | `float?` | Centre bore diameter in mm (52.1–225) |
| `limit` | `int` | Results per page (default 20) |
| `offset` | `int` | Pagination offset |

---

### `find_vehicles_for_rim`

**API**: `GET /v2/classified/by_rim/search/`

**Docstring**:
> Find vehicle generations compatible with a given rim via geometric backspace calculations.
>
> Unlike search_by_rim (which does direct 1:1 wheel pair matching),
> this endpoint uses advanced 2D geometric filtering based on
> frontspace/backspace calculations to determine physical fitment.
> This yields broader results — any vehicle where the rim physically
> fits the wheel housing, even if this exact spec isn't in the OEM database.
>
> Returns make/model/generation with fitment deltas (frontspace/backspace),
> load capacity, and OEM ratio ranges.
>
> Note: in some cases spacers or special bolts/nuts may be required.
> Always verify rims don't interfere with brake calipers or extend
> beyond the wheel arch.
>
> For e-commerce product pages: "This wheel fits: BMW X5, Audi Q7..."
> To drill into a specific generation, use find_vehicle_modifications_for_rim.

**Параметры**:
| Параметр | Тип | Описание |
|----------|-----|----------|
| `bolt_pattern` | `str` | Bolt pattern (e.g. '5x114.3') |
| `rim_diameter` | `float` | Rim diameter in inches (8–26) |
| `rim_width` | `float` | Rim width in inches (2–14) |
| `rim_offset` | `float` | Rim offset in mm (-150–150) |
| `cb` | `float?` | Centre bore diameter in mm (52.1–225) |
| `fs_poke` | `int?` | Frontspace poke tolerance in mm (0–150, default 2) |
| `bs_push` | `int?` | Backspace push tolerance in mm (0–150, default 2) |
| `rim_bst_from` | `int?` | Backspace tolerance lower bound in mm (1–8, default 2) |
| `rim_bst_to` | `int?` | Backspace tolerance upper bound in mm (1–8, default 2) |
| `od_tolerance` | `float?` | Overall diameter tolerance fraction (0–0.05, default 0.01) |
| `ow_tolerance` | `float?` | Overall width tolerance fraction (0–0.03, default 0) |
| `ordering` | `"name" \| "fitment" \| "load"?` | Sort: A-Z name, closest fitment delta, heaviest load |
| `limit` | `int` | Results per page (default 20) |
| `offset` | `int` | Pagination offset |

---

### `find_vehicle_modifications_for_rim`

**API**: `GET /v2/classified/by_rim/search/modifications/`

**Docstring**:
> Drill down into individual trims for a generation from find_vehicles_for_rim.
>
> PREREQUISITES — call find_vehicles_for_rim first to get:
> - make, model, generation slugs (from the results)
> - Use the same bolt_pattern, rim_diameter, rim_width, rim_offset
>
> Returns per-vehicle rows with OEM wheel specs (rim, tire, frontspace,
> backspace) and fitment deltas vs the searched rim.

**Параметры**:
| Параметр | Тип | Описание |
|----------|-----|----------|
| `make` | `str` | Make slug from find_vehicles_for_rim results |
| `model` | `str` | Model slug from find_vehicles_for_rim results |
| `generation` | `str` | Generation slug from find_vehicles_for_rim results |
| `bolt_pattern` | `str` | Bolt pattern (e.g. '5x114.3') |
| `rim_diameter` | `float` | Rim diameter in inches (8–26) |
| `rim_width` | `float` | Rim width in inches (2–14) |
| `rim_offset` | `float` | Rim offset in mm (-150–150) |
| `cb` | `float?` | Centre bore diameter in mm (52.1–225) |
| `region` | `list[str]?` | Region slug(s). Filter modifications by market region. |
| `limit` | `int` | Results per page (default 20) |
| `offset` | `int` | Pagination offset |

---

### `find_vehicles_for_tire`

**API**: `GET /v2/classified/by_tire/search/`

**Docstring**:
> Find vehicle generations that use a specific tire size.
>
> Simplest classified search — matches tire dimensions only,
> no bolt pattern or backspace filtering.
>
> For e-commerce: "This tire fits: Honda Civic, Toyota Camry..."

**Параметры**:
| Параметр | Тип | Описание |
|----------|-----|----------|
| `section_width` | `int` | Tire section width in mm (115–365) |
| `aspect_ratio` | `int` | Tire aspect ratio (25–95) |
| `rim_diameter` | `float` | Rim diameter in inches (8–26) |
| `limit` | `int` | Results per page (default 20) |
| `offset` | `int` | Pagination offset |

---

### `find_vehicles_for_package`

**API**: `GET /v2/classified/by_package/search/`

**Docstring**:
> Find vehicles compatible with a rim + tire package.
>
> Most precise classified search — considers both physical wheel
> fitment (backspace) and tire size compatibility simultaneously.
>
> For e-commerce combo/bundle product pages.

**Параметры**:
| Параметр | Тип | Описание |
|----------|-----|----------|
| `bolt_pattern` | `str` | Bolt pattern (e.g. '5x114.3') |
| `rim_diameter` | `float` | Rim diameter in inches (8–26) |
| `rim_width` | `float` | Rim width in inches (2–14) |
| `rim_offset` | `float` | Rim offset in mm (-150–150) |
| `section_width` | `int` | Tire section width in mm (115–365) |
| `aspect_ratio` | `int` | Tire aspect ratio (25–95) |
| `cb` | `float?` | Centre bore diameter in mm (52.1–225) |
| `rim_bst_from` | `int?` | Backspace tolerance lower bound in mm (1–8, default 2) |
| `rim_bst_to` | `int?` | Backspace tolerance upper bound in mm (1–8, default 2) |
| `od_tolerance` | `float?` | Overall diameter tolerance fraction (0–0.05, default 0.01) |
| `ow_tolerance` | `float?` | Overall width tolerance fraction (0–0.03, default 0) |
| `ordering` | `"name" \| "fitment" \| "load"?` | Sort order |
| `limit` | `int` | Results per page (default 20) |
| `offset` | `int` | Pagination offset |

---

## Utility (`tools/utility.py`) — 1 тул

---

### `get_spec_metadata` (составной)

**API**: `GET /v2/spec/metadata/` + MCP-side `_build_hints()`

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

**Параметры**:
| Параметр | Тип | Описание |
|----------|-----|----------|
| `rim_diameter` | `float?` | Rim diameter in inches (8–30, e.g. 18) |
| `rim_width` | `float?` | Rim width in inches (2–16, e.g. 8.0) |
| `rim_offset` | `float?` | Offset ET in mm (-150–150, e.g. 45). Enables geometry. |
| `bolt_pattern` | `str?` | Bolt pattern (e.g. '5x114.3'). Narrows population stats. |
| `section_width` | `float?` | Метрические шины: мм (95–405, e.g. 225). HF (задан `overall_diameter`): дюймы (4.5–14, e.g. 12.5) |
| `aspect_ratio` | `int?` | Tire aspect ratio (20–95, e.g. 45) |
| `overall_diameter` | `float?` | Overall tire diameter in inches (20–50, e.g. 33). HF mode. |

**MCP-side логика (`_build_hints`)** генерирует текстовые подсказки для LLM:
- Процентиль вылета (ET) в рамках данного размера диска
- Оценка количества совпадений при расширении толерансов
- Рекомендация параметров `fs_poke`/`bs_push` для classified-поиска когда offset-поиск не даёт результатов
- Предупреждение когда backspace близок к минимуму в БД
- Топ-3 болтовых паттернов
- Основная ось использования (front/rear) и процент стоковых фитментов
- Стаггер-пары (с чем чаще всего ставят на другую ось)
- Оценка веса диска/шины
- Совместимость ширины диска с шиной (для package-режима)

---

## Сводка


| Модуль     | Кол-во тулов | API-эндпоинтов | Ограничения         |
| ---------- | ------------ | -------------- | ------------------- |
| Catalog    | 6            | 6              | Нет                 |
| Search     | 6            | 6              | ToS (кроме upsteps) |
| Classified | 5            | 5              | Нет                 |
| Utility    | 1            | 1              | Нет                 |
| **Итого**  | **18**       | **18**         | —                   |


**Простых тулов (1:1 с API)**: 15
**Составных (API + MCP-логика)**: 3 (`get_spec_metadata`, `check_rim_fitment_for_vehicle`, `check_tire_fitment_for_vehicle`)
