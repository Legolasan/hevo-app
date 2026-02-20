"""
Action executor for handling LLM action requests.

Parses action JSON from LLM responses and executes them via the Hevo API.
"""

import json
import re
from dataclasses import dataclass
from typing import Any, Callable, Optional

from rich.console import Console

from hevo_assistant.api.client import APIError, get_client
from hevo_assistant.api.pipelines import get_pipeline_operations
from hevo_assistant.api.destinations import get_destination_operations
from hevo_assistant.api.models import get_model_operations, get_workflow_operations

console = Console()


# Patterns for requests that are not supported via API
UNSUPPORTED_PATTERNS = [
    (
        r"\b(delete|remove)\s+(my\s+)?destination",
        "Deleting destinations is not available via the API for safety reasons. "
        "Please use the Hevo dashboard to delete destinations."
    ),
    (
        r"\b(change|update|reset)\s+(my\s+)?password",
        "Password changes are not supported via the API. "
        "Please use the Hevo dashboard or the password reset feature."
    ),
    (
        r"\b(billing|invoice|payment|subscription|plan)",
        "Billing and subscription management is not available via the API. "
        "Please visit the Hevo dashboard or contact support."
    ),
    (
        r"\b(export|download)\s+(my\s+)?data",
        "Direct data export is not supported. Your data is synced to your "
        "destination where you can query it directly."
    ),
    (
        r"\bsnowflake\b.{0,20}\b(as\s+)?source\b",
        "Snowflake cannot be used as a data source. "
        "It's only supported as a destination. "
        "Check docs.hevodata.com for supported source connectors."
    ),
    (
        r"\bfrom\s+snowflake\b",
        "Snowflake cannot be used as a source connector. "
        "Hevo supports Snowflake only as a destination."
    ),
    (
        r"\bdatabricks\b.{0,20}\b(as\s+)?source\b",
        "Databricks cannot be used as a data source. "
        "It's only supported as a destination."
    ),
]


def check_unsupported_query(query: str) -> Optional[str]:
    """
    Check if the query is asking for something not supported.

    Args:
        query: User's query text

    Returns:
        Error message if unsupported, None if supported
    """
    query_lower = query.lower()

    for pattern, message in UNSUPPORTED_PATTERNS:
        if re.search(pattern, query_lower, re.IGNORECASE):
            return message

    return None


@dataclass
class ActionResult:
    """Result of executing an action."""

    success: bool
    message: str
    data: Optional[Any] = None


