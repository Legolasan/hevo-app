"""
Schema contracts for multi-agent communication.

Defines the structured data types passed between agents:
- ActionDirective: Coordinator → Executor
- AgentActionResult: Executor → Coordinator
"""

import json
from dataclasses import dataclass, field, asdict
from enum import Enum
from typing import Optional, Any


class DirectiveType(str, Enum):
    """Types of directives the Coordinator can produce."""

    EXECUTE = "execute"  # Ready to execute an action
    CLARIFY = "clarify"  # Need more information from user
    UNSUPPORTED = "unsupported"  # Request cannot be fulfilled
    INFO_ONLY = "info_only"  # Just provide information, no action needed


@dataclass
class ActionDirective:
    """
    Contract from Coordinator Agent to Executor Agent.

    Represents what the Coordinator wants the Executor to do.
    """

    directive_type: DirectiveType

    # For EXECUTE directives
    action: Optional[str] = None  # Action name (e.g., "pause_pipeline")
    params: Optional[dict] = field(default_factory=dict)  # Action parameters
    context: Optional[str] = None  # Why the user wants this (for logging/debugging)

    # For CLARIFY directives
    question: Optional[str] = None  # Question to ask the user
    missing_params: Optional[list] = field(default_factory=list)  # What we need

    # For UNSUPPORTED and INFO_ONLY directives
    info_response: Optional[str] = None  # Message to return to user

    def to_dict(self) -> dict:
        """Convert to dictionary for JSON serialization."""
        result = {
            "directive_type": self.directive_type.value,
        }

        if self.action:
            result["action"] = self.action
        if self.params:
            result["params"] = self.params
        if self.context:
            result["context"] = self.context
        if self.question:
            result["question"] = self.question
        if self.missing_params:
            result["missing_params"] = self.missing_params
        if self.info_response:
            result["info_response"] = self.info_response

        return result

    def to_json(self) -> str:
        """Convert to JSON string."""
        return json.dumps(self.to_dict(), indent=2)

    @classmethod
    def from_dict(cls, data: dict) -> "ActionDirective":
        """Create from dictionary."""
        directive_type = DirectiveType(data.get("directive_type", "execute"))

        return cls(
            directive_type=directive_type,
            action=data.get("action"),
            params=data.get("params", {}),
            context=data.get("context"),
            question=data.get("question"),
            missing_params=data.get("missing_params", []),
            info_response=data.get("info_response"),
        )

    @classmethod
    def from_json(cls, json_str: str) -> "ActionDirective":
        """Create from JSON string."""
        return cls.from_dict(json.loads(json_str))

    @classmethod
    def execute(
        cls,
        action: str,
        params: dict = None,
        context: str = None,
    ) -> "ActionDirective":
        """Factory for EXECUTE directive."""
        return cls(
            directive_type=DirectiveType.EXECUTE,
            action=action,
            params=params or {},
            context=context,
        )

    @classmethod
    def clarify(
        cls,
        question: str,
        missing_params: list = None,
    ) -> "ActionDirective":
        """Factory for CLARIFY directive."""
        return cls(
            directive_type=DirectiveType.CLARIFY,
            question=question,
            missing_params=missing_params or [],
        )

    @classmethod
    def unsupported(cls, message: str) -> "ActionDirective":
        """Factory for UNSUPPORTED directive."""
        return cls(
            directive_type=DirectiveType.UNSUPPORTED,
            info_response=message,
        )

    @classmethod
    def info_only(cls, response: str) -> "ActionDirective":
        """Factory for INFO_ONLY directive."""
        return cls(
            directive_type=DirectiveType.INFO_ONLY,
            info_response=response,
        )


@dataclass
class AgentActionResult:
    """
    Contract from Executor Agent back to Coordinator.

    Contains the result of executing an action.
    """

    success: bool
    action_taken: str

    # Success case
    result: Optional[dict] = field(default_factory=dict)
    message: Optional[str] = None

    # Error case
    error: Optional[dict] = field(default_factory=dict)

    # Suggestions for follow-up
    suggestions: Optional[list] = field(default_factory=list)

    def to_dict(self) -> dict:
        """Convert to dictionary for JSON serialization."""
        data = {
            "success": self.success,
            "action_taken": self.action_taken,
        }

        if self.success:
            data["result"] = self.result or {}
            if self.message:
                data["message"] = self.message
        else:
            data["error"] = self.error or {}

        if self.suggestions:
            data["suggestions"] = self.suggestions

        return data

    def to_json(self) -> str:
        """Convert to JSON string."""
        return json.dumps(self.to_dict(), indent=2)

    @classmethod
    def from_dict(cls, data: dict) -> "AgentActionResult":
        """Create from dictionary."""
        return cls(
            success=data.get("success", False),
            action_taken=data.get("action_taken", "unknown"),
            result=data.get("result", {}),
            message=data.get("message"),
            error=data.get("error", {}),
            suggestions=data.get("suggestions", []),
        )

    @classmethod
    def success_result(
        cls,
        action: str,
        result: dict = None,
        message: str = None,
        suggestions: list = None,
    ) -> "AgentActionResult":
        """Factory for successful result."""
        return cls(
            success=True,
            action_taken=action,
            result=result or {},
            message=message,
            suggestions=suggestions or [],
        )

    @classmethod
    def error_result(
        cls,
        action: str,
        error_code: str,
        error_message: str,
    ) -> "AgentActionResult":
        """Factory for error result."""
        return cls(
            success=False,
            action_taken=action,
            error={
                "code": error_code,
                "message": error_message,
            },
        )
