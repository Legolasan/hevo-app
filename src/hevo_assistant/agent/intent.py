"""
Intent parsing for user queries.

Analyzes user queries to determine intent and extract parameters.
"""

import re
from dataclasses import dataclass
from enum import Enum
from typing import Optional


class IntentType(Enum):
    """Types of user intents."""

    # Information queries
    QUESTION = "question"  # General question about Hevo
    LIST = "list"  # List resources (pipelines, destinations, etc.)
    STATUS = "status"  # Check status of a resource

    # Actions
    PAUSE = "pause"  # Pause a resource
    RESUME = "resume"  # Resume a resource
    RUN = "run"  # Run/trigger a resource
    SKIP = "skip"  # Skip an object
    RESTART = "restart"  # Restart an object

    # Help
    HELP = "help"  # Help or greeting
    UNKNOWN = "unknown"  # Can't determine intent


@dataclass
class ParsedIntent:
    """Parsed intent from user query."""

    intent_type: IntentType
    resource_type: Optional[str] = None  # pipeline, destination, model, etc.
    resource_name: Optional[str] = None  # Name of the resource
    resource_id: Optional[str] = None  # ID of the resource
    object_name: Optional[str] = None  # For object-level operations
    confidence: float = 0.0  # Confidence score (0-1)
    raw_query: str = ""


class IntentParser:
    """
    Parses user queries to extract intent and parameters.

    This is a lightweight parser for common patterns. Complex queries
    are handled by the LLM.
    """

    # Resource type patterns
    RESOURCE_PATTERNS = {
        "pipeline": r"\b(pipeline|pipelines|pipe)\b",
        "destination": r"\b(destination|destinations|dest)\b",
        "model": r"\b(model|models|dbt)\b",
        "workflow": r"\b(workflow|workflows)\b",
        "object": r"\b(object|objects|table|tables)\b",
    }

    # Intent patterns (order matters - first match wins)
    INTENT_PATTERNS = [
        # Actions
        (IntentType.PAUSE, r"\b(pause|stop|halt|disable)\b"),
        (IntentType.RESUME, r"\b(resume|start|enable|activate|unpause)\b"),
        (IntentType.RUN, r"\b(run|trigger|execute|sync)\b"),
        (IntentType.SKIP, r"\b(skip)\b"),
        (IntentType.RESTART, r"\b(restart|rerun|retry)\b"),
        # Information
        (IntentType.STATUS, r"\b(status|state|health|check)\b"),
        (IntentType.LIST, r"\b(list|show|display|get all|what are)\b"),
        # Help
        (IntentType.HELP, r"\b(help|hi|hello|hey|how do|what can|guide)\b"),
    ]

    # Name extraction patterns
    NAME_PATTERNS = [
        r"(?:called|named|name)\s+['\"]?([^'\"]+)['\"]?",
        r"['\"]([^'\"]+)['\"]",  # Quoted names
        r"\b(?:pipeline|destination|model|workflow)\s+(\w+[\w\-_]*)",
    ]

    def parse(self, query: str) -> ParsedIntent:
        """
        Parse a user query into structured intent.

        Args:
            query: User's natural language query

        Returns:
            ParsedIntent with extracted information
        """
        query_lower = query.lower().strip()

        # Extract intent type
        intent_type = IntentType.UNKNOWN
        confidence = 0.0

        for intent, pattern in self.INTENT_PATTERNS:
            if re.search(pattern, query_lower):
                intent_type = intent
                confidence = 0.8
                break

        # If no pattern matched, check if it's a question
        if intent_type == IntentType.UNKNOWN:
            if query_lower.endswith("?") or query_lower.startswith(("what", "how", "why", "when", "where", "can")):
                intent_type = IntentType.QUESTION
                confidence = 0.6

        # Extract resource type
        resource_type = None
        for res_type, pattern in self.RESOURCE_PATTERNS.items():
            if re.search(pattern, query_lower):
                resource_type = res_type
                break

        # Extract resource name
        resource_name = self._extract_name(query)

        return ParsedIntent(
            intent_type=intent_type,
            resource_type=resource_type,
            resource_name=resource_name,
            confidence=confidence,
            raw_query=query,
        )

    def _extract_name(self, query: str) -> Optional[str]:
        """Extract resource name from query."""
        for pattern in self.NAME_PATTERNS:
            match = re.search(pattern, query, re.IGNORECASE)
            if match:
                name = match.group(1).strip()
                # Filter out common words
                if name.lower() not in ("the", "my", "a", "an", "this", "that"):
                    return name
        return None

    def requires_llm(self, intent: ParsedIntent) -> bool:
        """
        Determine if the query needs LLM processing.

        Simple queries (like "list pipelines") can be handled directly.
        Complex queries need LLM for understanding context.
        """
        # Questions always need LLM
        if intent.intent_type == IntentType.QUESTION:
            return True

        # Unknown intent needs LLM
        if intent.intent_type == IntentType.UNKNOWN:
            return True

        # Low confidence needs LLM
        if intent.confidence < 0.7:
            return True

        # Actions without a clear target need LLM
        if intent.intent_type in (IntentType.PAUSE, IntentType.RESUME, IntentType.RUN):
            if not intent.resource_name and not intent.resource_type:
                return True

        return False

    def to_action_hint(self, intent: ParsedIntent) -> Optional[dict]:
        """
        Convert parsed intent to an action hint for the LLM.

        This helps the LLM understand what action the user likely wants.
        """
        if intent.intent_type == IntentType.UNKNOWN:
            return None

        hint = {
            "likely_intent": intent.intent_type.value,
            "resource_type": intent.resource_type,
            "resource_name": intent.resource_name,
        }

        # Suggest specific actions
        action_map = {
            (IntentType.LIST, "pipeline"): "list_pipelines",
            (IntentType.LIST, "destination"): "list_destinations",
            (IntentType.LIST, "model"): "list_models",
            (IntentType.LIST, "workflow"): "list_workflows",
            (IntentType.STATUS, "pipeline"): "get_pipeline",
            (IntentType.PAUSE, "pipeline"): "pause_pipeline",
            (IntentType.RESUME, "pipeline"): "resume_pipeline",
            (IntentType.RUN, "pipeline"): "run_pipeline",
            (IntentType.RUN, "model"): "run_model",
            (IntentType.RUN, "workflow"): "run_workflow",
        }

        key = (intent.intent_type, intent.resource_type)
        if key in action_map:
            hint["suggested_action"] = action_map[key]

        return hint


def get_intent_parser() -> IntentParser:
    """Get an IntentParser instance."""
    return IntentParser()
