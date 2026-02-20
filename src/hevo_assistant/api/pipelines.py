"""
Pipeline-specific API operations.

Provides high-level methods for working with Hevo pipelines.
"""

from dataclasses import dataclass
from typing import Optional

from hevo_assistant.api.client import HevoClient, get_client


@dataclass
class PipelineStatus:
    """Pipeline status information."""

    id: str
    name: str
    status: str
    source_type: str
    destination_name: str
    destination_type: str
    objects_count: int
    active_objects: int
    failed_objects: int
    health_status: str = "OK"

    @classmethod
    def from_api(cls, data: dict, objects: list[dict] = None) -> "PipelineStatus":
        """Create from API response."""
        objects = objects or []
        active = sum(1 for o in objects if o.get("status") == "ACTIVE")
        failed = sum(1 for o in objects if o.get("status") in ("FAILED", "PERMISSION_DENIED"))

        # Get pipeline name from source.name (pipelines don't have top-level name)
        source = data.get("source", {})
        name = source.get("name") if isinstance(source, dict) else None
        if not name:
            # Fallback to ID-based name
            name = f"Pipeline #{data.get('id', '?')}"

        # Get source type display name
        source_type_data = source.get("type", {}) if isinstance(source, dict) else {}
        if isinstance(source_type_data, dict):
            source_type = source_type_data.get("display_name") or source_type_data.get("name") or "Unknown"
        else:
            source_type = str(source_type_data) if source_type_data else "Unknown"

        # Get destination info
        dest = data.get("destination", {})
        dest_name = dest.get("name", "Unknown") if isinstance(dest, dict) else "Unknown"
        dest_type_data = dest.get("type", {}) if isinstance(dest, dict) else {}
        if isinstance(dest_type_data, dict):
            dest_type = dest_type_data.get("display_name") or dest_type_data.get("name") or "Unknown"
        else:
            dest_type = str(dest_type_data) if dest_type_data else "Unknown"

        return cls(
            id=str(data.get("id", "")),
            name=name,
            status=data.get("status", "UNKNOWN"),
            source_type=source_type,
            destination_name=dest_name,
            destination_type=dest_type,
            objects_count=len(objects),
            active_objects=active,
            failed_objects=failed,
            health_status=data.get("health_status", "OK"),
        )


class PipelineOperations:
    """High-level pipeline operations."""

    def __init__(self, client: Optional[HevoClient] = None):
        self.client = client or get_client()

    def list_all(self) -> list[dict]:
        """List all pipelines with basic info."""
        return self.client.list_pipelines()

    def get_status(self, pipeline_id: Optional[str] = None, name: Optional[str] = None) -> Optional[PipelineStatus]:
        """
        Get detailed status for a pipeline.

        Args:
            pipeline_id: Pipeline ID
            name: Pipeline name (used if ID not provided)

        Returns:
            PipelineStatus or None if not found
        """
        if not pipeline_id and name:
            pipeline = self.client.get_pipeline_by_name(name)
            if not pipeline:
                return None
            pipeline_id = pipeline.get("id")

        if not pipeline_id:
            return None

        pipeline = self.client.get_pipeline(pipeline_id)
        objects = self.client.get_pipeline_objects(pipeline_id)

        return PipelineStatus.from_api(pipeline, objects)

    def get_summary(self) -> dict:
        """
        Get a summary of all pipelines.

        Returns:
            Dictionary with counts by status
        """
        pipelines = self.list_all()

        summary = {
            "total": len(pipelines),
            "active": 0,
            "paused": 0,
            "draft": 0,
            "other": 0,
        }

        for p in pipelines:
            status = p.get("status", "").upper()
            if status == "ACTIVE":
                summary["active"] += 1
            elif status == "PAUSED":
                summary["paused"] += 1
            elif status == "DRAFT":
                summary["draft"] += 1
            else:
                summary["other"] += 1

        return summary

    def pause(self, pipeline_id: Optional[str] = None, name: Optional[str] = None) -> dict:
        """Pause a pipeline."""
        if not pipeline_id and name:
            pipeline = self.client.get_pipeline_by_name(name)
            if not pipeline:
                raise ValueError(f"Pipeline not found: {name}")
            pipeline_id = pipeline.get("id")

        return self.client.pause_pipeline(pipeline_id)

    def resume(self, pipeline_id: Optional[str] = None, name: Optional[str] = None) -> dict:
        """Resume a pipeline."""
        if not pipeline_id and name:
            pipeline = self.client.get_pipeline_by_name(name)
            if not pipeline:
                raise ValueError(f"Pipeline not found: {name}")
            pipeline_id = pipeline.get("id")

        return self.client.resume_pipeline(pipeline_id)

    def run_now(self, pipeline_id: Optional[str] = None, name: Optional[str] = None) -> dict:
        """Run a pipeline immediately."""
        if not pipeline_id and name:
            pipeline = self.client.get_pipeline_by_name(name)
            if not pipeline:
                raise ValueError(f"Pipeline not found: {name}")
            pipeline_id = pipeline.get("id")

        return self.client.run_pipeline(pipeline_id)

    def get_failed_objects(self, pipeline_id: str) -> list[dict]:
        """Get failed objects in a pipeline."""
        objects = self.client.get_pipeline_objects(pipeline_id)
        return [o for o in objects if o.get("status") in ("FAILED", "PERMISSION_DENIED")]

    def skip_object(self, pipeline_id: str, object_name: str) -> dict:
        """Skip an object in a pipeline."""
        return self.client.skip_object(pipeline_id, object_name)

    def restart_object(self, pipeline_id: str, object_name: str) -> dict:
        """Restart an object in a pipeline."""
        return self.client.restart_object(pipeline_id, object_name)


def get_pipeline_operations() -> PipelineOperations:
    """Get a PipelineOperations instance."""
    return PipelineOperations()
