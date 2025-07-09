"""AI Chat widget for Magic Tools."""

import logging
import asyncio
from typing import Optional
from PyQt5 import QtWidgets, QtCore, QtGui
from PyQt5.QtCore import Qt, pyqtSignal, QThread, QTimer

from ..ai import AIManager
from ..ai.ai_manager import AIMessage, AIResponse
from ..config.settings import UISettings
from .style import StyleManager


class MessageWidget(QtWidgets.QWidget):
    """Widget for displaying a chat message."""
    
    def __init__(self, message: AIMessage, parent=None):
        super().__init__(parent)
        self.message = message
        self.setup_ui()
    
    def setup_ui(self):
        """Setup the message widget UI."""
        layout = QtWidgets.QHBoxLayout(self)
        layout.setContentsMargins(10, 5, 10, 5)
        
        # Message bubble
        bubble = QtWidgets.QLabel(self.message.content)
        bubble.setWordWrap(True)
        bubble.setTextInteractionFlags(Qt.TextSelectableByMouse)
        
        # Style based on role
        if self.message.role == "user":
            bubble.setAlignment(Qt.AlignRight)
            bubble.setProperty("class", "message-bubble-user")
            layout.addStretch()
            layout.addWidget(bubble)
        else:  # assistant
            bubble.setAlignment(Qt.AlignLeft)
            bubble.setProperty("class", "message-bubble-assistant")
            layout.addWidget(bubble)
            layout.addStretch()


class AIWorker(QThread):
    """Worker thread for AI operations."""
    
    response_received = pyqtSignal(AIResponse)
    streaming_chunk = pyqtSignal(str)
    error_occurred = pyqtSignal(str)
    
    def __init__(self, ai_manager: AIManager, message: str, context: str = ""):
        super().__init__()
        self.ai_manager = ai_manager
        self.message = message
        self.context = context
        self.streaming = False
    
    def run(self):
        """Run the AI request in a separate thread."""
        try:
            # Set up event loop for async operations
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            
            if self.streaming:
                # Stream response
                async def stream_response():
                    async for chunk in self.ai_manager.stream_response(self.message, self.context):
                        self.streaming_chunk.emit(chunk)
                
                loop.run_until_complete(stream_response())
            else:
                # Get complete response
                response = loop.run_until_complete(
                    self.ai_manager.send_message(self.message, self.context)
                )
                self.response_received.emit(response)
                
        except Exception as e:
            self.error_occurred.emit(str(e))
        finally:
            loop.close()


