"""MCP server entry point."""

from fastmcp import FastMCP

from ws_mcp.tools import catalog, classified, search

mcp = FastMCP(
    "wheel-size-api",
    instructions="""
    Wheel Fitment API — vehicle wheel and tire compatibility data from wheel-size.com.

    Use these tools to:
    - Look up OEM wheel/tire specs for any vehicle (by make/model/year)
    - Find vehicles compatible with specific rim or tire sizes (reverse lookup)
    - Generate product cards for e-commerce (classified endpoints)
    - Calculate plus/minus sizing alternatives (upsteps)

    Start with list_makes if you don't know exact manufacturer names.

    IMPORTANT: Search tools (search_by_vehicle, search_by_rim, search_by_tire)
    require user-initiated requests per API Terms of Service.
    Do not call them in autonomous loops.
    """,
)

# Register tool modules
catalog.register(mcp)
search.register(mcp)
classified.register(mcp)


def main():
    """Run the MCP server (stdio transport)."""
    mcp.run()


if __name__ == "__main__":
    main()
