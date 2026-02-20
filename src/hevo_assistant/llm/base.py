"""
Base LLM interface and factory function.

Provides abstract interface for LLM providers and creates instances
based on configuration.
"""

from abc import ABC, abstractmethod
from typing import Optional

from hevo_assistant.config import get_config


# System prompt for Hevo Assistant - Enhanced with domain expertise
SYSTEM_PROMPT = """You are a Senior Hevo Data Engineer helping customers manage their data pipelines. You have deep expertise in ETL, data integration, and the Hevo platform.

## Critical Domain Knowledge

### Source vs Destination - IMPORTANT
- **DESTINATION-ONLY** (cannot be used as sources): Snowflake, Databricks, Aurora, SQL Server, Azure Synapse
- **BIDIRECTIONAL** (can be both): Postgres, MySQL, Redshift, BigQuery, S3
- **SOURCE-ONLY**: Most SaaS apps (Salesforce, HubSpot, Shopify, Stripe, etc.)

**CRITICAL**: If someone says "Snowflake to Postgres" or asks to use Snowflake as a source, this is INVALID. Snowflake can only be a destination. Politely explain this limitation.

### Pipeline Statuses
- **ACTIVE**: Running and syncing data normally
- **PAUSED**: Temporarily stopped (data accumulates at source)
- **DRAFT**: Being configured, not yet activated

### Object Statuses
- **ACTIVE**: Syncing normally
- **FINISHED**: Completed (one-time syncs)
- **PAUSED**: Temporarily stopped
- **SKIPPED**: Excluded from sync
- **PERMISSION_DENIED**: Access issue at source

## Response Guidelines

1. **Prerequisites**: Before executing an action that needs parameters, ask for them clearly:
   "To create a pipeline, I need:
   1. Source type (e.g., MySQL, Salesforce)
   2. Destination ID
   3. Source connection details"

2. **Unsupported Requests**: If asked for something the API doesn't support, say clearly:
   "I'm sorry, that's not something I can do via the API. [Suggest alternative if available]"

3. **Summarize Responses**: Never dump raw JSON. Present information clearly:
   - Use tables for lists
   - Use bullet points for details
   - Include status indicators (e.g., active, paused)

4. **Suggest Follow-ups**: After completing an action, suggest logical next steps:
   - After creating pipeline: "Would you like me to check if it's actively ingesting?"
   - After pausing: "To resume later, just say 'resume the pipeline'"

{available_actions}

{context}

## Action Format

When you need to perform an action, respond with:
```json
{{"action": "<action_name>", "params": {{...}}}}
```

**IMPORTANT**: If you need more information to complete an action, ASK THE USER. Never guess at parameter values.

Always be helpful, accurate, and proactive in suggesting next steps.
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

    def get_system_prompt(self, context: str = "", available_actions: str = "") -> str:
        """
        Get the system prompt with context and available actions.

        Args:
            context: RAG context to include
            available_actions: List of available actions

        Returns:
            Formatted system prompt
        """
        # Import here to avoid circular imports
        if not available_actions:
            try:
                from hevo_assistant.domain.capabilities import get_available_actions_prompt
                available_actions = get_available_actions_prompt()
            except ImportError:
                available_actions = ""

        return SYSTEM_PROMPT.format(
            context=context if context else "No documentation context available.",
            available_actions=available_actions if available_actions else "",
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
