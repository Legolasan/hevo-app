"""
Executor Agent for multi-agent system.

The Executor Agent:
- Receives structured ActionDirectives
- Validates directives have required parameters
- Executes actions via the Hevo API
- Returns structured ActionResults with suggestions
"""

import json
import re
from typing import Optional

from hevo_assistant.agents.schemas import ActionDirective, AgentActionResult, DirectiveType
from hevo_assistant.agents.prompts.executor import get_executor_prompt
from hevo_assistant.agent.actions import ActionExecutor, ActionResult
from hevo_assistant.config import get_config
from hevo_assistant.llm import get_llm


class ExecutorAgent:
    """
    Action execution agent that takes directives and executes API calls.

    The Executor is the "hands" of the system - it takes clear directives
    from the Coordinator and executes them, returning structured results.
    """

    def __init__(self, model: Optional[str] = None, temperature: float = 0.2):
        """
        Initialize the Executor Agent.

        Args:
            model: LLM model to use (defaults to config or gpt-3.5-turbo)
            temperature: Sampling temperature (lower for more deterministic)
        """
        cfg = get_config()

        # Use agent config if available, else fall back to faster model
        self.model = model or getattr(cfg.agents, "executor_model", None) or "gpt-3.5-turbo"
        self.temperature = temperature

        # LLM is optional - used for enriching results
        self._llm = None

        # Use existing ActionExecutor for actual API calls
        self.action_executor = ActionExecutor()

    @property
    def llm(self):
        """Lazy-load LLM only when needed."""
        if self._llm is None:
            self._llm = get_llm(model=self.model)
        return self._llm

    def execute(self, directive: ActionDirective) -> AgentActionResult:
        """
        Execute an ActionDirective.

        Args:
            directive: The directive to execute

        Returns:
            AgentActionResult with execution result
        """
        # Only handle EXECUTE directives
        if directive.directive_type != DirectiveType.EXECUTE:
            return AgentActionResult.error_result(
                action="unknown",
                error_code="INVALID_DIRECTIVE",
                error_message=f"Cannot execute directive of type: {directive.directive_type.value}",
            )

        # Validate action exists
        action = directive.action
        if not action:
            return AgentActionResult.error_result(
                action="unknown",
                error_code="MISSING_ACTION",
                error_message="No action specified in directive",
            )

        # Validate action is registered
        if action not in self.action_executor.ACTIONS:
            return AgentActionResult.error_result(
                action=action,
                error_code="UNKNOWN_ACTION",
                error_message=f"Unknown action: {action}",
            )

        # Execute via existing ActionExecutor
        try:
            result = self.action_executor.execute({
                "action": action,
                "params": directive.params or {},
            })

            # Convert to AgentActionResult
            return self._convert_result(action, result)

        except Exception as e:
            return AgentActionResult.error_result(
                action=action,
                error_code="EXECUTION_ERROR",
                error_message=str(e),
            )

    def execute_with_enrichment(self, directive: ActionDirective) -> AgentActionResult:
        """
        Execute directive with LLM-based result enrichment.

        Uses LLM to add helpful suggestions and format the result nicely.

        Args:
            directive: The directive to execute

        Returns:
            Enriched AgentActionResult
        """
        # First, execute normally
        result = self.execute(directive)

        # If successful, use LLM to add suggestions
        if result.success:
            result = self._enrich_result(result, directive)

        return result

    def _convert_result(self, action: str, result: ActionResult) -> AgentActionResult:
        """
        Convert ActionResult to AgentActionResult.

        Args:
            action: Action that was executed
            result: Result from ActionExecutor

        Returns:
            AgentActionResult
        """
        if result.success:
            # Extract useful data
            result_data = {}
            if result.data:
                if hasattr(result.data, '__dict__'):
                    result_data = result.data.__dict__
                elif isinstance(result.data, dict):
                    result_data = result.data
                elif isinstance(result.data, list):
                    result_data = {"items": result.data, "count": len(result.data)}

            # Add common suggestions based on action
            suggestions = self._get_suggestions(action, result.success, result_data)

            return AgentActionResult.success_result(
                action=action,
                result=result_data,
                message=result.message,
                suggestions=suggestions,
            )
        else:
            # Parse error code from message
            error_code = "API_ERROR"
            error_message = result.message

            if "not found" in error_message.lower():
                error_code = "NOT_FOUND"
            elif "permission" in error_message.lower():
                error_code = "PERMISSION_DENIED"
            elif "already" in error_message.lower():
                error_code = "ALREADY_EXISTS"

            return AgentActionResult.error_result(
                action=action,
                error_code=error_code,
                error_message=error_message,
            )

    def _get_suggestions(
        self,
        action: str,
        success: bool,
        result_data: dict,
    ) -> list:
        """
        Get follow-up suggestions based on action and result.

        Args:
            action: Action that was executed
            success: Whether execution succeeded
            result_data: Result data

        Returns:
            List of suggestion strings
        """
        suggestions = []

        if not success:
            return suggestions

        # Action-specific suggestions
        action_suggestions = {
            "list_pipelines": [
                "View details of a specific pipeline",
                "Run a pipeline immediately",
            ],
            "get_pipeline": [
                "List objects in this pipeline",
                "Run the pipeline now",
                "Pause the pipeline",
            ],
            "pause_pipeline": [
                "Resume the pipeline when ready",
                "Check pipeline status",
            ],
            "resume_pipeline": [
                "Run the pipeline immediately",
                "Check pipeline status",
            ],
            "run_pipeline": [
                "Check pipeline status",
                "List objects being synced",
            ],
            "list_objects": [
                "Skip an object from syncing",
                "Restart an object",
            ],
            "skip_object": [
                "Include the object again later",
                "List all objects",
            ],
            "restart_object": [
                "Check object status",
                "List all objects",
            ],
            "list_destinations": [
                "View destination details",
            ],
            "list_models": [
                "Run a model",
            ],
            "run_model": [
                "List models to see status",
            ],
            "list_workflows": [
                "Run a workflow",
            ],
            "run_workflow": [
                "List workflows to see status",
            ],
        }

        suggestions = action_suggestions.get(action, [])
        return suggestions[:3]  # Limit to 3 suggestions

    def _enrich_result(
        self,
        result: AgentActionResult,
        directive: ActionDirective,
    ) -> AgentActionResult:
        """
        Use LLM to enrich result with better formatting and suggestions.

        Args:
            result: Original result
            directive: Original directive

        Returns:
            Enriched result
        """
        # For now, return the result as-is
        # In a future version, we could use LLM to:
        # - Summarize complex results
        # - Provide context-aware suggestions
        # - Format data for better readability
        return result

    def validate_directive(self, directive: ActionDirective) -> tuple[bool, Optional[str]]:
        """
        Validate that a directive can be executed.

        Args:
            directive: Directive to validate

        Returns:
            Tuple of (is_valid, error_message)
        """
        if directive.directive_type != DirectiveType.EXECUTE:
            return False, f"Cannot execute directive of type: {directive.directive_type.value}"

        if not directive.action:
            return False, "No action specified"

        if directive.action not in self.action_executor.ACTIONS:
            return False, f"Unknown action: {directive.action}"

        # Check for required parameters based on action
        params = directive.params or {}

        # Actions that need identification (name or id)
        id_actions = [
            "get_pipeline", "pause_pipeline", "resume_pipeline", "run_pipeline",
            "run_model", "run_workflow",
        ]
        if directive.action in id_actions:
            if not params.get("name") and not params.get("id"):
                return False, f"Pipeline/resource name or ID is required for {directive.action}"

        # Actions that need pipeline + object
        object_actions = ["skip_object", "restart_object", "pause_object", "resume_object"]
        if directive.action in object_actions:
            if not params.get("pipeline_id") and not params.get("pipeline_name"):
                return False, "Pipeline ID or name is required"
            if not params.get("object_name"):
                return False, "Object name is required"

        return True, None


def get_executor_agent(
    model: Optional[str] = None,
    temperature: float = 0.2,
) -> ExecutorAgent:
    """
    Factory function to create an ExecutorAgent.

    Args:
        model: LLM model to use
        temperature: Sampling temperature

    Returns:
        ExecutorAgent instance
    """
    return ExecutorAgent(model=model, temperature=temperature)
