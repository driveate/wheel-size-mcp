"""Shared fixtures for integration tests."""

import json
import os

import httpx
import pytest

# Point client at local API before importing ws_mcp modules
os.environ.setdefault("API_BASE_URL", "http://api.ws.local")

from ws_mcp.client import WheelSizeClient, api  # noqa: E402
from ws_mcp.server import mcp  # noqa: E402


def _api_is_reachable() -> bool:
    """Check if the local API is reachable."""
    try:
        r = httpx.get(
            f"{api.base_url}/v2/regions/",
            headers={"Host": api.host_header},
            timeout=5.0,
        )
        return r.status_code == 200
    except httpx.ConnectError:
        return False


_reachable = _api_is_reachable()

pytestmark = pytest.mark.integration


@pytest.fixture(autouse=True)
def _require_api():
    """Skip integration tests when the local API is not reachable."""
    if not _reachable:
        pytest.skip("Local API not reachable")


@pytest.fixture
def call_tool():
    """Helper to call an MCP tool and return the parsed dict."""

    async def _call(name: str, arguments: dict | None = None) -> dict:
        result = await mcp.call_tool(name, arguments or {})
        return json.loads(result.content[0].text)

    return _call
