"""
Hevo capabilities registry.

Defines all available actions with their parameters, prerequisites, examples,
and follow-up suggestions.
"""

from dataclasses import dataclass, field
from enum import Enum
from typing import Optional, List, Dict, Any


class ActionCategory(Enum):
    """Categories of Hevo API actions."""
    PIPELINES = "Pipelines"
    OBJECTS = "Pipeline Objects"
    TRANSFORMATIONS = "Transformations"
    SCHEMA_MAPPING = "Schema Mapping"
    EVENT_TYPES = "Event Types"
    DESTINATIONS = "Destinations"
    MODELS = "Models"
    WORKFLOWS = "Workflows"
    USERS = "Team Management"
    OAUTH = "OAuth Accounts"


@dataclass
class Parameter:
    """Definition of an action parameter."""
    name: str
    description: str
    required: bool = True
    param_type: str = "string"
    example: Optional[str] = None

    def __str__(self) -> str:
        req = "(required)" if self.required else "(optional)"
        ex = f" e.g., {self.example}" if self.example else ""
        return f"{self.name} {req}: {self.description}{ex}"


@dataclass
class ActionDefinition:
    """Definition of an available action."""
    name: str
    description: str
    category: ActionCategory
    method: str = "GET"
    endpoint: str = ""
    parameters: List[Parameter] = field(default_factory=list)
    examples: List[str] = field(default_factory=list)
    follow_ups: List[str] = field(default_factory=list)
    implemented: bool = True  # Whether this action is currently implemented


# ============================================================================
# CAPABILITIES REGISTRY
# ============================================================================

