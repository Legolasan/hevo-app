"""
Anthropic Claude LLM implementation.

Supports Claude 3 models (Opus, Sonnet, Haiku).
"""

from typing import Optional

from hevo_assistant.llm.base import BaseLLM


class AnthropicLLM(BaseLLM):
    """Anthropic Claude implementation."""

    DEFAULT_MODEL = "claude-3-sonnet-20240229"

    def __init__(
        self,
        model: Optional[str] = None,
        api_key: Optional[str] = None,
        temperature: float = 0.7,
    ):
        """
        Initialize Anthropic LLM.

        Args:
            model: Model name (default: claude-3-sonnet)
            api_key: Anthropic API key
            temperature: Sampling temperature
        """
        super().__init__(model=model or self.DEFAULT_MODEL, temperature=temperature)
        self.api_key = api_key
        self._client = None

    @property
    def client(self):
        """Get or create Anthropic client (lazy loaded)."""
        if self._client is None:
            import anthropic

            self._client = anthropic.Anthropic(api_key=self.api_key)
        return self._client

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
            conversation_history: Previous messages

        Returns:
            Assistant's response
        """
        # Build messages (Anthropic format)
        messages = []

        # Add conversation history
        if conversation_history:
            for msg in conversation_history:
                messages.append(
                    {
                        "role": msg["role"],
                        "content": msg["content"],
                    }
                )

        # Add current message
        messages.append({"role": "user", "content": message})

        # Call Anthropic API
        response = self.client.messages.create(
            model=self.model,
            max_tokens=2048,
            system=self.get_system_prompt(context),
            messages=messages,
            temperature=self.temperature,
        )

        return response.content[0].text

    def is_configured(self) -> bool:
        """Check if API key is configured."""
        return bool(self.api_key)
