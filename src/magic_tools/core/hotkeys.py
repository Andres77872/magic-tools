"""Global hotkey management for Magic Tools."""

import logging
from typing import Dict, Callable, Optional
from PyQt5 import QtCore
from pynput import keyboard as pyn_keyboard


class GlobalHotkeyManager(QtCore.QObject):
    """Manages global system hotkeys using pynput."""
    
    # Signals for hotkey events
    toggle_requested = QtCore.pyqtSignal()
    ai_chat_requested = QtCore.pyqtSignal()
    quick_search_requested = QtCore.pyqtSignal()
    focus_selected_requested = QtCore.pyqtSignal()
    
    def __init__(self):
        super().__init__()
        self.logger = logging.getLogger(__name__)
        self.hotkey_listeners: Dict[str, pyn_keyboard.GlobalHotKeys] = {}
        self.active_hotkeys: Dict[str, str] = {}
        
    def _format_hotkey(self, sequence: str) -> str:
        """Convert Qt-style shortcut to pynput format.
        
        Args:
            sequence: Qt-style shortcut (e.g., 'Ctrl+Space')
            
        Returns:
            pynput-formatted hotkey string
        """
        parts = [p.strip().lower() for p in sequence.split('+')]
        mapping = {
            'ctrl': '<ctrl>',
            'control': '<ctrl>',
            'alt': '<alt>',
            'shift': '<shift>',
            'meta': '<cmd>',
            'cmd': '<cmd>',
            'space': '<space>',
            'tab': '<tab>',
            'enter': '<enter>',
            'return': '<enter>',
            'escape': '<esc>',
            'backspace': '<backspace>',
            'delete': '<delete>',
            'up': '<up>',
            'down': '<down>',
            'left': '<left>',
            'right': '<right>',
            'home': '<home>',
            'end': '<end>',
            'page_up': '<page_up>',
            'page_down': '<page_down>',
            'f1': '<f1>', 'f2': '<f2>', 'f3': '<f3>', 'f4': '<f4>',
            'f5': '<f5>', 'f6': '<f6>', 'f7': '<f7>', 'f8': '<f8>',
            'f9': '<f9>', 'f10': '<f10>', 'f11': '<f11>', 'f12': '<f12>',
        }
        
        formatted_parts = []
        for part in parts:
            if part in mapping:
                formatted_parts.append(mapping[part])
            elif len(part) == 1:
                formatted_parts.append(part)
            else:
                # Handle function keys and other special keys
                formatted_parts.append(f'<{part}>')
        
        return '+'.join(formatted_parts)
    
    def register_hotkey(self, name: str, sequence: str, callback: Callable[[], None]) -> bool:
        """Register a global hotkey.
        
        Args:
            name: Hotkey identifier
            sequence: Qt-style shortcut sequence
            callback: Function to call when hotkey is pressed
            
        Returns:
            True if registered successfully
        """
        try:
            # Stop existing hotkey if it exists
            self.unregister_hotkey(name)
            
            formatted_sequence = self._format_hotkey(sequence)
            self.logger.debug(f"Registering hotkey '{name}': {sequence} -> {formatted_sequence}")
            
            # Create new hotkey listener
            hotkey_dict = {formatted_sequence: callback}
            listener = pyn_keyboard.GlobalHotKeys(hotkey_dict)
            
            # Start the listener
            listener.start()
            
            # Store the listener and sequence
            self.hotkey_listeners[name] = listener
            self.active_hotkeys[name] = sequence
            
            self.logger.info(f"Registered global hotkey '{name}': {sequence}")
            return True
            
        except Exception as e:
            self.logger.error(f"Failed to register hotkey '{name}' ({sequence}): {e}")
            return False
    
    def unregister_hotkey(self, name: str) -> bool:
        """Unregister a global hotkey.
        
        Args:
            name: Hotkey identifier
            
        Returns:
            True if unregistered successfully
        """
        try:
            if name in self.hotkey_listeners:
                listener = self.hotkey_listeners[name]
                listener.stop()
                del self.hotkey_listeners[name]
                
                if name in self.active_hotkeys:
                    del self.active_hotkeys[name]
                
                self.logger.info(f"Unregistered global hotkey '{name}'")
                return True
            else:
                self.logger.warning(f"Hotkey '{name}' not found for unregistration")
                return False
                
        except Exception as e:
            self.logger.error(f"Failed to unregister hotkey '{name}': {e}")
            return False
    
    def update_hotkey(self, name: str, new_sequence: str) -> bool:
        """Update an existing hotkey's sequence.
        
        Args:
            name: Hotkey identifier
            new_sequence: New Qt-style shortcut sequence
            
        Returns:
            True if updated successfully
        """
        if name not in self.hotkey_listeners:
            self.logger.warning(f"Cannot update non-existent hotkey '{name}'")
            return False
        
        # Get the current callback
        old_listener = self.hotkey_listeners[name]
        
        # For built-in hotkeys, we know the callbacks
        callback_map = {
            'toggle': lambda: self.toggle_requested.emit(),
            'ai_chat': lambda: self.ai_chat_requested.emit(),
            'quick_search': lambda: self.quick_search_requested.emit(),
            'focus_selected': lambda: self.focus_selected_requested.emit(),
        }
        
        if name in callback_map:
            return self.register_hotkey(name, new_sequence, callback_map[name])
        else:
            self.logger.error(f"Cannot update hotkey '{name}': unknown callback")
            return False
    
    def register_default_hotkeys(self, toggle_shortcut: str = "Ctrl+Space", 
                                ai_chat_shortcut: str = "Ctrl+Alt+A",
                                quick_search_shortcut: str = "Ctrl+Alt+S",
                                focus_selected_shortcut: str = "Ctrl+Alt+F"):
        """Register default application hotkeys.
        
        Args:
            toggle_shortcut: Main toggle shortcut
            ai_chat_shortcut: AI chat shortcut
            quick_search_shortcut: Quick search shortcut
            focus_selected_shortcut: Focus window matching selected text
        """
        self.register_hotkey('toggle', toggle_shortcut, lambda: self.toggle_requested.emit())
        self.register_hotkey('ai_chat', ai_chat_shortcut, lambda: self.ai_chat_requested.emit())
        self.register_hotkey('quick_search', quick_search_shortcut, lambda: self.quick_search_requested.emit())
        self.register_hotkey('focus_selected', focus_selected_shortcut, lambda: self.focus_selected_requested.emit())
    
    def get_active_hotkeys(self) -> Dict[str, str]:
        """Get currently active hotkeys.
        
        Returns:
            Dictionary of hotkey names and their sequences
        """
        return self.active_hotkeys.copy()
    
    def cleanup(self):
        """Clean up all hotkey listeners."""
        for name in list(self.hotkey_listeners.keys()):
            self.unregister_hotkey(name)
        self.logger.info("Global hotkey manager cleaned up") 