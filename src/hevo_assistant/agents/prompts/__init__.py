"""
System prompts for multi-agent system.
"""

from hevo_assistant.agents.prompts.coordinator import COORDINATOR_PROMPT, get_coordinator_prompt
from hevo_assistant.agents.prompts.executor import EXECUTOR_PROMPT, get_executor_prompt

__all__ = [
    "COORDINATOR_PROMPT",
    "get_coordinator_prompt",
    "EXECUTOR_PROMPT",
    "get_executor_prompt",
]
