"""Launcher widget for Magic Tools."""

import logging
from typing import List, Optional
from PyQt5 import QtWidgets, QtCore, QtGui
from PyQt5.QtCore import Qt, pyqtSignal

from ..ai import AIManager
from ..tools import ToolManager
from ..tools.base_tool import ToolInfo, ToolResult
from ..config.settings import UISettings
from .style import StyleManager


class ToolButton(QtWidgets.QPushButton):
    """Custom button for tool items."""
    
    tool_clicked = pyqtSignal(str)  # Emits tool name
    
    def __init__(self, tool_info: ToolInfo, parent=None):
        super().__init__(parent)
        self.tool_info = tool_info
        self.setup_ui()
    
    def setup_ui(self):
        """Setup the tool button UI."""
        self.setText(self.tool_info.name)
        self.setToolTip(self.tool_info.description)
        self.setFixedSize(120, 80)
        self.setObjectName("toolButton")
        
        # Connect click signal
        self.clicked.connect(lambda: self.tool_clicked.emit(self.tool_info.name.lower().replace(" ", "_")))
        
        # Apply CSS class
        self.setProperty("class", "tool-button")


class SearchLineEdit(QtWidgets.QLineEdit):
    """Custom search line edit with enhanced features."""
    
    search_requested = pyqtSignal(str)
    ai_chat_requested = pyqtSignal()
    tool_execute_requested = pyqtSignal(str, str)  # tool_name, query
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setup_ui()
    
    def setup_ui(self):
        """Setup the search input UI."""
        self.setPlaceholderText("Search tools or ask AI... (Type '/' for AI)")
        self.textChanged.connect(self.on_text_changed)
        self.returnPressed.connect(self.on_return_pressed)
        
        # Add search icon
        self.search_action = self.addAction(
            self.style().standardIcon(QtWidgets.QStyle.SP_FileDialogDetailedView),
            QtWidgets.QLineEdit.LeadingPosition
        )
    
    def on_text_changed(self, text: str):
        """Handle text change events."""
        if text.startswith('/'):
            # AI chat mode
            self.setPlaceholderText("Ask AI... (Press Enter to open chat)")
        else:
            # Search mode
            self.setPlaceholderText("Search tools or ask AI... (Type '/' for AI)")
            self.search_requested.emit(text)
    
    def on_return_pressed(self):
        """Handle return key press."""
        text = self.text().strip()
        
        if text.startswith('/'):
            # Open AI chat
            self.ai_chat_requested.emit()
        elif text:
            # Try to execute as tool command
            parts = text.split(' ', 1)
            tool_name = parts[0].lower()
            query = parts[1] if len(parts) > 1 else ""
            
            self.tool_execute_requested.emit(tool_name, query)


