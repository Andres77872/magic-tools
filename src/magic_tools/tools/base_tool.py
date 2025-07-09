"""Base tool class for Magic Tools plugin system."""

import logging
from abc import ABC, abstractmethod
from typing import Dict, Any, Optional, List
from dataclasses import dataclass
from PyQt5 import QtWidgets, QtCore, QtGui


@dataclass
class ToolInfo:
    """Information about a tool."""
    name: str
    description: str
    icon: Optional[str] = None
    category: str = "General"
    keywords: List[str] = None
    version: str = "1.0.0"
    author: str = "Unknown"
    
    def __post_init__(self):
        if self.keywords is None:
            self.keywords = []


@dataclass
class ToolResult:
    """Result of a tool execution."""
    success: bool
    message: str = ""
    data: Optional[Any] = None
    error: Optional[str] = None


class BaseTool(ABC):
    """Base class for all tools in Magic Tools."""
    
    def __init__(self):
        self.logger = logging.getLogger(self.__class__.__name__)
        self._info = self.get_tool_info()
        self._enabled = True
        self._widget = None
    
    @abstractmethod
    def get_tool_info(self) -> ToolInfo:
        """Get information about this tool.
        
        Returns:
            ToolInfo object with tool details
        """
        pass
    
    @abstractmethod
    def execute(self, **kwargs) -> ToolResult:
        """Execute the tool with given parameters.
        
        Args:
            **kwargs: Tool-specific parameters
            
        Returns:
            ToolResult with execution results
        """
        pass
    
    def get_widget(self) -> Optional[QtWidgets.QWidget]:
        """Get the tool's GUI widget.
        
        Returns:
            QWidget or None if tool doesn't have a GUI
        """
        if self._widget is None:
            self._widget = self.create_widget()
        return self._widget
    
    def create_widget(self) -> Optional[QtWidgets.QWidget]:
        """Create the tool's GUI widget.
        
        Override this method to provide a custom widget.
        
        Returns:
            QWidget or None if tool doesn't have a GUI
        """
        return None
    
    def is_enabled(self) -> bool:
        """Check if the tool is enabled."""
        return self._enabled
    
    def set_enabled(self, enabled: bool):
        """Enable or disable the tool."""
        self._enabled = enabled
        self.logger.info(f"Tool {self._info.name} {'enabled' if enabled else 'disabled'}")
    
    def get_info(self) -> ToolInfo:
        """Get tool information."""
        return self._info
    
    def matches_search(self, query: str) -> bool:
        """Check if tool matches search query.
        
        Args:
            query: Search query string
            
        Returns:
            True if tool matches the query
        """
        query_lower = query.lower()
        
        # Check name
        if query_lower in self._info.name.lower():
            return True
        
        # Check description
        if query_lower in self._info.description.lower():
            return True
        
        # Check keywords
        for keyword in self._info.keywords:
            if query_lower in keyword.lower():
                return True
        
        # Check category
        if query_lower in self._info.category.lower():
            return True
        
        return False
    
    def get_icon(self) -> Optional[QtGui.QIcon]:
        """Get tool icon.
        
        Returns:
            QIcon or None if no icon is available
        """
        if self._info.icon:
            try:
                return QtGui.QIcon(self._info.icon)
            except Exception as e:
                self.logger.warning(f"Failed to load icon for {self._info.name}: {e}")
        return None
    
    def cleanup(self):
        """Clean up tool resources."""
        if self._widget:
            self._widget.deleteLater()
            self._widget = None
        self.logger.debug(f"Tool {self._info.name} cleaned up")


class QuickTool(BaseTool):
    """Base class for tools that can be executed quickly without a GUI."""
    
    def __init__(self):
        super().__init__()
    
    @abstractmethod
    def quick_execute(self, query: str = "") -> ToolResult:
        """Execute tool quickly with minimal input.
        
        Args:
            query: Optional query string
            
        Returns:
            ToolResult with execution results
        """
        pass
    
    def execute(self, query: str = "", **kwargs) -> ToolResult:
        """Execute the tool (delegates to quick_execute for quick tools)."""
        return self.quick_execute(query)


class WidgetTool(BaseTool):
    """Base class for tools that primarily provide a GUI widget."""
    
    def __init__(self):
        super().__init__()
    
    @abstractmethod
    def create_widget(self) -> QtWidgets.QWidget:
        """Create the tool's GUI widget.
        
        Returns:
            QWidget for the tool
        """
        pass
    
    def execute(self, **kwargs) -> ToolResult:
        """Execute the tool (for widget tools, this typically shows the widget)."""
        widget = self.get_widget()
        if widget:
            widget.show()
            return ToolResult(success=True, message="Tool widget displayed")
        else:
            return ToolResult(success=False, error="Failed to create widget")


class CommandTool(BaseTool):
    """Base class for tools that execute system commands."""
    
    def __init__(self):
        super().__init__()
    
    @abstractmethod
    def get_command(self, **kwargs) -> str:
        """Get the system command to execute.
        
        Args:
            **kwargs: Command parameters
            
        Returns:
            Command string
        """
        pass
    
    def execute(self, **kwargs) -> ToolResult:
        """Execute the system command."""
        try:
            import subprocess
            
            command = self.get_command(**kwargs)
            self.logger.info(f"Executing command: {command}")
            
            result = subprocess.run(
                command,
                shell=True,
                capture_output=True,
                text=True,
                timeout=30
            )
            
            if result.returncode == 0:
                return ToolResult(
                    success=True,
                    message="Command executed successfully",
                    data=result.stdout
                )
            else:
                return ToolResult(
                    success=False,
                    error=f"Command failed with return code {result.returncode}",
                    data=result.stderr
                )
                
        except subprocess.TimeoutExpired:
            return ToolResult(
                success=False,
                error="Command timed out"
            )
        except Exception as e:
            self.logger.error(f"Command execution error: {e}")
            return ToolResult(
                success=False,
                error=f"Command execution error: {str(e)}"
            ) 