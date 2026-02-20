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
            "create_pipeline": self._create_pipeline,
            "delete_pipeline": self._delete_pipeline,
            "pause_pipeline": self._pause_pipeline,
            "resume_pipeline": self._resume_pipeline,
            "run_pipeline": self._run_pipeline,
            "update_pipeline_priority": self._update_pipeline_priority,
            "get_pipeline_schedule": self._get_pipeline_schedule,
            "update_pipeline_schedule": self._update_pipeline_schedule,
            "get_pipeline_position": self._get_pipeline_position,
            "update_pipeline_position": self._update_pipeline_position,
            "update_pipeline_source": self._update_pipeline_source,

            # Object actions
            "list_objects": self._list_objects,
            "get_object": self._get_object,
            "pause_object": self._pause_object,
            "resume_object": self._resume_object,
            "skip_object": self._skip_object,
            "include_object": self._include_object,
            "restart_object": self._restart_object,
            "get_object_position": self._get_object_position,
            "update_object_position": self._update_object_position,
            "get_object_stats": self._get_object_stats,
            "get_object_query_mode": self._get_object_query_mode,
            "update_object_query_mode": self._update_object_query_mode,

            # Destination actions
            "list_destinations": self._list_destinations,
            "get_destination": self._get_destination,
            "create_destination": self._create_destination,
            "update_destination": self._update_destination,
            "get_destination_stats": self._get_destination_stats,
            "load_destination": self._load_destination,

            # Model actions
            "list_models": self._list_models,
            "get_model": self._get_model,
            "create_model": self._create_model,
            "update_model": self._update_model,
            "delete_model": self._delete_model,
            "run_model": self._run_model,
            "pause_model": self._pause_model,
            "resume_model": self._resume_model,
            "reset_model": self._reset_model,
            "update_model_schedule": self._update_model_schedule,

            # Workflow actions
            "list_workflows": self._list_workflows,
            "get_workflow": self._get_workflow,
            "run_workflow": self._run_workflow,

            # Transformation actions
            "get_transformation": self._get_transformation,
            "update_transformation": self._update_transformation,
            "test_transformation": self._test_transformation,
            "get_transformation_sample": self._get_transformation_sample,

            # Event type actions
            "list_event_types": self._list_event_types,
            "skip_event_type": self._skip_event_type,
            "include_event_type": self._include_event_type,

            # Schema mapping actions
            "update_auto_mapping": self._update_auto_mapping,
            "get_schema_mapping": self._get_schema_mapping,
            "update_schema_mapping": self._update_schema_mapping,

            # User management actions
            "list_users": self._list_users,
            "invite_user": self._invite_user,
            "update_user_role": self._update_user_role,
            "delete_user": self._delete_user,

            # OAuth account actions
            "list_oauth_accounts": self._list_oauth_accounts,
            "get_oauth_account": self._get_oauth_account,
            "remove_oauth_account": self._remove_oauth_account,
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

    # ==================== New Pipeline Actions ====================

    def _create_pipeline(self, params: dict) -> ActionResult:
        """Create a new pipeline."""
        source_type = params.get("source_type")
        source_config = params.get("source_config")
        destination_id = params.get("destination_id")
        name = params.get("name") or params.get("source_name")
        auto_mapping = params.get("auto_mapping", "ENABLED")
        destination_table_prefix = params.get("destination_table_prefix")
        json_parsing_strategy = params.get("json_parsing_strategy")
        object_configurations = params.get("object_configurations")
        status = params.get("status")

        if not source_type:
            return ActionResult(
                success=False,
                message="Source type is required (e.g., MYSQL, POSTGRES, SALESFORCE_V2).",
            )

        if not source_config:
            return ActionResult(
                success=False,
                message="Source configuration is required.",
            )

        if not destination_id:
            return ActionResult(
                success=False,
                message="Destination ID is required.",
            )

        # Validate json_parsing_strategy if provided
        valid_strategies = ["FLAT", "SPLIT", "COLLAPSE", "NATIVE", "NATURAL", "COLLAPSE_EXCEPT_ARRAYS"]
        if json_parsing_strategy and json_parsing_strategy.upper() not in valid_strategies:
            return ActionResult(
                success=False,
                message=f"Invalid json_parsing_strategy. Must be one of: {', '.join(valid_strategies)}",
            )

        # Validate status if provided
        valid_statuses = ["PAUSED", "STREAMING", "SINKING"]
        if status and status.upper() not in valid_statuses:
            return ActionResult(
                success=False,
                message=f"Invalid status. Must be one of: {', '.join(valid_statuses)}",
            )

        try:
            result = self.pipelines.create(
                source_type=source_type.upper(),
                source_config=source_config,
                destination_id=int(destination_id),
                name=name,
                auto_mapping=auto_mapping.upper() if auto_mapping else "ENABLED",
                destination_table_prefix=destination_table_prefix,
                json_parsing_strategy=json_parsing_strategy.upper() if json_parsing_strategy else None,
                object_configurations=object_configurations,
                status=status.upper() if status else None,
            )
            pipeline_id = result.get("id", "unknown")
            return ActionResult(
                success=True,
                message=f"✓ Pipeline created successfully! ID: {pipeline_id}",
                data=result,
            )
        except ValueError as e:
            return ActionResult(success=False, message=str(e))

    def _delete_pipeline(self, params: dict) -> ActionResult:
        """Delete a pipeline."""
        pipeline_id = params.get("id")
        name = params.get("name")
        confirmed = params.get("confirmed", False)

        if not confirmed:
            return ActionResult(
                success=False,
                message=(
                    "⚠️ Deleting a pipeline is permanent and cannot be undone.\n"
                    "This will stop all data syncing and remove the pipeline configuration.\n"
                    "Data already in the destination will NOT be deleted.\n\n"
                    "To confirm, use: {\"action\": \"delete_pipeline\", \"params\": {"
                    f"\"{'name' if name else 'id'}\": \"{name or pipeline_id}\", \"confirmed\": true}}"
                ),
            )

        try:
            self.pipelines.delete(pipeline_id=pipeline_id, name=name)
            return ActionResult(
                success=True,
                message=f"✓ Pipeline '{name or pipeline_id}' deleted successfully.",
            )
        except ValueError as e:
            return ActionResult(success=False, message=str(e))

    def _update_pipeline_priority(self, params: dict) -> ActionResult:
        """Update pipeline priority."""
        pipeline_id = params.get("id")
        name = params.get("name")
        priority = params.get("priority")

        if not priority:
            return ActionResult(
                success=False,
                message="Priority is required (HIGH or NORMAL).",
            )

        if priority.upper() not in ("HIGH", "NORMAL"):
            return ActionResult(
                success=False,
                message="Priority must be HIGH or NORMAL.",
            )

        try:
            self.pipelines.update_priority(
                priority=priority,
                pipeline_id=pipeline_id,
                name=name,
            )
            return ActionResult(
                success=True,
                message=f"✓ Pipeline '{name or pipeline_id}' priority set to {priority.upper()}.",
            )
        except ValueError as e:
            return ActionResult(success=False, message=str(e))

    def _get_pipeline_schedule(self, params: dict) -> ActionResult:
        """Get pipeline schedule."""
        pipeline_id = params.get("id")
        name = params.get("name")

        try:
            schedule = self.pipelines.get_schedule(pipeline_id=pipeline_id, name=name)
            schedule_type = schedule.get("type", "Unknown")
            frequency = schedule.get("frequency", "N/A")

            return ActionResult(
                success=True,
                message=(
                    f"📅 Pipeline '{name or pipeline_id}' schedule:\n"
                    f"Type: {schedule_type}\n"
                    f"Frequency: {frequency}"
                ),
                data=schedule,
            )
        except ValueError as e:
            return ActionResult(success=False, message=str(e))

    def _update_pipeline_schedule(self, params: dict) -> ActionResult:
        """Update pipeline schedule."""
        pipeline_id = params.get("id")
        name = params.get("name")
        frequency = params.get("frequency")

        if not frequency:
            return ActionResult(
                success=False,
                message="Frequency (in minutes) is required.",
            )

        try:
            frequency_int = int(frequency)
        except (ValueError, TypeError):
            return ActionResult(
                success=False,
                message="Frequency must be an integer (minutes).",
            )

        try:
            self.pipelines.update_schedule(
                frequency=frequency_int,
                pipeline_id=pipeline_id,
                name=name,
            )
            return ActionResult(
                success=True,
                message=f"✓ Pipeline '{name or pipeline_id}' schedule updated to every {frequency_int} minutes.",
            )
        except ValueError as e:
            return ActionResult(success=False, message=str(e))

    def _get_pipeline_position(self, params: dict) -> ActionResult:
        """Get position for a log-based pipeline."""
        pipeline_id = params.get("id") or params.get("pipeline_id")
        name = params.get("name")

        if not pipeline_id and name:
            pipeline = self.client.get_pipeline_by_name(name)
            if not pipeline:
                return ActionResult(
                    success=False,
                    message=f"Pipeline not found: {name}",
                )
            pipeline_id = pipeline.get("id")

        if not pipeline_id:
            return ActionResult(
                success=False,
                message="Pipeline ID or name is required.",
            )

        try:
            positions = self.client.get_pipeline_position(pipeline_id)
            if not positions:
                return ActionResult(
                    success=True,
                    message=f"No position data for pipeline {pipeline_id}. Note: Position is only available for log-based pipelines.",
                    data=[],
                )

            lines = [f"📍 Pipeline position for {name or pipeline_id}:", ""]
            for pos in positions:
                pos_type = pos.get("type", "UNKNOWN")
                display = pos.get("display_position", "N/A")
                file_name = pos.get("file_name", "")
                lines.append(f"  Type: {pos_type}")
                lines.append(f"  Position: {display}")
                if file_name:
                    lines.append(f"  File: {file_name}")
                lines.append("")

            return ActionResult(
                success=True,
                message="\n".join(lines),
                data=positions,
            )
        except APIError as e:
            if e.status_code == 400:
                return ActionResult(
                    success=False,
                    message="Position is only defined for log-based pipelines.",
                )
            raise

    def _update_pipeline_position(self, params: dict) -> ActionResult:
        """Update position for a log-based pipeline."""
        pipeline_id = params.get("id") or params.get("pipeline_id")
        name = params.get("name")
        file_name = params.get("file_name")
        offset = params.get("offset")

        if not pipeline_id and name:
            pipeline = self.client.get_pipeline_by_name(name)
            if not pipeline:
                return ActionResult(
                    success=False,
                    message=f"Pipeline not found: {name}",
                )
            pipeline_id = pipeline.get("id")

        if not pipeline_id:
            return ActionResult(
                success=False,
                message="Pipeline ID or name is required.",
            )

        if file_name is None and offset is None:
            return ActionResult(
                success=False,
                message="At least one of file_name or offset is required.",
            )

        try:
            offset_int = int(offset) if offset is not None else None
        except (ValueError, TypeError):
            return ActionResult(
                success=False,
                message="Offset must be an integer.",
            )

        try:
            self.client.update_pipeline_position(
                pipeline_id=pipeline_id,
                file_name=file_name,
                offset=offset_int,
            )
            msg_parts = []
            if file_name:
                msg_parts.append(f"file_name={file_name}")
            if offset_int is not None:
                msg_parts.append(f"offset={offset_int}")
            return ActionResult(
                success=True,
                message=f"✓ Pipeline position updated: {', '.join(msg_parts)}",
            )
        except APIError as e:
            if e.status_code == 400:
                return ActionResult(
                    success=False,
                    message="Position update is only available for log-based pipelines.",
                )
            raise

    def _update_pipeline_source(self, params: dict) -> ActionResult:
        """Update pipeline source configuration."""
        pipeline_id = params.get("id") or params.get("pipeline_id")
        name = params.get("name")
        source_config = params.get("source_config")

        if not pipeline_id and name:
            pipeline = self.client.get_pipeline_by_name(name)
            if not pipeline:
                return ActionResult(
                    success=False,
                    message=f"Pipeline not found: {name}",
                )
            pipeline_id = pipeline.get("id")

        if not pipeline_id:
            return ActionResult(
                success=False,
                message="Pipeline ID or name is required.",
            )

        if not source_config:
            return ActionResult(
                success=False,
                message="Source configuration is required.",
            )

        self.client.update_pipeline_source(pipeline_id, source_config)
        return ActionResult(
            success=True,
            message=f"✓ Pipeline '{name or pipeline_id}' source configuration updated.",
        )

    # ==================== New Object Actions ====================

    def _get_object(self, params: dict) -> ActionResult:
        """Get object details."""
        pipeline_id = params.get("pipeline_id")
        object_name = params.get("object_name")

        if not pipeline_id or not object_name:
            return ActionResult(
                success=False,
                message="Both pipeline_id and object_name are required.",
            )

        obj = self.client.get_object(pipeline_id, object_name)
        status = obj.get("status", "UNKNOWN")
        events_count = obj.get("events_count", 0)

        return ActionResult(
            success=True,
            message=(
                f"📦 Object: {object_name}\n"
                f"Status: {status}\n"
                f"Events synced: {events_count:,}"
            ),
            data=obj,
        )

    def _pause_object(self, params: dict) -> ActionResult:
        """Pause an object."""
        pipeline_id = params.get("pipeline_id")
        object_name = params.get("object_name")

        if not pipeline_id or not object_name:
            return ActionResult(
                success=False,
                message="Both pipeline_id and object_name are required.",
            )

        self.client.pause_object(pipeline_id, object_name)
        return ActionResult(
            success=True,
            message=f"✓ Object '{object_name}' paused.",
        )

    def _resume_object(self, params: dict) -> ActionResult:
        """Resume an object."""
        pipeline_id = params.get("pipeline_id")
        object_name = params.get("object_name")

        if not pipeline_id or not object_name:
            return ActionResult(
                success=False,
                message="Both pipeline_id and object_name are required.",
            )

        self.client.resume_object(pipeline_id, object_name)
        return ActionResult(
            success=True,
            message=f"✓ Object '{object_name}' resumed.",
        )

    def _include_object(self, params: dict) -> ActionResult:
        """Include a previously skipped object."""
        pipeline_id = params.get("pipeline_id")
        object_name = params.get("object_name")

        if not pipeline_id or not object_name:
            return ActionResult(
                success=False,
                message="Both pipeline_id and object_name are required.",
            )

        self.pipelines.include_object(pipeline_id, object_name)
        return ActionResult(
            success=True,
            message=f"✓ Object '{object_name}' included.",
        )

    def _get_object_position(self, params: dict) -> ActionResult:
        """Get position for a specific object in a pipeline."""
        pipeline_id = params.get("pipeline_id")
        object_name = params.get("object_name")

        if not pipeline_id or not object_name:
            return ActionResult(
                success=False,
                message="Both pipeline_id and object_name are required.",
            )

        try:
            positions = self.client.get_object_position(pipeline_id, object_name)
            if not positions:
                return ActionResult(
                    success=True,
                    message=f"No position data for object '{object_name}'.",
                    data=[],
                )

            lines = [f"📍 Object position for '{object_name}':", ""]
            for pos in positions:
                pos_type = pos.get("type", "UNKNOWN")
                display = pos.get("display_position", "N/A")
                field = pos.get("field_name", "")
                lines.append(f"  Type: {pos_type}")
                lines.append(f"  Position: {display}")
                if field:
                    lines.append(f"  Field: {field}")
                lines.append("")

            return ActionResult(
                success=True,
                message="\n".join(lines),
                data=positions,
            )
        except APIError as e:
            if e.status_code == 400:
                return ActionResult(
                    success=False,
                    message="Position is only defined for log-based pipelines.",
                )
            raise

    def _update_object_position(self, params: dict) -> ActionResult:
        """Update position for a specific object in a pipeline."""
        pipeline_id = params.get("pipeline_id")
        object_name = params.get("object_name")
        time = params.get("time")
        month = params.get("month")
        year = params.get("year")
        key_values = params.get("key_values")

        if not pipeline_id or not object_name:
            return ActionResult(
                success=False,
                message="Both pipeline_id and object_name are required.",
            )

        if time is None and month is None and year is None and key_values is None:
            return ActionResult(
                success=False,
                message="At least one of time, month, year, or key_values is required.",
            )

        # Convert to proper types
        try:
            time_int = int(time) if time is not None else None
            month_int = int(month) if month is not None else None
            year_int = int(year) if year is not None else None
        except (ValueError, TypeError):
            return ActionResult(
                success=False,
                message="time, month, and year must be integers.",
            )

        try:
            self.client.update_object_position(
                pipeline_id=pipeline_id,
                object_name=object_name,
                time=time_int,
                month=month_int,
                year=year_int,
                key_values=key_values,
            )
            return ActionResult(
                success=True,
                message=f"✓ Object '{object_name}' position updated.",
            )
        except APIError as e:
            if e.status_code == 400:
                return ActionResult(
                    success=False,
                    message="Position update is only available for log-based pipelines.",
                )
            raise

    def _get_object_stats(self, params: dict) -> ActionResult:
        """Get statistics for a specific object."""
        pipeline_id = params.get("pipeline_id")
        object_name = params.get("object_name")

        if not pipeline_id or not object_name:
            return ActionResult(
                success=False,
                message="Both pipeline_id and object_name are required.",
            )

        stats = self.client.get_object_stats(pipeline_id, object_name)
        events = stats.get("events_count", 0)
        last_sync = stats.get("last_sync_time", "N/A")

        return ActionResult(
            success=True,
            message=(
                f"📊 Object '{object_name}' statistics:\n"
                f"Events synced: {events:,}\n"
                f"Last sync: {last_sync}"
            ),
            data=stats,
        )

    def _get_object_query_mode(self, params: dict) -> ActionResult:
        """Get query mode for a specific object."""
        pipeline_id = params.get("pipeline_id")
        object_name = params.get("object_name")

        if not pipeline_id or not object_name:
            return ActionResult(
                success=False,
                message="Both pipeline_id and object_name are required.",
            )

        result = self.client.get_object_query_mode(pipeline_id, object_name)
        query_mode = result.get("query_mode", "UNKNOWN")

        return ActionResult(
            success=True,
            message=f"📋 Object '{object_name}' query mode: {query_mode}",
            data=result,
        )

    def _update_object_query_mode(self, params: dict) -> ActionResult:
        """Update query mode for a specific object."""
        pipeline_id = params.get("pipeline_id")
        object_name = params.get("object_name")
        query_mode = params.get("query_mode")

        if not pipeline_id or not object_name:
            return ActionResult(
                success=False,
                message="Both pipeline_id and object_name are required.",
            )

        if not query_mode:
            return ActionResult(
                success=False,
                message="Query mode is required (e.g., FULL_DUMP, INCREMENTAL).",
            )

        self.client.update_object_query_mode(pipeline_id, object_name, query_mode.upper())
        return ActionResult(
            success=True,
            message=f"✓ Object '{object_name}' query mode updated to {query_mode.upper()}.",
        )

    # ==================== New Destination Actions ====================

    def _get_destination(self, params: dict) -> ActionResult:
        """Get destination details."""
        destination_id = params.get("id")
        name = params.get("name")

        if not destination_id and name:
            dest = self.destinations.get_by_name(name)
            if not dest:
                return ActionResult(
                    success=False,
                    message=f"Destination not found: {name}",
                )
            destination_id = dest.id

        if not destination_id:
            return ActionResult(
                success=False,
                message="Destination ID or name is required.",
            )

        dest = self.destinations.get(destination_id)
        if not dest:
            return ActionResult(
                success=False,
                message=f"Destination not found: {destination_id}",
            )

        return ActionResult(
            success=True,
            message=(
                f"🎯 Destination: {dest.name}\n"
                f"Type: {dest.type}\n"
                f"Status: {dest.status}"
            ),
            data=dest,
        )

    def _create_destination(self, params: dict) -> ActionResult:
        """Create a new destination."""
        dest_type = params.get("type")
        name = params.get("name")
        config = params.get("config")

        if not dest_type:
            return ActionResult(
                success=False,
                message="Destination type is required (e.g., SNOWFLAKE, BIGQUERY, POSTGRES).",
            )

        if not name:
            return ActionResult(
                success=False,
                message="Destination name is required.",
            )

        if not config:
            return ActionResult(
                success=False,
                message="Connection configuration is required.",
            )

        result = self.destinations.create(dest_type.upper(), name, config)
        dest_id = result.get("id", "unknown")
        return ActionResult(
            success=True,
            message=f"✓ Destination '{name}' created successfully! ID: {dest_id}",
            data=result,
        )

    def _update_destination(self, params: dict) -> ActionResult:
        """Update destination configuration."""
        destination_id = params.get("id")
        dest_name = params.get("dest_name")
        new_name = params.get("name")
        config = params.get("config")

        if not destination_id and dest_name:
            dest = self.destinations.get_by_name(dest_name)
            if not dest:
                return ActionResult(
                    success=False,
                    message=f"Destination not found: {dest_name}",
                )
            destination_id = dest.id

        if not destination_id:
            return ActionResult(
                success=False,
                message="Destination ID or name (dest_name) is required.",
            )

        if not new_name and not config:
            return ActionResult(
                success=False,
                message="At least one of name or config is required.",
            )

        self.client.update_destination(destination_id, name=new_name, config=config)
        return ActionResult(
            success=True,
            message=f"✓ Destination '{dest_name or destination_id}' updated.",
        )

    def _get_destination_stats(self, params: dict) -> ActionResult:
        """Get destination table statistics."""
        destination_id = params.get("destination_id")
        table_name = params.get("table_name")

        if not destination_id or not table_name:
            return ActionResult(
                success=False,
                message="Both destination_id and table_name are required.",
            )

        stats = self.destinations.get_table_stats(destination_id, table_name)
        rows = stats.get("row_count", 0)
        size = stats.get("size_bytes", 0)

        return ActionResult(
            success=True,
            message=(
                f"📊 Table '{table_name}' statistics:\n"
                f"Rows: {rows:,}\n"
                f"Size: {size / (1024*1024):.2f} MB"
            ),
            data=stats,
        )

    def _load_destination(self, params: dict) -> ActionResult:
        """Load events to destination immediately."""
        destination_id = params.get("destination_id")

        if not destination_id:
            return ActionResult(
                success=False,
                message="Destination ID is required.",
            )

        self.destinations.load_now(destination_id)
        return ActionResult(
            success=True,
            message=f"✓ Load triggered for destination {destination_id}.",
        )

    # ==================== New Model Actions ====================

    def _get_model(self, params: dict) -> ActionResult:
        """Get model details."""
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

        model = self.models.get(model_id)
        if not model:
            return ActionResult(
                success=False,
                message=f"Model not found: {model_id}",
            )

        return ActionResult(
            success=True,
            message=(
                f"📐 Model: {model.name}\n"
                f"Status: {model.status}\n"
                f"Schedule: {model.schedule}\n"
                f"Destination ID: {model.destination_id}"
            ),
            data=model,
        )

    def _create_model(self, params: dict) -> ActionResult:
        """Create a new model."""
        source_destination_id = params.get("source_destination_id") or params.get("destination_id")
        name = params.get("name")
        query = params.get("query") or params.get("source_query")
        table_name = params.get("table_name") or params.get("target_table")
        primary_keys = params.get("primary_keys")
        load_type = params.get("load_type", "TRUNCATE_AND_LOAD")
        schedule = params.get("schedule")

        if not source_destination_id:
            return ActionResult(
                success=False,
                message="Source destination ID (source_destination_id) is required.",
            )

        if not name:
            return ActionResult(
                success=False,
                message="Model name is required.",
            )

        if not query:
            return ActionResult(
                success=False,
                message="SQL query (source_query) is required.",
            )

        if not table_name:
            return ActionResult(
                success=False,
                message="Table name (table_name) is required.",
            )

        # Validate load_type
        valid_load_types = ["TRUNCATE_AND_LOAD", "INCREMENTAL_LOAD"]
        if load_type.upper() not in valid_load_types:
            return ActionResult(
                success=False,
                message=f"Invalid load_type. Must be one of: {', '.join(valid_load_types)}",
            )

        result = self.models.create(
            source_destination_id=int(source_destination_id),
            name=name,
            source_query=query,
            table_name=table_name,
            primary_keys=primary_keys,
            load_type=load_type.upper(),
            schedule=schedule,
        )
        model_id = result.get("id", "unknown")
        return ActionResult(
            success=True,
            message=f"✓ Model '{name}' created successfully! ID: {model_id}",
            data=result,
        )

    def _update_model(self, params: dict) -> ActionResult:
        """Update a model."""
        model_id = params.get("id")
        name = params.get("name")
        new_name = params.get("new_name")
        query = params.get("query") or params.get("source_query")
        table_name = params.get("table_name") or params.get("target_table")
        primary_keys = params.get("primary_keys")
        load_type = params.get("load_type")

        if not model_id and not name:
            return ActionResult(
                success=False,
                message="Model ID or name is required.",
            )

        # Validate load_type if provided
        if load_type:
            valid_load_types = ["TRUNCATE_AND_LOAD", "INCREMENTAL_LOAD"]
            if load_type.upper() not in valid_load_types:
                return ActionResult(
                    success=False,
                    message=f"Invalid load_type. Must be one of: {', '.join(valid_load_types)}",
                )
            load_type = load_type.upper()

        try:
            self.models.update(
                model_id=model_id,
                name=name,
                new_name=new_name,
                source_query=query,
                table_name=table_name,
                primary_keys=primary_keys,
                load_type=load_type,
            )
            return ActionResult(
                success=True,
                message=f"✓ Model '{name or model_id}' updated.",
            )
        except ValueError as e:
            return ActionResult(success=False, message=str(e))

    def _delete_model(self, params: dict) -> ActionResult:
        """Delete a model."""
        model_id = params.get("id")
        name = params.get("name")
        confirmed = params.get("confirmed", False)

        if not confirmed:
            return ActionResult(
                success=False,
                message=(
                    "⚠️ Deleting a model is permanent and cannot be undone.\n\n"
                    "To confirm, use: {\"action\": \"delete_model\", \"params\": {"
                    f"\"{'name' if name else 'id'}\": \"{name or model_id}\", \"confirmed\": true}}"
                ),
            )

        try:
            self.models.delete(model_id=model_id, name=name)
            return ActionResult(
                success=True,
                message=f"✓ Model '{name or model_id}' deleted.",
            )
        except ValueError as e:
            return ActionResult(success=False, message=str(e))

    def _pause_model(self, params: dict) -> ActionResult:
        """Pause a model."""
        model_id = params.get("id")
        name = params.get("name")

        try:
            self.models.pause(model_id=model_id, name=name)
            return ActionResult(
                success=True,
                message=f"✓ Model '{name or model_id}' paused.",
            )
        except ValueError as e:
            return ActionResult(success=False, message=str(e))

    def _resume_model(self, params: dict) -> ActionResult:
        """Resume a model."""
        model_id = params.get("id")
        name = params.get("name")

        try:
            self.models.resume(model_id=model_id, name=name)
            return ActionResult(
                success=True,
                message=f"✓ Model '{name or model_id}' resumed.",
            )
        except ValueError as e:
            return ActionResult(success=False, message=str(e))

    def _reset_model(self, params: dict) -> ActionResult:
        """Reset a model (clear processed data)."""
        model_id = params.get("id")
        name = params.get("name")
        confirmed = params.get("confirmed", False)

        if not confirmed:
            return ActionResult(
                success=False,
                message=(
                    "⚠️ Resetting a model will clear all processed data. "
                    "The next run will reprocess everything from scratch.\n\n"
                    "To confirm, use: {\"action\": \"reset_model\", \"params\": {"
                    f"\"{'name' if name else 'id'}\": \"{name or model_id}\", \"confirmed\": true}}"
                ),
            )

        try:
            self.models.reset(model_id=model_id, name=name)
            return ActionResult(
                success=True,
                message=f"✓ Model '{name or model_id}' reset.",
            )
        except ValueError as e:
            return ActionResult(success=False, message=str(e))

    def _update_model_schedule(self, params: dict) -> ActionResult:
        """Update model schedule configuration."""
        model_id = params.get("id")
        name = params.get("name")
        schedule_config = params.get("schedule_config")

        if not model_id and name:
            model = self.models.get_by_name(name)
            if not model:
                return ActionResult(
                    success=False,
                    message=f"Model not found: {name}",
                )
            model_id = model.id

        if not model_id:
            return ActionResult(
                success=False,
                message="Model ID or name is required.",
            )

        if not schedule_config:
            return ActionResult(
                success=False,
                message="Schedule configuration is required (e.g., {type, frequency, cron_expression}).",
            )

        self.client.update_model_schedule(model_id, schedule_config)
        return ActionResult(
            success=True,
            message=f"✓ Model '{name or model_id}' schedule updated.",
        )

    # ==================== New Workflow Actions ====================

    def _get_workflow(self, params: dict) -> ActionResult:
        """Get workflow details."""
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

        workflow = self.workflows.get(workflow_id)
        if not workflow:
            return ActionResult(
                success=False,
                message=f"Workflow not found: {workflow_id}",
            )

        return ActionResult(
            success=True,
            message=(
                f"🔄 Workflow: {workflow.name}\n"
                f"Status: {workflow.status}\n"
                f"Last run: {workflow.last_run_status}"
            ),
            data=workflow,
        )

    # ==================== Transformation Actions ====================

    def _get_transformation(self, params: dict) -> ActionResult:
        """Get transformation code for a pipeline."""
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

        if not pipeline_id:
            return ActionResult(
                success=False,
                message="Pipeline ID or name is required.",
            )

        transform = self.client.get_transformation(pipeline_id)
        code = transform.get("code", "No transformation configured")

        return ActionResult(
            success=True,
            message=f"🔧 Transformation for pipeline {pipeline_id}:\n\n```python\n{code}\n```",
            data=transform,
        )

    def _update_transformation(self, params: dict) -> ActionResult:
        """Update transformation code."""
        pipeline_id = params.get("pipeline_id")
        code = params.get("code")

        if not pipeline_id:
            return ActionResult(
                success=False,
                message="Pipeline ID is required.",
            )

        if not code:
            return ActionResult(
                success=False,
                message="Transformation code is required.",
            )

        self.client.update_transformation(pipeline_id, code)
        return ActionResult(
            success=True,
            message=f"✓ Transformation updated for pipeline {pipeline_id}.",
        )

    def _test_transformation(self, params: dict) -> ActionResult:
        """Test transformation code."""
        pipeline_id = params.get("pipeline_id")
        sample_data = params.get("sample_data")

        if not pipeline_id:
            return ActionResult(
                success=False,
                message="Pipeline ID is required.",
            )

        result = self.client.test_transformation(pipeline_id, sample_data)
        success = result.get("success", False)
        output = result.get("output", "No output")
        errors = result.get("errors", [])

        if success:
            return ActionResult(
                success=True,
                message=f"✓ Transformation test passed!\n\nOutput:\n{output}",
                data=result,
            )
        else:
            error_msg = "\n".join(errors) if errors else "Unknown error"
            return ActionResult(
                success=False,
                message=f"❌ Transformation test failed:\n{error_msg}",
                data=result,
            )

    def _get_transformation_sample(self, params: dict) -> ActionResult:
        """Get sample data for transformation testing."""
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

        if not pipeline_id:
            return ActionResult(
                success=False,
                message="Pipeline ID or name is required.",
            )

        sample = self.client.get_transformation_sample(pipeline_id)
        return ActionResult(
            success=True,
            message=f"📋 Sample data for transformation:\n\n```json\n{sample}\n```",
            data=sample,
        )

    # ==================== Event Type Actions ====================

    def _list_event_types(self, params: dict) -> ActionResult:
        """List all event types in a pipeline."""
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

        if not pipeline_id:
            return ActionResult(
                success=False,
                message="Pipeline ID or name is required.",
            )

        event_types = self.client.list_event_types(pipeline_id)

        if not event_types:
            return ActionResult(
                success=True,
                message="No event types found in this pipeline.",
                data=[],
            )

        lines = [
            f"Found {len(event_types)} event types:",
            "",
            "| Event Type | Status |",
            "|------------|--------|",
        ]

        for et in event_types:
            et_name = et.get("name", "Unknown")
            status = et.get("status", "UNKNOWN")
            lines.append(f"| {et_name} | {status} |")

        return ActionResult(
            success=True,
            message="\n".join(lines),
            data=event_types,
        )

    def _skip_event_type(self, params: dict) -> ActionResult:
        """Skip an event type."""
        pipeline_id = params.get("pipeline_id")
        event_type = params.get("event_type")

        if not pipeline_id or not event_type:
            return ActionResult(
                success=False,
                message="Both pipeline_id and event_type are required.",
            )

        self.client.skip_event_type(pipeline_id, event_type)
        return ActionResult(
            success=True,
            message=f"✓ Event type '{event_type}' skipped.",
        )

    def _include_event_type(self, params: dict) -> ActionResult:
        """Include a previously skipped event type."""
        pipeline_id = params.get("pipeline_id")
        event_type = params.get("event_type")

        if not pipeline_id or not event_type:
            return ActionResult(
                success=False,
                message="Both pipeline_id and event_type are required.",
            )

        self.client.include_event_type(pipeline_id, event_type)
        return ActionResult(
            success=True,
            message=f"✓ Event type '{event_type}' included.",
        )

    # ==================== Schema Mapping Actions ====================

    def _update_auto_mapping(self, params: dict) -> ActionResult:
        """Enable or disable auto-mapping."""
        pipeline_id = params.get("pipeline_id")
        enabled = params.get("enabled")

        if not pipeline_id:
            return ActionResult(
                success=False,
                message="Pipeline ID is required.",
            )

        if enabled is None:
            return ActionResult(
                success=False,
                message="Enabled flag (true/false) is required.",
            )

        self.client.update_auto_mapping(pipeline_id, bool(enabled))
        status = "enabled" if enabled else "disabled"
        return ActionResult(
            success=True,
            message=f"✓ Auto-mapping {status} for pipeline {pipeline_id}.",
        )

    def _get_schema_mapping(self, params: dict) -> ActionResult:
        """Get schema mapping for an event type."""
        pipeline_id = params.get("pipeline_id")
        event_type = params.get("event_type")

        if not pipeline_id or not event_type:
            return ActionResult(
                success=False,
                message="Both pipeline_id and event_type are required.",
            )

        mapping = self.client.get_schema_mapping(pipeline_id, event_type)
        return ActionResult(
            success=True,
            message=f"Schema mapping for '{event_type}':\n```json\n{mapping}\n```",
            data=mapping,
        )

    def _update_schema_mapping(self, params: dict) -> ActionResult:
        """Update schema mapping for an event type."""
        pipeline_id = params.get("pipeline_id")
        event_type = params.get("event_type")
        mapping = params.get("mapping")

        if not pipeline_id or not event_type:
            return ActionResult(
                success=False,
                message="Both pipeline_id and event_type are required.",
            )

        if not mapping:
            return ActionResult(
                success=False,
                message="Mapping configuration is required.",
            )

        self.client.update_schema_mapping(pipeline_id, event_type, mapping)
        return ActionResult(
            success=True,
            message=f"✓ Schema mapping updated for '{event_type}'.",
        )

    # ==================== User Management Actions ====================

    def _list_users(self, params: dict) -> ActionResult:
        """List all users in the team."""
        users = self.client.list_users()

        if not users:
            return ActionResult(
                success=True,
                message="No users found.",
                data=[],
            )

        lines = [
            f"Found {len(users)} team members:",
            "",
            "| Email | Role | Status |",
            "|-------|------|--------|",
        ]

        for user in users:
            email = user.get("email", "Unknown")
            role = user.get("role", "UNKNOWN")
            status = user.get("status", "UNKNOWN")
            lines.append(f"| {email} | {role} | {status} |")

        return ActionResult(
            success=True,
            message="\n".join(lines),
            data=users,
        )

    def _invite_user(self, params: dict) -> ActionResult:
        """Invite a user to the team."""
        email = params.get("email")
        role = params.get("role", "MEMBER")

        if not email:
            return ActionResult(
                success=False,
                message="Email is required.",
            )

        if role.upper() not in ("OWNER", "ADMIN", "MEMBER", "VIEWER"):
            return ActionResult(
                success=False,
                message="Role must be OWNER, ADMIN, MEMBER, or VIEWER.",
            )

        self.client.invite_user(email, role.upper())
        return ActionResult(
            success=True,
            message=f"✓ Invitation sent to {email} as {role}.",
        )

    def _update_user_role(self, params: dict) -> ActionResult:
        """Update a user's role."""
        user_id = params.get("user_id")
        role = params.get("role")

        if not user_id:
            return ActionResult(
                success=False,
                message="User ID is required.",
            )

        if not role:
            return ActionResult(
                success=False,
                message="Role is required (OWNER, ADMIN, MEMBER, or VIEWER).",
            )

        if role.upper() not in ("OWNER", "ADMIN", "MEMBER", "VIEWER"):
            return ActionResult(
                success=False,
                message="Role must be OWNER, ADMIN, MEMBER, or VIEWER.",
            )

        self.client.update_user_role(user_id, role.upper())
        return ActionResult(
            success=True,
            message=f"✓ User role updated to {role}.",
        )

    def _delete_user(self, params: dict) -> ActionResult:
        """Remove a user from the team."""
        user_id = params.get("user_id")
        confirmed = params.get("confirmed", False)

        if not user_id:
            return ActionResult(
                success=False,
                message="User ID is required.",
            )

        if not confirmed:
            return ActionResult(
                success=False,
                message=(
                    "⚠️ Removing a user will revoke their access to this team.\n\n"
                    "To confirm, use: {\"action\": \"delete_user\", \"params\": {"
                    f"\"user_id\": \"{user_id}\", \"confirmed\": true}}"
                ),
            )

        self.client.delete_user(user_id)
        return ActionResult(
            success=True,
            message=f"✓ User {user_id} removed from team.",
        )

    # ==================== OAuth Account Actions ====================

    def _list_oauth_accounts(self, params: dict) -> ActionResult:
        """List all OAuth accounts."""
        accounts = self.client.list_oauth_accounts()

        if not accounts:
            return ActionResult(
                success=True,
                message="No OAuth accounts found.",
                data=[],
            )

        lines = [
            f"Found {len(accounts)} OAuth accounts:",
            "",
            "| Name | Provider | Status |",
            "|------|----------|--------|",
        ]

        for account in accounts:
            name = account.get("name", "Unknown")
            provider = account.get("provider", "Unknown")
            status = account.get("status", "UNKNOWN")
            lines.append(f"| {name} | {provider} | {status} |")

        return ActionResult(
            success=True,
            message="\n".join(lines),
            data=accounts,
        )

    def _get_oauth_account(self, params: dict) -> ActionResult:
        """Get OAuth account details."""
        account_id = params.get("id")

        if not account_id:
            return ActionResult(
                success=False,
                message="OAuth account ID is required.",
            )

        account = self.client.get_oauth_account(account_id)
        name = account.get("name", "Unknown")
        provider = account.get("provider", "Unknown")
        status = account.get("status", "UNKNOWN")

        return ActionResult(
            success=True,
            message=(
                f"🔐 OAuth Account: {name}\n"
                f"Provider: {provider}\n"
                f"Status: {status}"
            ),
            data=account,
        )

    def _remove_oauth_account(self, params: dict) -> ActionResult:
        """Remove an OAuth account."""
        account_id = params.get("id")
        confirmed = params.get("confirmed", False)

        if not account_id:
            return ActionResult(
                success=False,
                message="OAuth account ID is required.",
            )

        if not confirmed:
            return ActionResult(
                success=False,
                message=(
                    "⚠️ Removing an OAuth account may break pipelines that use it.\n\n"
                    "To confirm, use: {\"action\": \"remove_oauth_account\", \"params\": {"
                    f"\"id\": \"{account_id}\", \"confirmed\": true}}"
                ),
            )

        self.client.delete_oauth_account(account_id)
        return ActionResult(
            success=True,
            message=f"✓ OAuth account {account_id} removed.",
        )


def get_action_executor() -> ActionExecutor:
    """Get an ActionExecutor instance."""
    return ActionExecutor()
