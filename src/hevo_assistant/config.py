"""
Configuration management for Hevo Assistant.

Handles loading, saving, and validating configuration from ~/.hevo/config.json
"""

import json
import os
from datetime import datetime
from pathlib import Path
from typing import Literal, Optional

from pydantic import BaseModel, Field, SecretStr


class HevoConfig(BaseModel):
    """Hevo API credentials configuration."""

    api_key: SecretStr = Field(default=SecretStr(""), description="Hevo API Key")
    api_secret: SecretStr = Field(default=SecretStr(""), description="Hevo API Secret")
    region: Literal["us", "eu", "in", "apac"] = Field(
        default="us", description="Hevo region"
    )

    @property
    def base_url(self) -> str:
        """Get the base URL for the Hevo API based on region."""
        region_urls = {
            "us": "https://us.hevodata.com/api/public/v2.0",
            "eu": "https://eu.hevodata.com/api/public/v2.0",
            "in": "https://in.hevodata.com/api/public/v2.0",
            "apac": "https://apac.hevodata.com/api/public/v2.0",
        }
        return region_urls.get(self.region, region_urls["us"])

    def is_configured(self) -> bool:
        """Check if Hevo credentials are configured."""
        return bool(
            self.api_key.get_secret_value() and self.api_secret.get_secret_value()
        )


class LLMConfig(BaseModel):
    """LLM provider configuration."""

    provider: Literal["openai", "anthropic", "ollama"] = Field(
        default="openai", description="LLM provider to use"
    )
    api_key: SecretStr = Field(default=SecretStr(""), description="LLM API Key")
    model: str = Field(default="gpt-4", description="Model name to use")
    temperature: float = Field(default=0.7, ge=0, le=2, description="Model temperature")

    def is_configured(self) -> bool:
        """Check if LLM is configured (Ollama doesn't need API key)."""
        if self.provider == "ollama":
            return True
        return bool(self.api_key.get_secret_value())


class RAGConfig(BaseModel):
    """RAG system configuration."""

    # Backend selection: "pinecone" (default, lightweight) or "local" (heavy)
    backend: Literal["pinecone", "local"] = Field(
        default="pinecone", description="RAG backend: 'pinecone' or 'local'"
    )

    # Pinecone configuration (default backend)
    pinecone_api_key: SecretStr = Field(
        default=SecretStr(""), description="Pinecone API Key"
    )
    pinecone_index: str = Field(
        default="hevo-docs", description="Pinecone index name"
    )

    # Local ChromaDB configuration (optional, requires local-rag extra)
    db_path: str = Field(
        default="~/.hevo/vectordb", description="Path to ChromaDB storage"
    )
    embedding_model: str = Field(
        default="all-MiniLM-L6-v2", description="Sentence transformer model"
    )

    # Common settings
    chunk_size: int = Field(default=500, description="Text chunk size for embedding")
    chunk_overlap: int = Field(default=50, description="Overlap between chunks")
    top_k: int = Field(default=5, description="Number of results to retrieve")
    last_updated: Optional[datetime] = Field(
        default=None, description="Last documentation update time"
    )

    @property
    def resolved_db_path(self) -> Path:
        """Get the resolved path for the vector database."""
        return Path(self.db_path).expanduser()

    def is_configured(self) -> bool:
        """Check if RAG backend is configured."""
        if self.backend == "pinecone":
            return bool(self.pinecone_api_key.get_secret_value())
        return True  # Local doesn't need external config


class AgentConfig(BaseModel):
    """Multi-agent system configuration."""

    # Coordinator Agent - handles conversation and intent
    coordinator_model: str = Field(
        default="gpt-4", description="Model for Coordinator Agent (smarter reasoning)"
    )
    coordinator_temperature: float = Field(
        default=0.7, ge=0, le=2, description="Temperature for Coordinator Agent"
    )

    # Executor Agent - handles action execution
    executor_model: str = Field(
        default="gpt-3.5-turbo", description="Model for Executor Agent (faster, cheaper)"
    )
    executor_temperature: float = Field(
        default=0.2, ge=0, le=2, description="Temperature for Executor Agent (more deterministic)"
    )

    # Enable/disable multi-agent mode
    enabled: bool = Field(
        default=True, description="Enable multi-agent architecture"
    )