CAPABILITIES: Dict[str, ActionDefinition] = {
    # =========================================================================
    # PIPELINES
    # =========================================================================
    "list_pipelines": ActionDefinition(
        name="list_pipelines",
        description="List all pipelines in your account (optionally filter by status)",
        category=ActionCategory.PIPELINES,
        method="GET",
        endpoint="/pipelines",
        parameters=[
            Parameter("status", "Filter by status: ACTIVE, PAUSED, or DRAFT", required=False, example="ACTIVE"),
        ],
        examples=[
            "Show all my pipelines",
            "List pipelines",
            "What pipelines do I have?",
            "List my active pipelines",
            "Show paused pipelines",
        ],
        follow_ups=["get_pipeline", "run_pipeline"],
    ),
    "get_pipeline": ActionDefinition(
        name="get_pipeline",
        description="Get details for a specific pipeline",
        category=ActionCategory.PIPELINES,
        method="GET",
        endpoint="/pipelines/{id}",
        parameters=[
            Parameter("name", "Pipeline name", required=False, example="Salesforce_to_Snowflake"),
            Parameter("id", "Pipeline ID", required=False, example="12345"),
        ],
        examples=[
            "Check status of Salesforce pipeline",
            "Show me pipeline details",
            "What's the status of my MySQL pipeline?",
        ],
        follow_ups=["list_objects", "pause_pipeline", "run_pipeline"],
    ),
    "create_pipeline": ActionDefinition(
        name="create_pipeline",
        description="Create a new pipeline",
        category=ActionCategory.PIPELINES,
        method="POST",
        endpoint="/pipelines",
        parameters=[
            Parameter("source_type", "Type of source connector", required=True, example="MYSQL"),
            Parameter("source_config", "Source connection configuration", required=True),
            Parameter("destination_id", "ID of the destination", required=True, example="123"),
            Parameter("name", "Pipeline name", required=False, example="MySQL_to_Snowflake"),
        ],
        examples=[
            "Create a new pipeline",
            "Set up MySQL to Snowflake pipeline",
            "Create pipeline from Postgres to BigQuery",
        ],
        follow_ups=["list_objects", "run_pipeline", "get_pipeline"],
        implemented=True,
    ),
    "delete_pipeline": ActionDefinition(
        name="delete_pipeline",
        description="Delete a pipeline",
        category=ActionCategory.PIPELINES,
        method="DELETE",
        endpoint="/pipelines/{id}",
        parameters=[
            Parameter("id", "Pipeline ID", required=True, example="12345"),
            Parameter("name", "Pipeline name", required=False, example="Salesforce_to_Snowflake"),
            Parameter("confirmed", "Confirmation flag", required=True, param_type="boolean"),
        ],
        examples=["Delete the pipeline", "Remove my old pipeline"],
        follow_ups=["list_pipelines"],
        implemented=True,
    ),
    "pause_pipeline": ActionDefinition(
        name="pause_pipeline",
        description="Pause a pipeline (stops data ingestion)",
        category=ActionCategory.PIPELINES,
        method="PUT",
        endpoint="/pipelines/{id}/status",
        parameters=[
            Parameter("name", "Pipeline name", required=False, example="Salesforce_to_Snowflake"),
            Parameter("id", "Pipeline ID", required=False, example="12345"),
        ],
        examples=[
            "Pause the Salesforce pipeline",
            "Stop my MySQL pipeline",
            "Halt the data sync",
        ],
        follow_ups=["resume_pipeline", "list_pipelines"],
    ),
    "resume_pipeline": ActionDefinition(
        name="resume_pipeline",
        description="Resume a paused pipeline",
        category=ActionCategory.PIPELINES,
        method="PUT",
        endpoint="/pipelines/{id}/status",
        parameters=[
            Parameter("name", "Pipeline name", required=False, example="Salesforce_to_Snowflake"),
            Parameter("id", "Pipeline ID", required=False, example="12345"),
        ],
        examples=[
            "Resume the Salesforce pipeline",
            "Start my MySQL pipeline again",
            "Unpause the sync",
        ],
        follow_ups=["run_pipeline", "get_pipeline"],
    ),
    "run_pipeline": ActionDefinition(
        name="run_pipeline",
        description="Run a pipeline immediately (trigger sync now)",
        category=ActionCategory.PIPELINES,
        method="POST",
        endpoint="/pipelines/{id}/run-now",
        parameters=[
            Parameter("name", "Pipeline name", required=False, example="Salesforce_to_Snowflake"),
            Parameter("id", "Pipeline ID", required=False, example="12345"),
        ],
        examples=[
            "Run the Salesforce pipeline now",
            "Sync my MySQL data immediately",
            "Trigger the pipeline",
        ],
        follow_ups=["get_pipeline", "list_objects"],
    ),
    "update_pipeline_schedule": ActionDefinition(
        name="update_pipeline_schedule",
        description="Update pipeline sync schedule",
        category=ActionCategory.PIPELINES,
        method="PUT",
        endpoint="/pipelines/{id}/schedule",
        parameters=[
            Parameter("id", "Pipeline ID", required=False, example="12345"),
            Parameter("name", "Pipeline name", required=False, example="Salesforce_to_Snowflake"),
            Parameter("schedule", "Schedule configuration", required=True),
        ],
        examples=["Change pipeline schedule", "Update sync frequency"],
        follow_ups=["get_pipeline"],
        implemented=True,
    ),
    "update_pipeline_priority": ActionDefinition(
        name="update_pipeline_priority",
        description="Update pipeline priority (HIGH, NORMAL, LOW)",
        category=ActionCategory.PIPELINES,
        method="PUT",
        endpoint="/pipelines/{id}/priority",
        parameters=[
            Parameter("id", "Pipeline ID", required=False, example="12345"),
            Parameter("name", "Pipeline name", required=False, example="Salesforce_to_Snowflake"),
            Parameter("priority", "Priority level", required=True, example="HIGH"),
        ],
        examples=["Set pipeline priority to high", "Change priority"],
        follow_ups=["get_pipeline"],
        implemented=True,
    ),
    "get_pipeline_schedule": ActionDefinition(
        name="get_pipeline_schedule",
        description="Get pipeline schedule configuration",
        category=ActionCategory.PIPELINES,
        method="GET",
        endpoint="/pipelines/{id}/schedule",
        parameters=[
            Parameter("id", "Pipeline ID", required=False, example="12345"),
            Parameter("name", "Pipeline name", required=False, example="Salesforce_to_Snowflake"),
        ],
        examples=["Show pipeline schedule", "Get sync frequency"],
        follow_ups=["update_pipeline_schedule"],
        implemented=True,
    ),

    # =========================================================================
    # PIPELINE OBJECTS
    # =========================================================================
    "list_objects": ActionDefinition(
        name="list_objects",
        description="List all objects (tables) in a pipeline",
        category=ActionCategory.OBJECTS,
        method="GET",
        endpoint="/pipelines/{id}/objects",
        parameters=[
            Parameter("pipeline_name", "Pipeline name", required=False, example="Salesforce_to_Snowflake"),
            Parameter("pipeline_id", "Pipeline ID", required=False, example="12345"),
        ],
        examples=[
            "Show objects in my Salesforce pipeline",
            "List tables being synced",
            "What tables are in this pipeline?",
        ],
        follow_ups=["skip_object", "restart_object"],
    ),
    "pause_object": ActionDefinition(
        name="pause_object",
        description="Pause syncing for a specific object",
        category=ActionCategory.OBJECTS,
        method="POST",
        endpoint="/pipelines/{id}/objects/{name}/pause",
        parameters=[
            Parameter("pipeline_id", "Pipeline ID", required=True, example="12345"),
            Parameter("object_name", "Object/table name", required=True, example="users"),
        ],
        examples=["Pause the users table", "Stop syncing orders"],
        follow_ups=["resume_object", "list_objects"],
    ),
    "resume_object": ActionDefinition(
        name="resume_object",
        description="Resume syncing for a paused object",
        category=ActionCategory.OBJECTS,
        method="POST",
        endpoint="/pipelines/{id}/objects/{name}/resume",
        parameters=[
            Parameter("pipeline_id", "Pipeline ID", required=True, example="12345"),
            Parameter("object_name", "Object/table name", required=True, example="users"),
        ],
        examples=["Resume the users table", "Start syncing orders again"],
        follow_ups=["list_objects"],
    ),
    "skip_object": ActionDefinition(
        name="skip_object",
        description="Skip (exclude) an object from syncing",
        category=ActionCategory.OBJECTS,
        method="POST",
        endpoint="/pipelines/{id}/objects/{name}/skip",
        parameters=[
            Parameter("pipeline_id", "Pipeline ID", required=True, example="12345"),
            Parameter("object_name", "Object/table name", required=True, example="audit_logs"),
        ],
        examples=[
            "Skip the audit_logs table",
            "Exclude this table from sync",
            "Don't sync the temp table",
        ],
        follow_ups=["include_object", "list_objects"],
    ),
    "include_object": ActionDefinition(
        name="include_object",
        description="Include a previously skipped object",
        category=ActionCategory.OBJECTS,
        method="POST",
        endpoint="/pipelines/{id}/objects/{name}/include",
        parameters=[
            Parameter("pipeline_id", "Pipeline ID", required=True, example="12345"),
            Parameter("object_name", "Object/table name", required=True, example="audit_logs"),
        ],
        examples=["Include the audit_logs table again", "Start syncing this table"],
        follow_ups=["list_objects", "restart_object"],
        implemented=True,
    ),
    "get_object": ActionDefinition(
        name="get_object",
        description="Get details for a specific object",
        category=ActionCategory.OBJECTS,
        method="GET",
        endpoint="/pipelines/{id}/objects/{name}",
        parameters=[
            Parameter("pipeline_id", "Pipeline ID", required=True, example="12345"),
            Parameter("object_name", "Object/table name", required=True, example="users"),
        ],
        examples=["Show object details", "Get info about users table"],
        follow_ups=["pause_object", "restart_object"],
        implemented=True,
    ),
    "restart_object": ActionDefinition(
        name="restart_object",
        description="Restart syncing for an object (full resync)",
        category=ActionCategory.OBJECTS,
        method="POST",
        endpoint="/pipelines/{id}/objects/{name}/restart",
        parameters=[
            Parameter("pipeline_id", "Pipeline ID", required=True, example="12345"),
            Parameter("object_name", "Object/table name", required=True, example="orders"),
        ],
        examples=[
            "Restart the orders table",
            "Resync the users table",
            "Do a full refresh of this table",
        ],
        follow_ups=["list_objects", "get_pipeline"],
    ),

    # =========================================================================
    # TRANSFORMATIONS
    # =========================================================================
    "get_transformation": ActionDefinition(
        name="get_transformation",
        description="Get transformation code for a pipeline",
        category=ActionCategory.TRANSFORMATIONS,
        method="GET",
        endpoint="/pipelines/{id}/transformations",
        parameters=[
            Parameter("pipeline_id", "Pipeline ID", required=True, example="12345"),
            Parameter("pipeline_name", "Pipeline name", required=False, example="Salesforce_to_Snowflake"),
        ],
        examples=["Show transformation code", "Get the transformation"],
        follow_ups=["update_transformation", "test_transformation"],
        implemented=True,
    ),
    "update_transformation": ActionDefinition(
        name="update_transformation",
        description="Update transformation code",
        category=ActionCategory.TRANSFORMATIONS,
        method="PUT",
        endpoint="/pipelines/{id}/transformations",
        parameters=[
            Parameter("pipeline_id", "Pipeline ID", required=True, example="12345"),
            Parameter("code", "Transformation code", required=True),
        ],
        examples=["Update the transformation", "Change transformation code"],
        follow_ups=["test_transformation", "get_transformation"],
        implemented=True,
    ),
    "test_transformation": ActionDefinition(
        name="test_transformation",
        description="Test transformation code with sample data",
        category=ActionCategory.TRANSFORMATIONS,
        method="POST",
        endpoint="/pipelines/{id}/transformations/test",
        parameters=[
            Parameter("pipeline_id", "Pipeline ID", required=True, example="12345"),
            Parameter("sample_data", "Sample data to test with", required=False),
        ],
        examples=["Test the transformation", "Try the transformation"],
        follow_ups=["update_transformation"],
        implemented=True,
    ),

    # =========================================================================
    # SCHEMA MAPPING
    # =========================================================================
    "get_schema_mapping": ActionDefinition(
        name="get_schema_mapping",
        description="Get schema mapping for an event type",
        category=ActionCategory.SCHEMA_MAPPING,
        method="GET",
        endpoint="/pipelines/{id}/mappings/{event_type}",
        parameters=[
            Parameter("pipeline_id", "Pipeline ID", required=True, example="12345"),
            Parameter("event_type", "Event type name", required=True, example="users"),
        ],
        examples=["Show schema mapping", "Get the mapping"],
        follow_ups=["update_schema_mapping"],
        implemented=True,
    ),
    "update_schema_mapping": ActionDefinition(
        name="update_schema_mapping",
        description="Update schema mapping for an event type",
        category=ActionCategory.SCHEMA_MAPPING,
        method="PUT",
        endpoint="/pipelines/{id}/mappings/{event_type}",
        parameters=[
            Parameter("pipeline_id", "Pipeline ID", required=True, example="12345"),
            Parameter("event_type", "Event type name", required=True, example="users"),
            Parameter("mapping", "Mapping configuration", required=True),
        ],
        examples=["Update schema mapping", "Change the mapping"],
        follow_ups=["get_schema_mapping"],
        implemented=True,
    ),
    "update_auto_mapping": ActionDefinition(
        name="update_auto_mapping",
        description="Enable/disable auto-mapping for a pipeline",
        category=ActionCategory.SCHEMA_MAPPING,
        method="PUT",
        endpoint="/pipelines/{id}/auto-mapping",
        parameters=[
            Parameter("pipeline_id", "Pipeline ID", required=True, example="12345"),
            Parameter("enabled", "Enable auto-mapping", required=True, param_type="boolean"),
        ],
        examples=["Enable auto-mapping", "Turn on auto schema mapping"],
        follow_ups=["get_pipeline"],
        implemented=True,
    ),

    # =========================================================================
    # EVENT TYPES
    # =========================================================================
    "list_event_types": ActionDefinition(
        name="list_event_types",
        description="List all event types in a pipeline",
        category=ActionCategory.EVENT_TYPES,
        method="GET",
        endpoint="/pipelines/{id}/event-types",
        parameters=[
            Parameter("pipeline_id", "Pipeline ID", required=True, example="12345"),
            Parameter("pipeline_name", "Pipeline name", required=False, example="Salesforce_to_Snowflake"),
        ],
        examples=["Show event types", "List event types"],
        follow_ups=["skip_event_type"],
        implemented=True,
    ),
    "skip_event_type": ActionDefinition(
        name="skip_event_type",
        description="Skip an event type",
        category=ActionCategory.EVENT_TYPES,
        method="POST",
        endpoint="/pipelines/{id}/event-types/{event_type}/skip",
        parameters=[
            Parameter("pipeline_id", "Pipeline ID", required=True, example="12345"),
            Parameter("event_type", "Event type name", required=True, example="debug_logs"),
        ],
        examples=["Skip this event type", "Exclude debug events"],
        follow_ups=["include_event_type", "list_event_types"],
        implemented=True,
    ),
    "include_event_type": ActionDefinition(
        name="include_event_type",
        description="Include a previously skipped event type",
        category=ActionCategory.EVENT_TYPES,
        method="POST",
        endpoint="/pipelines/{id}/event-types/{event_type}/include",
        parameters=[
            Parameter("pipeline_id", "Pipeline ID", required=True, example="12345"),
            Parameter("event_type", "Event type name", required=True, example="debug_logs"),
        ],
        examples=["Include this event type", "Start syncing these events"],
        follow_ups=["list_event_types"],
        implemented=True,
    ),

    # =========================================================================
    # DESTINATIONS
    # =========================================================================
    "list_destinations": ActionDefinition(
        name="list_destinations",
        description="List all destinations in your account",
        category=ActionCategory.DESTINATIONS,
        method="GET",
        endpoint="/destinations",
        parameters=[],
        examples=[
            "Show all destinations",
            "List my destinations",
            "What destinations do I have?",
        ],
        follow_ups=["get_destination"],
    ),
    "get_destination": ActionDefinition(
        name="get_destination",
        description="Get details for a specific destination",
        category=ActionCategory.DESTINATIONS,
        method="GET",
        endpoint="/destinations/{id}",
        parameters=[
            Parameter("id", "Destination ID", required=False, example="123"),
            Parameter("name", "Destination name", required=False, example="Production_Snowflake"),
        ],
        examples=["Show destination details", "Get my Snowflake destination"],
        follow_ups=["list_destinations", "get_destination_stats"],
        implemented=True,
    ),
    "create_destination": ActionDefinition(
        name="create_destination",
        description="Create a new destination",
        category=ActionCategory.DESTINATIONS,
        method="POST",
        endpoint="/destinations",
        parameters=[
            Parameter("type", "Destination type", required=True, example="SNOWFLAKE"),
            Parameter("name", "Destination name", required=True, example="Production_Snowflake"),
            Parameter("config", "Connection configuration", required=True),
        ],
        examples=["Create a new destination", "Add Snowflake destination"],
        follow_ups=["list_destinations"],
        implemented=True,
    ),
    "get_destination_stats": ActionDefinition(
        name="get_destination_stats",
        description="Get table statistics for a destination",
        category=ActionCategory.DESTINATIONS,
        method="GET",
        endpoint="/destinations/{id}/tables/{table_name}/stats",
        parameters=[
            Parameter("destination_id", "Destination ID", required=True, example="123"),
            Parameter("table_name", "Table name", required=True, example="users"),
        ],
        examples=["Show table stats", "Get stats for users table"],
        follow_ups=["list_destinations"],
        implemented=True,
    ),
    "load_destination": ActionDefinition(
        name="load_destination",
        description="Load events to destination immediately",
        category=ActionCategory.DESTINATIONS,
        method="POST",
        endpoint="/destinations/{id}/load-now",
        parameters=[
            Parameter("destination_id", "Destination ID", required=True, example="123"),
        ],
        examples=["Load data to destination now", "Flush to destination"],
        follow_ups=["list_destinations"],
        implemented=True,
    ),

    # =========================================================================
    # MODELS
    # =========================================================================
    "list_models": ActionDefinition(
        name="list_models",
        description="List all models in your account",
        category=ActionCategory.MODELS,
        method="GET",
        endpoint="/models",
        parameters=[],
        examples=[
            "Show all models",
            "List my models",
            "What models do I have?",
        ],
        follow_ups=["run_model"],
    ),
    "get_model": ActionDefinition(
        name="get_model",
        description="Get details for a specific model",
        category=ActionCategory.MODELS,
        method="GET",
        endpoint="/models/{id}",
        parameters=[
            Parameter("id", "Model ID", required=False, example="456"),
            Parameter("name", "Model name", required=False, example="daily_summary"),
        ],
        examples=["Show model details", "Get my revenue model"],
        follow_ups=["run_model", "update_model"],
        implemented=True,
    ),
    "create_model": ActionDefinition(
        name="create_model",
        description="Create a new model",
        category=ActionCategory.MODELS,
        method="POST",
        endpoint="/models",
        parameters=[
            Parameter("destination_id", "Destination ID", required=True, example="123"),
            Parameter("query", "SQL query", required=True),
            Parameter("name", "Model name", required=True, example="daily_summary"),
            Parameter("target_table", "Target table name", required=False, example="daily_sales"),
            Parameter("load_type", "Load type (FULL_LOAD or INCREMENTAL)", required=False, example="FULL_LOAD"),
        ],
        examples=["Create a new model", "Add a model"],
        follow_ups=["run_model", "list_models"],
        implemented=True,
    ),
    "update_model": ActionDefinition(
        name="update_model",
        description="Update a model",
        category=ActionCategory.MODELS,
        method="PUT",
        endpoint="/models/{id}",
        parameters=[
            Parameter("id", "Model ID", required=False, example="456"),
            Parameter("name", "Model name", required=False, example="daily_summary"),
            Parameter("new_name", "New model name", required=False),
            Parameter("query", "New SQL query", required=False),
            Parameter("target_table", "New target table", required=False),
        ],
        examples=["Update the model", "Change model query"],
        follow_ups=["run_model", "get_model"],
        implemented=True,
    ),
    "delete_model": ActionDefinition(
        name="delete_model",
        description="Delete a model",
        category=ActionCategory.MODELS,
        method="DELETE",
        endpoint="/models/{id}",
        parameters=[
            Parameter("id", "Model ID", required=False, example="456"),
            Parameter("name", "Model name", required=False, example="daily_summary"),
            Parameter("confirmed", "Confirmation flag", required=True, param_type="boolean"),
        ],
        examples=["Delete the model", "Remove my old model"],
        follow_ups=["list_models"],
        implemented=True,
    ),
    "pause_model": ActionDefinition(
        name="pause_model",
        description="Pause a model",
        category=ActionCategory.MODELS,
        method="PUT",
        endpoint="/models/{id}/activity-status",
        parameters=[
            Parameter("id", "Model ID", required=False, example="456"),
            Parameter("name", "Model name", required=False, example="daily_summary"),
        ],
        examples=["Pause the model", "Stop running the model"],
        follow_ups=["resume_model", "list_models"],
        implemented=True,
    ),
    "resume_model": ActionDefinition(
        name="resume_model",
        description="Resume a paused model",
        category=ActionCategory.MODELS,
        method="PUT",
        endpoint="/models/{id}/activity-status",
        parameters=[
            Parameter("id", "Model ID", required=False, example="456"),
            Parameter("name", "Model name", required=False, example="daily_summary"),
        ],
        examples=["Resume the model", "Start the model again"],
        follow_ups=["run_model", "get_model"],
        implemented=True,
    ),
    "run_model": ActionDefinition(
        name="run_model",
        description="Run a model immediately",
        category=ActionCategory.MODELS,
        method="POST",
        endpoint="/models/{id}/run-now",
        parameters=[
            Parameter("name", "Model name", required=False, example="daily_summary"),
            Parameter("id", "Model ID", required=False, example="456"),
        ],
        examples=[
            "Run the daily_summary model",
            "Execute my revenue model",
            "Trigger the model now",
        ],
        follow_ups=["list_models"],
    ),
    "reset_model": ActionDefinition(
        name="reset_model",
        description="Reset a model (clear processed data)",
        category=ActionCategory.MODELS,
        method="DELETE",
        endpoint="/models/{id}/reset",
        parameters=[
            Parameter("id", "Model ID", required=False, example="456"),
            Parameter("name", "Model name", required=False, example="daily_summary"),
            Parameter("confirmed", "Confirmation flag", required=True, param_type="boolean"),
        ],
        examples=["Reset the model", "Clear model data"],
        follow_ups=["run_model"],
        implemented=True,
    ),

    # =========================================================================
    # WORKFLOWS
    # =========================================================================
    "list_workflows": ActionDefinition(
        name="list_workflows",
        description="List all workflows in your account",
        category=ActionCategory.WORKFLOWS,
        method="GET",
        endpoint="/workflows",
        parameters=[],
        examples=[
            "Show all workflows",
            "List my workflows",
            "What workflows do I have?",
        ],
        follow_ups=["run_workflow"],
    ),
    "get_workflow": ActionDefinition(
        name="get_workflow",
        description="Get details for a specific workflow",
        category=ActionCategory.WORKFLOWS,
        method="GET",
        endpoint="/workflows/{id}",
        parameters=[
            Parameter("id", "Workflow ID", required=False, example="789"),
            Parameter("name", "Workflow name", required=False, example="nightly_etl"),
        ],
        examples=["Show workflow details", "Get my ETL workflow"],
        follow_ups=["run_workflow"],
        implemented=True,
    ),
    "run_workflow": ActionDefinition(
        name="run_workflow",
        description="Run a workflow immediately",
        category=ActionCategory.WORKFLOWS,
        method="POST",
        endpoint="/workflows/{id}/run-now",
        parameters=[
            Parameter("name", "Workflow name", required=False, example="nightly_etl"),
            Parameter("id", "Workflow ID", required=False, example="789"),
        ],
        examples=[
            "Run the nightly_etl workflow",
            "Execute my ETL workflow",
            "Trigger the workflow now",
        ],
        follow_ups=["list_workflows"],
    ),

    # =========================================================================
    # TEAM MANAGEMENT
    # =========================================================================
    "list_users": ActionDefinition(
        name="list_users",
        description="List all users in your team",
        category=ActionCategory.USERS,
        method="GET",
        endpoint="/accounts/users",
        parameters=[],
        examples=[
            "Show team members",
            "List users",
            "Who's on my team?",
        ],
        follow_ups=["invite_user"],
        implemented=True,
    ),
    "invite_user": ActionDefinition(
        name="invite_user",
        description="Invite a user to your team",
        category=ActionCategory.USERS,
        method="POST",
        endpoint="/accounts/users",
        parameters=[
            Parameter("email", "User email", required=True, example="john@company.com"),
            Parameter("role", "User role (OWNER, ADMIN, MEMBER, VIEWER)", required=False, example="MEMBER"),
        ],
        examples=["Invite john@company.com", "Add a new team member"],
        follow_ups=["list_users"],
        implemented=True,
    ),
    "update_user_role": ActionDefinition(
        name="update_user_role",
        description="Update a user's role",
        category=ActionCategory.USERS,
        method="PUT",
        endpoint="/accounts/users/{user_id}",
        parameters=[
            Parameter("user_id", "User ID", required=True, example="user123"),
            Parameter("role", "New role (OWNER, ADMIN, MEMBER, VIEWER)", required=True, example="ADMIN"),
        ],
        examples=["Make this user an admin", "Change user role"],
        follow_ups=["list_users"],
        implemented=True,
    ),
    "delete_user": ActionDefinition(
        name="delete_user",
        description="Remove a user from your team",
        category=ActionCategory.USERS,
        method="DELETE",
        endpoint="/accounts/users/{user_id}",
        parameters=[
            Parameter("user_id", "User ID", required=True, example="user123"),
            Parameter("confirmed", "Confirmation flag", required=True, param_type="boolean"),
        ],
        examples=["Remove this user", "Delete team member"],
        follow_ups=["list_users"],
        implemented=True,
    ),

    # =========================================================================
    # OAUTH ACCOUNTS
    # =========================================================================
    "list_oauth_accounts": ActionDefinition(
        name="list_oauth_accounts",
        description="List all OAuth accounts",
        category=ActionCategory.OAUTH,
        method="GET",
        endpoint="/oauth-accounts",
        parameters=[],
        examples=["Show OAuth accounts", "List connected accounts"],
        follow_ups=["get_oauth_account"],
        implemented=True,
    ),
    "get_oauth_account": ActionDefinition(
        name="get_oauth_account",
        description="Get details for an OAuth account",
        category=ActionCategory.OAUTH,
        method="GET",
        endpoint="/oauth-accounts/{id}",
        parameters=[
            Parameter("id", "OAuth account ID", required=True, example="oauth123"),
        ],
        examples=["Show OAuth account details"],
        follow_ups=["list_oauth_accounts"],
        implemented=True,
    ),
    "remove_oauth_account": ActionDefinition(
        name="remove_oauth_account",
        description="Remove an OAuth account",
        category=ActionCategory.OAUTH,
        method="DELETE",
        endpoint="/oauth-accounts/{id}",
        parameters=[
            Parameter("id", "OAuth account ID", required=True, example="oauth123"),
            Parameter("confirmed", "Confirmation flag", required=True, param_type="boolean"),
        ],
        examples=["Remove OAuth account", "Disconnect this account"],
        follow_ups=["list_oauth_accounts"],
        implemented=True,
    ),
}


