"""
Destination-specific API operations.

Provides high-level methods for working with Hevo destinations.
"""

from dataclasses import dataclass
from typing import Optional

from hevo_assistant.api.client import HevoClient, get_client


@dataclass
class DestinationInfo:
    """Destination information."""

    id: str
    name: str
    type: str
    status: str

    @classmethod
    def from_api(cls, data: dict) -> "DestinationInfo":
        """Create from API response."""
        return cls(
            id=str(data.get("id", "")),
            name=data.get("name", "Unknown"),
            type=data.get("type", "Unknown"),
            status=data.get("status", "UNKNOWN"),
        )


class DestinationOperations:
    """High-level destination operations."""

    def __init__(self, client: Optional[HevoClient] = None):
        self.client = client or get_client()

    def list_all(self) -> list[DestinationInfo]:
        """List all destinations."""
        destinations = self.client.list_destinations()
        return [DestinationInfo.from_api(d) for d in destinations]

    def get(self, destination_id: str) -> Optional[DestinationInfo]:
        """Get destination by ID."""
        try:
            data = self.client.get_destination(destination_id)
            return DestinationInfo.from_api(data)
        except Exception:
            return None

    def get_by_name(self, name: str) -> Optional[DestinationInfo]:
        """Find destination by name."""
        destinations = self.list_all()
        for dest in destinations:
            if dest.name.lower() == name.lower():
                return dest
        return None

    def get_summary(self) -> dict:
        """Get summary of destinations by type."""
        destinations = self.list_all()

        summary = {
            "total": len(destinations),
            "by_type": {},
        }

        for dest in destinations:
            dest_type = dest.type
            if dest_type not in summary["by_type"]:
                summary["by_type"][dest_type] = 0
            summary["by_type"][dest_type] += 1

        return summary


def get_destination_operations() -> DestinationOperations:
    """Get a DestinationOperations instance."""
    return DestinationOperations()
