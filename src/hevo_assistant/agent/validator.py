"""
Request validation for Hevo actions.

Validates action requests, checks prerequisites, and prompts for missing parameters.
"""

import re
from typing import Optional, Tuple, List, Dict, Any

from hevo_assistant.domain.capabilities import (
    CAPABILITIES,
    get_missing_prerequisites,
    Parameter,
    get_action_definition,
)
from hevo_assistant.domain.knowledge import validate_pipeline_direction


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


class RequestValidator:
    """
    Validates action requests and prompts for missing information.
    """

    def check_unsupported(self, query: str) -> Optional[str]:
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

    def validate_action(
        self,
        action_name: str,
        params: Dict[str, Any]
    ) -> Tuple[bool, Optional[str], List[Parameter]]:
        """
        Validate an action request.

        Args:
            action_name: Name of the action to execute
            params: Parameters provided for the action

        Returns:
            Tuple of (is_valid, error_message, missing_parameters)
        """
        # Check if action exists
        action = get_action_definition(action_name)
        if not action:
            supported = sorted(CAPABILITIES.keys())[:5]
            return (
                False,
                f"Unknown action '{action_name}'. Some available actions: {', '.join(supported)}...",
                []
            )

        # Check if action is implemented
        if not action.implemented:
            return (
                False,
                f"The '{action_name}' action is not yet available via the API. "
                "This feature is coming soon!",
                []
            )

        # Check for missing required parameters
        missing = get_missing_prerequisites(action_name, params)
        if missing:
            return False, None, missing

        # Special validation for pipeline creation
        if action_name == "create_pipeline":
            source = params.get("source_type", "")
            dest = params.get("destination_type", "")
            if source and dest:
                is_valid, msg = validate_pipeline_direction(source, dest)
                if not is_valid:
                    return False, msg, []

        return True, None, []

    def format_missing_params_prompt(
        self,
        action_name: str,
        missing: List[Parameter]
    ) -> str:
        """
        Format a user-friendly prompt asking for missing parameters.

        Args:
            action_name: Name of the action
            missing: List of missing Parameter objects

        Returns:
            Formatted prompt string
        """
        action = get_action_definition(action_name)
        action_desc = action.description if action else action_name

        lines = [f"To {action_desc.lower()}, I need a few details:\n"]

        for i, param in enumerate(missing, 1):
            example = f" (e.g., {param.example})" if param.example else ""
            lines.append(f"{i}. **{param.name}**: {param.description}{example}")

        lines.append("\nPlease provide these details and I'll help you proceed.")

        return "\n".join(lines)

    def validate_connector_direction(
        self,
        source: str,
        destination: str
    ) -> Tuple[bool, str]:
        """
        Validate that a source-destination combination is valid.

        Args:
            source: Source connector type
            destination: Destination connector type

        Returns:
            Tuple of (is_valid, message)
        """
        return validate_pipeline_direction(source, destination)

    def get_action_requirements(self, action_name: str) -> Optional[str]:
        """
        Get a description of what's needed for an action.

        Args:
            action_name: Name of the action

        Returns:
            Requirements description or None
        """
        action = get_action_definition(action_name)
        if not action:
            return None

        if not action.parameters:
            return f"No additional information needed for '{action.description}'."

        required = [p for p in action.parameters if p.required]
        optional = [p for p in action.parameters if not p.required]

        lines = [f"To {action.description.lower()}, you'll need:\n"]

        if required:
            lines.append("**Required:**")
            for param in required:
                ex = f" (e.g., {param.example})" if param.example else ""
                lines.append(f"  - {param.name}: {param.description}{ex}")

        if optional:
            lines.append("\n**Optional:**")
            for param in optional:
                ex = f" (e.g., {param.example})" if param.example else ""
                lines.append(f"  - {param.name}: {param.description}{ex}")

        return "\n".join(lines)


# Module-level instance
_validator: Optional[RequestValidator] = None


def get_validator() -> RequestValidator:
    """Get the global RequestValidator instance."""
    global _validator
    if _validator is None:
        _validator = RequestValidator()
    return _validator