class ActionExecutor:
    """
    Executes actions requested by the LLM.

    Parses action JSON from LLM responses and calls the appropriate
    Hevo API methods.
    """

    # Action name to handler mapping
    ACTIONS: dict[str, Callable] = {}

    def __init__(self):
        self.client = get_client()
        self.pipelines = get_pipeline_operations()
        self.destinations = get_destination_operations()
        self.models = get_model_operations()
        self.workflows = get_workflow_operations()

        # Register action handlers
        self._register_actions()

    def _register_actions(self):
        """Register all available actions."""
        self.ACTIONS = {
            # Pipeline actions
            "list_pipelines": self._list_pipelines,
            "get_pipeline": self._get_pipeline,
            "pause_pipeline": self._pause_pipeline,
            "resume_pipeline": self._resume_pipeline,
            "run_pipeline": self._run_pipeline,

            # Object actions
            "list_objects": self._list_objects,
            "skip_object": self._skip_object,
            "restart_object": self._restart_object,

            # Destination actions
            "list_destinations": self._list_destinations,

            # Model actions
            "list_models": self._list_models,
            "run_model": self._run_model,

            # Workflow actions
            "list_workflows": self._list_workflows,
            "run_workflow": self._run_workflow,
        }

    def parse_action(self, response: str) -> Optional[dict]:
        """
        Parse action JSON from LLM response.

        Args:
            response: LLM response text

        Returns:
            Action dictionary or None if no action found
        """
        # Try to find JSON block in response
        patterns = [
            r"```json\s*(\{.*?\})\s*```",  # Markdown code block
            r"```\s*(\{.*?\})\s*```",       # Code block without json tag
            r"(\{\"action\".*?\})",          # Inline JSON
        ]

        for pattern in patterns:
            match = re.search(pattern, response, re.DOTALL)
            if match:
                try:
                    return json.loads(match.group(1))
                except json.JSONDecodeError:
                    continue

        return None

    def execute(self, action: dict) -> ActionResult:
        """
        Execute an action.

        Args:
            action: Action dictionary with "action" and optional "params"

        Returns:
            ActionResult with success status and message
        """
        action_name = action.get("action")
        params = action.get("params", {})

        if not action_name:
            return ActionResult(
                success=False,
                message="No action specified",
            )

        handler = self.ACTIONS.get(action_name)
        if not handler:
            return ActionResult(
                success=False,
                message=f"Unknown action: {action_name}",
            )

        try:
            return handler(params)
        except APIError as e:
            return ActionResult(
                success=False,
                message=f"API error: {e.message}",
            )
        except Exception as e:
            return ActionResult(
                success=False,
                message=f"Error executing action: {str(e)}",
            )

    def execute_from_response(self, response: str) -> Optional[ActionResult]:
        """
        Parse and execute action from LLM response.

        Args:
            response: LLM response text

        Returns:
            ActionResult or None if no action found
        """
        action = self.parse_action(response)
        if action:
            return self.execute(action)
        return None

    # ==================== Action Handlers ====================

    def _list_pipelines(self, params: dict) -> ActionResult:
        """List all pipelines in table format."""
        pipelines = self.pipelines.list_all()

        if not pipelines:
            return ActionResult(
                success=True,
                message="No pipelines found.",
                data=[],
            )

        # Helper to get pipeline name from source.name
        def get_name(p: dict) -> str:
            source = p.get("source", {})
            if isinstance(source, dict):
                name = source.get("name")
                if name:
                    return str(name)
            pid = p.get("id", "?")
            return f"Pipeline #{pid}"

        # Helper to get source type display name
        def get_source_type(p: dict) -> str:
            source = p.get("source", {})
            if isinstance(source, dict):
                type_data = source.get("type", {})
                if isinstance(type_data, dict):
                    return type_data.get("display_name") or type_data.get("name") or ""
            return ""

        # Helper to get destination name
        def get_dest_name(p: dict) -> str:
            dest = p.get("destination", {})
            if isinstance(dest, dict):
                return dest.get("name", "")
            return ""

        # Filter by status if requested
        status_filter = params.get("status", "").upper()
        if status_filter:
            pipelines = [p for p in pipelines if p.get("status", "").upper() == status_filter]

        if not pipelines:
            return ActionResult(
                success=True,
                message=f"No {status_filter.lower()} pipelines found.",
                data=[],
            )

        # Get limit from params (default 20)
        limit = params.get("limit", 20)
        total = len(pipelines)

        # Build markdown table
        lines = [
            f"Found {total} pipelines:",
            "",
            "| Name | Source | Destination | Status |",
            "|------|--------|-------------|--------|",
        ]

        for p in pipelines[:limit]:
            name = get_name(p)
            source = get_source_type(p)
            dest = get_dest_name(p)
            status = p.get("status", "UNKNOWN")
            lines.append(f"| {name} | {source} | {dest} | {status} |")

        if total > limit:
            lines.append("")
            lines.append(f"*Showing {limit} of {total} pipelines. Say 'show more' or 'show all' to see more.*")

        return ActionResult(
            success=True,
            message="\n".join(lines),
            data=pipelines,
        )

    def _get_pipeline(self, params: dict) -> ActionResult:
        """Get pipeline details."""
        pipeline_id = params.get("id")
        name = params.get("name")

        status = self.pipelines.get_status(pipeline_id=pipeline_id, name=name)

        if not status:
            return ActionResult(
                success=False,
                message=f"Pipeline not found: {name or pipeline_id}",
            )

        status_emoji = "🟢" if status.status == "ACTIVE" else "🟡"

        return ActionResult(
            success=True,
            message=(
                f"{status_emoji} Pipeline: {status.name}\n"
                f"Status: {status.status}\n"
                f"Source: {status.source_type}\n"
                f"Objects: {status.objects_count} total, "
                f"{status.active_objects} active, "
                f"{status.failed_objects} failed"
            ),
            data=status,
        )

    def _pause_pipeline(self, params: dict) -> ActionResult:
        """Pause a pipeline."""
        pipeline_id = params.get("id")
        name = params.get("name")

        try:
            self.pipelines.pause(pipeline_id=pipeline_id, name=name)
            return ActionResult(
                success=True,
                message=f"✓ Pipeline '{name or pipeline_id}' paused.",
            )
        except ValueError as e:
            return ActionResult(success=False, message=str(e))

    def _resume_pipeline(self, params: dict) -> ActionResult:
        """Resume a pipeline."""
        pipeline_id = params.get("id")
        name = params.get("name")

        try:
            self.pipelines.resume(pipeline_id=pipeline_id, name=name)
            return ActionResult(
                success=True,
                message=f"✓ Pipeline '{name or pipeline_id}' resumed.",
            )
        except ValueError as e:
            return ActionResult(success=False, message=str(e))

    def _run_pipeline(self, params: dict) -> ActionResult:
        """Run a pipeline immediately."""
        pipeline_id = params.get("id")
        name = params.get("name")

        try:
            self.pipelines.run_now(pipeline_id=pipeline_id, name=name)
            return ActionResult(
                success=True,
                message=f"✓ Pipeline '{name or pipeline_id}' triggered.",
            )
        except ValueError as e:
            return ActionResult(success=False, message=str(e))

    def _list_objects(self, params: dict) -> ActionResult:
        """List objects in a pipeline in table format."""
        pipeline_id = params.get("pipeline_id")
        name = params.get("pipeline_name")

        if not pipeline_id and name:
            pipeline = self.client.get_pipeline_by_name(name)
            if not pipeline:
                return ActionResult(
                    success=False,
                    message=f"Pipeline not found: {name}",
                )
            pipeline_id = pipeline.get("id")

        objects = self.client.get_pipeline_objects(pipeline_id)

        if not objects:
            return ActionResult(
                success=True,
                message="No objects found in this pipeline.",
                data=[],
            )

        # Get limit from params (default 20)
        limit = params.get("limit", 20)
        total = len(objects)

        # Build markdown table
        lines = [
            f"Found {total} objects:",
            "",
            "| Object | Status |",
            "|--------|--------|",
        ]

        for obj in objects[:limit]:
            obj_name = obj.get("name", "Unknown")
            status = obj.get("status", "UNKNOWN")
            lines.append(f"| {obj_name} | {status} |")

        if total > limit:
            lines.append("")
            lines.append(f"*Showing {limit} of {total} objects. Say 'show more' or 'show all' to see more.*")

        return ActionResult(
            success=True,
            message="\n".join(lines),
            data=objects,
        )

    def _skip_object(self, params: dict) -> ActionResult:
        """Skip an object."""
        pipeline_id = params.get("pipeline_id")
        object_name = params.get("object_name")

        if not pipeline_id or not object_name:
            return ActionResult(
                success=False,
                message="Both pipeline_id and object_name are required.",
            )

        self.pipelines.skip_object(pipeline_id, object_name)
        return ActionResult(
            success=True,
            message=f"✓ Object '{object_name}' skipped.",
        )

    def _restart_object(self, params: dict) -> ActionResult:
        """Restart an object."""
        pipeline_id = params.get("pipeline_id")
        object_name = params.get("object_name")

        if not pipeline_id or not object_name:
            return ActionResult(
                success=False,
                message="Both pipeline_id and object_name are required.",
            )

        self.pipelines.restart_object(pipeline_id, object_name)
        return ActionResult(
            success=True,
            message=f"✓ Object '{object_name}' restarted.",
        )

    def _list_destinations(self, params: dict) -> ActionResult:
        """List all destinations in table format."""
        destinations = self.destinations.list_all()

        if not destinations:
            return ActionResult(
                success=True,
                message="No destinations found.",
                data=[],
            )

        # Get limit from params (default 20)
        limit = params.get("limit", 20)
        total = len(destinations)

        # Build markdown table
        lines = [
            f"Found {total} destinations:",
            "",
            "| Name | Type | Status |",
            "|------|------|--------|",
        ]

        for d in destinations[:limit]:
            lines.append(f"| {d.name} | {d.type} | {d.status} |")

        if total > limit:
            lines.append("")
            lines.append(f"*Showing {limit} of {total} destinations. Say 'show more' or 'show all' to see more.*")

        return ActionResult(
            success=True,
            message="\n".join(lines),
            data=destinations,
        )

    def _list_models(self, params: dict) -> ActionResult:
        """List all models in table format."""
        models = self.models.list_all()

        if not models:
            return ActionResult(
                success=True,
                message="No models found.",
                data=[],
            )

        # Get limit from params (default 20)
        limit = params.get("limit", 20)
        total = len(models)

        # Build markdown table
        lines = [
            f"Found {total} models:",
            "",
            "| Name | Status | Schedule |",
            "|------|--------|----------|",
        ]

        for m in models[:limit]:
            lines.append(f"| {m.name} | {m.status} | {m.schedule} |")

        if total > limit:
            lines.append("")
            lines.append(f"*Showing {limit} of {total} models. Say 'show more' or 'show all' to see more.*")

        return ActionResult(
            success=True,
            message="\n".join(lines),
            data=models,
        )

    def _run_model(self, params: dict) -> ActionResult:
        """Run a model."""
        model_id = params.get("id")
        name = params.get("name")

        if not model_id and name:
            model = self.models.get_by_name(name)
            if not model:
                return ActionResult(
                    success=False,
                    message=f"Model not found: {name}",
                )
            model_id = model.id

        self.models.run_now(model_id)
        return ActionResult(
            success=True,
            message=f"✓ Model '{name or model_id}' triggered.",
        )

    def _list_workflows(self, params: dict) -> ActionResult:
        """List all workflows in table format."""
        workflows = self.workflows.list_all()

        if not workflows:
            return ActionResult(
                success=True,
                message="No workflows found.",
                data=[],
            )

        # Get limit from params (default 20)
        limit = params.get("limit", 20)
        total = len(workflows)

        # Build markdown table
        lines = [
            f"Found {total} workflows:",
            "",
            "| Name | Status |",
            "|------|--------|",
        ]

        for w in workflows[:limit]:
            lines.append(f"| {w.name} | {w.status} |")

        if total > limit:
            lines.append("")
            lines.append(f"*Showing {limit} of {total} workflows. Say 'show more' or 'show all' to see more.*")

        return ActionResult(
            success=True,
            message="\n".join(lines),
            data=workflows,
        )

    def _run_workflow(self, params: dict) -> ActionResult:
        """Run a workflow."""
        workflow_id = params.get("id")
        name = params.get("name")

        if not workflow_id and name:
            workflow = self.workflows.get_by_name(name)
            if not workflow:
                return ActionResult(
                    success=False,
                    message=f"Workflow not found: {name}",
                )
            workflow_id = workflow.id

        self.workflows.run_now(workflow_id)
        return ActionResult(
            success=True,
            message=f"✓ Workflow '{name or workflow_id}' triggered.",
        )


def get_action_executor() -> ActionExecutor:
    """Get an ActionExecutor instance."""
    return ActionExecutor()
