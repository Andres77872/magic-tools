#!/usr/bin/env python3
"""Test script for Magic Tools configuration panel."""

import sys
import os

# Add the src directory to the Python path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'src'))

from PyQt5.QtWidgets import QApplication
from magic_tools.config import ConfigManager
from magic_tools.ui.config_widget import ConfigWidget


def main():
    """Test the configuration widget."""
    app = QApplication(sys.argv)
    
    # Create config manager
    config_manager = ConfigManager()
    
    # Create and show config widget
    config_widget = ConfigWidget(config_manager)
    config_widget.setWindowTitle("Magic Tools - Configuration Test")
    config_widget.resize(700, 600)
    config_widget.show()
    
    # Connect settings changed signal to print changes
    def on_settings_changed(settings):
        print("Settings changed!")
        print(f"AI Provider: {settings.ai.provider}")
        print(f"AI Model: {settings.ai.model}")
        print(f"Theme: {settings.ui.theme}")
        print(f"Toggle Shortcut: {settings.hotkeys.toggle_shortcut}")
        print("=" * 50)
    
    config_widget.settings_changed.connect(on_settings_changed)
    
    return app.exec_()


if __name__ == "__main__":
    sys.exit(main()) 