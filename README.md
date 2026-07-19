# wheel-size-mcp

<!-- mcp-name: io.github.driveate/wheel-size-mcp -->

MCP server for the [Wheel Fitment API](https://api.wheel-size.com/v2/swagger/) — gives LLM agents access to vehicle wheel and tire compatibility data from [wheel-size.com](https://www.wheel-size.com).

Ask your AI assistant things like:
- "What are the OEM wheel specs for a 2024 Toyota Camry?"
- "Which vehicles fit 5x114.3 18x8 ET35 rims?"
- "Calculate plus-size options for 225/50R17 on 7Jx17 ET40"
- "Generate a product card for this wheel showing all compatible vehicles"

## Quick Start

### 1. Get an API key

Sign up at [developer.wheel-size.com](https://developer.wheel-size.com) and copy your API key.

### 2. Set the API key in your shell

Add to your `~/.zshrc` (or `~/.bashrc`):

```bash
export WHEELSIZE_API_KEY="your-api-key-here"
```

Then reload your shell: `source ~/.zshrc`

### 3. Add to your AI client

Choose your client below — each config block is copy-paste ready.

#### Claude Code

```bash
claude mcp add wheel-size-api -- uvx wheel-size-mcp
```

Or add to `.mcp.json` in your project root:

```json
{
  "mcpServers": {
    "wheel-size-api": {
      "command": "uvx",
      "args": ["wheel-size-mcp"],
      "env": {
        "WHEELSIZE_API_KEY": "${WHEELSIZE_API_KEY}"
      }
    }
  }
}
```

#### Claude Desktop

Add to `claude_desktop_config.json` (`~/Library/Application Support/Claude/claude_desktop_config.json` on macOS, `%APPDATA%\Claude\claude_desktop_config.json` on Windows):

```json
{
  "mcpServers": {
    "wheel-size-api": {
      "command": "uvx",
      "args": ["wheel-size-mcp"],
      "env": {
        "WHEELSIZE_API_KEY": "your-api-key-here"
      }
    }
  }
}
```

#### Cursor

Add to `.cursor/mcp.json` in your project root:

```json
{
  "mcpServers": {
    "wheel-size-api": {
      "command": "uvx",
      "args": ["wheel-size-mcp"],
      "env": {
        "WHEELSIZE_API_KEY": "your-api-key-here"
      }
    }
  }
}
```

#### Windsurf

Add to `~/.codeium/windsurf/mcp_config.json`:

```json
{
  "mcpServers": {
    "wheel-size-api": {
      "command": "uvx",
      "args": ["wheel-size-mcp"],
      "env": {
        "WHEELSIZE_API_KEY": "your-api-key-here"
      }
    }
  }
}
```

#### Zed

Add to your Zed `settings.json` (Cmd+, → Open Settings):

```json
{
  "context_servers": {
    "wheel-size-api": {
      "command": {
        "path": "uvx",
        "args": ["wheel-size-mcp"],
        "env": {
          "WHEELSIZE_API_KEY": "your-api-key-here"
        }
      }
    }
  }
}
```

### 4. Restart your client

The MCP server starts automatically when the client launches.

## Remote Server (Streamable HTTP)

Besides stdio, the server can run as a standalone HTTP service — useful for hosting one shared instance instead of installing Python on every machine:

```bash
wheel-size-mcp --transport http --port 8000
```

The MCP endpoint is served at `http://127.0.0.1:8000/mcp/`. Point HTTP-capable clients at it:

```json
{
  "mcpServers": {
    "wheel-size-api": {
      "url": "http://127.0.0.1:8000/mcp/"
    }
  }
}
```

**Security**: the server binds to `127.0.0.1` by default. The `WHEELSIZE_API_KEY` lives on the server side, so anyone who can reach the port consumes your API quota — expose it beyond localhost (`--host 0.0.0.0`) only behind a reverse proxy that handles authentication.

## Available Tools (21)

### Catalog — vehicle lookup

| Tool | Description |
|------|-------------|
| `ws_list_makes` | List all manufacturers. **Start here.** |
| `ws_list_models` | Models for a make (e.g. Toyota → Camry, Corolla…). |
| `ws_list_years` | Available years for a make/model. |
| `ws_list_generations` | Generations for a make/model (alternative to years). |
| `ws_list_modifications` | Trims for a specific vehicle (e.g. 2.0i, 3.0 V6…). |
| `ws_list_regions` | Market regions (USDM, EUDM, JDM…). |

### Search — fitment data

| Tool | Description |
|------|-------------|
| `ws_search_by_vehicle` | OEM wheel/tire specs for a vehicle. Requires `modification` or `region`, plus `year` or `generation` (unless `modification` is given). |
| `ws_search_by_rim` | Find vehicles compatible with a rim (exact specs or min/max ranges). |
| `ws_search_by_tire` | Find vehicles by metric tire size, with speed/load/staggered filters and refinement facets. |
| `ws_search_by_hf_tire` | Find vehicles by high-flotation (LT) inch size (e.g. 31x10.50R15). |
| `ws_check_rim_fitment_for_vehicle` | "Will these rims fit my 2020 Civic?" — one-call fitment check. |
| `ws_check_tire_fitment_for_vehicle` | Same for a metric tire size. |
| `ws_check_hf_tire_fitment_for_vehicle` | Same for a high-flotation tire size. |
| `ws_calculate_upsteps` | Plus/minus sizing calculator with width/diameter tolerances. |

### Classified — product cards for e-commerce

| Tool | Description |
|------|-------------|
| `ws_find_tires_for_rim` | Compatible tire sizes for a rim spec. |
| `ws_find_vehicles_for_rim` | Vehicles that fit a given rim (geometric 2D filtering). |
| `ws_find_vehicle_modifications_for_rim` | Drill down into trims for a specific generation. |
| `ws_find_vehicles_for_tire` | Vehicles that use a specific tire size. |
| `ws_find_vehicles_for_package` | Vehicles compatible with a rim + tire combo. |
| `ws_find_vehicle_modifications_for_package` | Drill down into trims for a rim + tire package. |

### Utility

| Tool | Description |
|------|-------------|
| `ws_get_spec_metadata` | Computed geometry, population stats, and intelligence hints for any spec. |

## MCP Prompts

Pre-built workflow prompts that guide LLM agents through multi-step operations:

| Prompt | Description |
|--------|-------------|
| `vehicle_fitment_lookup` | Complete catalog→search chain for a vehicle description |
| `rim_compatibility_check` | Metadata→classified flow for rim compatibility |
| `product_card_generation` | E-commerce product card workflow for wheels/packages |

## Environment Variables

| Variable | Required | Default | Description |
|----------|----------|---------|-------------|
| `WHEELSIZE_API_KEY` | **Yes** | — | API key from [developer.wheel-size.com](https://developer.wheel-size.com) |
| `API_BASE_URL` | No | `https://api.wheel-size.com` | API base URL |
| `API_HOST_HEADER` | No | — | Host header override (only needed for local Docker routing) |
| `MCP_TRANSPORT` | No | `stdio` | `stdio` or `http` (same as `--transport`) |
| `MCP_HOST` | No | `127.0.0.1` | Bind address for http transport (same as `--host`) |
| `MCP_PORT` | No | `8000` | Port for http transport (same as `--port`) |

## API Terms of Service

Search tools (`ws_search_by_vehicle`, `ws_search_by_rim`, `ws_search_by_tire`, `ws_search_by_hf_tire`, and the `ws_check_*_fitment_for_vehicle` checks) **must be initiated by real users** per [API Terms of Usage](https://developer.wheel-size.com/api-tos). Do not call in autonomous agent loops. Catalog, classified, utility tools and `ws_calculate_upsteps` have no such restriction.

## Evals

[`tests/test_questions.json`](tests/test_questions.json) contains 89 natural-language questions across 12 categories (catalog navigation, fitment lookups, reverse searches, fitment checks, upstep calculation, e-commerce product cards, spec metadata, multi-step workflows, edge cases, tool selection). Each entry includes `expected_tools`, optional `expected_params` / `expected_params_search`, and a free-text `tests` note.

`evals/run_evals.py` feeds these questions to a real Claude model with the MCP tools attached, records which tools it calls with which parameters, and grades them against the expectations — catching regressions in tool descriptions and server instructions:

```bash
# needs ANTHROPIC_API_KEY and a reachable Wheel Fitment API; costs money
uv sync --group evals
uv run --group evals python evals/run_evals.py                  # all questions
uv run --group evals python evals/run_evals.py -n 10            # smoke run
uv run --group evals python evals/run_evals.py --category catalog_flow
uv run --group evals python evals/run_evals.py --json report.json --min-pass 0.8
```

Grading is deterministic (no LLM judge): every expected tool must be called (multiset — repeats counted, extra navigation calls allowed), and some single call must carry the expected parameters. Questions without machine-checkable expectations are reported as SKIP and excluded from the pass rate. The default model is pinned (`claude-sonnet-5`) so pass-rate history stays comparable; override with `--model`.

The eval runner is **not** part of pytest or CI — it bills the Anthropic API. The grading logic itself is unit-tested in CI (`tests/test_eval_grading.py`). ToS note: every question simulates a user-initiated request, so the search-tool restriction is respected.

## Development

```bash
# Install dev dependencies
uv sync --dev

# Unit tests (no API needed — this is what CI runs)
uv run pytest -m "not integration"

# Full test suite (requires a private API instance, see note below)
uv run pytest

# Lint
uv run ruff check .

# Run server (stdio)
wheel-size-mcp
```

**Note on tests**: integration tests run against a private test instance of the API and auto-skip when it is unreachable. External contributors should rely on the unit suite (`pytest -m "not integration"`), which mocks all HTTP and is what CI runs on every push and pull request.
