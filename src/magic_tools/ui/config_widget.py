"""Configuration widget for Magic Tools."""

import logging
from typing import Optional, Dict, Any
from PyQt5 import QtWidgets, QtCore, QtGui
from PyQt5.QtCore import Qt, pyqtSignal

from ..config import ConfigManager
from ..config.settings import Settings, AISettings, HotkeySettings, UISettings
from ..ai import AIManager
from .style import StyleManager


class AIConfigSection(QtWidgets.QGroupBox):
    """Section for AI configuration settings."""
    
    def __init__(self, ai_settings: AISettings, parent=None):
        super().__init__("AI Configuration", parent)
        self.ai_settings = ai_settings
        self.setup_ui()
    
    def setup_ui(self):
        """Setup the AI configuration UI."""
        layout = QtWidgets.QFormLayout(self)
        layout.setSpacing(10)
        
        # AI Provider
        self.provider_combo = QtWidgets.QComboBox()
        self.provider_combo.addItems(["openai", "local"])
        self.provider_combo.setCurrentText(self.ai_settings.provider)
        self.provider_combo.setToolTip("Select the AI provider backend.")
        layout.addRow("Provider:", self.provider_combo)
        
        # API Key
        self.api_key_edit = QtWidgets.QLineEdit()
        self.api_key_edit.setText(self.ai_settings.api_key)
        self.api_key_edit.setEchoMode(QtWidgets.QLineEdit.Password)
        self.api_key_edit.setPlaceholderText("Enter your API key...")
        self.api_key_edit.setToolTip("API key for the selected provider. Click 'Show' to reveal.")
        
        # Show/Hide API Key button
        self.toggle_key_btn = QtWidgets.QPushButton("Show")
        self.toggle_key_btn.setFixedSize(60, 25)
        self.toggle_key_btn.clicked.connect(self.toggle_api_key_visibility)
        
        api_key_layout = QtWidgets.QHBoxLayout()
        api_key_layout.addWidget(self.api_key_edit)
        api_key_layout.addWidget(self.toggle_key_btn)
        layout.addRow("API Key:", api_key_layout)
        
        # Base URL
        self.base_url_edit = QtWidgets.QLineEdit()
        self.base_url_edit.setText(self.ai_settings.base_url)
        self.base_url_edit.setPlaceholderText("https://api.openai.com/v1")
        self.base_url_edit.setToolTip("Base URL for the API endpoints.")
        layout.addRow("Base URL:", self.base_url_edit)
        
        # Model
        self.model_edit = QtWidgets.QLineEdit()
        self.model_edit.setText(self.ai_settings.model)
        self.model_edit.setPlaceholderText("gpt-4-1106-preview")
        self.model_edit.setToolTip("Model identifier, e.g. 'gpt-4-1106-preview'.")
        layout.addRow("Model:", self.model_edit)
        
        # Max Tokens
        self.max_tokens_spin = QtWidgets.QSpinBox()
        self.max_tokens_spin.setRange(1, 8000)
        self.max_tokens_spin.setValue(self.ai_settings.max_tokens)
        self.max_tokens_spin.setToolTip("Maximum tokens for responses.")
        layout.addRow("Max Tokens:", self.max_tokens_spin)
        
        # Temperature
        self.temperature_spin = QtWidgets.QDoubleSpinBox()
        self.temperature_spin.setRange(0.0, 2.0)
        self.temperature_spin.setSingleStep(0.1)
        self.temperature_spin.setValue(self.ai_settings.temperature)
        self.temperature_spin.setToolTip("Creativity of responses (0.0 = deterministic, 2.0 = very creative).")
        layout.addRow("Temperature:", self.temperature_spin)
        
        # Enabled checkbox
        self.enabled_check = QtWidgets.QCheckBox("Enable AI Integration")
        self.enabled_check.setChecked(self.ai_settings.enabled)
        self.enabled_check.setToolTip("Toggle to enable or disable AI features globally.")
        layout.addRow("", self.enabled_check)
        
        # Local model path (for local provider)
        self.local_model_edit = QtWidgets.QLineEdit()
        self.local_model_edit.setText(self.ai_settings.local_model_path)
        self.local_model_edit.setPlaceholderText("Path to local model file...")
        self.local_model_edit.setToolTip("Path to a local model file (used when provider is 'local').")
        
        self.browse_btn = QtWidgets.QPushButton("Browse")
        self.browse_btn.setFixedSize(60, 25)
        self.browse_btn.clicked.connect(self.browse_local_model)
        
        local_model_layout = QtWidgets.QHBoxLayout()
        local_model_layout.addWidget(self.local_model_edit)
        local_model_layout.addWidget(self.browse_btn)
        layout.addRow("Local Model:", local_model_layout)
        
        # Connect provider change to update UI
        self.provider_combo.currentTextChanged.connect(self.on_provider_changed)
        self.enabled_check.toggled.connect(self.update_enabled_state)
        # Initialize enabled state and provider-specific fields
        self.on_provider_changed(self.provider_combo.currentText())
        self.update_enabled_state()
    
    def toggle_api_key_visibility(self):
        """Toggle API key visibility."""
        if self.api_key_edit.echoMode() == QtWidgets.QLineEdit.Password:
            self.api_key_edit.setEchoMode(QtWidgets.QLineEdit.Normal)
            self.toggle_key_btn.setText("Hide")
        else:
            self.api_key_edit.setEchoMode(QtWidgets.QLineEdit.Password)
            self.toggle_key_btn.setText("Show")
    
    def browse_local_model(self):
        """Browse for local model file."""
        file_path, _ = QtWidgets.QFileDialog.getOpenFileName(
            self,
            "Select Local Model File",
            "",
            "Model Files (*.bin *.gguf *.safetensors);;All Files (*)"
        )
        if file_path:
            self.local_model_edit.setText(file_path)
    
    def on_provider_changed(self, provider: str):
        """Handle provider change."""
        # Show/hide relevant fields based on provider
        is_openai = provider == "openai"
        is_local = provider == "local"
        
        # API key and base URL only for OpenAI
        self.api_key_edit.setEnabled(is_openai and self.enabled_check.isChecked())
        self.toggle_key_btn.setEnabled(is_openai and self.enabled_check.isChecked())
        self.base_url_edit.setEnabled(is_openai and self.enabled_check.isChecked())
        
        # Local model path only for local
        self.local_model_edit.setEnabled(is_local and self.enabled_check.isChecked())
        self.browse_btn.setEnabled(is_local and self.enabled_check.isChecked())

        # Common fields depend on enabled state
        enabled = self.enabled_check.isChecked()
        self.model_edit.setEnabled(enabled)
        self.max_tokens_spin.setEnabled(enabled)
        self.temperature_spin.setEnabled(enabled)

    def update_enabled_state(self):
        """Enable/disable AI controls based on the master toggle."""
        self.on_provider_changed(self.provider_combo.currentText())
    
    def get_settings(self) -> AISettings:
        """Get the current AI settings from the form."""
        return AISettings(
            provider=self.provider_combo.currentText(),
            api_key=self.api_key_edit.text(),
            base_url=self.base_url_edit.text(),
            model=self.model_edit.text(),
            max_tokens=self.max_tokens_spin.value(),
            temperature=self.temperature_spin.value(),
            enabled=self.enabled_check.isChecked(),
            local_model_path=self.local_model_edit.text()
        )


