"""Unit tests for WheelSizeClient request shaping and error handling.

HTTP is mocked with respx — no API required.
"""

import httpx
import pytest
import respx
from fastmcp.exceptions import ToolError

from ws_mcp.client import WheelSizeClient

BASE = "https://api.example.test"


@pytest.fixture
def client():
    return WheelSizeClient(base_url=BASE, api_key="test-key")


@respx.mock
async def test_user_key_added_and_none_params_stripped(client):
    route = respx.get(f"{BASE}/v2/makes/").mock(return_value=httpx.Response(200, json={"data": []}))

    result = await client.get("/v2/makes/", {"year": 2024, "region": None})

    assert result == {"data": []}
    params = dict(httpx.QueryParams(route.calls.last.request.url.query))
    assert params == {"user_key": "test-key", "year": "2024"}


@respx.mock
async def test_no_user_key_when_api_key_empty():
    client = WheelSizeClient(base_url=BASE, api_key="")
    client.api_key = ""  # override any WHEELSIZE_API_KEY from the environment
    route = respx.get(f"{BASE}/v2/makes/").mock(return_value=httpx.Response(200, json={}))

    await client.get("/v2/makes/")

    assert "user_key" not in dict(httpx.QueryParams(route.calls.last.request.url.query))


@respx.mock
async def test_401_mentions_api_key_env_var(client):
    respx.get(f"{BASE}/v2/makes/").mock(return_value=httpx.Response(401, json={"message": "bad key"}))

    with pytest.raises(ToolError, match="WHEELSIZE_API_KEY"):
        await client.get("/v2/makes/")


@respx.mock
async def test_429_mentions_rate_limit(client):
    respx.get(f"{BASE}/v2/makes/").mock(return_value=httpx.Response(429, json={"message": "slow down"}))

    with pytest.raises(ToolError, match="Rate limited"):
        await client.get("/v2/makes/")


@respx.mock
async def test_validation_error_includes_param_hint(client):
    error = {
        "code": "VALIDATION_ERROR",
        "details": [{"field": "make", "message": "Invalid slug."}],
    }
    respx.get(f"{BASE}/v2/models/").mock(return_value=httpx.Response(400, json=error))

    with pytest.raises(ToolError, match="list_makes"):
        await client.get("/v2/models/", {"make": "Toyota Motor"})


@respx.mock
async def test_non_json_error_body_is_truncated(client):
    respx.get(f"{BASE}/v2/makes/").mock(return_value=httpx.Response(500, text="<html>oops</html>"))

    with pytest.raises(ToolError, match=r"API error \(500\)"):
        await client.get("/v2/makes/")
