"""
Coordinator Agent for multi-agent system.

The Coordinator Agent:
- Understands user intent from natural language
- Gathers missing parameters through conversation
- Outputs structured ActionDirective for the Executor Agent
"""

import json
import re
from typing import Optional

from hevo_assistant.agents.schemas import ActionDirective, DirectiveType
from hevo_assistant.agents.prompts.coordinator import get_coordinator_prompt
from hevo_assistant.config import get_config
from hevo_assistant.llm import get_llm


class CoordinatorAgent:
    """
    Conversational agent that understands user intent and produces directives.

    The Coordinator is the "brain" of the system - it interprets what the user
    wants and translates that into structured directives that the Executor
    can act upon.
    """

    def __init__(self, model: Optional[str] = None, temperature: float = 0.7):
        """
        Initialize the Coordinator Agent.

        Args:
            model: LLM model to use (defaults to config or gpt-4)
            temperature: Sampling temperature for LLM
        """
        cfg = get_config()

        # Use agent config if available, else fall back to main LLM config
        self.model = model or getattr(cfg.agents, "coordinator_model", None) or cfg.llm.model
        self.temperature = temperature
        self.llm = get_llm(model=self.model)

    def process(
        self,
        user_message: str,
        conversation_history: Optional[list] = None,
        rag_context: str = "",
        available_pipelines: Optional[list] = None,
        available_destinations: Optional[list] = None,
    ) -> ActionDirective:
        """
        Process a user message and return an ActionDirective.

        Args:
            user_message: The user's natural language message
            conversation_history: Previous messages in the conversation
            rag_context: Context from RAG retrieval
            available_pipelines: List of user's pipelines (for context)
            available_destinations: List of user's destinations (for context)

        Returns:
            ActionDirective indicating what action to take
        """
        # Build available actions list
        available_actions = self._get_available_actions()

        # Build system prompt
        system_prompt = get_coordinator_prompt(
            available_actions=available_actions,
            context=rag_context,
        )

        # Add context about available resources
        resource_context = ""
        if available_pipelines:
            pipeline_list = ", ".join(available_pipelines[:10])
            resource_context += f"\nUser's pipelines: {pipeline_list}"
        if available_destinations:
            dest_list = ", ".join(available_destinations[:10])
            resource_context += f"\nUser's destinations: {dest_list}"

        if resource_context:
            system_prompt += f"\n## User's Resources{resource_context}"

        # Call LLM
        try:
            response = self.llm.chat(
                message=user_message,
                context=system_prompt,
                conversation_history=conversation_history or [],
            )
        except Exception as e:
            # Return error directive
            return ActionDirective.unsupported(
                f"I'm having trouble understanding right now. Error: {str(e)}"
            )

        # Parse directive from response
        directive = self._parse_directive(response)
        return directive

    def _get_available_actions(self) -> str:
        """Get formatted list of available actions."""
        try:
            from hevo_assistant.domain.capabilities import get_available_actions_prompt
            return get_available_actions_prompt()
        except ImportError:
            return """
## Available Actions

### Pipelines
- list_pipelines: List all pipelines
- get_pipeline: Get pipeline details (params: name or id)
- pause_pipeline: Pause a pipeline (params: name or id)
- resume_pipeline: Resume a paused pipeline (params: name or id)
- run_pipeline: Run a pipeline immediately (params: name or id)

### Pipeline Objects
- list_objects: List objects in a pipeline (params: pipeline_name or pipeline_id)
- skip_object: Skip an object (params: pipeline_id, object_name)
- restart_object: Restart an object (params: pipeline_id, object_name)

### Destinations
- list_destinations: List all destinations

### Models
- list_models: List all models
- run_model: Run a model (params: name or id)

### Workflows
- list_workflows: List all workflows
- run_workflow: Run a workflow (params: name or id)
"""

    def _parse_directive(self, response: str) -> ActionDirective:
        """
        Parse ActionDirective from LLM response.

        Args:
            response: LLM response text

        Returns:
            Parsed ActionDirective
        """
        # Try to extract JSON from response
        json_patterns = [
            r"```json\s*(\{.*?\})\s*```",  # Markdown code block
            r"```\s*(\{.*?\})\s*```",       # Code block without json tag
            r"(\{[^{}]*\"directive_type\"[^{}]*\})",  # Inline JSON with directive_type
        ]

        for pattern in json_patterns:
            match = re.search(pattern, response, re.DOTALL)
            if match:
                try:
                    data = json.loads(match.group(1))
                    return ActionDirective.from_dict(data)
                except (json.JSONDecodeError, KeyError, ValueError):
                    continue

        # If no JSON found, try to infer from response
        response_lower = response.lower()

        # Check for clarification
        if any(q in response_lower for q in ["which", "what", "please specify", "could you"]):
            return ActionDirective.clarify(
                question=response,
                missing_params=["unknown"],
            )

        # Check for unsupported
        if any(u in response_lower for u in ["cannot", "not supported", "not available", "sorry"]):
            return ActionDirective.unsupported(response)

        # Default to info_only with the response
        return ActionDirective.info_only(response)

    def format_response(
        self,
        directive: ActionDirective,
        action_result: Optional[dict] = None,
    ) -> str:
        """
        Format a user-friendly response from directive and result.

        Args:
            directive: The ActionDirective that was processed
            action_result: Result from executing the action (if any)

        Returns:
            Formatted response string
        """
        if directive.directive_type == DirectiveType.CLARIFY:
            return directive.question or "Could you please provide more details?"

        if directive.directive_type == DirectiveType.UNSUPPORTED:
            return f"I'm sorry, {directive.info_response or 'that action is not supported.'}"

        if directive.directive_type == DirectiveType.INFO_ONLY:
            return directive.info_response or ""

        # For EXECUTE, format based on result
        if action_result:
            if action_result.get("success"):
                message = action_result.get("message", "Action completed successfully!")
                suggestions = action_result.get("suggestions", [])
                if suggestions:
                    message += "\n\nYou might also want to:\n"
                    for s in suggestions[:3]:
                        message += f"  - {s}\n"
                return message
            else:
                error = action_result.get("error", {})
                return f"Error: {error.get('message', 'Something went wrong.')}"

        return "Processing your request..."


def get_coordinator_agent(
    model: Optional[str] = None,
    temperature: float = 0.7,
) -> CoordinatorAgent:
    """
    Factory function to create a CoordinatorAgent.

    Args:
        model: LLM model to use
        temperature: Sampling temperature

    Returns:
        CoordinatorAgent instance
    """
    return CoordinatorAgent(model=model, temperature=temperature)