class HotkeyConfigSection(QtWidgets.QGroupBox):
    """Section for hotkey configuration settings."""
    
    def __init__(self, hotkey_settings: HotkeySettings, parent=None):
        super().__init__("Keyboard Shortcuts", parent)
        self.hotkey_settings = hotkey_settings
        self.setup_ui()
    
    def setup_ui(self):
        """Setup the hotkey configuration UI."""
        layout = QtWidgets.QFormLayout(self)
        layout.setSpacing(10)
        
        # Toggle shortcut
        self.toggle_edit = self.create_shortcut_edit(self.hotkey_settings.toggle_shortcut)
        layout.addRow("Toggle Window:", self.toggle_edit)
        
        # AI chat shortcut
        self.ai_chat_edit = self.create_shortcut_edit(self.hotkey_settings.ai_chat_shortcut)
        layout.addRow("AI Chat:", self.ai_chat_edit)
        
        # Quick search shortcut
        self.quick_search_edit = self.create_shortcut_edit(self.hotkey_settings.quick_search_shortcut)
        layout.addRow("Quick Search:", self.quick_search_edit)
        
        # Help text
        help_label = QtWidgets.QLabel(
            "Use combinations like: Ctrl+Space, Alt+A, Ctrl+Alt+S\n"
            "Supported modifiers: Ctrl, Alt, Shift, Meta"
        )
        help_label.setWordWrap(True)
        help_label.setProperty("class", "config-help-text")
        layout.addRow("", help_label)
    
    def create_shortcut_edit(self, current_shortcut: str) -> QtWidgets.QLineEdit:
        """Create a shortcut input field."""
        edit = QtWidgets.QLineEdit()
        edit.setText(current_shortcut)
        edit.setPlaceholderText("Click and press keys...")
        edit.setToolTip("Click the field and press the desired key combination.")
        
        # Make it capture key sequences
        edit.installEventFilter(self)
        
        return edit
    
    def eventFilter(self, obj, event):
        """Filter events to capture key sequences."""
        if isinstance(obj, QtWidgets.QLineEdit) and event.type() == QtCore.QEvent.KeyPress:
            # Build shortcut string from key event
            key_sequence = self.build_key_sequence(event)
            if key_sequence:
                obj.setText(key_sequence)
                return True
        return super().eventFilter(obj, event)
    
    def build_key_sequence(self, event) -> str:
        """Build key sequence string from key event."""
        modifiers = []
        
        if event.modifiers() & Qt.ControlModifier:
            modifiers.append("Ctrl")
        if event.modifiers() & Qt.AltModifier:
            modifiers.append("Alt")
        if event.modifiers() & Qt.ShiftModifier:
            modifiers.append("Shift")
        if event.modifiers() & Qt.MetaModifier:
            modifiers.append("Meta")
        
        # Get key name
        key = event.key()
        key_name = None
        
        # Special keys
        special_keys = {
            Qt.Key_Space: "Space",
            Qt.Key_Tab: "Tab",
            Qt.Key_Return: "Return",
            Qt.Key_Enter: "Enter",
            Qt.Key_Escape: "Escape",
            Qt.Key_Backspace: "Backspace",
            Qt.Key_Delete: "Delete",
            Qt.Key_F1: "F1", Qt.Key_F2: "F2", Qt.Key_F3: "F3", Qt.Key_F4: "F4",
            Qt.Key_F5: "F5", Qt.Key_F6: "F6", Qt.Key_F7: "F7", Qt.Key_F8: "F8",
            Qt.Key_F9: "F9", Qt.Key_F10: "F10", Qt.Key_F11: "F11", Qt.Key_F12: "F12",
        }
        
        if key in special_keys:
            key_name = special_keys[key]
        elif 32 <= key <= 126:  # Printable ASCII
            key_name = chr(key)
        
        if key_name and (modifiers or key_name in ["Space", "Tab", "Return", "Enter", "Escape"]):
            if modifiers:
                return "+".join(modifiers + [key_name])
            else:
                return key_name
        
        return ""
    
    def get_settings(self) -> HotkeySettings:
        """Get the current hotkey settings from the form."""
        return HotkeySettings(
            toggle_shortcut=self.toggle_edit.text(),
            ai_chat_shortcut=self.ai_chat_edit.text(),
            quick_search_shortcut=self.quick_search_edit.text()
        )


