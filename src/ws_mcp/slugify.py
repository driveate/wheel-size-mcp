"""Slug normalization for make/model/generation parameters."""

from __future__ import annotations


def normalize_slug(value: str) -> str:
    """Normalize a user-facing value into an API-compatible slug.

    'BMW' -> 'bmw', '3 Series' -> '3-series', 'Land Rover' -> 'land-rover'
    """
    return value.strip().lower().replace(" ", "-")


def normalize_regions(regions: list[str] | None) -> list[str] | None:
    """Normalize a list of region slugs.

    Returns None if the input is None or empty, otherwise a list of
    normalized slugs ready for httpx (which expands lists into repeated
    query params: region=eudm&region=audm).
    """
    if not regions:
        return None
    return [normalize_slug(r) for r in regions]
