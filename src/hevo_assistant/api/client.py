"""
Hevo API HTTP client.

Handles authentication, rate limiting, and API requests.
"""

import time
from typing import Any, Optional

import requests
from pydantic import BaseModel
from rich.console import Console

from hevo_assistant.config import get_config

console = Console()


class APIError(Exception):
    """Exception for API errors."""

    def __init__(self, message: str, status_code: Optional[int] = None):
        self.message = message
        self.status_code = status_code
        super().__init__(self.message)


class RateLimiter:
    """Simple rate limiter for API requests."""

    def __init__(self, requests_per_minute: int = 100):
        self.requests_per_minute = requests_per_minute
        self.requests = []

    def wait_if_needed(self):
        """Wait if we've exceeded the rate limit."""
        now = time.time()
        # Remove requests older than 1 minute
        self.requests = [t for t in self.requests if now - t < 60]

        if len(self.requests) >= self.requests_per_minute:
            # Wait until the oldest request is 1 minute old
            wait_time = 60 - (now - self.requests[0])
            if wait_time > 0:
                console.print(f"[dim]Rate limited. Waiting {wait_time:.1f}s...[/dim]")
                time.sleep(wait_time)

        self.requests.append(time.time())


class HevoClient:
    """
    Client for Hevo Data API.

    Handles authentication, rate limiting, and provides methods
    for common API operations.
    """

    def __init__(
        self,
        api_key: Optional[str] = None,
        api_secret: Optional[str] = None,
        region: Optional[str] = None,
    ):
        """
        Initialize the Hevo API client.

        Args:
            api_key: Hevo API key
            api_secret: Hevo API secret
            region: Hevo region (us, eu, in, apac)
        """
        config = get_config()

        self.api_key = api_key or config.hevo.api_key.get_secret_value()
        self.api_secret = api_secret or config.hevo.api_secret.get_secret_value()
        self.base_url = config.hevo.base_url if not region else self._get_base_url(region)

        self.session = requests.Session()
        self.session.auth = (self.api_key, self.api_secret)
        self.session.headers.update(
            {
                "Content-Type": "application/json",
                "Accept": "application/json",
                "User-Agent": "HevoAssistant/1.0",
            }
        )

        self.rate_limiter = RateLimiter()

    def _get_base_url(self, region: str) -> str:
        """Get base URL for a region."""
        urls = {
            "us": "https://us.hevodata.com/api/public/v2.0",
            "us2": "https://us2.hevodata.com/api/public/v2.0",
            "eu": "https://eu.hevodata.com/api/public/v2.0",
            "in": "https://in.hevodata.com/api/public/v2.0",
            "asia": "https://asia.hevodata.com/api/public/v2.0",
            "au": "https://au.hevodata.com/api/public/v2.0",
            "apac": "https://asia.hevodata.com/api/public/v2.0",  # Deprecated alias
        }
        return urls.get(region, urls["us"])

    def _request(
        self,
        method: str,
        endpoint: str,
        params: Optional[dict] = None,
        json: Optional[dict] = None,
    ) -> dict:
        """
        Make an API request.

        Args:
            method: HTTP method
            endpoint: API endpoint (without base URL)
            params: Query parameters
            json: JSON body

        Returns:
            Response JSON

        Raises:
            APIError: If the request fails
        """
        self.rate_limiter.wait_if_needed()

        url = f"{self.base_url}{endpoint}"

        try:
            response = self.session.request(
                method=method,
                url=url,
                params=params,
                json=json,
                timeout=30,
            )

            # Handle common errors
            if response.status_code == 401:
                raise APIError("Authentication failed. Check your API key and secret.", 401)
            elif response.status_code == 403:
                raise APIError("Permission denied. Check your API permissions.", 403)
            elif response.status_code == 404:
                raise APIError("Resource not found.", 404)
            elif response.status_code == 429:
                raise APIError("Rate limit exceeded. Please wait and try again.", 429)
            elif response.status_code >= 500:
                raise APIError(f"Hevo server error: {response.status_code}", response.status_code)

            response.raise_for_status()

            # Some endpoints return 204 No Content
            if response.status_code == 204:
                return {"success": True}

            return response.json()

        except requests.RequestException as e:
            raise APIError(f"Request failed: {str(e)}")

    def get(self, endpoint: str, params: Optional[dict] = None) -> dict:
        """Make a GET request."""
        return self._request("GET", endpoint, params=params)

    def post(self, endpoint: str, json: Optional[dict] = None) -> dict:
        """Make a POST request."""
        return self._request("POST", endpoint, json=json)

    def put(self, endpoint: str, json: Optional[dict] = None) -> dict:
        """Make a PUT request."""
        return self._request("PUT", endpoint, json=json)

    def delete(self, endpoint: str, params: Optional[dict] = None) -> dict:
        """Make a DELETE request."""
        return self._request("DELETE", endpoint, params=params)

    def is_connected(self) -> bool:
        """
        Check if we can connect to the Hevo API.

        Returns:
            True if connection is successful
        """
        try:
            self.get("/pipelines", params={"limit": 1})
            return True
        except APIError:
            return False

    # ==================== Pipeline Operations ====================

    def list_pipelines(self, limit: int = 100) -> list[dict]:
        """List all pipelines."""
        response = self.get("/pipelines", params={"limit": limit})
        return response.get("data", [])

    def get_pipeline(self, pipeline_id: str) -> dict:
        """Get pipeline details."""
        return self.get(f"/pipelines/{pipeline_id}")

    def get_pipeline_by_name(self, name: str) -> Optional[dict]:
        """Find a pipeline by name."""
        pipelines = self.list_pipelines()
        for pipeline in pipelines:
            if pipeline.get("name", "").lower() == name.lower():
                return self.get_pipeline(pipeline["id"])
        return None

    def pause_pipeline(self, pipeline_id: str) -> dict:
        """Pause a pipeline."""
        return self.put(f"/pipelines/{pipeline_id}/status", json={"status": "PAUSED"})

    def resume_pipeline(self, pipeline_id: str) -> dict:
        """Resume a pipeline."""
        return self.put(f"/pipelines/{pipeline_id}/status", json={"status": "ACTIVE"})

    def run_pipeline(self, pipeline_id: str) -> dict:
        """Run a pipeline immediately."""
        return self.post(f"/pipelines/{pipeline_id}/run-now")

    def get_pipeline_objects(
        self, pipeline_id: str, status: Optional[str] = None
    ) -> list[dict]:
        """Get objects in a pipeline."""
        params = {"limit": 100}
        if status:
            params["statuses"] = status
        response = self.get(f"/pipelines/{pipeline_id}/objects", params=params)
        return response.get("data", [])

    # ==================== Object Operations ====================

    def pause_object(self, pipeline_id: str, object_name: str) -> dict:
        """Pause an object."""
        return self.post(f"/pipelines/{pipeline_id}/objects/{object_name}/pause")

    def resume_object(self, pipeline_id: str, object_name: str) -> dict:
        """Resume an object."""
        return self.post(f"/pipelines/{pipeline_id}/objects/{object_name}/resume")

    def skip_object(self, pipeline_id: str, object_name: str) -> dict:
        """Skip an object."""
        return self.post(f"/pipelines/{pipeline_id}/objects/{object_name}/skip")

    def restart_object(self, pipeline_id: str, object_name: str) -> dict:
        """Restart an object."""
        return self.post(f"/pipelines/{pipeline_id}/objects/{object_name}/restart")

    # ==================== Destination Operations ====================

    def list_destinations(self, limit: int = 50) -> list[dict]:
        """List all destinations."""
        response = self.get("/destinations", params={"limit": limit})
        return response.get("data", [])

    def get_destination(self, destination_id: str) -> dict:
        """Get destination details."""
        return self.get(f"/destinations/{destination_id}")

    # ==================== Model Operations ====================

    def list_models(self, limit: int = 50) -> list[dict]:
        """List all models."""
        response = self.get("/models", params={"limit": limit})
        return response.get("data", [])

    def run_model(self, model_id: str) -> dict:
        """Run a model immediately."""
        return self.post(f"/models/{model_id}/run-now")

    # ==================== Workflow Operations ====================

    def list_workflows(self, limit: int = 50) -> list[dict]:
        """List all workflows."""
        response = self.get("/workflows", params={"limit": limit})
        return response.get("data", [])

    def run_workflow(self, workflow_id: str) -> dict:
        """Run a workflow immediately."""
        return self.post(f"/workflows/{workflow_id}/run-now")


def get_client() -> HevoClient:
    """Get a Hevo API client instance."""
    return HevoClient()