class Config(BaseModel):
    """Main configuration for Hevo Assistant."""

    hevo: HevoConfig = Field(default_factory=HevoConfig)
    llm: LLMConfig = Field(default_factory=LLMConfig)
    rag: RAGConfig = Field(default_factory=RAGConfig)
    agents: AgentConfig = Field(default_factory=AgentConfig)

    @classmethod
    def get_config_dir(cls) -> Path:
        """Get the configuration directory path."""
        return Path.home() / ".hevo"

    @classmethod
    def get_config_path(cls) -> Path:
        """Get the configuration file path."""
        return cls.get_config_dir() / "config.json"

    @classmethod
    def load(cls) -> "Config":
        """Load configuration from file or create default."""
        config_path = cls.get_config_path()

        if config_path.exists():
            try:
                with open(config_path, "r") as f:
                    data = json.load(f)
                return cls.model_validate(data)
            except (json.JSONDecodeError, Exception) as e:
                # If config is corrupted, return default
                print(f"Warning: Could not load config: {e}")
                return cls()
        return cls()

    def save(self) -> None:
        """Save configuration to file."""
        config_dir = self.get_config_dir()
        config_dir.mkdir(parents=True, exist_ok=True)

        config_path = self.get_config_path()

        # Convert to dict, handling SecretStr
        data = self._to_saveable_dict()

        with open(config_path, "w") as f:
            json.dump(data, f, indent=2, default=str)

        # Set restrictive permissions on config file (contains secrets)
        os.chmod(config_path, 0o600)

    def _to_saveable_dict(self) -> dict:
        """Convert config to a dictionary suitable for JSON serialization."""
        return {
            "hevo": {
                "api_key": self.hevo.api_key.get_secret_value(),
                "api_secret": self.hevo.api_secret.get_secret_value(),
                "region": self.hevo.region,
            },
            "llm": {
                "provider": self.llm.provider,
                "api_key": self.llm.api_key.get_secret_value(),
                "model": self.llm.model,
                "temperature": self.llm.temperature,
            },
            "rag": {
                "backend": self.rag.backend,
                "pinecone_api_key": self.rag.pinecone_api_key.get_secret_value(),
                "pinecone_index": self.rag.pinecone_index,
                "db_path": self.rag.db_path,
                "embedding_model": self.rag.embedding_model,
                "chunk_size": self.rag.chunk_size,
                "chunk_overlap": self.rag.chunk_overlap,
                "top_k": self.rag.top_k,
                "last_updated": (
                    self.rag.last_updated.isoformat() if self.rag.last_updated else None
                ),
            },
            "agents": {
                "coordinator_model": self.agents.coordinator_model,
                "coordinator_temperature": self.agents.coordinator_temperature,
                "executor_model": self.agents.executor_model,
                "executor_temperature": self.agents.executor_temperature,
                "enabled": self.agents.enabled,
            },
        }

    def is_ready(self) -> tuple[bool, list[str]]:
        """
        Check if the configuration is ready for use.

        Returns:
            Tuple of (is_ready, list of missing items)
        """
        missing = []

        if not self.hevo.is_configured():
            missing.append("Hevo API credentials (run 'hevo setup')")

        if not self.llm.is_configured():
            missing.append("LLM API key (run 'hevo setup')")

        return len(missing) == 0, missing


# Global config instance (lazy loaded)
_config: Optional[Config] = None


def get_config() -> Config:
    """Get the global configuration instance."""
    global _config
    if _config is None:
        _config = Config.load()
    return _config


def reload_config() -> Config:
    """Reload configuration from file."""
    global _config
    _config = Config.load()
    return _config


def save_config(config: Config) -> None:
    """Save configuration and update global instance."""
    global _config
    config.save()
    _config = config
