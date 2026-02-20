"""
Agent Orchestrator for multi-agent system.

The Orchestrator:
- Coordinates the Coordinator and Executor agents
- Manages the flow: User → Coordinator → Executor → Response
- Handles RAG context retrieval
- Formats final responses for the user
"""

from typing import Optional
from rich.console import Console

from hevo_assistant.agents.schemas import ActionDirective, AgentActionResult, DirectiveType
from hevo_assistant.agents.coordinator import CoordinatorAgent
from hevo_assistant.agents.executor import ExecutorAgent
from hevo_assistant.agent.responses import ResponseFormatter, get_response_formatter
from hevo_assistant.config import get_config

console = Console()


class AgentOrchestrator:
    """
    Orchestrates the multi-agent pipeline.

    Flow:
    1. User message → Coordinator Agent (understand intent)
    2. ActionDirective → Executor Agent (execute action)
    3. ActionResult → Response Formatter (display to user)
    """

    def __init__(
        self,
        coordinator: Optional[CoordinatorAgent] = None,
        executor: Optional[ExecutorAgent] = None,
        formatter: Optional[ResponseFormatter] = None,
    ):
        """
        Initialize the orchestrator.

        Args:
            coordinator: Coordinator agent (created if not provided)
            executor: Executor agent (created if not provided)
            formatter: Response formatter (created if not provided)
        """
        self.coordinator = coordinator or CoordinatorAgent()
        self.executor = executor or ExecutorAgent()
        self.formatter = formatter or get_response_formatter()

        # For caching available resources
        self._pipelines_cache = None
        self._destinations_cache = None

    def process(
        self,
        user_message: str,
        conversation_history: Optional[list] = None,
        rag_context: str = "",
    ) -> str:
        """
        Process a user message through the full agent pipeline.

        Args:
            user_message: The user's natural language message
            conversation_history: Previous messages in the conversation
            rag_context: Context from RAG retrieval

        Returns:
            Response string to display to the user
        """
        # Get available resources for context
        available_pipelines = self._get_available_pipelines()
        available_destinations = self._get_available_destinations()

        # Step 1: Coordinator understands intent and produces directive
        directive = self.coordinator.process(
            user_message=user_message,
            conversation_history=conversation_history,
            rag_context=rag_context,
            available_pipelines=available_pipelines,
            available_destinations=available_destinations,
        )

        # Step 2: Handle based on directive type
        if directive.directive_type == DirectiveType.CLARIFY:
            # Need more information from user
            return directive.question or "Could you please provide more details?"

        if directive.directive_type == DirectiveType.UNSUPPORTED:
            # Request cannot be fulfilled
            return f"I'm sorry, {directive.info_response or 'that action is not supported.'}"

        if directive.directive_type == DirectiveType.INFO_ONLY:
            # Just information, no action needed
            return directive.info_response or ""

        # Step 3: Validate directive before execution
        is_valid, error = self.executor.validate_directive(directive)
        if not is_valid:
            return f"I couldn't execute that action: {error}"

        # Step 4: Execute via Executor Agent
        result = self.executor.execute(directive)

        # Step 5: Format response for user
        return self._format_response(directive, result)

    def process_with_display(
        self,
        user_message: str,
        conversation_history: Optional[list] = None,
        rag_context: str = "",
    ) -> str:
        """
        Process and display response using Rich formatting.

        Args:
            user_message: The user's natural language message
            conversation_history: Previous messages
            rag_context: RAG context

        Returns:
            Response text (also displayed via formatter)
        """
        response = self.process(user_message, conversation_history, rag_context)

        # Display using formatter
        from hevo_assistant.agent.responses import FormattedResponse
        formatted = FormattedResponse(text=response)
        self.formatter.display(formatted)

        return response

    def _format_response(
        self,
        directive: ActionDirective,
        result: AgentActionResult,
    ) -> str:
        """
        Format the final response for the user.

        Args:
            directive: The directive that was executed
            result: The execution result

        Returns:
            Formatted response string
        """
        lines = []

        if result.success:
            # Success message
            if result.message:
                lines.append(result.message)
            else:
                lines.append(f"Action '{directive.action}' completed successfully!")

            # Include relevant result data
            if result.result:
                # Format based on action type
                if directive.action in ("list_pipelines", "list_destinations", "list_models", "list_workflows"):
                    # Already formatted in message
                    pass
                elif "status" in result.result:
                    lines.append(f"\nStatus: {result.result['status']}")

            # Add suggestions
            if result.suggestions:
                lines.append("\nYou might want to:")
                for suggestion in result.suggestions[:3]:
                    lines.append(f"  - {suggestion}")

        else:
            # Error message
            error = result.error or {}
            error_msg = error.get("message", "Something went wrong.")
            error_code = error.get("code", "ERROR")

            lines.append(f"Error ({error_code}): {error_msg}")

            # Add helpful suggestions based on error
            if error_code == "NOT_FOUND":
                lines.append("\nTip: You can list available resources first:")
                if "pipeline" in directive.action.lower():
                    lines.append('  - "List my pipelines"')
                elif "model" in directive.action.lower():
                    lines.append('  - "List my models"')
                elif "workflow" in directive.action.lower():
                    lines.append('  - "List my workflows"')

        return "\n".join(lines)

    def _get_available_pipelines(self) -> list:
        """Get list of available pipeline names for context."""
        if self._pipelines_cache is not None:
            return self._pipelines_cache

        def get_name(p: dict) -> str:
            """Try multiple possible name keys."""
            return p.get("name") or p.get("pipeline_name") or p.get("display_name") or ""

        try:
            from hevo_assistant.api.pipelines import get_pipeline_operations
            ops = get_pipeline_operations()
            pipelines = ops.list_all()
            self._pipelines_cache = [get_name(p) for p in pipelines if get_name(p)]
            return self._pipelines_cache
        except Exception:
            return []

    def _get_available_destinations(self) -> list:
        """Get list of available destination names for context."""
        if self._destinations_cache is not None:
            return self._destinations_cache

        try:
            from hevo_assistant.api.destinations import get_destination_operations
            ops = get_destination_operations()
            destinations = ops.list_all()
            self._destinations_cache = [d.name for d in destinations if d.name]
            return self._destinations_cache
        except Exception:
            return []

    def clear_cache(self):
        """Clear cached resources."""
        self._pipelines_cache = None
        self._destinations_cache = None


def get_orchestrator() -> AgentOrchestrator:
    """
    Factory function to create an AgentOrchestrator.

    Returns:
        AgentOrchestrator instance
    """
    return AgentOrchestrator()
