"""Main application class for Magic Tools."""

import sys
import logging
from typing import Optional
from PyQt5 import QtWidgets, QtCore, QtGui

from ..config import ConfigManager
from ..ui import MainWindow
from ..ai import AIManager
from ..tools import ToolManager
from .hotkeys import GlobalHotkeyManager


class MagicToolsApp(QtWidgets.QApplication):
    """Main application class for Magic Tools."""
    
    def __init__(self, argv):
        super().__init__(argv)
        
        # Set up logging
        self.setup_logging()
        self.logger = logging.getLogger(__name__)
        
        # Initialize core components
        self.config_manager = ConfigManager()
        self.settings = self.config_manager.get_settings()
        
        # Initialize managers
        self.hotkey_manager = GlobalHotkeyManager()
        self.ai_manager = AIManager(self.settings.ai)
        self.tool_manager = ToolManager(self.settings.tools)
        
        # Initialize main window
        self.main_window = MainWindow(
            self.config_manager,
            self.ai_manager,
            self.tool_manager
        )
        
        # Set up application properties
        self.setup_application()
        
        # Set up system tray icon
        self.setup_tray_icon()
        
        # Connect signals
        self.setup_signals()
        
        # Register hotkeys
        self.setup_hotkeys()
        
        # Show window if configured to do so
        if self.settings.ui.show_on_startup:
            self.main_window.show()
    
    def setup_logging(self):
        """Set up application logging."""
        logging.basicConfig(
            level=logging.INFO,
            format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
            handlers=[
                logging.StreamHandler(sys.stdout),
                logging.FileHandler('magic_tools.log')
            ]
        )
    
    def setup_application(self):
        """Set up application-wide properties."""
        self.setApplicationName("Magic Tools")
        self.setApplicationVersion("0.1.0")
        self.setOrganizationName("Magic Tools")
        self.setQuitOnLastWindowClosed(False)  # Keep running in background
        
        # Set application icon if available
        try:
            icon_path = "resources/icon.png"  # You can add an icon later
            if QtCore.QFile.exists(icon_path):
                self.setWindowIcon(QtGui.QIcon(icon_path))
        except Exception as e:
            self.logger.debug(f"Could not load application icon: {e}")
    
    def setup_tray_icon(self):
        """Create and show a system tray icon with an Exit option."""
        try:
            if not QtWidgets.QSystemTrayIcon.isSystemTrayAvailable():
                self.logger.info("System tray is not available on this system")
                self.tray_icon = None
                return
            
            # Choose application icon or a reasonable fallback
            icon = QtGui.QIcon()
            try:
                if QtCore.QFile.exists("resources/icon.png"):
                    icon = QtGui.QIcon("resources/icon.png")
            except Exception:
                pass
            if icon.isNull():
                icon = self.style().standardIcon(QtWidgets.QStyle.SP_ComputerIcon)
            
            self.tray_icon = QtWidgets.QSystemTrayIcon(icon, self)
            self.tray_icon.setToolTip("Magic Tools")
            
            # Context menu with Exit option
            tray_menu = QtWidgets.QMenu()
            exit_action = tray_menu.addAction("Exit")
            exit_action.triggered.connect(self.quit)
            self.tray_icon.setContextMenu(tray_menu)
            
            # Optional: left-click toggles visibility
            def on_tray_activated(reason):
                if reason == QtWidgets.QSystemTrayIcon.Trigger:
                    self.main_window.toggle_visibility()
            self.tray_icon.activated.connect(on_tray_activated)
            
            self.tray_icon.show()
            self.logger.info("System tray icon initialized")
        except Exception as e:
            self.logger.error(f"Failed to initialize system tray icon: {e}")
    
    def setup_signals(self):
        """Connect signals between components."""
        # Connect hotkey signals to main window
        self.hotkey_manager.toggle_requested.connect(self.main_window.toggle_visibility)
        self.hotkey_manager.ai_chat_requested.connect(self.main_window.show_ai_chat)
        self.hotkey_manager.quick_search_requested.connect(self.main_window.show_quick_search)
        self.hotkey_manager.hide_requested.connect(self.main_window.hide)
        
        # Connect application quit signal
        self.aboutToQuit.connect(self.cleanup)
        
        # Connect main window settings changes to reload hotkeys
        self.main_window.config_widget.settings_changed.connect(self.on_settings_changed)
    
    def setup_hotkeys(self):
        """Set up global hotkeys based on current settings."""
        hotkey_settings = self.settings.hotkeys
        self.hotkey_manager.register_default_hotkeys(
            toggle_shortcut=hotkey_settings.toggle_shortcut,
            ai_chat_shortcut=hotkey_settings.ai_chat_shortcut,
            quick_search_shortcut=hotkey_settings.quick_search_shortcut,
            hide_shortcut=hotkey_settings.hide_shortcut
        )
    
    def update_hotkeys(self):
        """Update hotkeys when settings change."""
        hotkey_settings = self.settings.hotkeys
        self.hotkey_manager.update_hotkey('toggle', hotkey_settings.toggle_shortcut)
        self.hotkey_manager.update_hotkey('ai_chat', hotkey_settings.ai_chat_shortcut)
        self.hotkey_manager.update_hotkey('quick_search', hotkey_settings.quick_search_shortcut)
        self.hotkey_manager.update_hotkey('hide', hotkey_settings.hide_shortcut)
    
    def on_settings_changed(self, new_settings):
        """Handle settings changes from the config widget."""
        self.logger.info("Application received settings changes")
        self.settings = new_settings
        self.update_hotkeys()
    
    def reload_settings(self):
        """Reload settings from configuration."""
        self.logger.info("Reloading application settings")
        self.config_manager.load_settings()
        self.settings = self.config_manager.get_settings()
        
        # Update components with new settings
        self.ai_manager.update_settings(self.settings.ai)
        self.tool_manager.update_settings(self.settings.tools)
        self.main_window.update_settings(self.settings.ui)
        self.update_hotkeys()
    
    def save_settings(self):
        """Save current settings to configuration."""
        self.logger.info("Saving application settings")
        return self.config_manager.save_settings()
    
    def get_main_window(self) -> MainWindow:
        """Get the main window instance."""
        return self.main_window
    
    def get_config_manager(self) -> ConfigManager:
        """Get the configuration manager."""
        return self.config_manager
    
    def get_ai_manager(self) -> AIManager:
        """Get the AI manager."""
        return self.ai_manager
    
    def get_tool_manager(self) -> ToolManager:
        """Get the tool manager."""
        return self.tool_manager
    
    def cleanup(self):
        """Clean up application resources."""
        self.logger.info("Cleaning up application resources")
        
        # Save settings before exit
        self.save_settings()
        
        # Clean up managers
        self.hotkey_manager.cleanup()
        self.ai_manager.cleanup()
        self.tool_manager.cleanup()
        
        # Hide main window
        if self.main_window.isVisible():
            self.main_window.hide()
        
        # Hide tray icon
        try:
            if getattr(self, 'tray_icon', None):
                self.tray_icon.hide()
                self.tray_icon.deleteLater()
        except Exception:
            pass
        
        self.logger.info("Application cleanup completed")
    
    def run(self) -> int:
        """Run the application."""
        self.logger.info("Starting Magic Tools application")
        
        return self.exec_()


def create_app(argv: Optional[list] = None) -> MagicToolsApp:
    """Create and return a Magic Tools application instance.
    
    Args:
        argv: Command line arguments (defaults to sys.argv)
        
    Returns:
        MagicToolsApp instance
    """
    if argv is None:
        argv = sys.argv
    
    app = MagicToolsApp(argv)
    return app 