class AIChatWidget(QtWidgets.QWidget):
    """AI chat interface widget."""
    
    back_to_launcher = pyqtSignal()
    close_requested = pyqtSignal()
    
    def __init__(self, ai_manager: AIManager, parent=None):
        super().__init__(parent)
        
        self.logger = logging.getLogger(__name__)
        self.ai_manager = ai_manager
        self.ui_settings = None
        
        # Initialize style manager
        self.style_manager = StyleManager()
        
        # UI components
        self.chat_display = None
        self.input_field = None
        self.send_button = None
        self.status_label = None
        
        # Chat state
        self.is_waiting_for_response = False
        self.current_worker = None
        self.streaming_message_widget = None
        
        # Setup UI
        self.setup_ui()
        self.setup_signals()
        
        # Apply styles
        self.apply_styles()
    
    def setup_ui(self):
        """Setup the AI chat UI."""
        # Main layout
        self.main_layout = QtWidgets.QVBoxLayout(self)
        self.main_layout.setContentsMargins(20, 20, 20, 20)
        self.main_layout.setSpacing(10)
        
        # Header
        self.setup_header()
        
        # Chat display area
        self.setup_chat_display()
        
        # Input area
        self.setup_input_area()
        
        # Status bar
        self.setup_status_bar()
        
        # Initial welcome message
        self.show_welcome_message()
    
    def setup_header(self):
        """Setup the header section."""
        header_layout = QtWidgets.QHBoxLayout()
        
        # Back button
        back_button = QtWidgets.QPushButton("← Back")
        back_button.setFixedSize(60, 30)
        back_button.clicked.connect(self.back_to_launcher.emit)
        back_button.setProperty("class", "chat-back-button")
        
        # Title
        title_label = QtWidgets.QLabel("AI Assistant")
        title_label.setAlignment(Qt.AlignCenter)
        title_label.setProperty("class", "chat-title")
        
        # AI status
        ai_status = "🟢 Connected" if self.ai_manager.is_available() else "🔴 Disconnected"
        self.ai_status_label = QtWidgets.QLabel(ai_status)
        self.ai_status_label.setAlignment(Qt.AlignRight)
        self.ai_status_label.setProperty("class", "chat-ai-status")
        
        header_layout.addWidget(back_button)
        header_layout.addWidget(title_label)
        header_layout.addWidget(self.ai_status_label)
        
        self.main_layout.addLayout(header_layout)
    
    def setup_chat_display(self):
        """Setup the chat display area."""
        # Scroll area for chat history
        self.chat_scroll = QtWidgets.QScrollArea()
        self.chat_scroll.setWidgetResizable(True)
        self.chat_scroll.setVerticalScrollBarPolicy(Qt.ScrollBarAsNeeded)
        self.chat_scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        
        # Chat widget
        self.chat_widget = QtWidgets.QWidget()
        self.chat_layout = QtWidgets.QVBoxLayout(self.chat_widget)
        self.chat_layout.setSpacing(5)
        self.chat_layout.addStretch()  # Push messages to bottom
        
        self.chat_scroll.setWidget(self.chat_widget)
        self.main_layout.addWidget(self.chat_scroll)
    
    def setup_input_area(self):
        """Setup the input area."""
        input_layout = QtWidgets.QHBoxLayout()
        
        # Input field
        self.input_field = QtWidgets.QLineEdit()
        self.input_field.setPlaceholderText("Ask me anything...")
        self.input_field.returnPressed.connect(self.send_message)
        
        # Send button
        self.send_button = QtWidgets.QPushButton("Send")
        self.send_button.setFixedSize(60, 35)
        self.send_button.clicked.connect(self.send_message)
        self.send_button.setProperty("class", "chat-send-button")
        
        input_layout.addWidget(self.input_field)
        input_layout.addWidget(self.send_button)
        
        self.main_layout.addLayout(input_layout)
    
    def setup_status_bar(self):
        """Setup the status bar."""
        status_layout = QtWidgets.QHBoxLayout()
        
        # Status label
        self.status_label = QtWidgets.QLabel("Ready")
        self.status_label.setProperty("class", "chat-status-label")
        
        # Clear button
        clear_button = QtWidgets.QPushButton("Clear")
        clear_button.setFixedSize(50, 25)
        clear_button.clicked.connect(self.clear_chat)
        clear_button.setProperty("class", "chat-clear-button")
        
        status_layout.addWidget(self.status_label)
        status_layout.addStretch()
        status_layout.addWidget(clear_button)
        
        self.main_layout.addLayout(status_layout)
    
    def apply_styles(self):
        """Apply styles using the StyleManager."""
        self.style_manager.apply_styles_to_widget(self, components=['chat'])
    
    def setup_signals(self):
        """Setup signal connections."""
        # Timer for updating status
        self.status_timer = QTimer()
        self.status_timer.timeout.connect(self.update_status)
        self.status_timer.start(1000)  # Update every second
    
    def show_welcome_message(self):
        """Show welcome message."""
        welcome_text = """👋 Welcome to Magic Tools AI Assistant!

I'm here to help you with:
• Answering questions
• Providing information
• Assisting with tasks
• General conversation

How can I help you today?"""
        
        welcome_message = AIMessage(role="assistant", content=welcome_text)
        self.add_message_to_chat(welcome_message)
    
    def send_message(self):
        """Send a message to the AI."""
        message_text = self.input_field.text().strip()
        
        if not message_text:
            return
        
        if self.is_waiting_for_response:
            self.show_status("Please wait for the current response to complete...")
            return
        
        if not self.ai_manager.is_available():
            self.show_status("AI is not available. Please check your configuration.")
            return
        
        # Clear input
        self.input_field.clear()
        
        # Add user message to chat
        user_message = AIMessage(role="user", content=message_text)
        self.add_message_to_chat(user_message)
        
        # Send to AI
        self.send_to_ai(message_text)
    
    def send_to_ai(self, message: str):
        """Send message to AI in a separate thread."""
        self.is_waiting_for_response = True
        self.send_button.setEnabled(False)
        self.input_field.setEnabled(False)
        self.show_status("Thinking...")
        
        # Create worker thread
        self.current_worker = AIWorker(self.ai_manager, message)
        self.current_worker.response_received.connect(self.on_ai_response)
        self.current_worker.error_occurred.connect(self.on_ai_error)
        self.current_worker.start()
    
    def on_ai_response(self, response: AIResponse):
        """Handle AI response."""
        self.is_waiting_for_response = False
        self.send_button.setEnabled(True)
        self.input_field.setEnabled(True)
        
        if response.success:
            # Add AI response to chat
            ai_message = AIMessage(role="assistant", content=response.content)
            self.add_message_to_chat(ai_message)
            
            # Update status
            tokens_info = f"({response.tokens_used} tokens)" if response.tokens_used else ""
            self.show_status(f"Response received {tokens_info}")
        else:
            self.show_status(f"Error: {response.error}")
            
            # Show error message in chat
            error_message = AIMessage(
                role="assistant", 
                content=f"Sorry, I encountered an error: {response.error}"
            )
            self.add_message_to_chat(error_message)
        
        # Focus input
        self.input_field.setFocus()
    
    def on_ai_error(self, error: str):
        """Handle AI error."""
        self.is_waiting_for_response = False
        self.send_button.setEnabled(True)
        self.input_field.setEnabled(True)
        
        self.show_status(f"Error: {error}")
        
        # Show error message in chat
        error_message = AIMessage(
            role="assistant", 
            content=f"Sorry, I encountered an error: {error}"
        )
        self.add_message_to_chat(error_message)
        
        # Focus input
        self.input_field.setFocus()
    
    def add_message_to_chat(self, message: AIMessage):
        """Add a message to the chat display."""
        # Remove the stretch from the end
        if self.chat_layout.count() > 0:
            stretch_item = self.chat_layout.takeAt(self.chat_layout.count() - 1)
            if stretch_item:
                widget = stretch_item.widget()
                if widget is not None:
                    widget.deleteLater()
                # If stretch_item has no widget (e.g., QSpacerItem), no deletion needed
        
        # Add message widget
        message_widget = MessageWidget(message)
        self.chat_layout.addWidget(message_widget)
        
        # Add stretch back at the end
        self.chat_layout.addStretch()
        
        # Scroll to bottom
        QtCore.QTimer.singleShot(100, self.scroll_to_bottom)
    
    def scroll_to_bottom(self):
        """Scroll chat to the bottom."""
        scrollbar = self.chat_scroll.verticalScrollBar()
        scrollbar.setValue(scrollbar.maximum())
    
    def clear_chat(self):
        """Clear the chat history."""
        # Clear widgets
        for i in reversed(range(self.chat_layout.count())):
            item = self.chat_layout.takeAt(i)
            if item.widget():
                item.widget().deleteLater()
        
        # Clear AI conversation history
        self.ai_manager.clear_conversation()
        
        # Add stretch back
        self.chat_layout.addStretch()
        
        # Show welcome message again
        self.show_welcome_message()
        
        self.show_status("Chat cleared")
    
    def show_status(self, message: str):
        """Show status message."""
        self.status_label.setText(message)
        self.logger.info(f"Status: {message}")
        
        # Clear status after 5 seconds
        QtCore.QTimer.singleShot(5000, lambda: self.status_label.setText("Ready"))
    
    def update_status(self):
        """Update status information."""
        if self.ai_manager.is_available():
            self.ai_status_label.setText("🟢 Connected")
        else:
            self.ai_status_label.setText("🔴 Disconnected")
    
    def focus_input(self):
        """Focus the input field."""
        self.input_field.setFocus()
    
    def update_settings(self, ui_settings: UISettings):
        """Update UI settings."""
        self.ui_settings = ui_settings
        
        # Update theme and apply styles
        self.style_manager.set_theme(ui_settings.theme)
        self.apply_styles()
        
        # Update status
        self.update_status()
    
    def keyPressEvent(self, event):
        """Handle key press events."""
        if event.key() == Qt.Key_Escape:
            self.close_requested.emit()
        elif event.key() == Qt.Key_Return and event.modifiers() == Qt.ControlModifier:
            self.send_message()
        else:
            super().keyPressEvent(event)
    
    def closeEvent(self, event):
        """Handle close event."""
        # Stop any running worker
        if self.current_worker and self.current_worker.isRunning():
            self.current_worker.quit()
            self.current_worker.wait()
        
        super().closeEvent(event) 