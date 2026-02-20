"""
Hevo Assistant - Chat-to-Action CLI for Hevo Data pipelines.

A RAG-powered CLI that enables natural language interaction with
Hevo Data pipelines, destinations, and models.
"""

__version__ = "0.1.0"
__author__ = "Hevo App"

from hevo_assistant.config import Config, get_config

__all__ = ["Config", "get_config", "__version__"]
