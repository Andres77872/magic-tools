"""Prompt-based slash commands tool for AI chat.

Provides a registry of slash commands (e.g., translate, rewrite, shorter)
that define system prompts to steer the LLM behavior. The AI chat will
look up commands here when the user types "/command text".
"""

import re
from dataclasses import dataclass
from typing import Dict, Optional, List

from .base_tool import BaseTool, ToolInfo, ToolResult
from PyQt5 import QtWidgets, QtCore, QtGui


VALID_COMMAND_RE = re.compile(r"^[A-Za-z0-9_-]+$")


@dataclass
class CommandDefinition:
    """Definition of a slash command."""
    name: str
    description: str
    system_prompt: str


class PromptCommandsTool(BaseTool):
    """Registry and utilities for prompt-based LLM commands.

    Examples of commands:
    - translate: Detect source language and translate to English.
    - rewrite: Improve clarity and style while preserving meaning.
    - shorter / shorten: Make the text more concise in the same language.
    """

    def __init__(self):
        self._commands: Dict[str, CommandDefinition] = {}
        super().__init__()
        self._register_from_settings_or_defaults()

    def get_tool_info(self) -> ToolInfo:
        return ToolInfo(
            name="Prompt Commands",
            description="Slash commands for AI chat (translate, rewrite, shorter, etc.)",
            category="AI",
            keywords=["prompt", "commands", "slash", "translate", "rewrite", "shorter"],
            author="Magic Tools",
        )

    # Public API used by the chat widget
    def list_commands(self) -> List[str]:
        return sorted(self._commands.keys())

    def has_command(self, name: str) -> bool:
        return name in self._commands

    def get_system_prompt(self, name: str) -> Optional[str]:
        cmd = self._commands.get(name)
        return cmd.system_prompt if cmd else None

    def get_description(self, name: str) -> Optional[str]:
        cmd = self._commands.get(name)
        return cmd.description if cmd else None

    def register_command(self, name: str, description: str, system_prompt: str) -> bool:
        """Register a new command if name is valid and unique.

        Returns True on success, False otherwise.
        """
        try:
            normalized = (name or "").strip().lower()
            if not normalized or not VALID_COMMAND_RE.match(normalized):
                self.logger.warning(f"Invalid command name: '{name}'")
                return False
            if normalized in self._commands:
                self.logger.warning(f"Command already exists: '{normalized}'")
                return False
            self._commands[normalized] = CommandDefinition(
                name=normalized,
                description=description.strip(),
                system_prompt=system_prompt.strip(),
            )
            self.logger.info(f"Registered prompt command: {normalized}")
            return True
        except Exception as e:
            self.logger.error(f"Failed to register command '{name}': {e}")
            return False

    # Tool interface
    def execute(self, **kwargs) -> ToolResult:
        """Open the prompt commands editor widget."""
        widget = self.get_widget()
        if widget:
            widget.show()
            return ToolResult(success=True, message="Prompt Commands editor opened")
        return ToolResult(success=False, error="Failed to create editor UI")

    def create_widget(self) -> QtWidgets.QWidget:
        """Create the modern prompt commands editor UI."""
        try:
            from ..ui.style import StyleManager
            from ..config.config_manager import ConfigManager
            
            w = QtWidgets.QWidget()
            w.setProperty("class", "prompt-commands-main")
            main_layout = QtWidgets.QVBoxLayout(w)
            main_layout.setContentsMargins(20, 20, 20, 20)
            main_layout.setSpacing(15)

            # Header section
            header_widget = self._create_header_section()
            main_layout.addWidget(header_widget)

            # Main content with splitter
            splitter = QtWidgets.QSplitter(QtCore.Qt.Horizontal)
            
            # Left panel: Command list
            left_panel = self._create_command_list_panel()
            splitter.addWidget(left_panel)
            
            # Right panel: Command editor
            right_panel = self._create_command_editor_panel()
            splitter.addWidget(right_panel)
            
            # Set splitter proportions (40% list, 60% editor)
            splitter.setSizes([300, 450])
            main_layout.addWidget(splitter)

            # Bottom action bar
            bottom_bar = self._create_bottom_action_bar()
            main_layout.addLayout(bottom_bar)

            # Store references for later use
            w.command_list = left_panel.findChild(QtWidgets.QListWidget)
            w.command_name_input = right_panel.findChild(QtWidgets.QLineEdit, "command_name_input")
            w.description_input = right_panel.findChild(QtWidgets.QLineEdit, "description_input")
            w.system_prompt_input = right_panel.findChild(QtWidgets.QTextEdit, "system_prompt_input")
            w.validation_label = right_panel.findChild(QtWidgets.QLabel, "validation_label")
            w.examples_combo = right_panel.findChild(QtWidgets.QComboBox, "examples_combo")

            # Initialize the interface
            self._populate_command_list(w)
            self._setup_event_handlers(w)
            self._clear_editor_form(w)

            # Get current theme from settings and apply styles
            try:
                cm = ConfigManager()
                current_theme = cm.get_settings().ui.theme
            except Exception:
                current_theme = "dark"  # fallback
            
            style_manager = StyleManager()
            style_manager.set_theme(current_theme)
            style_manager.apply_styles_to_widget(w, theme=current_theme, components=['prompt_commands'])
            
            # Store theme info for later updates
            w._style_manager = style_manager
            w._current_theme = current_theme
            
            # Add method to update theme
            def update_theme(new_theme: str):
                """Update the widget's theme."""
                try:
                    w._current_theme = new_theme
                    w._style_manager.set_theme(new_theme)
                    w._style_manager.apply_styles_to_widget(w, theme=new_theme, components=['prompt_commands'])
                except Exception as e:
                    self.logger.error(f"Failed to update theme: {e}")
            
            w.update_theme = update_theme

            w.setWindowTitle("Prompt Commands Manager")
            w.resize(1000, 700)
            return w
        except Exception as e:
            self.logger.error(f"Failed to create PromptCommands UI: {e}")
            return None

    def _create_header_section(self) -> QtWidgets.QWidget:
        """Create the header section with title and description."""
        header = QtWidgets.QWidget()
        layout = QtWidgets.QVBoxLayout(header)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(8)

        # Title
        title = QtWidgets.QLabel("Prompt Commands Manager")
        title.setProperty("class", "prompt-commands-title")
        font = title.font()
        font.setPointSize(16)
        font.setBold(True)
        title.setFont(font)
        layout.addWidget(title)

        # Description
        desc = QtWidgets.QLabel(
            "Create and manage AI slash commands for the chat interface. "
            "Commands let you quickly apply specific instructions to your input text.\n"
            "Example: Type '/translate Hello world' to translate text to English."
        )
        desc.setProperty("class", "prompt-commands-description")
        desc.setWordWrap(True)
        font = desc.font()
        font.setPointSize(font.pointSize() - 1)
        desc.setFont(font)
        layout.addWidget(desc)

        return header

    def _create_command_list_panel(self) -> QtWidgets.QWidget:
        """Create the left panel with command list and controls."""
        panel = QtWidgets.QWidget()
        layout = QtWidgets.QVBoxLayout(panel)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(8)

        # Panel title
        title = QtWidgets.QLabel("Commands")
        title.setProperty("class", "prompt-commands-panel-title")
        font = title.font()
        font.setBold(True)
        title.setFont(font)
        layout.addWidget(title)

        # Search/filter box
        search_box = QtWidgets.QLineEdit()
        search_box.setPlaceholderText("Search commands...")
        search_box.setProperty("class", "prompt-commands-search")
        layout.addWidget(search_box)

        # Command list
        command_list = QtWidgets.QListWidget()
        command_list.setProperty("class", "prompt-commands-list")
        command_list.setSelectionMode(QtWidgets.QAbstractItemView.SingleSelection)
        layout.addWidget(command_list)

        # List control buttons
        list_controls = QtWidgets.QHBoxLayout()
        
        add_btn = QtWidgets.QPushButton("+ Add")
        add_btn.setProperty("class", "prompt-commands-add-button")
        add_btn.setToolTip("Create a new command")
        
        duplicate_btn = QtWidgets.QPushButton("Clone")
        duplicate_btn.setProperty("class", "prompt-commands-duplicate-button")
        duplicate_btn.setToolTip("Duplicate the selected command")
        duplicate_btn.setEnabled(False)
        
        remove_btn = QtWidgets.QPushButton("Remove")
        remove_btn.setProperty("class", "prompt-commands-remove-button")
        remove_btn.setToolTip("Remove the selected command")
        remove_btn.setEnabled(False)

        list_controls.addWidget(add_btn)
        list_controls.addWidget(duplicate_btn)
        list_controls.addWidget(remove_btn)
        layout.addLayout(list_controls)

        # Store button references
        panel.add_btn = add_btn
        panel.duplicate_btn = duplicate_btn
        panel.remove_btn = remove_btn
        panel.search_box = search_box

        return panel

    def _create_command_editor_panel(self) -> QtWidgets.QWidget:
        """Create the right panel with command editor form."""
        panel = QtWidgets.QWidget()
        layout = QtWidgets.QVBoxLayout(panel)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(12)

        # Panel title
        title = QtWidgets.QLabel("Command Editor")
        title.setProperty("class", "prompt-commands-panel-title")
        font = title.font()
        font.setBold(True)
        title.setFont(font)
        layout.addWidget(title)

        # Form layout
        form_widget = QtWidgets.QWidget()
        form_layout = QtWidgets.QFormLayout(form_widget)
        form_layout.setFieldGrowthPolicy(QtWidgets.QFormLayout.ExpandingFieldsGrow)
        form_layout.setLabelAlignment(QtCore.Qt.AlignRight | QtCore.Qt.AlignTop)

        # Command name field
        command_name_container = QtWidgets.QWidget()
        name_layout = QtWidgets.QVBoxLayout(command_name_container)
        name_layout.setContentsMargins(0, 0, 0, 0)
        name_layout.setSpacing(4)

        command_name_input = QtWidgets.QLineEdit()
        command_name_input.setObjectName("command_name_input")
        command_name_input.setPlaceholderText("e.g., translate, rewrite, summarize")
        command_name_input.setProperty("class", "prompt-commands-name-input")

        validation_label = QtWidgets.QLabel("")
        validation_label.setObjectName("validation_label")
        validation_label.setProperty("class", "prompt-commands-validation")
        validation_label.setVisible(False)

        name_layout.addWidget(command_name_input)
        name_layout.addWidget(validation_label)

        form_layout.addRow("Command Name:", command_name_container)

        # Description field
        description_input = QtWidgets.QLineEdit()
        description_input.setObjectName("description_input")
        description_input.setPlaceholderText("Brief description of what this command does")
        description_input.setProperty("class", "prompt-commands-description-input")
        form_layout.addRow("Description:", description_input)

        layout.addWidget(form_widget)

        # System prompt section
        prompt_section = QtWidgets.QWidget()
        prompt_layout = QtWidgets.QVBoxLayout(prompt_section)
        prompt_layout.setContentsMargins(0, 0, 0, 0)
        prompt_layout.setSpacing(8)

        # System prompt label with help
        prompt_header = QtWidgets.QHBoxLayout()
        prompt_label = QtWidgets.QLabel("System Prompt:")
        prompt_label.setProperty("class", "prompt-commands-prompt-label")
        font = prompt_label.font()
        font.setBold(True)
        prompt_label.setFont(font)

        help_btn = QtWidgets.QToolButton()
        help_btn.setText("?")
        help_btn.setToolTip("Show help for writing effective system prompts")
        help_btn.setProperty("class", "prompt-commands-help-button")

        prompt_header.addWidget(prompt_label)
        prompt_header.addWidget(help_btn)
        prompt_header.addStretch()
        prompt_layout.addLayout(prompt_header)

        # Examples dropdown
        examples_container = QtWidgets.QHBoxLayout()
        examples_label = QtWidgets.QLabel("Templates:")
        examples_combo = QtWidgets.QComboBox()
        examples_combo.setObjectName("examples_combo")
        examples_combo.setProperty("class", "prompt-commands-examples")
        examples_combo.addItem("Select a template...", "")
        examples_combo.addItem("Translation", "You are a high-quality translation engine. Detect the input language and translate it into natural, fluent English. Preserve meaning, tone, formatting, and inline code. Output only the translation, without quotes or commentary.")
        examples_combo.addItem("Text Improvement", "Rewrite the user's text to improve clarity, grammar, and style while preserving meaning. Keep the original language. Do not add new information. Output only the rewritten text.")
        examples_combo.addItem("Summarization", "Summarize the user's text into key points while preserving the most important information. Keep the original language. Output only the summary.")
        examples_combo.addItem("Code Explanation", "Explain the provided code in simple terms. Describe what it does, how it works, and any important details. Be clear and educational.")
        examples_combo.addItem("Custom...", "")

        examples_container.addWidget(examples_label)
        examples_container.addWidget(examples_combo)
        examples_container.addStretch()
        prompt_layout.addLayout(examples_container)

        # System prompt text editor
        system_prompt_input = QtWidgets.QTextEdit()
        system_prompt_input.setObjectName("system_prompt_input")
        system_prompt_input.setPlaceholderText(
            "Enter the system prompt that the AI will follow when this command is used.\n\n"
            "Tips:\n"
            "• Be specific and clear about what you want the AI to do\n"
            "• Include output format requirements (e.g., 'Output only the result')\n"
            "• Mention any constraints (e.g., 'Keep the original language')\n"
            "• Test your prompt to ensure it works as expected"
        )
        system_prompt_input.setProperty("class", "prompt-commands-prompt-input")
        system_prompt_input.setMinimumHeight(200)

        prompt_layout.addWidget(system_prompt_input)

        # Test section
        test_section = QtWidgets.QWidget()
        test_layout = QtWidgets.QHBoxLayout(test_section)
        test_layout.setContentsMargins(0, 0, 0, 0)

        test_btn = QtWidgets.QPushButton("Test Command")
        test_btn.setProperty("class", "prompt-commands-test-button")
        test_btn.setToolTip("Test this command with sample text")
        test_btn.setEnabled(False)

        test_layout.addWidget(test_btn)
        test_layout.addStretch()

        prompt_layout.addWidget(test_section)
        layout.addWidget(prompt_section)

        # Store references
        panel.help_btn = help_btn
        panel.test_btn = test_btn

        return panel

    def _create_bottom_action_bar(self) -> QtWidgets.QHBoxLayout:
        """Create the bottom action bar with main buttons."""
        bar = QtWidgets.QHBoxLayout()
        
        # Import/Export section
        import_btn = QtWidgets.QPushButton("Import...")
        import_btn.setProperty("class", "prompt-commands-import-button")
        import_btn.setToolTip("Import commands from file")
        
        export_btn = QtWidgets.QPushButton("Export...")
        export_btn.setProperty("class", "prompt-commands-export-button")
        export_btn.setToolTip("Export commands to file")

        bar.addWidget(import_btn)
        bar.addWidget(export_btn)
        bar.addStretch()

        # Main action buttons
        cancel_btn = QtWidgets.QPushButton("Cancel")
        cancel_btn.setProperty("class", "prompt-commands-cancel-button")
        
        save_btn = QtWidgets.QPushButton("Save Changes")
        save_btn.setProperty("class", "prompt-commands-save-button")
        save_btn.setDefault(True)

        bar.addWidget(cancel_btn)
        bar.addWidget(save_btn)

        # Store references for event handling
        bar.import_btn = import_btn
        bar.export_btn = export_btn
        bar.cancel_btn = cancel_btn
        bar.save_btn = save_btn

        return bar

    def _populate_command_list(self, widget: QtWidgets.QWidget):
        """Populate the command list with existing commands."""
        command_list = widget.command_list
        command_list.clear()
        
        for name, cmd in sorted(self._commands.items()):
            item = QtWidgets.QListWidgetItem()
            
            # Create rich text display for the list item
            item_widget = QtWidgets.QWidget()
            item_layout = QtWidgets.QVBoxLayout(item_widget)
            item_layout.setContentsMargins(8, 4, 8, 4)
            item_layout.setSpacing(2)
            
            name_label = QtWidgets.QLabel(f"/{name}")
            name_label.setProperty("class", "prompt-commands-item-name")
            font = name_label.font()
            font.setBold(True)
            font.setPointSize(font.pointSize() + 1)
            name_label.setFont(font)
            
            desc_label = QtWidgets.QLabel(cmd.description)
            desc_label.setProperty("class", "prompt-commands-item-description")
            desc_label.setWordWrap(True)
            font = desc_label.font()
            font.setPointSize(font.pointSize() - 1)
            desc_label.setFont(font)
            
            item_layout.addWidget(name_label)
            item_layout.addWidget(desc_label)
            
            item.setSizeHint(item_widget.sizeHint())
            item.setData(QtCore.Qt.UserRole, name)
            
            command_list.addItem(item)
            command_list.setItemWidget(item, item_widget)

    def _setup_event_handlers(self, widget: QtWidgets.QWidget):
        """Setup event handlers for the UI."""
        # Get widget references
        command_list = widget.command_list
        command_name_input = widget.command_name_input
        description_input = widget.description_input
        system_prompt_input = widget.system_prompt_input
        examples_combo = widget.examples_combo
        
        # Find panels and their buttons
        left_panel = command_list.parent()
        while not hasattr(left_panel, 'add_btn'):
            left_panel = left_panel.parent()
            
        right_panel = command_name_input.parent()
        while not hasattr(right_panel, 'help_btn'):
            right_panel = right_panel.parent()
            
        # Find bottom bar
        main_layout = widget.layout()
        bottom_bar = main_layout.itemAt(main_layout.count() - 1).layout()
        
        # Command list selection
        command_list.itemSelectionChanged.connect(
            lambda: self._on_command_selected(widget)
        )
        
        # List control buttons
        left_panel.add_btn.clicked.connect(lambda: self._add_new_command(widget))
        left_panel.duplicate_btn.clicked.connect(lambda: self._duplicate_command(widget))
        left_panel.remove_btn.clicked.connect(lambda: self._remove_command(widget))
        
        # Search functionality
        left_panel.search_box.textChanged.connect(
            lambda text: self._filter_commands(widget, text)
        )
        
        # Input validation
        command_name_input.textChanged.connect(
            lambda: self._validate_command_name(widget)
        )
        
        # Form change tracking
        command_name_input.textChanged.connect(lambda: self._mark_form_dirty(widget))
        description_input.textChanged.connect(lambda: self._mark_form_dirty(widget))
        system_prompt_input.textChanged.connect(lambda: self._mark_form_dirty(widget))
        
        # Template selection
        examples_combo.currentTextChanged.connect(
            lambda: self._apply_template(widget)
        )
        
        # Help and test buttons
        right_panel.help_btn.clicked.connect(lambda: self._show_help_dialog(widget))
        right_panel.test_btn.clicked.connect(lambda: self._test_command(widget))
        
        # Bottom bar buttons
        bottom_bar.import_btn.clicked.connect(lambda: self._import_commands(widget))
        bottom_bar.export_btn.clicked.connect(lambda: self._export_commands(widget))
        bottom_bar.cancel_btn.clicked.connect(lambda: widget.close())
        bottom_bar.save_btn.clicked.connect(lambda: self._save_commands(widget))
        
        # Keyboard shortcuts
        widget.setFocusPolicy(QtCore.Qt.StrongFocus)
        save_shortcut = QtWidgets.QShortcut(QtGui.QKeySequence("Ctrl+S"), widget)
        save_shortcut.activated.connect(lambda: self._save_commands(widget))
        
        new_shortcut = QtWidgets.QShortcut(QtGui.QKeySequence("Ctrl+N"), widget)
        new_shortcut.activated.connect(lambda: self._add_new_command(widget))

    def _on_command_selected(self, widget: QtWidgets.QWidget):
        """Handle command selection in the list."""
        command_list = widget.command_list
        current_item = command_list.currentItem()
        
        # Enable/disable buttons based on selection
        left_panel = command_list.parent()
        while not hasattr(left_panel, 'duplicate_btn'):
            left_panel = left_panel.parent()
            
        has_selection = current_item is not None
        left_panel.duplicate_btn.setEnabled(has_selection)
        left_panel.remove_btn.setEnabled(has_selection)
        
        # Load command data into editor
        if current_item:
            command_name = current_item.data(QtCore.Qt.UserRole)
            if command_name in self._commands:
                cmd = self._commands[command_name]
                self._load_command_into_editor(widget, cmd)
        else:
            self._clear_editor_form(widget)

    def _load_command_into_editor(self, widget: QtWidgets.QWidget, cmd: CommandDefinition):
        """Load a command into the editor form."""
        widget.command_name_input.setText(cmd.name)
        widget.description_input.setText(cmd.description)
        widget.system_prompt_input.setText(cmd.system_prompt)
        
        # Reset validation
        widget.validation_label.setVisible(False)
        widget.validation_label.setText("")
        
        # Enable test button
        self._update_test_button_state(widget)

    def _clear_editor_form(self, widget: QtWidgets.QWidget):
        """Clear the editor form."""
        widget.command_name_input.clear()
        widget.description_input.clear()
        widget.system_prompt_input.clear()
        widget.examples_combo.setCurrentIndex(0)
        widget.validation_label.setVisible(False)
        widget.validation_label.setText("")
        
        # Disable test button
        right_panel = widget.command_name_input.parent()
        while not hasattr(right_panel, 'test_btn'):
            right_panel = right_panel.parent()
        right_panel.test_btn.setEnabled(False)

    def _validate_command_name(self, widget: QtWidgets.QWidget) -> bool:
        """Validate the command name input and show feedback."""
        name = widget.command_name_input.text().strip().lower()
        validation_label = widget.validation_label
        
        if not name:
            validation_label.setText("")
            validation_label.setVisible(False)
            return False
            
        # Check format
        if not VALID_COMMAND_RE.match(name):
            validation_label.setText("⚠ Command name can only contain letters, numbers, hyphens, and underscores")
            validation_label.setProperty("class", "prompt-commands-validation-error")
            validation_label.setVisible(True)
            validation_label.style().unpolish(validation_label)
            validation_label.style().polish(validation_label)
            return False
            
        # Check for duplicates (excluding current selection)
        command_list = widget.command_list
        current_item = command_list.currentItem()
        current_name = current_item.data(QtCore.Qt.UserRole) if current_item else None
        
        if name in self._commands and name != current_name:
            validation_label.setText("⚠ A command with this name already exists")
            validation_label.setProperty("class", "prompt-commands-validation-error")
            validation_label.setVisible(True)
            validation_label.style().unpolish(validation_label)
            validation_label.style().polish(validation_label)
            return False
        
        # Valid
        validation_label.setText("✓ Valid command name")
        validation_label.setProperty("class", "prompt-commands-validation-success")
        validation_label.setVisible(True)
        validation_label.style().unpolish(validation_label)
        validation_label.style().polish(validation_label)
        return True

    def _mark_form_dirty(self, widget: QtWidgets.QWidget):
        """Mark the form as having unsaved changes."""
        self._update_test_button_state(widget)

    def _update_test_button_state(self, widget: QtWidgets.QWidget):
        """Update the test button enabled state."""
        name = widget.command_name_input.text().strip()
        prompt = widget.system_prompt_input.toPlainText().strip()
        
        right_panel = widget.command_name_input.parent()
        while not hasattr(right_panel, 'test_btn'):
            right_panel = right_panel.parent()
            
        # Enable test button if we have both name and prompt
        right_panel.test_btn.setEnabled(bool(name and prompt))

    def _apply_template(self, widget: QtWidgets.QWidget):
        """Apply the selected template to the system prompt."""
        combo = widget.examples_combo
        current_data = combo.currentData()
        
        if current_data and current_data.strip():
            widget.system_prompt_input.setText(current_data)
            self._update_test_button_state(widget)

    def _filter_commands(self, widget: QtWidgets.QWidget, search_text: str):
        """Filter the command list based on search text."""
        command_list = widget.command_list
        
        for i in range(command_list.count()):
            item = command_list.item(i)
            command_name = item.data(QtCore.Qt.UserRole)
            cmd = self._commands.get(command_name)
            
            # Search in name and description
            visible = True
            if search_text.strip():
                search_lower = search_text.lower()
                visible = (
                    search_lower in command_name.lower() or
                    (cmd and search_lower in cmd.description.lower())
                )
            
            item.setHidden(not visible)

    def _add_new_command(self, widget: QtWidgets.QWidget):
        """Add a new command."""
        command_list = widget.command_list
        
        # Clear selection and form
        command_list.clearSelection()
        self._clear_editor_form(widget)
        
        # Focus on name input
        widget.command_name_input.setFocus()
        widget.command_name_input.setPlaceholderText("Enter command name (e.g., translate, summarize)")

    def _duplicate_command(self, widget: QtWidgets.QWidget):
        """Duplicate the selected command."""
        command_list = widget.command_list
        current_item = command_list.currentItem()
        
        if not current_item:
            return
            
        command_name = current_item.data(QtCore.Qt.UserRole)
        if command_name not in self._commands:
            return
            
        cmd = self._commands[command_name]
        
        # Find a unique name
        base_name = f"{command_name}_copy"
        new_name = base_name
        counter = 1
        while new_name in self._commands:
            new_name = f"{base_name}_{counter}"
            counter += 1
        
        # Clear selection and load duplicate data
        command_list.clearSelection()
        widget.command_name_input.setText(new_name)
        widget.description_input.setText(cmd.description)
        widget.system_prompt_input.setText(cmd.system_prompt)
        
        # Focus on name for editing
        widget.command_name_input.setFocus()
        widget.command_name_input.selectAll()

    def _remove_command(self, widget: QtWidgets.QWidget):
        """Remove the selected command."""
        command_list = widget.command_list
        current_item = command_list.currentItem()
        
        if not current_item:
            return
            
        command_name = current_item.data(QtCore.Qt.UserRole)
        
        # Confirm deletion
        reply = QtWidgets.QMessageBox.question(
            widget,
            "Remove Command",
            f"Are you sure you want to remove the command '/{command_name}'?",
            QtWidgets.QMessageBox.Yes | QtWidgets.QMessageBox.No,
            QtWidgets.QMessageBox.No
        )
        
        if reply == QtWidgets.QMessageBox.Yes:
            # Remove from internal registry
            if command_name in self._commands:
                del self._commands[command_name]
            
            # Remove from list and clear form
            row = command_list.row(current_item)
            command_list.takeItem(row)
            self._clear_editor_form(widget)

    def _show_help_dialog(self, widget: QtWidgets.QWidget):
        """Show help dialog for writing system prompts."""
        dialog = QtWidgets.QDialog(widget)
        dialog.setWindowTitle("System Prompt Help")
        dialog.setModal(True)
        dialog.resize(600, 500)
        
        # Apply current theme to dialog
        if hasattr(widget, '_style_manager') and hasattr(widget, '_current_theme'):
            widget._style_manager.apply_styles_to_widget(
                dialog, 
                theme=widget._current_theme, 
                components=['prompt_commands']
            )
        
        layout = QtWidgets.QVBoxLayout(dialog)
        layout.setContentsMargins(20, 20, 20, 20)
        layout.setSpacing(15)
        
        # Create help content
        help_text = QtWidgets.QTextEdit()
        help_text.setReadOnly(True)
        help_text.setProperty("class", "prompt-commands-help-content")
        help_text.setHtml("""
        <h2>Writing Effective System Prompts</h2>
        
        <p>A system prompt defines how the AI should behave when your command is used. Here are best practices:</p>
        
        <h3>✅ Do:</h3>
        <ul>
            <li><b>Be specific and clear</b> about what you want the AI to do</li>
            <li><b>Define the output format</b> (e.g., "Output only the result")</li>
            <li><b>Set constraints</b> (e.g., "Keep the original language", "Use simple terms")</li>
            <li><b>Specify the role</b> (e.g., "You are a professional translator")</li>
            <li><b>Include examples</b> if the task is complex</li>
        </ul>
        
        <h3>❌ Don't:</h3>
        <ul>
            <li>Be vague or ambiguous</li>
            <li>Make the prompt too long or complex</li>
            <li>Forget to specify output requirements</li>
            <li>Include contradictory instructions</li>
        </ul>
        
        <h3>📝 Example Templates:</h3>
        
        <h4>Translation:</h4>
        <code>You are a high-quality translation engine. Detect the input language and translate it into natural, fluent English. Preserve meaning, tone, formatting, and inline code. Output only the translation, without quotes or commentary.</code>
        
        <h4>Summarization:</h4>
        <code>Summarize the user's text into 3-5 key bullet points. Focus on the most important information and maintain the original language. Output only the bullet points without additional commentary.</code>
        
        <h4>Code Review:</h4>
        <code>Review the provided code and identify potential issues, improvements, or best practices. Focus on readability, performance, and maintainability. Provide specific, actionable feedback.</code>
        """)
        
        layout.addWidget(help_text)
        
        # Close button
        close_btn = QtWidgets.QPushButton("Close")
        close_btn.setProperty("class", "prompt-commands-cancel-button")
        close_btn.clicked.connect(dialog.accept)
        
        button_layout = QtWidgets.QHBoxLayout()
        button_layout.addStretch()
        button_layout.addWidget(close_btn)
        layout.addLayout(button_layout)
        
        dialog.exec_()

    def _test_command(self, widget: QtWidgets.QWidget):
        """Test the current command with sample text."""
        name = widget.command_name_input.text().strip()
        system_prompt = widget.system_prompt_input.toPlainText().strip()
        
        if not name or not system_prompt:
            QtWidgets.QMessageBox.warning(
                widget, "Test Command", 
                "Please enter both a command name and system prompt before testing."
            )
            return
        
        # Create test dialog
        dialog = QtWidgets.QDialog(widget)
        dialog.setWindowTitle(f"Test Command: /{name}")
        dialog.setModal(True)
        dialog.resize(700, 500)
        
        # Apply current theme to dialog
        if hasattr(widget, '_style_manager') and hasattr(widget, '_current_theme'):
            widget._style_manager.apply_styles_to_widget(
                dialog, 
                theme=widget._current_theme, 
                components=['prompt_commands']
            )
        
        layout = QtWidgets.QVBoxLayout(dialog)
        layout.setContentsMargins(20, 20, 20, 20)
        layout.setSpacing(15)
        
        # Input section
        input_label = QtWidgets.QLabel("Test Input:")
        input_label.setProperty("class", "prompt-commands-test-label")
        layout.addWidget(input_label)
        
        test_input = QtWidgets.QTextEdit()
        test_input.setPlaceholderText("Enter some text to test the command with...")
        test_input.setMaximumHeight(100)
        layout.addWidget(test_input)
        
        # System prompt preview
        prompt_label = QtWidgets.QLabel("System Prompt:")
        prompt_label.setProperty("class", "prompt-commands-test-label")
        layout.addWidget(prompt_label)
        
        prompt_preview = QtWidgets.QTextEdit()
        prompt_preview.setPlainText(system_prompt)
        prompt_preview.setReadOnly(True)
        prompt_preview.setMaximumHeight(100)
        layout.addWidget(prompt_preview)
        
        # Note about testing
        note = QtWidgets.QLabel(
            "Note: This is a preview of how your command would work. "
            "The actual AI response will depend on your AI provider settings."
        )
        note.setProperty("class", "prompt-commands-test-note")
        note.setWordWrap(True)
        layout.addWidget(note)
        
        # Buttons
        button_layout = QtWidgets.QHBoxLayout()
        close_btn = QtWidgets.QPushButton("Close")
        close_btn.clicked.connect(dialog.accept)
        button_layout.addStretch()
        button_layout.addWidget(close_btn)
        layout.addLayout(button_layout)
        
        dialog.exec_()

    def _save_commands(self, widget: QtWidgets.QWidget) -> bool:
        """Save all commands to settings."""
        try:
            # Collect all commands from UI
            commands_data = []
            command_list = widget.command_list
            
            # Add current form data if valid
            current_name = widget.command_name_input.text().strip().lower()
            current_desc = widget.description_input.text().strip()
            current_prompt = widget.system_prompt_input.toPlainText().strip()
            
            if current_name and current_prompt and self._validate_command_name(widget):
                # Update or add current command
                self._commands[current_name] = CommandDefinition(
                    name=current_name,
                    description=current_desc or current_name,
                    system_prompt=current_prompt
                )
            
            # Convert all commands to settings format
            for name, cmd in self._commands.items():
                commands_data.append({
                    "name": cmd.name,
                    "description": cmd.description,
                    "system_prompt": cmd.system_prompt
                })
            
            # Save to settings
            from ..config.config_manager import ConfigManager
            cm = ConfigManager()
            settings = cm.get_settings()
            settings.tools.prompt_commands = commands_data
            cm.settings = settings
            success = cm.save_settings()
            
            if success:
                QtWidgets.QMessageBox.information(
                    widget, "Success", 
                    f"Successfully saved {len(commands_data)} prompt commands."
                )
                widget.close()
                return True
            else:
                QtWidgets.QMessageBox.critical(
                    widget, "Save Error", 
                    "Failed to save commands to settings file."
                )
                return False
                
        except Exception as e:
            self.logger.error(f"Failed to save commands: {e}")
            QtWidgets.QMessageBox.critical(
                widget, "Save Error", 
                f"Failed to save commands: {str(e)}"
            )
            return False

    def _import_commands(self, widget: QtWidgets.QWidget):
        """Import commands from a JSON file."""
        file_path, _ = QtWidgets.QFileDialog.getOpenFileName(
            widget,
            "Import Prompt Commands",
            "",
            "JSON Files (*.json);;All Files (*)"
        )
        
        if not file_path:
            return
            
        try:
            import json
            with open(file_path, 'r', encoding='utf-8') as f:
                data = json.load(f)
            
            # Validate structure
            if not isinstance(data, list):
                raise ValueError("Import file must contain a list of commands")
            
            imported_count = 0
            for item in data:
                if not isinstance(item, dict):
                    continue
                    
                name = item.get("name", "").strip().lower()
                description = item.get("description", "").strip()
                system_prompt = item.get("system_prompt", "").strip()
                
                if name and system_prompt and VALID_COMMAND_RE.match(name):
                    self._commands[name] = CommandDefinition(
                        name=name,
                        description=description or name,
                        system_prompt=system_prompt
                    )
                    imported_count += 1
            
            # Refresh UI
            self._populate_command_list(widget)
            self._clear_editor_form(widget)
            
            QtWidgets.QMessageBox.information(
                widget, "Import Successful", 
                f"Successfully imported {imported_count} commands."
            )
            
        except Exception as e:
            self.logger.error(f"Failed to import commands: {e}")
            QtWidgets.QMessageBox.critical(
                widget, "Import Error", 
                f"Failed to import commands: {str(e)}"
            )

    def _export_commands(self, widget: QtWidgets.QWidget):
        """Export commands to a JSON file."""
        if not self._commands:
            QtWidgets.QMessageBox.information(
                widget, "No Commands", 
                "There are no commands to export."
            )
            return
            
        file_path, _ = QtWidgets.QFileDialog.getSaveFileName(
            widget,
            "Export Prompt Commands",
            "prompt_commands.json",
            "JSON Files (*.json);;All Files (*)"
        )
        
        if not file_path:
            return
            
        try:
            import json
            commands_data = [
                {
                    "name": cmd.name,
                    "description": cmd.description,
                    "system_prompt": cmd.system_prompt
                }
                for cmd in self._commands.values()
            ]
            
            with open(file_path, 'w', encoding='utf-8') as f:
                json.dump(commands_data, f, indent=2, ensure_ascii=False)
            
            QtWidgets.QMessageBox.information(
                widget, "Export Successful", 
                f"Successfully exported {len(commands_data)} commands to {file_path}"
            )
            
        except Exception as e:
            self.logger.error(f"Failed to export commands: {e}")
            QtWidgets.QMessageBox.critical(
                widget, "Export Error", 
                f"Failed to export commands: {str(e)}"
            )

    # Internals
    def _register_from_settings_or_defaults(self):
        """Load commands from persisted settings; otherwise seed defaults.
        The ToolManager ensures settings are available on app init.
        """
        try:
            # Try import locally to avoid circular imports at module level
            from ..config.config_manager import ConfigManager  # type: ignore
        except Exception:
            ConfigManager = None  # type: ignore

        loaded_any = False
        if ConfigManager is not None:
            try:
                cm = ConfigManager()
                prompt_cmds = getattr(cm.get_settings().tools, "prompt_commands", []) or []
                for item in prompt_cmds:
                    name = (item.get("name") or "").strip()
                    desc = (item.get("description") or "").strip()
                    sys_p = (item.get("system_prompt") or "").strip()
                    if name and desc and sys_p:
                        loaded_any |= self.register_command(name, desc, sys_p)
            except Exception as e:
                self.logger.warning(f"Failed to load prompt commands from settings: {e}")

        if not loaded_any:
            # Fallback defaults (same set as in ToolSettings defaults)
            self.register_command(
                name="translate",
                description="Translate the following text into English (auto-detect input language).",
                system_prompt=(
                    "You are a high-quality translation engine. Detect the input language and translate it "
                    "into natural, fluent English. Preserve meaning, tone, formatting, and inline code. "
                    "Output only the translation, without quotes or commentary."
                ),
            )
            self.register_command(
                name="rewrite",
                description="Rewrite for clarity and style; fix grammar; keep the original language.",
                system_prompt=(
                    "Rewrite the user's text to improve clarity, grammar, and style while preserving meaning. "
                    "Keep the original language. Do not add new information. Output only the rewritten text."
                ),
            )
            shorter_prompt = (
                "Rewrite the user's text to be more concise while preserving key information and tone. "
                "Keep the original language. Output only the shortened text."
            )
            self.register_command(
                name="shorter",
                description="Make the text more concise; keep the original language.",
                system_prompt=shorter_prompt,
            )
            self.register_command(
                name="shorten",
                description="Alias of /shorter: make the text more concise; keep the original language.",
                system_prompt=shorter_prompt,
            )


