# wheel-size-mcp

MCP server for the [Wheel Fitment API](https://api.wheel-size.com/v2/swagger/) — gives [Claude Code](https://docs.anthropic.com/en/docs/claude-code) access to vehicle wheel and tire compatibility data from [wheel-size.com](https://www.wheel-size.com).

Ask Claude things like:
- "What are the OEM wheel specs for a 2024 Toyota Camry?"
- "Which vehicles fit 5x114.3 18x8 ET35 rims?"
- "Calculate plus-size options for 225/50R17 on 7Jx17 ET40"

## Quick Start

### 1. Get an API key

Sign up at [developer.wheel-size.com](https://developer.wheel-size.com) and copy your API key.

### 2. Set the API key in your shell

Add to your `~/.zshrc` (or `~/.bashrc`):

```bash
export WHEELSIZE_API_KEY="your-api-key-here"
```

Then reload your shell: `source ~/.zshrc`

### 3. Add to Claude Code

Run this in your terminal:

```bash
claude mcp add wheel-size-api -- uvx --from git+https://github.com/driveate/wheel-size-mcp wheel-size-mcp
```

This tells `uvx` to install the package from GitHub and run it. Claude Code will start the server automatically.

Alternatively, create a `.mcp.json` file in your project root:

```json
{
  "mcpServers": {
    "wheel-size-api": {
      "command": "uvx",
      "args": ["--from", "git+https://github.com/driveate/wheel-size-mcp", "wheel-size-mcp"],
      "env": {
        "WHEELSIZE_API_KEY": "${WHEELSIZE_API_KEY}"
      }
    }
  }
}
```

### 4. Restart Claude Code

The MCP server starts automatically when Claude Code launches in the project directory.

## Available Tools (15)

### Catalog — vehicle lookup

| Tool | Description |
|------|-------------|
| `list_makes` | List all manufacturers. **Start here.** |
| `list_models` | Models for a make (e.g. Toyota → Camry, Corolla…). |
| `list_years` | Available years for a make/model. |
| `list_generations` | Generations for a make/model (alternative to years). |
| `list_modifications` | Trims for a specific vehicle (e.g. 2.0i, 3.0 V6…). |
| `list_regions` | Market regions (USDM, EUDM, JDM…). |

### Search — fitment data

| Tool | Description |
|------|-------------|
| `search_by_vehicle` | OEM wheel/tire specs for a vehicle. |
| `search_by_rim` | Find vehicles compatible with a rim (by bolt pattern, diameter, width). |
| `search_by_tire` | Find vehicles compatible with a tire size. |
| `calculate_upsteps` | Plus/minus sizing calculator. |

### Classified — product cards for e-commerce

| Tool | Description |
|------|-------------|
| `find_tires_for_rim` | Compatible tire sizes for a rim spec. |
| `find_vehicles_for_rim` | Vehicles that fit a given rim. |
| `find_vehicle_modifications_for_rim` | Drill down into trims for a specific generation. |
| `find_vehicles_for_tire` | Vehicles that use a specific tire size. |
| `find_vehicles_for_package` | Vehicles compatible with a rim + tire combo. |

## Environment Variables

| Variable | Required | Default | Description |
|----------|----------|---------|-------------|
| `WHEELSIZE_API_KEY` | **Yes** | — | API key from [developer.wheel-size.com](https://developer.wheel-size.com) |
| `API_BASE_URL` | No | `https://api.wheel-size.com` | API base URL |
| `API_HOST_HEADER` | No | — | Host header override (only needed for local Docker routing) |

## API Terms of Service

Search tools (`search_by_vehicle`, `search_by_rim`, `search_by_tire`) **must be initiated by real users** per [API Terms of Usage](https://api-demo.wheel-size.com/api-tos/). Do not call in autonomous agent loops.

## Development

```bash
# Install dev dependencies
uv sync --dev

# Run tests (requires local API at http://api.ws.local)
uv run pytest

# Unit tests only (no API needed)
uv run pytest -m "not integration"

# Lint
ruff check .

# Run server (stdio)
wheel-size-mcp
```
