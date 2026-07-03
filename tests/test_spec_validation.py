"""Unit tests for ws_get_spec_metadata section_width dual-unit validation.

Metric tires use mm (95-405); HF tires (overall_diameter set) use inches
(4.5-14). No API required — api.get is monkeypatched.
"""

import json

import pytest
from fastmcp.exceptions import ToolError

from ws_mcp.client import api
from ws_mcp.server import mcp


@pytest.fixture
def captured_params(monkeypatch):
    """Monkeypatch api.get to capture outgoing params instead of calling the API."""
    captured = {}

    async def fake_get(path, params=None):
        captured["path"] = path
        captured["params"] = {k: v for k, v in (params or {}).items() if v is not None}
        return {"mode": "stub"}

    monkeypatch.setattr(api, "get", fake_get)
    return captured


async def test_hf_mode_rejects_metric_section_width(captured_params):
    """With overall_diameter set, a mm-scale section_width must be rejected."""
    with pytest.raises(ToolError, match="inches"):
        await mcp.call_tool(
            "ws_get_spec_metadata",
            {"overall_diameter": 35, "section_width": 225, "rim_diameter": 17},
        )
    assert "params" not in captured_params  # rejected before reaching the API


async def test_metric_mode_rejects_inch_section_width(captured_params):
    """Without overall_diameter, an inch-scale section_width must be rejected."""
    with pytest.raises(ToolError, match="overall_diameter"):
        await mcp.call_tool(
            "ws_get_spec_metadata",
            {"section_width": 12.5, "aspect_ratio": 45, "rim_diameter": 17},
        )
    assert "params" not in captured_params


async def test_hf_mode_accepts_inch_section_width(captured_params):
    """35x12.50R17 — inch width passes through unchanged in HF mode."""
    await mcp.call_tool(
        "ws_get_spec_metadata",
        {"overall_diameter": 35, "section_width": 12.5, "rim_diameter": 17},
    )
    assert captured_params["params"]["section_width"] == 12.5
    assert captured_params["params"]["overall_diameter"] == 35


async def test_metric_mode_normalizes_whole_float_to_int(captured_params):
    """225.0 is sent as integer 225 (the API validates metric width as int)."""
    await mcp.call_tool(
        "ws_get_spec_metadata",
        {"section_width": 225.0, "aspect_ratio": 45, "rim_diameter": 17},
    )
    sw = captured_params["params"]["section_width"]
    assert sw == 225
    assert isinstance(sw, int)


async def test_metric_mode_accepts_valid_width(captured_params):
    """Plain metric request still works end-to-end through the wrapper."""
    result = await mcp.call_tool(
        "ws_get_spec_metadata",
        {"section_width": 225, "aspect_ratio": 45, "rim_diameter": 17},
    )
    data = json.loads(result.content[0].text)
    assert data["mode"] == "stub"
    assert captured_params["path"] == "/v2/spec/metadata/"
