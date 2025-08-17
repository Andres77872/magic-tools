"""Built-in tools for Magic Tools."""

import os
import subprocess
import math
import platform
import shutil
from typing import Dict, Type, Optional
from PyQt5 import QtWidgets, QtCore, QtGui

from .base_tool import BaseTool, QuickTool, WidgetTool, CommandTool, ToolInfo, ToolResult


class CalculatorTool(QuickTool):
    """Simple calculator tool."""
    
    def get_tool_info(self) -> ToolInfo:
        return ToolInfo(
            name="Calculator",
            description="Perform basic mathematical calculations",
            category="Utilities",
            keywords=["calc", "math", "calculate", "arithmetic"],
            author="Magic Tools"
        )
    
    def quick_execute(self, query: str = "") -> ToolResult:
        """Execute calculation from query string."""
        if not query.strip():
            return ToolResult(
                success=False,
                error="Please provide a mathematical expression"
            )
        
        try:
            # Basic security: only allow safe mathematical operations
            allowed_chars = set("0123456789+-*/.() ")
            if not all(c in allowed_chars for c in query):
                return ToolResult(
                    success=False,
                    error="Invalid characters in expression"
                )
            
            # Evaluate the expression
            result = eval(query)
            
            return ToolResult(
                success=True,
                message=f"{query} = {result}",
                data=result
            )
            
        except ZeroDivisionError:
            return ToolResult(
                success=False,
                error="Division by zero"
            )
        except Exception as e:
            return ToolResult(
                success=False,
                error=f"Invalid expression: {str(e)}"
            )


class SystemInfoTool(QuickTool):
    """System information tool."""
    
    def get_tool_info(self) -> ToolInfo:
        return ToolInfo(
            name="System Info",
            description="Display system information",
            category="System",
            keywords=["system", "info", "hardware", "os"],
            author="Magic Tools"
        )
    
    def quick_execute(self, query: str = "") -> ToolResult:
        """Get system information."""
        try:
            import psutil
            
            # Get system info
            system_info = {
                "OS": platform.system(),
                "OS Version": platform.release(),
                "Architecture": platform.architecture()[0],
                "Processor": platform.processor(),
                "CPU Count": psutil.cpu_count(),
                "Memory (GB)": round(psutil.virtual_memory().total / (1024**3), 2),
                "Disk Usage (GB)": round(psutil.disk_usage('/').total / (1024**3), 2),
            }
            
            # Format output
            info_text = "\n".join([f"{key}: {value}" for key, value in system_info.items()])
            
            return ToolResult(
                success=True,
                message="System Information",
                data=info_text
            )
            
        except ImportError:
            # Fallback without psutil
            system_info = {
                "OS": platform.system(),
                "OS Version": platform.release(),
                "Architecture": platform.architecture()[0],
                "Processor": platform.processor(),
            }
            
            info_text = "\n".join([f"{key}: {value}" for key, value in system_info.items()])
            
            return ToolResult(
                success=True,
                message="System Information (Limited)",
                data=info_text
            )
        except Exception as e:
            return ToolResult(
                success=False,
                error=f"Failed to get system info: {str(e)}"
            )


class FileSearchTool(QuickTool):
    """File search tool."""
    
    def get_tool_info(self) -> ToolInfo:
        return ToolInfo(
            name="File Search",
            description="Search for files and directories",
            category="Files",
            keywords=["search", "find", "file", "directory"],
            author="Magic Tools"
        )
    
    def quick_execute(self, query: str = "") -> ToolResult:
        """Search for files matching the query."""
        if not query.strip():
            return ToolResult(
                success=False,
                error="Please provide a search term"
            )
        
        try:
            import glob
            import os
            
            # Search in home directory
            home_dir = os.path.expanduser("~")
            search_pattern = f"**/*{query}*"
            
            matches = []
            for root, dirs, files in os.walk(home_dir):
                # Skip hidden directories and common irrelevant directories
                dirs[:] = [d for d in dirs if not d.startswith('.') and d not in ['__pycache__', 'node_modules']]
                
                for file in files:
                    if query.lower() in file.lower():
                        full_path = os.path.join(root, file)
                        matches.append(full_path)
                        
                        # Limit results to prevent overwhelming output
                        if len(matches) >= 20:
                            break
                
                if len(matches) >= 20:
                    break
            
            if matches:
                results = "\n".join(matches[:20])
                if len(matches) > 20:
                    results += f"\n... and {len(matches) - 20} more files"
                
                return ToolResult(
                    success=True,
                    message=f"Found {len(matches)} files matching '{query}'",
                    data=results
                )
            else:
                return ToolResult(
                    success=True,
                    message=f"No files found matching '{query}'",
                    data=""
                )
                
        except Exception as e:
            return ToolResult(
                success=False,
                error=f"Search failed: {str(e)}"
            )


