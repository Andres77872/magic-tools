"""Style Manager for Magic Tools UI."""

import logging
import os
from pathlib import Path
from typing import Dict, Optional, List
from PyQt5 import QtWidgets


class StyleManager:
    """Manages CSS styles for the Magic Tools UI."""
    
    def __init__(self):
        self.logger = logging.getLogger(__name__)
        self.style_dir = Path(__file__).parent
        self.loaded_styles: Dict[str, str] = {}
        self.current_theme = "dark"
        
        # Load all CSS files on initialization
        self.load_all_styles()
    
    def load_all_styles(self):
        """Load all CSS files from the style directory."""
        css_files = {
            'themes': 'themes.css',
            'chat': 'chat.css',
            'launcher': 'launcher.css',
            'config': 'config.css'
        }
        
        for name, filename in css_files.items():
            self.load_style_file(name, filename)
    
    def load_style_file(self, name: str, filename: str) -> bool:
        """Load a specific CSS file."""
        file_path = self.style_dir / filename
        
        try:
            if file_path.exists():
                with open(file_path, 'r', encoding='utf-8') as f:
                    content = f.read()
                    self.loaded_styles[name] = content
                    self.logger.debug(f"Loaded style file: {filename}")
                    return True
            else:
                self.logger.warning(f"Style file not found: {file_path}")
                return False
        except Exception as e:
            self.logger.error(f"Error loading style file {filename}: {e}")
            return False
    
    def _filter_styles_by_theme(self, styles: str, theme: str) -> str:
        """Filter a stylesheet that uses `.dark-theme`/`.light-theme` prefixes.

        If the stylesheet does not contain those prefixes, the input is returned unchanged.
        """
        if not styles or ('.dark-theme' not in styles and '.light-theme' not in styles):
            return styles

        lines = styles.split('\n')
        filtered: List[str] = []

        if theme == 'dark':
            in_section = False
            for line in lines:
                if '.dark-theme' in line:
                    in_section = True
                    filtered.append(line.replace('.dark-theme ', ''))
                elif '.light-theme' in line:
                    in_section = False
                elif in_section:
                    filtered.append(line)
            return '\n'.join(filtered)
        elif theme == 'light':
            in_section = False
            for line in lines:
                if '.light-theme' in line:
                    in_section = True
                    filtered.append(line.replace('.light-theme ', ''))
                elif '.dark-theme' in line:
                    in_section = False
                elif in_section:
                    filtered.append(line)
            return '\n'.join(filtered)

        return ''

    def get_theme_styles(self, theme: str = None) -> str:
        """Get the complete theme styles."""
        if theme is None:
            theme = self.current_theme
        
        theme_styles = self.loaded_styles.get('themes', '')
        
        # Filter styles for the specified theme
        if theme == "dark":
            # Extract dark theme styles and remove the .dark-theme prefix
            lines = theme_styles.split('\n')
            filtered_lines = []
            in_dark_section = False
            
            for line in lines:
                if '.dark-theme' in line:
                    in_dark_section = True
                    # Remove .dark-theme prefix
                    filtered_lines.append(line.replace('.dark-theme ', ''))
                elif '.light-theme' in line:
                    in_dark_section = False
                elif in_dark_section:
                    filtered_lines.append(line)
            
            return '\n'.join(filtered_lines)
        
        elif theme == "light":
            # Extract light theme styles and remove the .light-theme prefix
            lines = theme_styles.split('\n')
            filtered_lines = []
            in_light_section = False
            
            for line in lines:
                if '.light-theme' in line:
                    in_light_section = True
                    # Remove .light-theme prefix
                    filtered_lines.append(line.replace('.light-theme ', ''))
                elif '.dark-theme' in line:
                    in_light_section = False
                elif in_light_section:
                    filtered_lines.append(line)
            
            return '\n'.join(filtered_lines)
        
        return ""
    
    def get_component_styles(self, component: str, theme: Optional[str] = None) -> str:
        """Get styles for a specific component, filtered by theme if applicable."""
        styles = self.loaded_styles.get(component, '')
        if theme is None:
            theme = self.current_theme
        return self._filter_styles_by_theme(styles, theme)
    
    def get_combined_styles(self, theme: str = None, components: list = None) -> str:
        """Get combined styles for theme and specified components."""
        if theme is None:
            theme = self.current_theme
        
        if components is None:
            components = ['chat', 'launcher', 'config']
        
        styles = []
        
        # Add theme styles
        theme_styles = self.get_theme_styles(theme)
        if theme_styles:
            styles.append(theme_styles)
        
        # Add component styles (theme-filtered)
        for component in components:
            component_styles = self.get_component_styles(component, theme)
            if component_styles:
                styles.append(component_styles)
        
        return '\n\n'.join(styles)
    
    def apply_styles_to_widget(self, widget: QtWidgets.QWidget, theme: str = None, components: list = None):
        """Apply styles to a specific widget."""
        styles = self.get_combined_styles(theme, components)
        
        if styles:
            widget.setStyleSheet(styles)
            self.logger.debug(f"Applied styles to {widget.__class__.__name__}")
    
    def apply_theme_to_widget(self, widget: QtWidgets.QWidget, theme: str = None):
        """Apply only theme styles to a widget."""
        if theme is None:
            theme = self.current_theme
        
        theme_styles = self.get_theme_styles(theme)
        
        if theme_styles:
            widget.setStyleSheet(theme_styles)
            self.logger.debug(f"Applied {theme} theme to {widget.__class__.__name__}")
    
    def set_theme(self, theme: str):
        """Set the current theme."""
        if theme in ["dark", "light"]:
            self.current_theme = theme
            self.logger.info(f"Theme set to: {theme}")
        else:
            self.logger.warning(f"Unknown theme: {theme}")
    
    def get_current_theme(self) -> str:
        """Get the current theme."""
        return self.current_theme
    
    def reload_styles(self):
        """Reload all style files."""
        self.loaded_styles.clear()
        self.load_all_styles()
        self.logger.info("Reloaded all style files")
    
    def get_chat_styles(self) -> str:
        """Get chat-specific styles."""
        return self.get_component_styles('chat')
    
    def get_launcher_styles(self) -> str:
        """Get launcher-specific styles."""
        return self.get_component_styles('launcher') 