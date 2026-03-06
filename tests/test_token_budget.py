"""Token budget tests — verify no tool response exceeds Claude Code limits.

Claude Code warns at 10,000 tokens and caps at 25,000 tokens (MAX_MCP_OUTPUT_TOKENS).
Conservative estimate: 1 token ≈ 3 characters for JSON content.

Requires the local API at http://api.ws.local (see conftest.py).
"""

import json

import pytest

pytestmark = pytest.mark.integration

# Claude Code limits
TOKEN_CAP = 25_000
TOKEN_WARN = 10_000
CHARS_PER_TOKEN = 3  # conservative estimate for JSON


def assert_under_token_cap(text: str, tool_name: str):
    tokens_est = len(text) // CHARS_PER_TOKEN
    assert tokens_est < TOKEN_CAP, (
        f"{tool_name} response ~{tokens_est:,} tokens (est.) exceeds {TOKEN_CAP:,} cap "
        f"({len(text):,} chars)"
    )


# ---------------------------------------------------------------------------
# Catalog tools (return ALL items, no pagination)
# ---------------------------------------------------------------------------


async def test_list_makes_all(call_tool):
    """list_makes returns all 246+ makes — must stay under budget."""
    from ws_mcp.server import mcp

    result = await mcp.call_tool("list_makes", {})
    text = result.content[0].text
    data = json.loads(text)
    assert data["total"] > 200
    assert_under_token_cap(text, "list_makes (all)")


async def test_list_models_largest_make(call_tool):
    """Toyota has 264+ models — largest catalog response."""
    from ws_mcp.server import mcp

    result = await mcp.call_tool("list_models", {"make": "toyota"})
    text = result.content[0].text
    data = json.loads(text)
    assert data["total"] > 200
    assert_under_token_cap(text, "list_models (toyota)")


async def test_list_modifications_many_trims(call_tool):
    """BMW 3 Series has 60+ modifications — large untruncated response."""
    from ws_mcp.server import mcp

    result = await mcp.call_tool("list_modifications", {
        "make": "bmw", "model": "3-series", "year": 2024,
    })
    text = result.content[0].text
    data = json.loads(text)
    assert data["total"] > 30
    assert_under_token_cap(text, "list_modifications (BMW 3-series)")


# ---------------------------------------------------------------------------
# Search tools (paginated, worst case = full detail + many wheel sets)
# ---------------------------------------------------------------------------


async def test_search_by_vehicle_full_detail_heavy(call_tool):
    """BMW 3 Series EUDM full detail — heaviest known search response."""
    from ws_mcp.server import mcp

    result = await mcp.call_tool("search_by_vehicle", {
        "make": "bmw", "model": "3-series", "year": 2024,
        "region": "eudm", "detail_level": "full",
    })
    text = result.content[0].text
    data = json.loads(text)
    assert data["total"] > 20
    assert_under_token_cap(text, "search_by_vehicle (BMW 3-series full)")


async def test_search_by_rim_max_limit(call_tool):
    """search_by_rim with limit=50 — max page size."""
    from ws_mcp.server import mcp

    result = await mcp.call_tool("search_by_rim", {
        "bolt_pattern": "5x114.3", "rim_diameter": 18, "rim_width": 8, "limit": 50,
    })
    text = result.content[0].text
    assert_under_token_cap(text, "search_by_rim (limit=50)")


# ---------------------------------------------------------------------------
# Classified tools (paginated, worst case = many generations)
# ---------------------------------------------------------------------------


async def test_find_vehicles_for_rim_max_limit(call_tool):
    """find_vehicles_for_rim with limit=50 — enriched response with deltas."""
    from ws_mcp.server import mcp

    result = await mcp.call_tool("find_vehicles_for_rim", {
        "bolt_pattern": "5x114.3", "rim_diameter": 18, "rim_width": 8,
        "rim_offset": 35, "limit": 50,
    })
    text = result.content[0].text
    data = json.loads(text)
    assert data["total"] > 50
    assert_under_token_cap(text, "find_vehicles_for_rim (limit=50)")