# ============================================================================
# HELPER FUNCTIONS
# ============================================================================

def get_action_definition(action_name: str) -> Optional[ActionDefinition]:
    """
    Get the definition for an action.

    Args:
        action_name: Name of the action

    Returns:
        ActionDefinition or None if not found
    """
    return CAPABILITIES.get(action_name)


def get_capabilities_by_category() -> Dict[str, List[ActionDefinition]]:
    """
    Get capabilities grouped by category.

    Returns:
        Dict mapping category names to lists of ActionDefinition
    """
    grouped: Dict[str, List[ActionDefinition]] = {}
    for action in CAPABILITIES.values():
        cat = action.category.value
        if cat not in grouped:
            grouped[cat] = []
        grouped[cat].append(action)
    return grouped


def get_implemented_capabilities() -> Dict[str, ActionDefinition]:
    """
    Get only implemented capabilities.

    Returns:
        Dict of implemented actions
    """
    return {
        name: action
        for name, action in CAPABILITIES.items()
        if action.implemented
    }


def get_missing_prerequisites(
    action_name: str,
    provided_params: Dict[str, Any]
) -> List[Parameter]:
    """
    Get list of required parameters that are missing.

    Args:
        action_name: Name of the action
        provided_params: Parameters that were provided

    Returns:
        List of missing required Parameters
    """
    action = CAPABILITIES.get(action_name)
    if not action:
        return []

    missing = []
    for param in action.parameters:
        if param.required and param.name not in provided_params:
            # Check for alternative names (e.g., name vs id)
            has_alternative = False
            if param.name in ("name", "id"):
                alt_name = "id" if param.name == "name" else "name"
                if alt_name in provided_params:
                    has_alternative = True
            if not has_alternative:
                missing.append(param)

    return missing


