"""Main window for Magic Tools application."""

import logging
from typing import Optional
from PyQt5 import QtWidgets, QtCore, QtGui
from PyQt5.QtCore import Qt, QPropertyAnimation, QEasingCurve

from ..config import ConfigManager
from ..config.settings import UISettings
from ..ai import AIManager
from ..tools import ToolManager
from .launcher_widget import LauncherWidget
from .ai_chat_widget import AIChatWidget
from .config_widget import ConfigWidget
from .style import StyleManager


class MainWindow(QtWidgets.QMainWindow):
    """Main application window for Magic Tools."""
    
    def __init__(self, config_manager: ConfigManager, ai_manager: AIManager, tool_manager: ToolManager):
        super().__init__()
        
        self.logger = logging.getLogger(__name__)
        self.config_manager = config_manager
        self.ai_manager = ai_manager
        self.tool_manager = tool_manager
        self.ui_settings = config_manager.get_settings().ui
        
        # Initialize style manager
        self.style_manager = StyleManager()
        self.style_manager.set_theme(self.ui_settings.theme)
        
        # Initialize UI components
        self.launcher_widget = None
        self.ai_chat_widget = None
        self.config_widget = None
        self.current_mode = "launcher"  # "launcher", "ai_chat", or "config"
        
        # Animation for smooth transitions
        self.fade_animation = None
        
        # Setup window
        self.setup_window()
        self.setup_ui()
        self.apply_theme()
        
        # Connect signals
        self.setup_signals()
    
    def setup_window(self):
        """Setup main window properties."""
        self.setWindowTitle("Magic Tools")
        self.setWindowFlags(
            Qt.WindowStaysOnTopHint |
            Qt.FramelessWindowHint |
            Qt.Tool
        )
        
        # Set window size
        self.resize(self.ui_settings.window_width, self.ui_settings.window_height)
        
        # Center window on screen
        self.center_on_screen()
        
        # Set window opacity
        self.setWindowOpacity(self.ui_settings.opacity)
        
        # Set window attributes
        self.setAttribute(Qt.WA_TranslucentBackground, True)
        self.setAttribute(Qt.WA_ShowWithoutActivating, False)
    
    def setup_ui(self):
        """Setup the user interface."""
        # Main widget with rounded corners
        self.main_widget = QtWidgets.QWidget()
        self.main_widget.setObjectName("mainWidget")
        self.setCentralWidget(self.main_widget)
        
        # Main layout
        self.main_layout = QtWidgets.QStackedLayout(self.main_widget)
        self.main_layout.setContentsMargins(0, 0, 0, 0)
        
        # Create and add launcher widget
        self.launcher_widget = LauncherWidget(self.tool_manager, self.ai_manager)
        self.main_layout.addWidget(self.launcher_widget)
        
        # Create and add AI chat widget
        self.ai_chat_widget = AIChatWidget(self.ai_manager)
        self.main_layout.addWidget(self.ai_chat_widget)
        
        # Create and add config widget
        self.config_widget = ConfigWidget(self.config_manager)
        self.main_layout.addWidget(self.config_widget)
        
        # Set initial widget
        self.main_layout.setCurrentWidget(self.launcher_widget)
    
    def setup_signals(self):
        """Setup signal connections."""
        # Connect launcher widget signals
        self.launcher_widget.ai_chat_requested.connect(self.show_ai_chat)
        self.launcher_widget.config_requested.connect(self.show_config)
        self.launcher_widget.tool_executed.connect(self.on_tool_executed)
        
        # Connect AI chat widget signals
        self.ai_chat_widget.back_to_launcher.connect(self.show_launcher)
        self.ai_chat_widget.close_requested.connect(self.hide)
        
        # Connect config widget signals
        self.config_widget.back_to_launcher.connect(self.show_launcher)
        self.config_widget.settings_changed.connect(self.on_settings_changed)
    
    def apply_theme(self):
        """Apply theme styling to the window."""
        self.style_manager.set_theme(self.ui_settings.theme)
        self.style_manager.apply_theme_to_widget(self)
    

    
    def center_on_screen(self):
        """Center the window on the screen."""
        screen = QtWidgets.QApplication.desktop().screenGeometry()
        window = self.geometry()
        self.move(
            (screen.width() - window.width()) // 2,
            (screen.height() - window.height()) // 2
        )
    
    def toggle_visibility(self):
        """Toggle window visibility."""
        if self.isVisible():
            self.hide()
        else:
            self.show()
    
    def show(self):
        """Show the window with animation if enabled."""
        super().show()
        self.raise_()
        self.activateWindow()
        
        # Reset to launcher mode when showing
        if self.current_mode != "launcher":
            self.show_launcher()
        
        # Focus on search input
        if self.launcher_widget:
            self.launcher_widget.focus_search_input()
        
        # Apply show animation if enabled
        if self.ui_settings.animation_enabled:
            self.animate_show()
    
    def hide(self):
        """Hide the window with animation if enabled."""
        if self.ui_settings.animation_enabled:
            self.animate_hide()
        else:
            super().hide()
    
    def animate_show(self):
        """Animate window appearance."""
        if self.fade_animation:
            self.fade_animation.stop()
        
        self.fade_animation = QPropertyAnimation(self, b"windowOpacity")
        self.fade_animation.setDuration(200)
        self.fade_animation.setStartValue(0.0)
        self.fade_animation.setEndValue(self.ui_settings.opacity)
        self.fade_animation.setEasingCurve(QEasingCurve.OutQuad)
        self.fade_animation.start()
    
    def animate_hide(self):
        """Animate window disappearance."""
        if self.fade_animation:
            self.fade_animation.stop()
        
        self.fade_animation = QPropertyAnimation(self, b"windowOpacity")
        self.fade_animation.setDuration(150)
        self.fade_animation.setStartValue(self.ui_settings.opacity)
        self.fade_animation.setEndValue(0.0)
        self.fade_animation.setEasingCurve(QEasingCurve.InQuad)
        self.fade_animation.finished.connect(lambda: super(MainWindow, self).hide())
        self.fade_animation.start()
    
    def show_launcher(self):
        """Switch to launcher mode."""
        self.current_mode = "launcher"
        self.main_layout.setCurrentWidget(self.launcher_widget)
        self.launcher_widget.focus_search_input()
        self.logger.debug("Switched to launcher mode")
    
    def show_ai_chat(self):
        """Switch to AI chat mode."""
        self.current_mode = "ai_chat"
        self.main_layout.setCurrentWidget(self.ai_chat_widget)
        self.ai_chat_widget.focus_input()
        self.logger.debug("Switched to AI chat mode")
    
    def show_config(self):
        """Switch to config mode."""
        self.current_mode = "config"
        self.main_layout.setCurrentWidget(self.config_widget)
        self.logger.debug("Switched to config mode")
    
    def show_quick_search(self):
        """Show the window in quick search mode."""
        self.show()
        self.show_launcher()
        if self.launcher_widget:
            self.launcher_widget.focus_search_input()
    
    def on_tool_executed(self, tool_name: str, result):
        """Handle tool execution completion."""
        self.logger.info(f"Tool executed: {tool_name}")
        
        # Optionally hide the window after tool execution
        # You can customize this behavior based on user preferences
        # self.hide()
    
    def on_settings_changed(self, new_settings):
        """Handle settings changes from the config widget."""
        self.logger.info("Settings changed, updating application...")
        
        # Update the config manager's settings
        self.config_manager.settings = new_settings
        
        # Update managers directly since we have references
        self.ai_manager.update_settings(new_settings.ai)
        self.tool_manager.update_settings(new_settings.tools)
        
        # Update UI settings
        self.ui_settings = new_settings.ui
        self.update_settings(new_settings.ui)
        
        # Signal the parent app to update hotkeys if possible
        try:
            from PyQt5.QtWidgets import QApplication
            app = QApplication.instance()
            if hasattr(app, 'update_hotkeys'):
                app.update_hotkeys()
        except Exception as e:
            self.logger.warning(f"Could not update hotkeys: {e}")
    
    def update_settings(self, ui_settings: UISettings):
        """Update UI settings and apply changes."""
        self.ui_settings = ui_settings
        
        # Update window properties
        self.resize(ui_settings.window_width, ui_settings.window_height)
        self.setWindowOpacity(ui_settings.opacity)
        
        # Update always on top
        flags = self.windowFlags()
        if ui_settings.always_on_top:
            flags |= Qt.WindowStaysOnTopHint
        else:
            flags &= ~Qt.WindowStaysOnTopHint
        self.setWindowFlags(flags)
        
        # Apply theme
        self.style_manager.set_theme(ui_settings.theme)
        self.apply_theme()
        
        # Update child widgets
        if self.launcher_widget:
            self.launcher_widget.update_settings(ui_settings)
        if self.ai_chat_widget:
            self.ai_chat_widget.update_settings(ui_settings)
        if self.config_widget:
            self.config_widget.update_settings(ui_settings)
        
        self.logger.info("UI settings updated")
    
    def keyPressEvent(self, event):
        """Handle key press events."""
        if event.key() == Qt.Key_Escape:
            self.hide()
        elif event.key() == Qt.Key_Tab and event.modifiers() == Qt.ControlModifier:
            # Switch between launcher and AI chat
            if self.current_mode == "launcher":
                self.show_ai_chat()
            else:
                self.show_launcher()
        elif event.key() == Qt.Key_Comma and event.modifiers() == Qt.ControlModifier:
            # Open settings with Ctrl+,
            self.show_config()
        else:
            super().keyPressEvent(event)
    
    def mousePressEvent(self, event):
        """Handle mouse press events for window dragging."""
        if event.button() == Qt.LeftButton:
            self.drag_position = event.globalPos() - self.frameGeometry().topLeft()
            event.accept()
    
    def mouseMoveEvent(self, event):
        """Handle mouse move events for window dragging."""
        if event.buttons() == Qt.LeftButton and hasattr(self, 'drag_position'):
            self.move(event.globalPos() - self.drag_position)
            event.accept()
    
    def closeEvent(self, event):
        """Handle close event."""
        # Hide instead of closing
        event.ignore()
        self.hide() 