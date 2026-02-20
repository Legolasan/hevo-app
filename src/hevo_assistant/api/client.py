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

    def list_pipelines(self, limit: int = 500) -> list[dict]:
        """List all pipelines with pagination support."""
        all_pipelines = []
        starting_after = None

        while True:
            params = {"limit": min(limit, 100)}  # API max is 100 per page
            if starting_after:
                params["starting_after"] = starting_after

            response = self.get("/pipelines", params=params)
            pipelines = response.get("data", [])
            all_pipelines.extend(pipelines)

            # Check for more pages
            pagination = response.get("pagination", {})
            starting_after = pagination.get("starting_after")

            if not starting_after or len(all_pipelines) >= limit:
                break

        return all_pipelines[:limit]

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

    def create_pipeline(
        self,
        source_type: str,
        source_config: dict,
        destination_id: int,
        source_name: Optional[str] = None,
        auto_mapping: str = "ENABLED",
        destination_table_prefix: Optional[str] = None,
        json_parsing_strategy: Optional[str] = None,
        object_configurations: Optional[list] = None,
        status: Optional[str] = None,
    ) -> dict:
        """
        Create a new pipeline.

        Args:
            source_type: Type of source (e.g., MYSQL, POSTGRES, SALESFORCE_V2)
            source_config: Source connection configuration
            destination_id: ID of the destination to connect to
            source_name: Optional name for the pipeline
            auto_mapping: Auto-mapping mode (ENABLED, DISABLED)
            destination_table_prefix: Prefix to apply to destination table names
            json_parsing_strategy: JSON parsing approach (FLAT, SPLIT, COLLAPSE,
                                   NATIVE, NATURAL, COLLAPSE_EXCEPT_ARRAYS)
            object_configurations: Array of object configs with namespace,
                                   task_category_type, id, config, status
            status: Initial pipeline state (PAUSED, STREAMING, SINKING)

        Returns:
            Created pipeline data
        """
        payload = {
            "source_type": source_type,
            "source_config": source_config,
            "destination_id": destination_id,
            "auto_mapping": auto_mapping,
        }
        if source_name:
            payload["source_name"] = source_name
        if destination_table_prefix:
            payload["destination_table_prefix"] = destination_table_prefix
        if json_parsing_strategy:
            payload["json_parsing_strategy"] = json_parsing_strategy
        if object_configurations:
            payload["object_configurations"] = object_configurations
        if status:
            payload["status"] = status
        return self.post("/pipelines", json=payload)

    def delete_pipeline(self, pipeline_id: str) -> dict:
        """Delete a pipeline."""
        return self.delete(f"/pipelines/{pipeline_id}")

    def update_pipeline_priority(self, pipeline_id: str, priority: str) -> dict:
        """
        Update pipeline priority.

        Args:
            pipeline_id: Pipeline ID
            priority: Priority level (HIGH, NORMAL, LOW)

        Returns:
            Updated pipeline data
        """
        return self.put(f"/pipelines/{pipeline_id}/priority", json={"priority": priority})

    def get_pipeline_schedule(self, pipeline_id: str) -> dict:
        """Get pipeline schedule configuration."""
        return self.get(f"/pipelines/{pipeline_id}/schedule")

    def update_pipeline_schedule(self, pipeline_id: str, schedule_config: dict) -> dict:
        """
        Update pipeline schedule.

        Args:
            pipeline_id: Pipeline ID
            schedule_config: Schedule configuration (type, frequency, etc.)

        Returns:
            Updated schedule data
        """
        return self.put(f"/pipelines/{pipeline_id}/schedule", json=schedule_config)

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

    def include_object(self, pipeline_id: str, object_name: str) -> dict:
        """Include a previously skipped object."""
        return self.post(f"/pipelines/{pipeline_id}/objects/{object_name}/include")

    def get_object(self, pipeline_id: str, object_name: str) -> dict:
        """Get details for a specific object in a pipeline."""
        return self.get(f"/pipelines/{pipeline_id}/objects/{object_name}")

    # ==================== Destination Operations ====================

    def list_destinations(self, limit: int = 500) -> list[dict]:
        """List all destinations with pagination support."""
        all_destinations = []
        starting_after = None

        while True:
            params = {"limit": min(limit, 100)}
            if starting_after:
                params["starting_after"] = starting_after

            response = self.get("/destinations", params=params)
            destinations = response.get("data", [])
            all_destinations.extend(destinations)

            pagination = response.get("pagination", {})
            starting_after = pagination.get("starting_after")

            if not starting_after or len(all_destinations) >= limit:
                break

        return all_destinations[:limit]

    def get_destination(self, destination_id: str) -> dict:
        """Get destination details."""
        return self.get(f"/destinations/{destination_id}")

    def create_destination(
        self,
        dest_type: str,
        name: str,
        config: dict,
    ) -> dict:
        """
        Create a new destination.

        Args:
            dest_type: Destination type (SNOWFLAKE, BIGQUERY, POSTGRES, etc.)
            name: Display name for the destination
            config: Connection configuration

        Returns:
            Created destination data
        """
        return self.post("/destinations", json={
            "type": dest_type,
            "name": name,
            "config": config,
        })

    def get_destination_table_stats(
        self,
        destination_id: str,
        table_name: str,
    ) -> dict:
        """Get statistics for a table in a destination."""
        return self.get(f"/destinations/{destination_id}/tables/{table_name}/stats")

    def load_destination(self, destination_id: str) -> dict:
        """Load events to destination immediately."""
        return self.post(f"/destinations/{destination_id}/load-now")

    # ==================== Model Operations ====================

    def list_models(self, limit: int = 500) -> list[dict]:
        """List all models with pagination support."""
        all_models = []
        starting_after = None

        while True:
            params = {"limit": min(limit, 100)}
            if starting_after:
                params["starting_after"] = starting_after

            response = self.get("/models", params=params)
            models = response.get("data", [])
            all_models.extend(models)

            pagination = response.get("pagination", {})
            starting_after = pagination.get("starting_after")

            if not starting_after or len(all_models) >= limit:
                break

        return all_models[:limit]

    def get_model(self, model_id: str) -> dict:
        """Get model details."""
        return self.get(f"/models/{model_id}")

    def run_model(self, model_id: str) -> dict:
        """Run a model immediately."""
        return self.post(f"/models/{model_id}/run-now")

    def create_model(
        self,
        destination_id: int,
        name: str,
        source_query: str,
        target_table: Optional[str] = None,
        load_type: str = "FULL_LOAD",
    ) -> dict:
        """
        Create a new model.

        Args:
            destination_id: ID of the destination
            name: Model name
            source_query: SQL query for the model
            target_table: Target table name (defaults to model name)
            load_type: Load type (FULL_LOAD or INCREMENTAL)

        Returns:
            Created model data
        """
        payload = {
            "destination_id": destination_id,
            "name": name,
            "source_query": source_query,
            "load_type": load_type,
        }
        if target_table:
            payload["target_table"] = target_table
        return self.post("/models", json=payload)

    def update_model(
        self,
        model_id: str,
        name: Optional[str] = None,
        source_query: Optional[str] = None,
        target_table: Optional[str] = None,
    ) -> dict:
        """
        Update a model.

        Args:
            model_id: Model ID
            name: New name (optional)
            source_query: New SQL query (optional)
            target_table: New target table (optional)

        Returns:
            Updated model data
        """
        payload = {}
        if name:
            payload["name"] = name
        if source_query:
            payload["source_query"] = source_query
        if target_table:
            payload["target_table"] = target_table
        return self.put(f"/models/{model_id}", json=payload)

    def update_model_status(self, model_id: str, status: str) -> dict:
        """
        Update model status (pause/resume).

        Args:
            model_id: Model ID
            status: Status (ACTIVE, PAUSED)

        Returns:
            Updated model data
        """
        return self.put(f"/models/{model_id}/activity-status", json={"status": status})

    def delete_model(self, model_id: str) -> dict:
        """Delete a model."""
        return self.delete(f"/models/{model_id}")

    def reset_model(self, model_id: str) -> dict:
        """Reset a model (clear processed data)."""
        return self.delete(f"/models/{model_id}/reset")

    def update_model_schedule(self, model_id: str, schedule_config: dict) -> dict:
        """Update model schedule."""
        return self.put(f"/models/{model_id}/schedule", json=schedule_config)

    # ==================== Workflow Operations ====================

    def list_workflows(self, limit: int = 500) -> list[dict]:
        """List all workflows with pagination support."""
        all_workflows = []
        starting_after = None

        while True:
            params = {"limit": min(limit, 100)}
            if starting_after:
                params["starting_after"] = starting_after

            response = self.get("/workflows", params=params)
            workflows = response.get("data", [])
            all_workflows.extend(workflows)

            pagination = response.get("pagination", {})
            starting_after = pagination.get("starting_after")

            if not starting_after or len(all_workflows) >= limit:
                break

        return all_workflows[:limit]

    def get_workflow(self, workflow_id: str) -> dict:
        """Get workflow details."""
        return self.get(f"/workflows/{workflow_id}")

    def run_workflow(self, workflow_id: str) -> dict:
        """Run a workflow immediately."""
        return self.post(f"/workflows/{workflow_id}/run-now")

    # ==================== Transformation Operations ====================

    def get_transformation(self, pipeline_id: str) -> dict:
        """Get transformation code for a pipeline."""
        return self.get(f"/pipelines/{pipeline_id}/transformations")

    def update_transformation(self, pipeline_id: str, code: str) -> dict:
        """
        Update transformation code.

        Args:
            pipeline_id: Pipeline ID
            code: Transformation code (Python)

        Returns:
            Updated transformation data
        """
        return self.put(f"/pipelines/{pipeline_id}/transformations", json={"code": code})

    def test_transformation(self, pipeline_id: str, sample_data: Optional[dict] = None) -> dict:
        """
        Test transformation code with sample data.

        Args:
            pipeline_id: Pipeline ID
            sample_data: Optional sample data to test with

        Returns:
            Test results
        """
        payload = {}
        if sample_data:
            payload["sample_data"] = sample_data
        return self.post(f"/pipelines/{pipeline_id}/transformations/test", json=payload)

    def get_transformation_sample(self, pipeline_id: str) -> dict:
        """Get sample data for transformation testing."""
        return self.get(f"/pipelines/{pipeline_id}/transformations/sample")

    # ==================== Event Type Operations ====================

    def list_event_types(self, pipeline_id: str) -> list[dict]:
        """List all event types in a pipeline."""
        response = self.get(f"/pipelines/{pipeline_id}/event-types")
        return response.get("data", [])

    def skip_event_type(self, pipeline_id: str, event_type: str) -> dict:
        """Skip an event type."""
        return self.post(f"/pipelines/{pipeline_id}/event-types/{event_type}/skip")

    def include_event_type(self, pipeline_id: str, event_type: str) -> dict:
        """Include a previously skipped event type."""
        return self.post(f"/pipelines/{pipeline_id}/event-types/{event_type}/include")

    # ==================== Schema Mapping Operations ====================

    def update_auto_mapping(self, pipeline_id: str, enabled: bool) -> dict:
        """Enable or disable auto-mapping for a pipeline."""
        return self.put(
            f"/pipelines/{pipeline_id}/auto-mapping",
            json={"enabled": enabled}
        )

    def get_schema_mapping(self, pipeline_id: str, event_type: str) -> dict:
        """Get schema mapping for an event type."""
        return self.get(f"/pipelines/{pipeline_id}/mappings/{event_type}")

    def update_schema_mapping(
        self,
        pipeline_id: str,
        event_type: str,
        mapping: dict,
    ) -> dict:
        """Update schema mapping for an event type."""
        return self.put(
            f"/pipelines/{pipeline_id}/mappings/{event_type}",
            json=mapping
        )

    # ==================== User Management Operations ====================

    def list_users(self) -> list[dict]:
        """List all users in the team."""
        response = self.get("/accounts/users")
        return response.get("data", [])

    def invite_user(self, email: str, role: str = "MEMBER") -> dict:
        """
        Invite a user to the team.

        Args:
            email: User's email address
            role: Role (OWNER, ADMIN, MEMBER, VIEWER)

        Returns:
            Created user data
        """
        return self.post("/accounts/users", json={"email": email, "role": role})

    def update_user_role(self, user_id: str, role: str) -> dict:
        """Update a user's role."""
        return self.put(f"/accounts/users/{user_id}", json={"role": role})

    def delete_user(self, user_id: str) -> dict:
        """Remove a user from the team."""
        return self.delete(f"/accounts/users/{user_id}")

    # ==================== OAuth Account Operations ====================

    def list_oauth_accounts(self) -> list[dict]:
        """List all OAuth accounts."""
        response = self.get("/oauth-accounts")
        return response.get("data", [])

    def get_oauth_account(self, account_id: str) -> dict:
        """Get OAuth account details."""
        return self.get(f"/oauth-accounts/{account_id}")

    def delete_oauth_account(self, account_id: str) -> dict:
        """Remove an OAuth account."""
        return self.delete(f"/oauth-accounts/{account_id}")


def get_client() -> HevoClient:
    """Get a Hevo API client instance."""
    return HevoClient()