class UIConfigSection(QtWidgets.QGroupBox):
    """Section for UI configuration settings."""
    
    def __init__(self, ui_settings: UISettings, parent=None):
        super().__init__("UI Settings", parent)
        self.ui_settings = ui_settings
        self.setup_ui()
    
    def setup_ui(self):
        """Setup the UI configuration UI."""
        layout = QtWidgets.QFormLayout(self)
        layout.setSpacing(10)
        
        # Theme
        self.theme_combo = QtWidgets.QComboBox()
        self.theme_combo.addItems(["dark", "light"])
        self.theme_combo.setCurrentText(self.ui_settings.theme)
        self.theme_combo.setToolTip("Choose the application theme.")
        layout.addRow("Theme:", self.theme_combo)
        
        # Window size
        size_layout = QtWidgets.QHBoxLayout()
        
        self.width_spin = QtWidgets.QSpinBox()
        self.width_spin.setRange(400, 1200)
        self.width_spin.setValue(self.ui_settings.window_width)
        self.width_spin.setSuffix(" px")
        self.width_spin.setToolTip("Window width in pixels.")
        size_layout.addWidget(self.width_spin)
        
        size_layout.addWidget(QtWidgets.QLabel("×"))
        
        self.height_spin = QtWidgets.QSpinBox()
        self.height_spin.setRange(300, 800)
        self.height_spin.setValue(self.ui_settings.window_height)
        self.height_spin.setSuffix(" px")
        self.height_spin.setToolTip("Window height in pixels.")
        size_layout.addWidget(self.height_spin)
        
        layout.addRow("Window Size:", size_layout)
        
        # Opacity
        self.opacity_spin = QtWidgets.QDoubleSpinBox()
        self.opacity_spin.setRange(0.3, 1.0)
        self.opacity_spin.setSingleStep(0.1)
        self.opacity_spin.setValue(self.ui_settings.opacity)
        self.opacity_spin.setDecimals(2)
        self.opacity_spin.setToolTip("Window opacity (0.30 to 1.00).")
        layout.addRow("Opacity:", self.opacity_spin)
        
        # Always on top
        self.always_on_top_check = QtWidgets.QCheckBox("Keep window always on top")
        self.always_on_top_check.setChecked(self.ui_settings.always_on_top)
        self.always_on_top_check.setToolTip("If enabled, the window will stay above others.")
        layout.addRow("", self.always_on_top_check)
        
        # Show on startup
        self.show_on_startup_check = QtWidgets.QCheckBox("Show window on startup")
        self.show_on_startup_check.setChecked(self.ui_settings.show_on_startup)
        self.show_on_startup_check.setToolTip("Open the launcher automatically when the app starts.")
        layout.addRow("", self.show_on_startup_check)
        
        # Animation enabled
        self.animation_check = QtWidgets.QCheckBox("Enable animations")
        self.animation_check.setChecked(self.ui_settings.animation_enabled)
        self.animation_check.setToolTip("Enable subtle UI animations.")
        layout.addRow("", self.animation_check)
    
    def get_settings(self) -> UISettings:
        """Get the current UI settings from the form."""
        return UISettings(
            theme=self.theme_combo.currentText(),
            window_width=self.width_spin.value(),
            window_height=self.height_spin.value(),
            opacity=self.opacity_spin.value(),
            always_on_top=self.always_on_top_check.isChecked(),
            show_on_startup=self.show_on_startup_check.isChecked(),
            animation_enabled=self.animation_check.isChecked()
        )


