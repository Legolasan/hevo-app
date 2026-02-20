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


class WorkflowOperations:
    """High-level workflow operations."""

    def __init__(self, client: Optional[HevoClient] = None):
        self.client = client or get_client()

    def list_all(self) -> list[WorkflowInfo]:
        """List all workflows."""
        workflows = self.client.list_workflows()
        return [WorkflowInfo.from_api(w) for w in workflows]

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
