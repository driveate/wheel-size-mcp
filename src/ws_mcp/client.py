"""HTTP client wrapper for the Wheel Fitment API."""

import os

import httpx

API_BASE_URL = os.environ.get("API_BASE_URL", "http://localhost:8000")
API_KEY = os.environ.get("WHEELSIZE_API_KEY", "")
API_HOST_HEADER = os.environ.get("API_HOST_HEADER", "api.ws.local")

# Claude Code token limits
DEFAULT_LIMIT = 20
MAX_ITEMS = 50


class APIError(Exception):
    """Raised when the API returns an error response."""

    def __init__(self, status_code: int, message: str):
        self.status_code = status_code
        self.message = message
        super().__init__(f"API error {status_code}: {message}")


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
            APIError: On non-2xx responses
        """
        params = dict(params or {})
        if self.api_key:
            params["user_key"] = self.api_key

        # Remove None values
        params = {k: v for k, v in params.items() if v is not None}

        headers = {"Host": self.host_header}

        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.get(
                f"{self.base_url}{path}",
                params=params,
                headers=headers,
            )

        if response.status_code != 200:
            try:
                error_data = response.json()
                message = error_data.get("message", response.text)
            except Exception:
                message = response.text
            raise APIError(response.status_code, message)

        return response.json()


# Singleton instance
api = WheelSizeClient()
