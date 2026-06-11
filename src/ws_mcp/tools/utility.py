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


def _build_hints(data: dict) -> list[str]:
    """Build human-readable hints from spec metadata response.

    Generates contextual insights for LLM agents based on the raw
    geometry and population data returned by the API.
    """
    hints = []
    mode = data.get("mode")

    if mode in ("rim", "package"):
        pop = data.get("population", {})
        total = pop.get("total_wheelpairs", 0)
        rim = data.get("rim", {})
        rd = _int_if_whole(rim.get("diameter", 0))
        rw = _int_if_whole(rim.get("width", 0))
        offset = rim.get("offset")

        if total == 0:
            hints.append(f"No data in database for {rd}x{rw} rims.")
        else:
            if offset is not None:
                et = _int_if_whole(offset)
                pct = pop.get("offset_percentile")
                dist = pop.get("offset_distribution", {})
                p25, p75 = dist.get("p25"), dist.get("p75")

                if pct is not None:
                    hints.append(
                        f"Offset ET{et} is at the {pct}th percentile for "
                        f"{rd}x{rw} — typical range ET{p25}-ET{p75}."
                    )

                estimates = pop.get("match_estimates", [])
                if len(estimates) >= 2:
                    exact = estimates[0]["vehicles"]
                    at_5 = estimates[1]["vehicles"]
                    if at_5 > exact:
                        hints.append(
                            f"Expanding tolerance to +/-5mm increases matches "
                            f"from {exact:,} to {at_5:,} vehicles."
                        )

                # Suggest classified search when offset search yields nothing
                if estimates and all(e["vehicles"] == 0 for e in estimates):
                    suggested = _suggest_classified_params(data)
                    if suggested:
                        hints.append(
                            f"No offset-based matches. Use find_vehicles_for_rim with "
                            f"fs_poke={suggested['fs_poke']}, bs_push={suggested['bs_push']} "
                            f"(or equivalently rim_bst_from={suggested['bs_push']}, "
                            f"rim_bst_to={suggested['fs_poke']}) "
                            f"for geometric fitment search."
                        )

                fs_bs = pop.get("fs_bs_range", {})
                bs_info = fs_bs.get("bs", {})
                if bs_info:
                    bs_yours = bs_info.get("yours")
                    bs_min = bs_info.get("min")
                    if bs_yours and bs_min and (bs_yours - bs_min) < 1.0:
                        hints.append(
                            f'Backspace {bs_yours}" is close to DB minimum ({bs_min}") — '
                            f"classified search may return few inner-side matches."
                        )

            bp = pop.get("top_bolt_patterns", [])
            if bp:
                top3 = ", ".join(b["pattern"] for b in bp[:3])
                hints.append(f"Most common bolt patterns: {top3}.")

            # Axle usage hints
            axle = pop.get("axle_usage", {})
            if axle:
                primary = axle.get("primary_axis")
                as_front = axle.get("as_front", 0)
                as_rear = axle.get("as_rear", 0)
                total_axle = as_front + as_rear
                if total_axle > 0 and primary in ("front", "rear"):
                    dominant = max(as_front, as_rear)
                    pct = round(dominant / total_axle * 100)
                    hints.append(f"Predominantly {primary}-axle rim ({pct}% of setups).")
                    stock_pct = axle.get("stock_pct")
                    if stock_pct is not None:
                        if stock_pct >= 80:
                            hints.append(f"{stock_pct}% are stock (OEM) fitments.")
                        elif stock_pct <= 20:
                            hints.append(f"Only {stock_pct}% are stock — mostly optional/aftermarket fitments.")

                    pairings = axle.get(
                        "staggered_rear_pairings" if primary == "front" else "staggered_front_pairings", []
                    )
                    if pairings:
                        top = pairings[0]
                        d = _int_if_whole(top["diameter"])
                        w = top["width"]
                        hints.append(
                            f"In staggered setups, most commonly paired with {d}x{w} on the "
                            f'{"rear" if primary == "front" else "front"}.'
                        )

            geom = data.get("geometry", {})
            weight = geom.get("est_weight_kg")
            if weight:
                hints.append(f"Estimated rim weight: {weight} kg (cast aluminum).")

    if mode in ("tire", "package"):
        tp = data.get("tire_population", {})
        total = tp.get("total_wheelpairs", 0)
        tire = data.get("tire", {})
        sw = tire.get("section_width", 0)
        ar = tire.get("aspect_ratio", 0)
        rd = _int_if_whole(tire.get("rim_diameter", 0))

        if total == 0:
            hints.append(f"No data for {sw}/{ar}R{rd} tires.")
        else:
            hints.append(f"{sw}/{ar}R{rd} has {total:,} wheel pairs in database.")
            rw_list = tp.get("common_rim_widths", [])
            if rw_list:
                hints.append(f'Most frequently paired with {rw_list[0]}" wide rims.')

        tg = data.get("tire_geometry", {})
        weight = tg.get("est_weight_kg")
        if weight:
            hints.append(f"Estimated tire weight: {weight} kg.")

        rmc = tg.get("rim_width_code")
        if rmc:
            hints.append(f'Recommended rim width code: {rmc}" (ISO standard).')

    if mode == "package":
        pkg = data.get("package", {})
        match = pkg.get("rim_width_match")
        rec_rw = pkg.get("recommended_rim_width")
        rw = data.get("rim", {}).get("width")
        if match == "within_recommended":
            hints.append(f'Rim width {rw}" is within recommended range for this tire (rec: {rec_rw}").')
        elif match == "outside_recommended":
            hints.append(f'Rim width {rw}" is outside recommended range (rec: {rec_rw}"). Check fitment carefully.')

    return hints


# Conservative OEM floor values (mm) for FS/BS across all vehicles
_OEM_FS_FLOOR_MM = 55
_OEM_BS_FLOOR_MM = 100


def _suggest_classified_params(data: dict) -> dict | None:
    """Compute recommended fs_poke/bs_push for find_vehicles_for_rim.

    Uses the searched rim's frontspace/backspace vs conservative OEM floors
    to suggest tolerance values that will yield results.
    """
    geom = data.get("geometry")
    if not geom:
        return None

    fs_inches = geom.get("frontspace")
    bs_inches = geom.get("backspace")
    if fs_inches is None or bs_inches is None:
        return None

    fs_mm = fs_inches * 25.4
    bs_mm = bs_inches * 25.4

    fs_poke = max(round(fs_mm - _OEM_FS_FLOOR_MM), 2)
    bs_push = max(round(bs_mm - _OEM_BS_FLOOR_MM), 2)

    return {"fs_poke": fs_poke, "bs_push": bs_push}


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
            "section_width": section_width,
            "aspect_ratio": aspect_ratio,
            "overall_diameter": overall_diameter,
        }
        data = await api.get("/v2/spec/metadata/", params)
        data["hints"] = _build_hints(data)
        suggested = _suggest_classified_params(data)
        if suggested:
            data["suggested_classified_params"] = suggested
        return data
