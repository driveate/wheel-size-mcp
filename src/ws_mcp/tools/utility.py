"""Utility tools — spec metadata, calculators, and intelligence helpers."""

from __future__ import annotations

from typing import Annotated

from fastmcp import FastMCP
from fastmcp.exceptions import ToolError
from pydantic import Field

from ws_mcp.client import api
from ws_mcp.tools._annotations import UTILITY_ANNOTATIONS

# section_width unit ranges: metric tires use mm, HF (high flotation) tires use inches
_SW_METRIC_MM = (95, 405)
_SW_HF_INCHES = (4.5, 14)


def _int_if_whole(v: float | int) -> float | int:
    """Display 18.0 as 18, but keep 8.5 as 8.5."""
    return int(v) if v == int(v) else v


def _mcp_routing_hints(data: dict) -> list[str]:
    """Hints the API cannot generate itself because they reference MCP tool names.

    The bulk of the hints (percentiles, tolerance estimates, axle usage,
    weights) is generated server-side via hints=true, and
    suggested_classified_params is computed server-side as well.
    """
    if data.get("mode") not in ("rim", "package"):
        return []
    if data.get("rim", {}).get("offset") is None:
        return []
    estimates = data.get("population", {}).get("match_estimates", [])
    suggested = data.get("suggested_classified_params")
    if not estimates or not suggested or any(e["vehicles"] for e in estimates):
        return []
    return [
        f"No offset-based matches. Use find_vehicles_for_rim with "
        f"fs_poke={suggested['fs_poke']}, bs_push={suggested['bs_push']} "
        f"(or equivalently rim_bst_from={suggested['bs_push']}, "
        f"rim_bst_to={suggested['fs_poke']}) "
        f"for geometric fitment search."
    ]


def register(mcp: FastMCP):
    """Register utility tools with the MCP server."""

    @mcp.tool(annotations=UTILITY_ANNOTATIONS, tags={"utility"})
    async def get_spec_metadata(
        rim_diameter: Annotated[
            float | None, Field(ge=8, le=30, description="Rim diameter in inches (e.g. 18)")
        ] = None,
        rim_width: Annotated[
            float | None, Field(ge=2, le=16, description="Rim width in inches (e.g. 8.0)")
        ] = None,
        rim_offset: Annotated[
            float | None,
            Field(ge=-150, le=150, description="Offset ET in mm (e.g. 45). Enables geometry."),
        ] = None,
        bolt_pattern: Annotated[
            str | None,
            Field(description="Bolt pattern (e.g. '5x114.3'). Narrows population stats."),
        ] = None,
        cb: Annotated[
            float | None,
            Field(ge=52.1, le=225, description="Centre bore in mm (e.g. 71.6). Passed to suggested classified params."),
        ] = None,
        section_width: Annotated[
            float | None,
            Field(
                description=(
                    "Tire section width. Metric tires: mm (95-405, e.g. 225). "
                    "HF tires (when overall_diameter is set): inches (4.5-14, e.g. 12.5)."
                )
            ),
        ] = None,
        aspect_ratio: Annotated[
            int | None, Field(ge=20, le=95, description="Tire aspect ratio (e.g. 45)")
        ] = None,
        overall_diameter: Annotated[
            float | None,
            Field(ge=20, le=50, description="Overall tire diameter in inches (e.g. 33). HF mode."),
        ] = None,
    ) -> dict:
        """Get computed geometry, population stats, and hints for a wheel/tire spec.

        Auto-detects mode from parameters:
        - rim: rim_diameter + rim_width (optionally rim_offset)
        - tire: section_width [mm] + aspect_ratio + rim_diameter
        - hf_tire: overall_diameter + section_width [inches] + rim_diameter
        - package: rim + tire params combined

        Use before search or classified calls to understand whether a spec
        is common or unusual, what tolerances to use, and what to expect.

        This is a utility tool — can be called freely without user initiation.
        """
        if section_width is not None:
            if overall_diameter is not None:
                lo, hi = _SW_HF_INCHES
                if not (lo <= section_width <= hi):
                    raise ToolError(
                        f"section_width={section_width} is out of range for HF mode. "
                        f"With overall_diameter set, section_width is in inches "
                        f"({lo}-{hi}, e.g. 12.5 for a 35x12.50R17 tire)."
                    )
            else:
                lo, hi = _SW_METRIC_MM
                if not (lo <= section_width <= hi):
                    raise ToolError(
                        f"section_width={section_width} is out of range for metric mode "
                        f"({lo}-{hi} mm, e.g. 225). For HF inch-based sizes like "
                        f"35x12.50R17, pass overall_diameter as well."
                    )
                # API validates metric section_width as an integer
                section_width = _int_if_whole(section_width)

        params = {
            "rim_diameter": rim_diameter,
            "rim_width": rim_width,
            "rim_offset": rim_offset,
            "bolt_pattern": bolt_pattern,
            "cb": cb,
            "section_width": section_width,
            "aspect_ratio": aspect_ratio,
            "overall_diameter": overall_diameter,
            "hints": True,
        }
        data = await api.get("/v2/spec/metadata/", params)
        data.setdefault("hints", [])
        data["hints"].extend(_mcp_routing_hints(data))
        return data
