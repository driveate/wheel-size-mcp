"""Shared ToolAnnotations for all tool modules."""

from mcp.types import ToolAnnotations

CATALOG_ANNOTATIONS = ToolAnnotations(
    title="Catalog (freely callable)",
    readOnlyHint=True,
    destructiveHint=False,
    idempotentHint=True,
    openWorldHint=False,
)

SEARCH_ANNOTATIONS = ToolAnnotations(
    title="Search (user-initiated only)",
    readOnlyHint=True,
    destructiveHint=False,
    idempotentHint=True,
    openWorldHint=False,
)

CLASSIFIED_ANNOTATIONS = ToolAnnotations(
    title="Classified (freely callable)",
    readOnlyHint=True,
    destructiveHint=False,
    idempotentHint=True,
    openWorldHint=False,
)

UTILITY_ANNOTATIONS = ToolAnnotations(
    title="Utility (freely callable)",
    readOnlyHint=True,
    destructiveHint=False,
    idempotentHint=True,
    openWorldHint=False,
)
