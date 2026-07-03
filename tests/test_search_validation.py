"""Unit tests for ws_search_by_vehicle parameter validation.

Validation raises before any HTTP request; the success path is mocked with respx.
"""

import json

import httpx
import pytest
import respx
from fastmcp.exceptions import ToolError

from ws_mcp.server import mcp


async def test_search_by_vehicle_requires_modification_or_region():
    """Either 'modification' or 'region' must narrow the results."""
    with pytest.raises(ToolError, match="modification.*region"):
        await mcp.call_tool("ws_search_by_vehicle", {
            "make": "toyota", "model": "camry", "year": 2024,
        })


async def test_search_by_vehicle_requires_year_or_generation_without_modification():
    """Without 'modification', either 'year' or 'generation' must identify the vehicle."""
    with pytest.raises(ToolError, match="year.*generation"):
        await mcp.call_tool("ws_search_by_vehicle", {
            "make": "toyota", "model": "camry", "region": "usdm",
        })


@respx.mock
async def test_search_by_vehicle_modification_alone_is_sufficient():
    """'modification' alone satisfies both conditions — no year/generation needed."""
    route = respx.get(url__regex=r".*/v2/search/by_model/.*").mock(
        return_value=httpx.Response(200, json={"meta": {"count": 0}, "data": []})
    )

    result = await mcp.call_tool("ws_search_by_vehicle", {
        "make": "toyota", "model": "camry", "modification": "35-v6",
    })

    assert route.called
    payload = json.loads(result.content[0].text)
    assert payload["total"] == 0
