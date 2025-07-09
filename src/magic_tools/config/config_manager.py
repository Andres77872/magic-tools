"""Configuration management for Magic Tools."""

import json
import os
from pathlib import Path
from typing import Optional
import logging
import aiohttp
import asyncio

from .settings import Settings


class ConfigManager:
    """Manages application configuration and settings."""
    
    def __init__(self, config_dir: Optional[str] = None):
        """Initialize the configuration manager.
        
        Args:
            config_dir: Custom configuration directory path
        """
        self.logger = logging.getLogger(__name__)
        
        # Determine configuration directory
        if config_dir:
            self.config_dir = Path(config_dir)
        else:
            # Use XDG Base Directory Specification
            xdg_config_home = os.environ.get("XDG_CONFIG_HOME")
            if xdg_config_home:
                self.config_dir = Path(xdg_config_home) / "magic-tools"
            else:
                self.config_dir = Path.home() / ".config" / "magic-tools"
        
        self.config_file = self.config_dir / "settings.json"
        self.settings = Settings()
        
        # Ensure config directory exists
        self.config_dir.mkdir(parents=True, exist_ok=True)
        
        # Load settings on initialization
        self.load_settings()
        # Ensure API key exists and validate configuration
        self._ensure_api_key()
        self._validate_ai_settings()
    
    def load_settings(self) -> Settings:
        """Load settings from the configuration file.
        
        Returns:
            Loaded settings object
        """
        try:
            if self.config_file.exists():
                with open(self.config_file, 'r') as f:
                    data = json.load(f)
                    self.settings = Settings.from_dict(data)
                    self.logger.info(f"Settings loaded from {self.config_file}")
            else:
                self.logger.info("No config file found, using defaults")
                self.save_settings()  # Create default config file
        except Exception as e:
            self.logger.error(f"Failed to load settings: {e}")
            self.settings = Settings()  # Fall back to defaults
        
        return self.settings
    
    def save_settings(self) -> bool:
        """Save current settings to the configuration file.
        
        Returns:
            True if saved successfully, False otherwise
        """
        try:
            with open(self.config_file, 'w') as f:
                json.dump(self.settings.to_dict(), f, indent=2)
            self.logger.info(f"Settings saved to {self.config_file}")
            return True
        except Exception as e:
            self.logger.error(f"Failed to save settings: {e}")
            return False
    
    def get_settings(self) -> Settings:
        """Get current settings.
        
        Returns:
            Current settings object
        """
        return self.settings
    
    def update_settings(self, **kwargs) -> bool:
        """Update specific settings.
        
        Args:
            **kwargs: Settings to update (nested dict structure)
            
        Returns:
            True if updated and saved successfully
        """
        try:
            current_dict = self.settings.to_dict()
            
            # Update nested dictionary
            for key, value in kwargs.items():
                if key in current_dict and isinstance(value, dict):
                    current_dict[key].update(value)
                else:
                    current_dict[key] = value
            
            self.settings = Settings.from_dict(current_dict)
            return self.save_settings()
        except Exception as e:
            self.logger.error(f"Failed to update settings: {e}")
            return False
    
    def reset_to_defaults(self) -> bool:
        """Reset settings to default values.
        
        Returns:
            True if reset successfully
        """
        try:
            self.settings = Settings()
            return self.save_settings()
        except Exception as e:
            self.logger.error(f"Failed to reset settings: {e}")
            return False
    
    def get_config_path(self) -> Path:
        """Get the configuration directory path.
        
        Returns:
            Path to configuration directory
        """
        return self.config_dir
    
    def _ensure_api_key(self):
        """Populate AI API key from environment if missing and persist it."""
        if self.settings.ai.provider == "openai" and not self.settings.ai.api_key:
            env_key = os.getenv("OPENAI_API_KEY", "")
            if env_key:
                self.settings.ai.api_key = env_key
                self.logger.info("OpenAI API key loaded from environment, saving to config file.")
                # Persist to config
                self.save_settings()
            else:
                self.logger.warning("OpenAI API key is not set. Functionality may be limited until provided.")

    def _validate_ai_settings(self) -> bool:
        """Validate AI settings by sending a small request to the provider base URL.

        Returns:
            bool: True if validation is successful, False otherwise.
        """
        if self.settings.ai.provider == "openai" and self.settings.ai.api_key:
            async def _validate_async():
                url = f"{self.settings.ai.base_url.rstrip('/')}/models"
                headers = {"Authorization": f"Bearer {self.settings.ai.api_key}"}
                try:
                    async with aiohttp.ClientSession() as session:
                        async with session.get(url, headers=headers, timeout=10) as resp:
                            if resp.status == 200:
                                self.logger.info("OpenAI API key validated successfully.")
                                return True
                            else:
                                text = await resp.text()
                                self.logger.error(
                                    f"OpenAI validation failed: {resp.status} – {text[:200]}"
                                )
                except Exception as exc:
                    self.logger.error(f"Failed to validate OpenAI API key: {exc}")
                return False
            try:
                return asyncio.run(_validate_async())
            except RuntimeError:
                # If already inside an event loop (e.g., PyQt's qasync), create task
                loop = asyncio.get_event_loop()
                future = asyncio.ensure_future(_validate_async())
                loop.run_until_complete(future)
                return future.result()
        return False

    def backup_config(self) -> bool:
        """Create a backup of the current configuration.
        
        Returns:
            True if backup created successfully
        """
        try:
            import shutil
            from datetime import datetime
            
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            backup_file = self.config_dir / f"settings_backup_{timestamp}.json"
            
            if self.config_file.exists():
                shutil.copy2(self.config_file, backup_file)
                self.logger.info(f"Config backup created: {backup_file}")
                return True
            else:
                self.logger.warning("No config file to backup")
                return False
        except Exception as e:
            self.logger.error(f"Failed to create backup: {e}")
            return False 