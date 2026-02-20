"""
Base LLM interface and factory function.

Provides abstract interface for LLM providers and creates instances
based on configuration.
"""

from abc import ABC, abstractmethod
from typing import Optional

from hevo_assistant.config import get_config


# System prompt for Hevo Assistant
SYSTEM_PROMPT = """You are Hevo Assistant, an AI helper for managing Hevo Data pipelines.

You help users with:
1. Understanding Hevo concepts (pipelines, sources, destinations, transformations, models, workflows)
2. Checking pipeline status and troubleshooting issues
3. Performing actions like pausing, resuming, or running pipelines
4. Creating and configuring new pipelines and destinations
5. Managing team members and permissions

Context from Hevo documentation:
{context}

When the user asks you to perform an action on their Hevo account, respond with a JSON action block:
```json
{{"action": "<action_name>", "params": {{...}}}}
```

Available actions:
- list_pipelines: List all pipelines
- get_pipeline: Get pipeline details (params: id or name)
- pause_pipeline: Pause a pipeline (params: id or name)
- resume_pipeline: Resume a pipeline (params: id or name)
- run_pipeline: Run a pipeline immediately (params: id or name)
- list_destinations: List all destinations
- list_objects: List objects in a pipeline (params: pipeline_id or pipeline_name)
- skip_object: Skip an object (params: pipeline_id, object_name)
- restart_object: Restart an object (params: pipeline_id, object_name)

If you need more information to complete the action, ask the user.
Always be helpful, concise, and accurate based on the documentation context provided.
"""


class BaseLLM(ABC):
    """Abstract base class for LLM providers."""

    def __init__(self, model: Optional[str] = None, temperature: float = 0.7):
        """
        Initialize the LLM.

        Args:
            model: Model name to use
            temperature: Sampling temperature
        """
        self.model = model
        self.temperature = temperature

    @abstractmethod
    def chat(
        self,
        message: str,
        context: str = "",
        conversation_history: Optional[list[dict]] = None,
    ) -> str:
        """
        Send a chat message and get a response.

        Args:
            message: User's message
            context: RAG context from documentation
            conversation_history: Previous messages in the conversation

        Returns:
            Assistant's response
        """
        pass

    @abstractmethod
    def is_configured(self) -> bool:
        """Check if the LLM is properly configured."""
        pass

    def get_system_prompt(self, context: str = "") -> str:
        """
        Get the system prompt with context.

        Args:
            context: RAG context to include

        Returns:
            Formatted system prompt
        """
        return SYSTEM_PROMPT.format(
            context=context if context else "No documentation context available."
        )


def get_llm(
    provider: Optional[str] = None,
    model: Optional[str] = None,
    api_key: Optional[str] = None,
) -> BaseLLM:
    """
    Factory function to create an LLM instance.

    Args:
        provider: LLM provider ("openai", "anthropic", "ollama")
        model: Model name
        api_key: API key (for OpenAI and Anthropic)

    Returns:
        LLM instance

    Raises:
        ValueError: If provider is not supported
    """
    config = get_config()

    # Use config values if not provided
    if provider is None:
        provider = config.llm.provider
    if model is None:
        model = config.llm.model
    if api_key is None:
        api_key = config.llm.api_key.get_secret_value()

    # Import and create the appropriate LLM
    if provider == "openai":
        from hevo_assistant.llm.openai_llm import OpenAILLM

        return OpenAILLM(model=model, api_key=api_key)

    elif provider == "anthropic":
        from hevo_assistant.llm.anthropic_llm import AnthropicLLM

        return AnthropicLLM(model=model, api_key=api_key)

    elif provider == "ollama":
        from hevo_assistant.llm.ollama_llm import OllamaLLM

        return OllamaLLM(model=model)

    else:
        raise ValueError(
            f"Unsupported LLM provider: {provider}. "
            f"Supported: openai, anthropic, ollama"
        )
