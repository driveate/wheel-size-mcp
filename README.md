# wheel-size-mcp

MCP (Model Context Protocol) server for the [Wheel Fitment API](https://api.wheel-size.com/v2/swagger/) — enables Claude Code and LLM agents to query vehicle wheel/tire compatibility data.

## Setup

```bash
pip install -e ".[dev]"
```

### Environment Variables

| Variable | Required | Default | Description |
|----------|----------|---------|-------------|
| `WHEELSIZE_API_KEY` | Yes | — | API key from [developer.wheel-size.com](https://developer.wheel-size.com) |
| `API_BASE_URL` | No | `http://localhost:8000` | API base URL |
| `API_HOST_HEADER` | No | `api.ws.local` | Host header for local Docker |

### Claude Code Configuration

Add to your project's `.mcp.json`:

```json
{
  "mcpServers": {
    "wheel-size-api": {
      "command": "wheel-size-mcp",
      "env": {
        "WHEELSIZE_API_KEY": "${WHEELSIZE_API_KEY}"
      }
    }
  }
}
```

Or add via CLI:

```bash
claude mcp add wheel-size-api -- wheel-size-mcp
```

## Available Tools

### Vehicle Lookup (call in order)

| Tool | Description |
|------|-------------|
| `list_makes` | List manufacturers. Start here. |
| `list_models(make)` | List models for a make. |
| `list_years(make, model)` | List available years. |
| `list_generations(make, model)` | List generations (alternative to years). |
| `list_modifications(make, model, year)` | List trims/modifications. |
| `search_by_vehicle(make, model, year)` | Get wheel/tire fitment data. **User-initiated.** |

### Reverse Lookup

| Tool | Description |
|------|-------------|
| `search_by_rim(bolt_pattern, ...)` | Find vehicles by rim specs. **User-initiated.** |
| `search_by_tire(section_width, aspect_ratio, rim_diameter)` | Find vehicles by tire size. **User-initiated.** |

### Product Cards (Classified)

| Tool | Description |
|------|-------------|
| `find_tires_for_rim(bolt_pattern, diameter, width, offset)` | Compatible tires for a rim. |
| `find_vehicles_for_rim(bolt_pattern, diameter, width, offset)` | Vehicles compatible with a rim. |
| `find_vehicle_modifications_for_rim(make, model, generation, ...)` | Per-vehicle drill-down. |
| `find_vehicles_for_tire(section_width, aspect_ratio, rim_diameter)` | Vehicles for a tire size. |
| `find_vehicles_for_package(bolt_pattern, ..., section_width, aspect_ratio)` | Vehicles for rim+tire combo. |

### Calculator

| Tool | Description |
|------|-------------|
| `calculate_upsteps(rim_diameter, rim_width, rim_offset, section_width, aspect_ratio)` | Plus/minus sizing. |
| `list_regions` | Available market regions. |

## API Terms of Service

Search tools (`search_by_vehicle`, `search_by_rim`, `search_by_tire`) **must be initiated by real users** per [API Terms of Usage](https://api-demo.wheel-size.com/api-tos/). Do not call in autonomous agent loops.

## Development

```bash
# Install dev dependencies
pip install -e ".[dev]"

# Run tests
pytest

# Lint
ruff check .

# Run server (stdio)
wheel-size-mcp
```
