"""Tool manager for Magic Tools."""

import logging
import os
import importlib
import inspect
from typing import Dict, List, Optional, Type
from pathlib import Path

from ..config.settings import ToolSettings
from .base_tool import BaseTool, ToolInfo, ToolResult
from .builtin_tools import BuiltinTools


class ToolManager:
    """Manages tools and plugins for Magic Tools."""
    
    def __init__(self, settings: ToolSettings):
        self.logger = logging.getLogger(__name__)
        self.settings = settings
        self.tools: Dict[str, BaseTool] = {}
        self.tool_classes: Dict[str, Type[BaseTool]] = {}
        
        # Load built-in tools
        self._load_builtin_tools()
        
        # Load custom tools if enabled
        if self.settings.auto_load_tools:
            self._load_custom_tools()
    
    def _load_builtin_tools(self):
        """Load built-in tools."""
        try:
            builtin_tools = BuiltinTools()
            tool_classes = builtin_tools.get_tool_classes()
            
            for tool_name, tool_class in tool_classes.items():
                if tool_name in self.settings.enabled_tools:
                    self.register_tool_class(tool_name, tool_class)
                    self.logger.info(f"Loaded built-in tool: {tool_name}")
            
            self.logger.info(f"Loaded {len(tool_classes)} built-in tools")
            
        except Exception as e:
            self.logger.error(f"Failed to load built-in tools: {e}")
    
    def _load_custom_tools(self):
        """Load custom tools from the custom tools directory."""
        if not self.settings.custom_tools_path:
            return
        
        custom_tools_path = Path(self.settings.custom_tools_path)
        if not custom_tools_path.exists():
            self.logger.warning(f"Custom tools path does not exist: {custom_tools_path}")
            return
        
        try:
            # Add custom tools path to Python path
            import sys
            if str(custom_tools_path) not in sys.path:
                sys.path.insert(0, str(custom_tools_path))
            
            # Scan for Python files in the custom tools directory
            for py_file in custom_tools_path.glob("*.py"):
                if py_file.name.startswith("__"):
                    continue
                
                try:
                    module_name = py_file.stem
                    module = importlib.import_module(module_name)
                    
                    # Find tool classes in the module
                    for name, obj in inspect.getmembers(module):
                        if (inspect.isclass(obj) and 
                            issubclass(obj, BaseTool) and 
                            obj != BaseTool):
                            
                            tool_name = name.lower()
                            self.register_tool_class(tool_name, obj)
                            self.logger.info(f"Loaded custom tool: {tool_name}")
                
                except Exception as e:
                    self.logger.error(f"Failed to load custom tool from {py_file}: {e}")
            
            self.logger.info("Custom tools loading completed")
            
        except Exception as e:
            self.logger.error(f"Failed to load custom tools: {e}")
    
    def register_tool_class(self, name: str, tool_class: Type[BaseTool]):
        """Register a tool class.
        
        Args:
            name: Tool name
            tool_class: Tool class
        """
        self.tool_classes[name] = tool_class
        
        # Instantiate the tool if it's enabled
        if name in self.settings.enabled_tools:
            self.instantiate_tool(name)
    
    def instantiate_tool(self, name: str) -> Optional[BaseTool]:
        """Instantiate a tool from its class.
        
        Args:
            name: Tool name
            
        Returns:
            Tool instance or None if failed
        """
        if name not in self.tool_classes:
            self.logger.error(f"Tool class not found: {name}")
            return None
        
        try:
            tool_class = self.tool_classes[name]
            tool_instance = tool_class()
            self.tools[name] = tool_instance
            self.logger.info(f"Instantiated tool: {name}")
            return tool_instance
            
        except Exception as e:
            self.logger.error(f"Failed to instantiate tool {name}: {e}")
            return None
    
    def get_tool(self, name: str) -> Optional[BaseTool]:
        """Get a tool instance by name.
        
        Args:
            name: Tool name
            
        Returns:
            Tool instance or None if not found
        """
        if name not in self.tools:
            # Try to instantiate the tool if class is available
            if name in self.tool_classes:
                return self.instantiate_tool(name)
            return None
        
        return self.tools[name]
    
    def get_all_tools(self) -> Dict[str, BaseTool]:
        """Get all instantiated tools.
        
        Returns:
            Dictionary of tool name to tool instance
        """
        return self.tools.copy()
    
    def get_enabled_tools(self) -> Dict[str, BaseTool]:
        """Get all enabled tools.
        
        Returns:
            Dictionary of enabled tools
        """
        return {name: tool for name, tool in self.tools.items() if tool.is_enabled()}
    
    def get_tool_info(self, name: str) -> Optional[ToolInfo]:
        """Get tool information.
        
        Args:
            name: Tool name
            
        Returns:
            ToolInfo or None if tool not found
        """
        tool = self.get_tool(name)
        if tool:
            return tool.get_info()
        return None
    
    def get_all_tool_info(self) -> Dict[str, ToolInfo]:
        """Get information about all tools.
        
        Returns:
            Dictionary of tool name to ToolInfo
        """
        tool_info = {}
        
        # Get info from instantiated tools
        for name, tool in self.tools.items():
            tool_info[name] = tool.get_info()
        
        # Get info from tool classes that aren't instantiated
        for name, tool_class in self.tool_classes.items():
            if name not in tool_info:
                try:
                    temp_instance = tool_class()
                    tool_info[name] = temp_instance.get_info()
                    temp_instance.cleanup()
                except Exception as e:
                    self.logger.error(f"Failed to get info for tool {name}: {e}")
        
        return tool_info
    
    def search_tools(self, query: str) -> List[str]:
        """Search for tools matching the query.
        
        Args:
            query: Search query
            
        Returns:
            List of matching tool names
        """
        matching_tools = []
        
        for name, tool in self.tools.items():
            if tool.matches_search(query):
                matching_tools.append(name)
        
        # Also check tool classes that aren't instantiated
        for name, tool_class in self.tool_classes.items():
            if name not in self.tools:
                try:
                    temp_instance = tool_class()
                    if temp_instance.matches_search(query):
                        matching_tools.append(name)
                    temp_instance.cleanup()
                except Exception as e:
                    self.logger.error(f"Failed to search tool {name}: {e}")
        
        return matching_tools
    
    def execute_tool(self, name: str, **kwargs) -> ToolResult:
        """Execute a tool by name.
        
        Args:
            name: Tool name
            **kwargs: Tool parameters
            
        Returns:
            ToolResult with execution results
        """
        tool = self.get_tool(name)
        if not tool:
            return ToolResult(
                success=False,
                error=f"Tool not found: {name}"
            )
        
        if not tool.is_enabled():
            return ToolResult(
                success=False,
                error=f"Tool is disabled: {name}"
            )
        
        try:
            return tool.execute(**kwargs)
        except Exception as e:
            self.logger.error(f"Error executing tool {name}: {e}")
            return ToolResult(
                success=False,
                error=f"Tool execution error: {str(e)}"
            )
    
    def enable_tool(self, name: str) -> bool:
        """Enable a tool.
        
        Args:
            name: Tool name
            
        Returns:
            True if enabled successfully
        """
        tool = self.get_tool(name)
        if tool:
            tool.set_enabled(True)
            if name not in self.settings.enabled_tools:
                self.settings.enabled_tools.append(name)
            return True
        return False
    
    def disable_tool(self, name: str) -> bool:
        """Disable a tool.
        
        Args:
            name: Tool name
            
        Returns:
            True if disabled successfully
        """
        tool = self.get_tool(name)
        if tool:
            tool.set_enabled(False)
            if name in self.settings.enabled_tools:
                self.settings.enabled_tools.remove(name)
            return True
        return False
    
    def get_categories(self) -> List[str]:
        """Get all tool categories.
        
        Returns:
            List of unique categories
        """
        categories = set()
        
        tool_info = self.get_all_tool_info()
        for info in tool_info.values():
            categories.add(info.category)
        
        return sorted(list(categories))
    
    def get_tools_by_category(self, category: str) -> List[str]:
        """Get tools in a specific category.
        
        Args:
            category: Category name
            
        Returns:
            List of tool names in the category
        """
        tools_in_category = []
        
        tool_info = self.get_all_tool_info()
        for name, info in tool_info.items():
            if info.category == category:
                tools_in_category.append(name)
        
        return tools_in_category
    
    def reload_tools(self):
        """Reload all tools."""
        self.logger.info("Reloading all tools")
        
        # Clean up existing tools
        for tool in self.tools.values():
            tool.cleanup()
        
        # Clear collections
        self.tools.clear()
        self.tool_classes.clear()
        
        # Reload tools
        self._load_builtin_tools()
        if self.settings.auto_load_tools:
            self._load_custom_tools()
    
    def update_settings(self, settings: ToolSettings):
        """Update tool settings.
        
        Args:
            settings: New tool settings
        """
        self.settings = settings
        
        # Update enabled/disabled status for existing tools
        for name, tool in self.tools.items():
            enabled = name in settings.enabled_tools
            tool.set_enabled(enabled)
        
        # Reload tools if auto-loading is enabled
        if settings.auto_load_tools:
            self.reload_tools()
    
    def cleanup(self):
        """Clean up all tools."""
        self.logger.info("Cleaning up tool manager")
        
        for tool in self.tools.values():
            tool.cleanup()
        
        self.tools.clear()
        self.tool_classes.clear()
        
        self.logger.info("Tool manager cleanup completed") 