class TerminalTool(CommandTool):
    """Terminal/command execution tool."""
    
    def get_tool_info(self) -> ToolInfo:
        return ToolInfo(
            name="Terminal",
            description="Execute terminal commands",
            category="System",
            keywords=["terminal", "command", "cmd", "bash", "shell"],
            author="Magic Tools"
        )
    
    def get_command(self, command: str = "", **kwargs) -> str:
        """Get the command to execute."""
        if not command:
            raise ValueError("No command provided")
        return command
    
    def execute(self, command: str = "", **kwargs) -> ToolResult:
        """Execute a terminal command."""
        if not command.strip():
            return ToolResult(
                success=False,
                error="Please provide a command to execute"
            )
        
        return super().execute(command=command, **kwargs)


class TextEditorTool(WidgetTool):
    """Simple text editor tool."""
    
    def get_tool_info(self) -> ToolInfo:
        return ToolInfo(
            name="Text Editor",
            description="Simple text editor",
            category="Utilities",
            keywords=["text", "editor", "edit", "write"],
            author="Magic Tools"
        )
    
    def create_widget(self) -> QtWidgets.QWidget:
        """Create the text editor widget."""
        widget = QtWidgets.QWidget()
        layout = QtWidgets.QVBoxLayout(widget)
        
        # Create text editor
        text_edit = QtWidgets.QTextEdit()
        text_edit.setPlainText("Welcome to Magic Tools Text Editor!\n\nStart typing...")
        
        # Create toolbar
        toolbar = QtWidgets.QHBoxLayout()
        
        # Save button
        save_btn = QtWidgets.QPushButton("Save")
        save_btn.clicked.connect(lambda: self._save_file(text_edit))
        
        # Load button
        load_btn = QtWidgets.QPushButton("Load")
        load_btn.clicked.connect(lambda: self._load_file(text_edit))
        
        # Clear button
        clear_btn = QtWidgets.QPushButton("Clear")
        clear_btn.clicked.connect(text_edit.clear)
        
        toolbar.addWidget(save_btn)
        toolbar.addWidget(load_btn)
        toolbar.addWidget(clear_btn)
        toolbar.addStretch()
        
        layout.addLayout(toolbar)
        layout.addWidget(text_edit)
        
        widget.setWindowTitle("Magic Tools - Text Editor")
        widget.resize(600, 400)
        
        return widget
    
    def _save_file(self, text_edit: QtWidgets.QTextEdit):
        """Save file dialog."""
        filename, _ = QtWidgets.QFileDialog.getSaveFileName(
            text_edit,
            "Save File",
            "",
            "Text Files (*.txt);;All Files (*)"
        )
        
        if filename:
            try:
                with open(filename, 'w') as f:
                    f.write(text_edit.toPlainText())
                QtWidgets.QMessageBox.information(
                    text_edit,
                    "Success",
                    f"File saved to {filename}"
                )
            except Exception as e:
                QtWidgets.QMessageBox.critical(
                    text_edit,
                    "Error",
                    f"Failed to save file: {str(e)}"
                )
    
    def _load_file(self, text_edit: QtWidgets.QTextEdit):
        """Load file dialog."""
        filename, _ = QtWidgets.QFileDialog.getOpenFileName(
            text_edit,
            "Load File",
            "",
            "Text Files (*.txt);;All Files (*)"
        )
        
        if filename:
            try:
                with open(filename, 'r') as f:
                    text_edit.setPlainText(f.read())
                QtWidgets.QMessageBox.information(
                    text_edit,
                    "Success",
                    f"File loaded from {filename}"
                )
            except Exception as e:
                QtWidgets.QMessageBox.critical(
                    text_edit,
                    "Error",
                    f"Failed to load file: {str(e)}"
                )


