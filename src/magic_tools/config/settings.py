"""Settings model for Magic Tools configuration."""

from dataclasses import dataclass, field
from typing import Dict, Any, List
import json
import os


@dataclass
class UISettings:
    """UI-related settings."""
    theme: str = "dark"
    window_width: int = 600
    window_height: int = 500
    opacity: float = 0.95
    always_on_top: bool = True
    show_on_startup: bool = False
    animation_enabled: bool = True


@dataclass
class HotkeySettings:
    """Hotkey configuration."""
    toggle_shortcut: str = "Ctrl+Space"
    ai_chat_shortcut: str = "Ctrl+Alt+A"
    quick_search_shortcut: str = "Ctrl+Alt+S"
    focus_selected_shortcut: str = "Ctrl+Alt+F"


@dataclass
class AISettings:
    """AI integration settings."""
    provider: str = "openai"  # openai, local, anthropic
    api_key: str = ""
    base_url: str = "https://api.openai.com/v1"
    model: str = "gpt-4.1-2025-04-14"
    max_tokens: int = 1000
    temperature: float = 0.7
    enabled: bool = True
    local_model_path: str = ""


@dataclass
class ToolSettings:
    """Tool system settings."""
    enabled_tools: List[str] = field(default_factory=lambda: ["calculator", "file_search", "system_info", "focus_window"])
    custom_tools_path: str = ""
    auto_load_tools: bool = True


@dataclass
class Settings:
    """Main settings container."""
    ui: UISettings = field(default_factory=UISettings)
    hotkeys: HotkeySettings = field(default_factory=HotkeySettings)
    ai: AISettings = field(default_factory=AISettings)
    tools: ToolSettings = field(default_factory=ToolSettings)
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert settings to dictionary."""
        return {
            "ui": {
                "theme": self.ui.theme,
                "window_width": self.ui.window_width,
                "window_height": self.ui.window_height,
                "opacity": self.ui.opacity,
                "always_on_top": self.ui.always_on_top,
                "show_on_startup": self.ui.show_on_startup,
                "animation_enabled": self.ui.animation_enabled,
            },
            "hotkeys": {
                "toggle_shortcut": self.hotkeys.toggle_shortcut,
                "ai_chat_shortcut": self.hotkeys.ai_chat_shortcut,
                "quick_search_shortcut": self.hotkeys.quick_search_shortcut,
                "focus_selected_shortcut": self.hotkeys.focus_selected_shortcut,
            },
            "ai": {
                "provider": self.ai.provider,
                "api_key": self.ai.api_key,
                "base_url": self.ai.base_url,
                "model": self.ai.model,
                "max_tokens": self.ai.max_tokens,
                "temperature": self.ai.temperature,
                "enabled": self.ai.enabled,
                "local_model_path": self.ai.local_model_path,
            },
            "tools": {
                "enabled_tools": self.tools.enabled_tools,
                "custom_tools_path": self.tools.custom_tools_path,
                "auto_load_tools": self.tools.auto_load_tools,
            },
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "Settings":
        """Create settings from dictionary."""
        settings = cls()
        
        if "ui" in data:
            ui_data = data["ui"]
            settings.ui = UISettings(
                theme=ui_data.get("theme", settings.ui.theme),
                window_width=ui_data.get("window_width", settings.ui.window_width),
                window_height=ui_data.get("window_height", settings.ui.window_height),
                opacity=ui_data.get("opacity", settings.ui.opacity),
                always_on_top=ui_data.get("always_on_top", settings.ui.always_on_top),
                show_on_startup=ui_data.get("show_on_startup", settings.ui.show_on_startup),
                animation_enabled=ui_data.get("animation_enabled", settings.ui.animation_enabled),
            )
        
        if "hotkeys" in data:
            hotkey_data = data["hotkeys"]
            settings.hotkeys = HotkeySettings(
                toggle_shortcut=hotkey_data.get("toggle_shortcut", settings.hotkeys.toggle_shortcut),
                ai_chat_shortcut=hotkey_data.get("ai_chat_shortcut", settings.hotkeys.ai_chat_shortcut),
                quick_search_shortcut=hotkey_data.get("quick_search_shortcut", settings.hotkeys.quick_search_shortcut),
                focus_selected_shortcut=hotkey_data.get("focus_selected_shortcut", settings.hotkeys.focus_selected_shortcut),
            )
        
        if "ai" in data:
            ai_data = data["ai"]
            settings.ai = AISettings(
                provider=ai_data.get("provider", settings.ai.provider),
                api_key=ai_data.get("api_key", settings.ai.api_key),
                base_url=ai_data.get("base_url", settings.ai.base_url),
                model=ai_data.get("model", settings.ai.model),
                max_tokens=ai_data.get("max_tokens", settings.ai.max_tokens),
                temperature=ai_data.get("temperature", settings.ai.temperature),
                enabled=ai_data.get("enabled", settings.ai.enabled),
                local_model_path=ai_data.get("local_model_path", settings.ai.local_model_path),
            )
        
        if "tools" in data:
            tools_data = data["tools"]
            settings.tools = ToolSettings(
                enabled_tools=tools_data.get("enabled_tools", settings.tools.enabled_tools),
                custom_tools_path=tools_data.get("custom_tools_path", settings.tools.custom_tools_path),
                auto_load_tools=tools_data.get("auto_load_tools", settings.tools.auto_load_tools),
            )
        
        return settings 