def format_capabilities_list() -> str:
    """
    Format all capabilities for display to the user.

    Returns:
        Formatted markdown string of capabilities
    """
    grouped = get_capabilities_by_category()
    lines = ["Here's what I can help you with:\n"]

    for category, actions in grouped.items():
        lines.append(f"\n**{category}**")
        for action in actions:
            status = "" if action.implemented else " (coming soon)"
            lines.append(f"  - {action.description}{status}")

    lines.append("\n\nJust ask me in natural language! For example:")
    lines.append('  - "List my pipelines"')
    lines.append('  - "Pause the Salesforce pipeline"')
    lines.append('  - "Run my daily_summary model"')

    return "\n".join(lines)


def format_action_help(action_name: str) -> Optional[str]:
    """
    Format help text for a specific action.

    Args:
        action_name: Name of the action

    Returns:
        Formatted help string or None if action not found
    """
    action = CAPABILITIES.get(action_name)
    if not action:
        return None

    lines = [f"**{action.description}**\n"]

    if action.parameters:
        lines.append("Required information:")
        for param in action.parameters:
            req = "(required)" if param.required else "(optional)"
            ex = f" e.g., {param.example}" if param.example else ""
            lines.append(f"  - {param.name} {req}: {param.description}{ex}")

    if action.examples:
        lines.append("\nYou can say things like:")
        for ex in action.examples[:3]:
            lines.append(f'  - "{ex}"')

    return "\n".join(lines)


def get_available_actions_prompt() -> str:
    """
    Generate a prompt-friendly list of available actions.

    Returns:
        String listing available actions for system prompt
    """
    lines = ["## Available Actions\n"]

    for category in ActionCategory:
        actions = [a for a in CAPABILITIES.values() if a.category == category and a.implemented]
        if actions:
            lines.append(f"\n### {category.value}")
            for action in actions:
                params = ", ".join(p.name for p in action.parameters[:2]) if action.parameters else "none"
                lines.append(f"- {action.name}: {action.description} (params: {params})")

    return "\n".join(lines)
