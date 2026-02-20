"""
OpenAI LLM implementation.

Supports GPT-4, GPT-3.5-turbo, and other OpenAI models.
"""

from typing import Optional

from hevo_assistant.llm.base import BaseLLM


class OpenAILLM(BaseLLM):
    """OpenAI GPT implementation."""

    DEFAULT_MODEL = "gpt-4"

    def __init__(
        self,
        model: Optional[str] = None,
        api_key: Optional[str] = None,
        temperature: float = 0.7,
    ):
        """
        Initialize OpenAI LLM.

        Args:
            model: Model name (default: gpt-4)
            api_key: OpenAI API key
            temperature: Sampling temperature
        """
        super().__init__(model=model or self.DEFAULT_MODEL, temperature=temperature)
        self.api_key = api_key
        self._client = None

    @property
    def client(self):
        """Get or create OpenAI client (lazy loaded)."""
        if self._client is None:
            from openai import OpenAI

            self._client = OpenAI(api_key=self.api_key)
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
        # Build messages
        messages = [{"role": "system", "content": self.get_system_prompt(context)}]

        # Add conversation history
        if conversation_history:
            messages.extend(conversation_history)

        # Add current message
        messages.append({"role": "user", "content": message})

        # Call OpenAI API
        response = self.client.chat.completions.create(
            model=self.model,
            messages=messages,
            temperature=self.temperature,
            max_tokens=2048,
        )

        return response.choices[0].message.content

    def is_configured(self) -> bool:
        """Check if API key is configured."""
        return bool(self.api_key)
