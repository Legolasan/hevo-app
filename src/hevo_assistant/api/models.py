"""
Model and Workflow API operations.

Provides high-level methods for working with Hevo models and workflows.
"""

from dataclasses import dataclass
from typing import Optional

from hevo_assistant.api.client import HevoClient, get_client


@dataclass
class ModelInfo:
    """Model information."""

    id: str
    name: str
    status: str
    destination_id: str
    schedule: str

    @classmethod
    def from_api(cls, data: dict) -> "ModelInfo":
        """Create from API response."""
        return cls(
            id=str(data.get("id", "")),
            name=data.get("name", "Unknown"),
            status=data.get("status", "UNKNOWN"),
            destination_id=str(data.get("destination_id", "")),
            schedule=data.get("schedule", {}).get("type", "Unknown"),
        )


@dataclass
class WorkflowInfo:
    """Workflow information."""

    id: str
    name: str
    status: str
    last_run_status: str

    @classmethod
    def from_api(cls, data: dict) -> "WorkflowInfo":
        """Create from API response."""
        return cls(
            id=str(data.get("id", "")),
            name=data.get("name", "Unknown"),
            status=data.get("status", "UNKNOWN"),
            last_run_status=data.get("last_run_status", "Unknown"),
        )


class ModelOperations:
    """High-level model operations."""

    def __init__(self, client: Optional[HevoClient] = None):
        self.client = client or get_client()

    def list_all(self) -> list[ModelInfo]:
        """List all models."""
        models = self.client.list_models()
        return [ModelInfo.from_api(m) for m in models]

    def get(self, model_id: str) -> Optional[ModelInfo]:
        """Get model by ID."""
        try:
            data = self.client.get_model(model_id)
            return ModelInfo.from_api(data)
        except Exception:
            return None

    def run_now(self, model_id: str) -> dict:
        """Run a model immediately."""
        return self.client.run_model(model_id)

    def get_by_name(self, name: str) -> Optional[ModelInfo]:
        """Find model by name."""
        models = self.list_all()
        for model in models:
            if model.name.lower() == name.lower():
                return model
        return None

    def create(
        self,
        source_destination_id: int,
        name: str,
        source_query: str,
        table_name: str,
        primary_keys: Optional[list] = None,
        load_type: str = "TRUNCATE_AND_LOAD",
        schedule: Optional[dict] = None,
    ) -> dict:
        """
        Create a new model.

        Args:
            source_destination_id: ID of the source destination for query execution
            name: Model name
            source_query: SQL query for the model
            table_name: Destination table name
            primary_keys: List of primary key column names (optional)
            load_type: TRUNCATE_AND_LOAD or INCREMENTAL_LOAD
            schedule: Schedule config with type, frequency, cron_expression, etc.

        Returns:
            Created model data
        """
        return self.client.create_model(
            source_destination_id=source_destination_id,
            name=name,
            source_query=source_query,
            table_name=table_name,
            primary_keys=primary_keys,
            load_type=load_type,
            schedule=schedule,
        )

    def update(
        self,
        model_id: Optional[str] = None,
        name: Optional[str] = None,
        new_name: Optional[str] = None,
        source_query: Optional[str] = None,
        table_name: Optional[str] = None,
        primary_keys: Optional[list] = None,
        load_type: Optional[str] = None,
    ) -> dict:
        """
        Update a model.

        Args:
            model_id: Model ID
            name: Model name (used if ID not provided)
            new_name: New name for the model
            source_query: New SQL query
            table_name: Destination table name
            primary_keys: List of primary key column names
            load_type: TRUNCATE_AND_LOAD or INCREMENTAL_LOAD

        Returns:
            Updated model data
        """
        if not model_id and name:
            model = self.get_by_name(name)
            if not model:
                raise ValueError(f"Model not found: {name}")
            model_id = model.id

        if not model_id:
            raise ValueError("Either model_id or name is required")

        return self.client.update_model(
            model_id=model_id,
            name=new_name,
            source_query=source_query,
            table_name=table_name,
            primary_keys=primary_keys,
            load_type=load_type,
        )

    def delete(
        self,
        model_id: Optional[str] = None,
        name: Optional[str] = None,
    ) -> dict:
        """Delete a model."""
        if not model_id and name:
            model = self.get_by_name(name)
            if not model:
                raise ValueError(f"Model not found: {name}")
            model_id = model.id

        if not model_id:
            raise ValueError("Either model_id or name is required")

        return self.client.delete_model(model_id)

    def pause(
        self,
        model_id: Optional[str] = None,
        name: Optional[str] = None,
    ) -> dict:
        """Pause a model."""
        if not model_id and name:
            model = self.get_by_name(name)
            if not model:
                raise ValueError(f"Model not found: {name}")
            model_id = model.id

        if not model_id:
            raise ValueError("Either model_id or name is required")

        return self.client.update_model_status(model_id, "PAUSED")

    def resume(
        self,
        model_id: Optional[str] = None,
        name: Optional[str] = None,
    ) -> dict:
        """Resume a paused model."""
        if not model_id and name:
            model = self.get_by_name(name)
            if not model:
                raise ValueError(f"Model not found: {name}")
            model_id = model.id

        if not model_id:
            raise ValueError("Either model_id or name is required")

        return self.client.update_model_status(model_id, "ACTIVE")

    def reset(
        self,
        model_id: Optional[str] = None,
        name: Optional[str] = None,
    ) -> dict:
        """Reset a model (clear processed data)."""
        if not model_id and name:
            model = self.get_by_name(name)
            if not model:
                raise ValueError(f"Model not found: {name}")
            model_id = model.id

        if not model_id:
            raise ValueError("Either model_id or name is required")

        return self.client.reset_model(model_id)


class WorkflowOperations:
    """High-level workflow operations."""

    def __init__(self, client: Optional[HevoClient] = None):
        self.client = client or get_client()

    def list_all(self) -> list[WorkflowInfo]:
        """List all workflows."""
        workflows = self.client.list_workflows()
        return [WorkflowInfo.from_api(w) for w in workflows]

    def get(self, workflow_id: str) -> Optional[WorkflowInfo]:
        """Get workflow by ID."""
        try:
            data = self.client.get_workflow(workflow_id)
            return WorkflowInfo.from_api(data)
        except Exception:
            return None

    def run_now(self, workflow_id: str) -> dict:
        """Run a workflow immediately."""
        return self.client.run_workflow(workflow_id)

    def get_by_name(self, name: str) -> Optional[WorkflowInfo]:
        """Find workflow by name."""
        workflows = self.list_all()
        for workflow in workflows:
            if workflow.name.lower() == name.lower():
                return workflow
        return None


def get_model_operations() -> ModelOperations:
    """Get a ModelOperations instance."""
    return ModelOperations()


def get_workflow_operations() -> WorkflowOperations:
    """Get a WorkflowOperations instance."""
    return WorkflowOperations()
