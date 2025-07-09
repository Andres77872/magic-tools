"""AI integration module for Magic Tools."""

from .ai_manager import AIManager
from .providers import OpenAIProvider, LocalProvider

__all__ = ["AIManager", "OpenAIProvider", "LocalProvider"] 