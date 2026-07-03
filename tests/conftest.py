"""Shared fixtures for integration tests."""

import functools
import json
import os

import httpx
import pytest

# Point client at local API before importing ws_mcp modules
os.environ.setdefault("API_BASE_URL", "http://api.ws.local:8080")
os.environ.setdefault("API_HOST_HEADER", "api.ws.local")

from ws_mcp.client import api  # noqa: E402
from ws_mcp.server import mcp  # noqa: E402


@functools.cache
def _api_is_reachable() -> bool:
    """Check if the local API is reachable (probed once, only for integration tests)."""
    try:
        headers = {"Host": api.host_header} if api.host_header else {}
        r = httpx.get(
            f"{api.base_url}/v2/regions/",
            headers=headers,
            timeout=5.0,
        )
        return r.status_code == 200
    except httpx.HTTPError:
        return False


@pytest.fixture(autouse=True)
def _require_api(request):
    """Skip integration tests when the local API is not reachable."""
    if request.node.get_closest_marker("integration") and not _api_is_reachable():
        pytest.skip("Local API not reachable")


@pytest.fixture
def call_tool():
    """Helper to call an MCP tool and return the parsed dict."""

    async def _call(name: str, arguments: dict | None = None) -> dict:
        result = await mcp.call_tool(name, arguments or {})
        return json.loads(result.content[0].text)

    return _call