class FocusWindowTool(QuickTool):
    """Focus a window/application matching the selected text or query."""
    
    def get_tool_info(self) -> ToolInfo:
        return ToolInfo(
            name="Focus Window",
            description="Focus a window/application matching the selected text or query",
            category="Productivity",
            keywords=["focus", "window", "application", "keybind"],
            author="Magic Tools"
        )
    
    def _get_selected_text(self) -> str:
        """Try to get currently selected text (X11 selection) or clipboard as fallback."""
        try:
            clipboard = QtWidgets.QApplication.clipboard()
            from PyQt5.QtGui import QClipboard
            text = clipboard.text(QClipboard.Selection)
            if not text or not text.strip():
                text = clipboard.text()
            return (text or "").strip()
        except Exception as e:
            self.logger.debug(f"Clipboard read failed: {e}")
            return ""
    
    def quick_execute(self, query: str = "") -> ToolResult:
        q = (query or self._get_selected_text()).strip()
        if not q:
            return ToolResult(success=False, error="No query or selected text available")
        
        try:
            system = platform.system().lower()
            if system == "linux":
                return self._focus_linux(q)
            elif system == "darwin":
                return self._focus_macos(q)
            elif system == "windows":
                return self._focus_windows(q)
            else:
                return ToolResult(success=False, error=f"Unsupported OS: {system}")
        except Exception as e:
            return ToolResult(success=False, error=f"Focus failed: {str(e)}")
    
    def _focus_linux(self, q: str) -> ToolResult:
        wmctrl = shutil.which("wmctrl")
        xdotool = shutil.which("xdotool")
        ql = q.lower()
        
        # Try wmctrl first for better matching and activation by window id
        if wmctrl:
            try:
                out = subprocess.check_output(["wmctrl", "-lx"], text=True, stderr=subprocess.STDOUT)
                best = None  # (score, win_id, title)
                for line in out.splitlines():
                    parts = line.split(None, 4)
                    if len(parts) >= 5:
                        win_id, _desk, _host, wclass, title = parts
                        hay = f"{wclass} {title}".lower()
                        if ql in hay:
                            score = 2 if title.lower().startswith(ql) else 1
                            if best is None or score > best[0]:
                                best = (score, win_id, title)
                if best:
                    win_id = best[1]
                    subprocess.run(["wmctrl", "-ia", win_id], check=False)
                    return ToolResult(success=True, message=f"Focused window: {best[2]}")
            except Exception as e:
                self.logger.debug(f"wmctrl failed: {e}")
        
        # Fallback to xdotool by name
        if xdotool:
            try:
                out = subprocess.check_output(["xdotool", "search", "--name", q], text=True, stderr=subprocess.STDOUT)
                win_ids = [line.strip() for line in out.splitlines() if line.strip()]
                if win_ids:
                    subprocess.run(["xdotool", "windowactivate", win_ids[0]], check=False)
                    return ToolResult(success=True, message=f"Focused window id: {win_ids[0]}")
            except subprocess.CalledProcessError:
                pass
            except Exception as e:
                self.logger.debug(f"xdotool failed: {e}")
        
        return ToolResult(success=False, error=f"No matching window found for '{q}'")
    
    def _focus_macos(self, q: str) -> ToolResult:
        try:
            script = (
                'tell application "System Events"\n'
                '    set frontApps to name of every process whose background only is false\n'
                'end tell\n'
                'repeat with appName in frontApps\n'
                f'    if (lowercase of appName as text) contains "{q.lower()}" then\n'
                '        tell application appName to activate\n'
                '        return\n'
                '    end if\n'
                'end repeat\n'
            )
            subprocess.run(["osascript", "-e", script], check=True)
            return ToolResult(success=True, message=f"Focused application matching '{q}'")
        except Exception as e:
            return ToolResult(success=False, error=f"macOS focus failed: {str(e)}")
    
    def _focus_windows(self, q: str) -> ToolResult:
        try:
            # Attempt to activate a window by title using PowerShell and user32 SetForegroundWindow
            ps = (
                "Add-Type @\"\n"
                "using System;\n"
                "using System.Runtime.InteropServices;\n"
                "public class Win32 {\n"
                "    [DllImport(\"user32.dll\")] public static extern bool SetForegroundWindow(IntPtr hWnd);\n"
                "}\n"
                "\"@\n"
                "$procs = Get-Process | Where-Object { $_.MainWindowHandle -ne 0 -and $_.MainWindowTitle -ne '' }\n"
                f"$match = $procs | Where-Object {{ $_.MainWindowTitle -match '{q.replace("'", "''")}' }} | Select-Object -First 1\n"
                "if ($match) { [Win32]::SetForegroundWindow($match.MainWindowHandle) }\n"
            )
            subprocess.run(["powershell", "-NoProfile", "-Command", ps], check=False)
            return ToolResult(success=True, message=f"Tried to focus window matching '{q}'")
        except Exception as e:
            return ToolResult(success=False, error=f"Windows focus failed: {str(e)}")


class BuiltinTools:
    """Container for built-in tools."""
    
    def __init__(self):
        self.tools = {
            "calculator": CalculatorTool,
            "system_info": SystemInfoTool,
            "file_search": FileSearchTool,
            "terminal": TerminalTool,
            "text_editor": TextEditorTool,
            "focus_window": FocusWindowTool,
        }
    
    def get_tool_classes(self) -> Dict[str, Type[BaseTool]]:
        """Get all built-in tool classes."""
        return self.tools.copy()
    
    def get_tool_names(self) -> list:
        """Get names of all built-in tools."""
        return list(self.tools.keys())
    
    def get_tool_class(self, name: str) -> Optional[Type[BaseTool]]:
        """Get a specific tool class by name."""
        return self.tools.get(name) 