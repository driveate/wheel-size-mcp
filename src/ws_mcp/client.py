"""HTTP client wrapper for the Wheel Fitment API."""

import os

import httpx
from fastmcp.exceptions import ToolError

API_BASE_URL = os.environ.get("API_BASE_URL", "https://api.wheel-size.com")
API_KEY = os.environ.get("WHEELSIZE_API_KEY", "")
API_HOST_HEADER = os.environ.get("API_HOST_HEADER", "")

# Claude Code token limits
DEFAULT_LIMIT = 20
MAX_ITEMS = 50

# Hints for common parameter errors
_PARAM_HINTS = {
    "make": "Use list_makes to find valid make slugs.",
    "model": "Use list_models(make) to find valid model slugs.",
    "year": "Use list_years(make, model) to see available years.",
    "generation": "Use list_generations(make, model) to find valid generation slugs.",
    "region": "Use list_regions to see valid region slugs (e.g. 'usdm', 'eudm').",
    "bolt_pattern": "Format: NxDDD.D (e.g. '5x114.3', '4x100').",
    "modification": "Use list_modifications(make, model, year) to find valid slugs.",
}


def _format_api_error(status_code: int, error_data: dict) -> str:
    """Convert an API error response into an actionable ToolError message."""
    code = error_data.get("code", "")
    details = error_data.get("details", [])

    if code == "VALIDATION_ERROR" and details:
        parts = []
        for detail in details:
            field = detail.get("field", "")
            msg = detail.get("message", "")
            hint = _PARAM_HINTS.get(field, "")
            line = f"- {field}: {msg}" if field != "non_field_errors" else f"- {msg}"
            if hint:
                line += f" {hint}"
            parts.append(line)
        return "Invalid parameters:\n" + "\n".join(parts)

    if status_code == 401:
        return "Authentication failed. Check that WHEELSIZE_API_KEY is set correctly."

    if status_code == 429:
        return "Rate limited by the API. Wait a moment and try again."

    message = error_data.get("message", "")
    return f"API error ({status_code}): {message}" if message else f"API error ({status_code})"


class WheelSizeClient:
    """Async HTTP client for the Wheel Fitment API v2."""

    def __init__(self, base_url: str | None = None, api_key: str | None = None):
        self.base_url = (base_url or API_BASE_URL).rstrip("/")
        self.api_key = api_key or API_KEY
        self.host_header = API_HOST_HEADER

    async def get(self, path: str, params: dict | None = None) -> dict:
        """Make a GET request to the API.

        Args:
            path: API path (e.g. "/v2/makes/")
            params: Query parameters (user_key is added automatically)

        Returns:
            Parsed JSON response

        Raises:
            ToolError: On non-2xx responses (actionable messages for LLM agents)
        """
        params = dict(params or {})
        if self.api_key:
            params["user_key"] = self.api_key

        # Remove None values
        params = {k: v for k, v in params.items() if v is not None}

        headers = {"Host": self.host_header} if self.host_header else {}

        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.get(
                f"{self.base_url}{path}",
                params=params,
                headers=headers,
            )

        if response.status_code != 200:
            try:
                error_data = response.json()
            except Exception:
                raise ToolError(f"API error ({response.status_code}): {response.text[:200]}")
            raise ToolError(_format_api_error(response.status_code, error_data))

        return response.json()


# Singleton instance
api = WheelSizeClient()