class LauncherWidget(QtWidgets.QWidget):
    """Main launcher widget with search and tool grid."""
    
    ai_chat_requested = pyqtSignal()
    tool_executed = pyqtSignal(str, object)  # tool_name, result
    
    def __init__(self, tool_manager: ToolManager, ai_manager: AIManager, parent=None):
        super().__init__(parent)
        
        self.logger = logging.getLogger(__name__)
        self.tool_manager = tool_manager
        self.ai_manager = ai_manager
        self.ui_settings = None
        
        # Initialize style manager
        self.style_manager = StyleManager()
        
        # Tool widgets
        self.tool_buttons = {}
        self.visible_tools = []
        
        # Setup UI
        self.setup_ui()
        self.setup_signals()
        self.refresh_tools()
        
        # Apply styles
        self.apply_styles()
    
    def setup_ui(self):
        """Setup the launcher UI."""
        # Main layout
        self.main_layout = QtWidgets.QVBoxLayout(self)
        self.main_layout.setContentsMargins(20, 20, 20, 20)
        self.main_layout.setSpacing(15)
        
        # Header with logo/title
        self.setup_header()
        
        # Search input
        self.search_input = SearchLineEdit()
        self.main_layout.addWidget(self.search_input)
        
        # Tool grid container
        self.setup_tool_grid()
        
        # Status bar
        self.setup_status_bar()
    
    def setup_header(self):
        """Setup the header section."""
        header_layout = QtWidgets.QHBoxLayout()
        
        # Title
        title_label = QtWidgets.QLabel("Magic Tools")
        title_label.setAlignment(Qt.AlignCenter)
        title_label.setProperty("class", "launcher-title")
        
        # AI status indicator
        self.ai_status_label = QtWidgets.QLabel("🤖 AI Ready" if self.ai_manager.is_available() else "🤖 AI Offline")
        self.ai_status_label.setAlignment(Qt.AlignRight)
        self.ai_status_label.setProperty("class", "launcher-ai-status")
        
        header_layout.addWidget(title_label)
        header_layout.addWidget(self.ai_status_label)
        
        self.main_layout.addLayout(header_layout)
    
    def setup_tool_grid(self):
        """Setup the tool grid area."""
        # Scroll area for tools
        self.scroll_area = QtWidgets.QScrollArea()
        self.scroll_area.setWidgetResizable(True)
        self.scroll_area.setVerticalScrollBarPolicy(Qt.ScrollBarAsNeeded)
        self.scroll_area.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        
        # Tool grid widget
        self.tool_grid_widget = QtWidgets.QWidget()
        self.tool_grid_layout = QtWidgets.QGridLayout(self.tool_grid_widget)
        self.tool_grid_layout.setSpacing(10)
        
        self.scroll_area.setWidget(self.tool_grid_widget)
        self.main_layout.addWidget(self.scroll_area)
    
    def setup_status_bar(self):
        """Setup the status bar."""
        status_layout = QtWidgets.QHBoxLayout()
        
        # Tool count
        self.tool_count_label = QtWidgets.QLabel("")
        self.tool_count_label.setProperty("class", "launcher-tool-count")
        
        # Quick actions
        ai_button = QtWidgets.QPushButton("💬 AI Chat")
        ai_button.setFixedSize(80, 25)
        ai_button.clicked.connect(self.ai_chat_requested.emit)
        ai_button.setProperty("class", "launcher-ai-chat-button")
        
        status_layout.addWidget(self.tool_count_label)
        status_layout.addStretch()
        status_layout.addWidget(ai_button)
        
        self.main_layout.addLayout(status_layout)
    
    def apply_styles(self):
        """Apply styles using the StyleManager."""
        self.style_manager.apply_styles_to_widget(self, components=['launcher'])
    
    def setup_signals(self):
        """Setup signal connections."""
        self.search_input.search_requested.connect(self.on_search)
        self.search_input.ai_chat_requested.connect(self.ai_chat_requested.emit)
        self.search_input.tool_execute_requested.connect(self.execute_tool)
    
    def refresh_tools(self):
        """Refresh the tool grid with current tools."""
        # Clear existing buttons
        for button in self.tool_buttons.values():
            button.setParent(None)
        self.tool_buttons.clear()
        
        # Get all tool info
        all_tools = self.tool_manager.get_all_tool_info()
        
        # Create buttons for each tool
        row, col = 0, 0
        cols_per_row = 4
        
        for tool_name, tool_info in all_tools.items():
            if tool_name in self.tool_manager.settings.enabled_tools:
                button = ToolButton(tool_info)
                button.tool_clicked.connect(self.on_tool_clicked)
                
                self.tool_buttons[tool_name] = button
                self.tool_grid_layout.addWidget(button, row, col)
                
                col += 1
                if col >= cols_per_row:
                    col = 0
                    row += 1
        
        # Update tool count
        self.update_tool_count()
        
        # Update visible tools list
        self.visible_tools = list(self.tool_buttons.keys())
    
    def on_search(self, query: str):
        """Handle search query."""
        if not query.strip():
            # Show all tools
            self.show_all_tools()
            return
        
        # Search for matching tools
        matching_tools = self.tool_manager.search_tools(query)
        
        # Hide non-matching tools
        for tool_name, button in self.tool_buttons.items():
            if tool_name in matching_tools:
                button.show()
            else:
                button.hide()
        
        self.visible_tools = matching_tools
        self.update_tool_count()
    
    def show_all_tools(self):
        """Show all available tools."""
        for button in self.tool_buttons.values():
            button.show()
        
        self.visible_tools = list(self.tool_buttons.keys())
        self.update_tool_count()
    
    def on_tool_clicked(self, tool_name: str):
        """Handle tool button click."""
        self.execute_tool(tool_name)
    
    def execute_tool(self, tool_name: str, query: str = ""):
        """Execute a tool."""
        self.logger.info(f"Executing tool: {tool_name} with query: '{query}'")
        
        try:
            # Execute the tool
            result = self.tool_manager.execute_tool(tool_name, query=query)
            
            # Show result
            self.show_tool_result(tool_name, result)
            
            # Emit signal
            self.tool_executed.emit(tool_name, result)
            
        except Exception as e:
            self.logger.error(f"Error executing tool {tool_name}: {e}")
            self.show_error(f"Error executing {tool_name}: {str(e)}")
    
    def show_tool_result(self, tool_name: str, result: ToolResult):
        """Show tool execution result."""
        if result.success:
            if result.data:
                # Show result in a dialog
                dialog = QtWidgets.QDialog(self)
                dialog.setWindowTitle(f"{tool_name} Result")
                dialog.setModal(True)
                dialog.resize(400, 300)
                
                layout = QtWidgets.QVBoxLayout(dialog)
                
                # Result text
                text_edit = QtWidgets.QTextEdit()
                text_edit.setPlainText(str(result.data))
                text_edit.setReadOnly(True)
                layout.addWidget(text_edit)
                
                # Close button
                close_button = QtWidgets.QPushButton("Close")
                close_button.clicked.connect(dialog.accept)
                layout.addWidget(close_button)
                
                dialog.show()
            else:
                self.show_status(result.message or f"{tool_name} executed successfully")
        else:
            self.show_error(result.error or f"Failed to execute {tool_name}")
    
    def show_status(self, message: str):
        """Show status message."""
        # You could implement a status bar or notification system here
        self.logger.info(f"Status: {message}")
    
    def show_error(self, message: str):
        """Show error message."""
        QtWidgets.QMessageBox.warning(self, "Error", message)
    
    def update_tool_count(self):
        """Update the tool count display."""
        visible_count = len(self.visible_tools)
        total_count = len(self.tool_buttons)
        
        if visible_count == total_count:
            text = f"{total_count} tools"
        else:
            text = f"{visible_count} of {total_count} tools"
        
        self.tool_count_label.setText(text)
    
    def focus_search_input(self):
        """Focus the search input field."""
        self.search_input.setFocus()
        self.search_input.selectAll()
    
    def update_settings(self, ui_settings: UISettings):
        """Update UI settings."""
        self.ui_settings = ui_settings
        
        # Update theme and apply styles
        self.style_manager.set_theme(ui_settings.theme)
        self.apply_styles()
        
        # Update AI status
        self.ai_status_label.setText("🤖 AI Ready" if self.ai_manager.is_available() else "🤖 AI Offline")
        
        # Refresh tools if needed
        self.refresh_tools()
    
    def keyPressEvent(self, event):
        """Handle key press events."""
        if event.key() == Qt.Key_F5:
            # Refresh tools
            self.refresh_tools()
        elif event.key() == Qt.Key_Slash:
            # Focus search input and add slash
            self.search_input.setFocus()
            self.search_input.setText("/")
        else:
            super().keyPressEvent(event) 