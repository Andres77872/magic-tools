"""Core functionality for Magic Tools."""

from .app import MagicToolsApp, create_app
from .hotkeys import GlobalHotkeyManager

__all__ = ["MagicToolsApp", "create_app", "GlobalHotkeyManager"] 