class ConfigWidget(QtWidgets.QWidget):
    """Main configuration widget."""
    
    back_to_launcher = pyqtSignal()
    settings_changed = pyqtSignal(Settings)
    
    def __init__(self, config_manager: ConfigManager, parent=None):
        super().__init__(parent)
        
        self.logger = logging.getLogger(__name__)
        self.config_manager = config_manager
        self.settings = config_manager.get_settings()
        
        # Initialize style manager
        self.style_manager = StyleManager()
        
        # Configuration sections
        self.ai_section = None
        self.hotkey_section = None
        self.ui_section = None
        
        # Setup UI
        self.setup_ui()
        self.apply_styles()
    
    def setup_ui(self):
        """Setup the configuration UI."""
        # Main layout
        self.main_layout = QtWidgets.QVBoxLayout(self)
        self.main_layout.setContentsMargins(20, 20, 20, 20)
        self.main_layout.setSpacing(15)
        
        # Header
        self.setup_header()
        
        # Scroll area for settings
        self.setup_scroll_area()
        
        # Buttons
        self.setup_buttons()
    
    def setup_header(self):
        """Setup the header section."""
        header_layout = QtWidgets.QHBoxLayout()
        
        # Back button
        back_button = QtWidgets.QPushButton("← Back")
        back_button.setFixedSize(60, 30)
        back_button.clicked.connect(self.back_to_launcher.emit)
        back_button.setProperty("class", "config-back-button")
        
        # Title
        title_label = QtWidgets.QLabel("Settings")
        title_label.setAlignment(Qt.AlignCenter)
        title_label.setProperty("class", "config-title")
        
        header_layout.addWidget(back_button)
        header_layout.addWidget(title_label)
        header_layout.addStretch()
        
        self.main_layout.addLayout(header_layout)
    
    def setup_scroll_area(self):
        """Setup the scrollable settings area."""
        # Scroll area
        scroll_area = QtWidgets.QScrollArea()
        scroll_area.setWidgetResizable(True)
        scroll_area.setVerticalScrollBarPolicy(Qt.ScrollBarAsNeeded)
        scroll_area.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        
        # Settings widget
        settings_widget = QtWidgets.QWidget()
        settings_layout = QtWidgets.QVBoxLayout(settings_widget)
        settings_layout.setSpacing(15)
        
        # AI Configuration Section
        self.ai_section = AIConfigSection(self.settings.ai)
        settings_layout.addWidget(self.ai_section)
        
        # Hotkey Configuration Section
        self.hotkey_section = HotkeyConfigSection(self.settings.hotkeys)
        settings_layout.addWidget(self.hotkey_section)
        
        # UI Configuration Section
        self.ui_section = UIConfigSection(self.settings.ui)
        settings_layout.addWidget(self.ui_section)
        # Live theme preview: update styles immediately when theme changes
        self.ui_section.theme_combo.currentTextChanged.connect(self.on_theme_combo_changed)
        
        settings_layout.addStretch()
        
        scroll_area.setWidget(settings_widget)
        self.main_layout.addWidget(scroll_area)
    
    def setup_buttons(self):
        """Setup action buttons."""
        button_layout = QtWidgets.QHBoxLayout()
        
        # Reset to defaults
        reset_button = QtWidgets.QPushButton("Reset to Defaults")
        reset_button.clicked.connect(self.reset_to_defaults)
        reset_button.setProperty("class", "config-reset-button")
        
        button_layout.addWidget(reset_button)
        button_layout.addStretch()
        
        # Cancel button
        cancel_button = QtWidgets.QPushButton("Cancel")
        cancel_button.clicked.connect(self.cancel_changes)
        cancel_button.setProperty("class", "config-cancel-button")
        
        # Save button
        save_button = QtWidgets.QPushButton("Save")
        save_button.clicked.connect(self.save_settings)
        save_button.setProperty("class", "config-save-button")
        
        button_layout.addWidget(cancel_button)
        button_layout.addWidget(save_button)
        
        self.main_layout.addLayout(button_layout)
    
    def apply_styles(self):
        """Apply styles using the StyleManager."""
        self.style_manager.apply_styles_to_widget(self, components=['config'])

    def on_theme_combo_changed(self, theme: str):
        """Handle live theme switching from the UI section."""
        try:
            self.style_manager.set_theme(theme)
            self.apply_styles()
        except Exception as e:
            self.logger.error(f"Failed to apply theme '{theme}': {e}")
    
    def reset_to_defaults(self):
        """Reset all settings to defaults."""
        reply = QtWidgets.QMessageBox.question(
            self,
            "Reset Settings",
            "Are you sure you want to reset all settings to their default values?",
            QtWidgets.QMessageBox.Yes | QtWidgets.QMessageBox.No,
            QtWidgets.QMessageBox.No
        )
        
        if reply == QtWidgets.QMessageBox.Yes:
            # Reset to defaults
            default_settings = Settings()
            
            # Update the form sections
            self.ai_section.deleteLater()
            self.hotkey_section.deleteLater()
            self.ui_section.deleteLater()
            
            # Recreate sections with default settings
            self.ai_section = AIConfigSection(default_settings.ai)
            self.hotkey_section = HotkeyConfigSection(default_settings.hotkeys)
            self.ui_section = UIConfigSection(default_settings.ui)
            
            # Re-add to layout (find the scroll area and update its widget)
            scroll_area = None
            for i in range(self.main_layout.count()):
                widget = self.main_layout.itemAt(i).widget()
                if isinstance(widget, QtWidgets.QScrollArea):
                    scroll_area = widget
                    break
            
            if scroll_area:
                settings_widget = QtWidgets.QWidget()
                settings_layout = QtWidgets.QVBoxLayout(settings_widget)
                settings_layout.setSpacing(15)
                
                settings_layout.addWidget(self.ai_section)
                settings_layout.addWidget(self.hotkey_section)
                settings_layout.addWidget(self.ui_section)
                settings_layout.addStretch()
                
                scroll_area.setWidget(settings_widget)
            
            self.logger.info("Settings reset to defaults")
    
    def cancel_changes(self):
        """Cancel changes and go back."""
        self.back_to_launcher.emit()
    
    def save_settings(self):
        """Save the current settings."""
        try:
            # Get settings from sections
            new_settings = Settings(
                ai=self.ai_section.get_settings(),
                hotkeys=self.hotkey_section.get_settings(),
                ui=self.ui_section.get_settings(),
                tools=self.settings.tools  # Keep existing tool settings
            )
            # Basic validation for AI settings when enabled
            ai_settings = new_settings.ai
            if ai_settings.enabled:
                if ai_settings.provider == "openai":
                    if not ai_settings.api_key.strip():
                        QtWidgets.QMessageBox.warning(
                            self,
                            "Validation Error",
                            "API Key is required when using the OpenAI provider."
                        )
                        return
                elif ai_settings.provider == "local":
                    if not ai_settings.local_model_path.strip():
                        QtWidgets.QMessageBox.warning(
                            self,
                            "Validation Error",
                            "Local model path is required when using the Local provider."
                        )
                        return
            
            # Save to config manager
            self.config_manager.settings = new_settings
            success = self.config_manager.save_settings()
            
            if success:
                # Emit signal to update the application
                self.settings_changed.emit(new_settings)
                
                QtWidgets.QMessageBox.information(
                    self,
                    "Settings Saved",
                    "Settings have been saved successfully!"
                )
                
                self.logger.info("Settings saved successfully")
                self.back_to_launcher.emit()
            else:
                QtWidgets.QMessageBox.critical(
                    self,
                    "Save Error",
                    "Failed to save settings. Please try again."
                )
                
        except Exception as e:
            self.logger.error(f"Error saving settings: {e}")
            QtWidgets.QMessageBox.critical(
                self,
                "Save Error",
                f"An error occurred while saving settings:\n{str(e)}"
            )
    
    def update_settings(self, ui_settings: UISettings):
        """Update UI settings."""
        # Update theme and apply styles
        self.style_manager.set_theme(ui_settings.theme)
        self.apply_styles()
    
    def keyPressEvent(self, event):
        """Handle key press events."""
        if event.key() == Qt.Key_Escape:
            self.back_to_launcher.emit()
        else:
            super().keyPressEvent(event) 