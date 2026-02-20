"""
Ollama LLM implementation for local models.

Supports running models locally without API keys.
"""

from typing import Optional

from hevo_assistant.llm.base import BaseLLM


class OllamaLLM(BaseLLM):
    """Ollama local LLM implementation."""

    DEFAULT_MODEL = "llama3"
    DEFAULT_HOST = "http://localhost:11434"

    def __init__(
        self,
        model: Optional[str] = None,
        host: Optional[str] = None,
        temperature: float = 0.7,
    ):
        """
        Initialize Ollama LLM.

        Args:
            model: Model name (default: llama3)
            host: Ollama server host (default: localhost:11434)
            temperature: Sampling temperature
        """
        super().__init__(model=model or self.DEFAULT_MODEL, temperature=temperature)
        self.host = host or self.DEFAULT_HOST
        self._client = None

    @property
    def client(self):
        """Get or create Ollama client (lazy loaded)."""
        if self._client is None:
            import ollama

            self._client = ollama.Client(host=self.host)
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

        # Call Ollama
        response = self.client.chat(
            model=self.model,
            messages=messages,
            options={
                "temperature": self.temperature,
            },
        )

        return response["message"]["content"]

    def is_configured(self) -> bool:
        """
        Check if Ollama is running and the model is available.

        Returns:
            True if Ollama is accessible
        """
        try:
            # Try to list models to check if Ollama is running
            self.client.list()
            return True
        except Exception:
            return False

    def list_models(self) -> list[str]:
        """
        List available models in Ollama.

        Returns:
            List of model names
        """
        try:
            response = self.client.list()
            return [model["name"] for model in response.get("models", [])]
        except Exception:
            return []

    def pull_model(self, model: Optional[str] = None) -> bool:
        """
        Pull a model from Ollama registry.

        Args:
            model: Model name to pull (default: configured model)

        Returns:
            True if successful
        """
        model = model or self.model
        try:
            self.client.pull(model)
            return True
        except Exception:
            return False
