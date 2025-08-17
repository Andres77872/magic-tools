"""Prompt-based slash commands tool for AI chat.

Provides a registry of slash commands (e.g., translate, rewrite, shorter)
that define system prompts to steer the LLM behavior. The AI chat will
look up commands here when the user types "/command text".
"""

import re
from dataclasses import dataclass
from typing import Dict, Optional, List

from .base_tool import BaseTool, ToolInfo, ToolResult
from PyQt5 import QtWidgets, QtCore


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
        """Create the prompt commands editor UI (table with controls)."""
        try:
            w = QtWidgets.QWidget()
            layout = QtWidgets.QVBoxLayout(w)
            layout.setContentsMargins(10, 10, 10, 10)
            layout.setSpacing(8)

            # Header/description
            desc = QtWidgets.QLabel(
                "Create and maintain slash commands for the chatbot.\n"
                "- Command: unique, only letters, numbers, '-' or '_' (no spaces).\n"
                "- System Prompt: instruction the AI will follow when you use /command.\n"
                "Use them in chat like: /translate Hola como estás"
            )
            desc.setWordWrap(True)
            layout.addWidget(desc)

            # Table
            table = QtWidgets.QTableWidget()
            table.setColumnCount(3)
            table.setHorizontalHeaderLabels(["Command", "System Prompt", "Description"])
            table.horizontalHeader().setStretchLastSection(True)
            table.horizontalHeader().setSectionResizeMode(0, QtWidgets.QHeaderView.ResizeToContents)
            table.horizontalHeader().setSectionResizeMode(1, QtWidgets.QHeaderView.Stretch)
            table.horizontalHeader().setSectionResizeMode(2, QtWidgets.QHeaderView.ResizeToContents)
            table.setSelectionBehavior(QtWidgets.QAbstractItemView.SelectRows)
            table.setSelectionMode(QtWidgets.QAbstractItemView.SingleSelection)
            table.setAlternatingRowColors(True)
            layout.addWidget(table)

            # Load current commands into the table
            cmds = [
                {
                    "name": name,
                    "system_prompt": cmd.system_prompt,
                    "description": cmd.description,
                }
                for name, cmd in self._commands.items()
            ]
            table.setRowCount(len(cmds))
            for r, item in enumerate(cmds):
                table.setItem(r, 0, QtWidgets.QTableWidgetItem(item["name"]))
                table.setItem(r, 1, QtWidgets.QTableWidgetItem(item["system_prompt"]))
                table.setItem(r, 2, QtWidgets.QTableWidgetItem(item["description"]))

            # Bottom bar
            btn_bar = QtWidgets.QHBoxLayout()
            add_btn = QtWidgets.QPushButton("Add Command")
            rem_btn = QtWidgets.QPushButton("Remove Selected")
            btn_bar.addWidget(add_btn)
            btn_bar.addWidget(rem_btn)
            btn_bar.addStretch()

            cancel_btn = QtWidgets.QPushButton("Cancel")
            save_btn = QtWidgets.QPushButton("Save")
            btn_bar.addWidget(cancel_btn)
            btn_bar.addWidget(save_btn)
            layout.addLayout(btn_bar)

            # Handlers
            def add_row():
                r = table.rowCount()
                table.insertRow(r)
                table.setItem(r, 0, QtWidgets.QTableWidgetItem("new_command"))
                table.setItem(r, 1, QtWidgets.QTableWidgetItem("Describe what the AI should do..."))
                table.setItem(r, 2, QtWidgets.QTableWidgetItem("Short description"))
                table.editItem(table.item(r, 0))

            def remove_selected():
                row = table.currentRow()
                if row >= 0:
                    table.removeRow(row)

            def collect_rows() -> List[Dict[str, str]]:
                import re as _re
                rows: List[Dict[str, str]] = []
                seen = set()
                for r in range(table.rowCount()):
                    name = (table.item(r, 0).text() if table.item(r, 0) else "").strip().lower()
                    sys_p = (table.item(r, 1).text() if table.item(r, 1) else "").strip()
                    desc = (table.item(r, 2).text() if table.item(r, 2) else "").strip()
                    if not name or not sys_p:
                        continue
                    if not _re.match(r"^[A-Za-z0-9_-]+$", name):
                        continue
                    if name in seen:
                        continue
                    seen.add(name)
                    rows.append({"name": name, "system_prompt": sys_p, "description": desc or name})
                return rows

            def save_changes():
                try:
                    # Persist to settings
                    from ..config.config_manager import ConfigManager  # type: ignore
                    cm = ConfigManager()
                    settings = cm.get_settings()
                    settings.tools.prompt_commands = collect_rows()
                    cm.settings = settings
                    cm.save_settings()

                    # Update in-memory registry
                    self._commands.clear()
                    for item in settings.tools.prompt_commands:
                        self.register_command(item["name"], item.get("description", item["name"]), item["system_prompt"])

                    w.close()
                except Exception as e:
                    QtWidgets.QMessageBox.critical(w, "Save Error", f"Failed to save commands: {e}")

            def cancel_changes():
                w.close()

            add_btn.clicked.connect(add_row)
            rem_btn.clicked.connect(remove_selected)
            save_btn.clicked.connect(save_changes)
            cancel_btn.clicked.connect(cancel_changes)

            w.setWindowTitle("Prompt Commands")
            w.resize(800, 420)
            return w
        except Exception as e:
            self.logger.error(f"Failed to create PromptCommands UI: {e}")
            return None

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


