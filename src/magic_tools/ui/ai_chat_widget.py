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
    """Widget for displaying a chat message with rich interactions.

    Uses QLabel with RichText for natural, dynamic height growth while streaming.
    """

    def __init__(self, message: AIMessage, parent=None):
        super().__init__(parent)
        self.message = message
        self._copy_button = None
        self._max_bubble_width = 520
        self._min_bubble_width = 180
        self.setup_ui()

    def setup_ui(self):
        """Setup the message widget UI with bubble and copy control."""
        layout = QtWidgets.QHBoxLayout(self)
        layout.setContentsMargins(10, 5, 10, 5)

        # Message bubble as rich text label (natural auto-height, no inner scrollbars)
        self.bubble = QtWidgets.QLabel()
        self.bubble.setOpenExternalLinks(True)
        self.bubble.setTextFormat(Qt.RichText)
        self.bubble.setWordWrap(True)
        self.bubble.setTextInteractionFlags(Qt.TextSelectableByMouse | Qt.LinksAccessibleByMouse)
        self.bubble.setFocusPolicy(Qt.NoFocus)
        self.bubble.setMinimumWidth(120)
        self.bubble.setSizePolicy(QtWidgets.QSizePolicy.Preferred, QtWidgets.QSizePolicy.Minimum)

        # Subtle shadow for depth
        try:
            shadow = QtWidgets.QGraphicsDropShadowEffect(self.bubble)
            shadow.setBlurRadius(12)
            shadow.setOffset(0, 2)
            shadow.setColor(QtGui.QColor(0, 0, 0, 60))
            self.bubble.setGraphicsEffect(shadow)
        except Exception:
            pass

        # Populate content
        self._set_rich_text(self.message.content)
        self._apply_bubble_size()

        # Copy button (appears on hover)
        self._copy_button = QtWidgets.QToolButton(self.bubble)
        self._copy_button.setText("⧉")
        self._copy_button.setToolTip("Copy message")
        self._copy_button.setCursor(Qt.PointingHandCursor)
        self._copy_button.setProperty("class", "chat-copy-button")
        self._copy_button.setFixedSize(18, 18)
        self._copy_button.clicked.connect(self.copy_to_clipboard)
        self._copy_button.hide()

        # Context menu
        self.bubble.setContextMenuPolicy(Qt.CustomContextMenu)
        self.bubble.customContextMenuRequested.connect(self._show_context_menu)

        # Style based on role
        if self.message.role == "user":
            self.bubble.setProperty("class", "message-bubble-user")
            layout.addStretch()
            layout.addWidget(self.bubble, 0, Qt.AlignRight)
        else:  # assistant
            self.bubble.setProperty("class", "message-bubble-assistant")
            layout.addWidget(self.bubble, 0, Qt.AlignLeft)
            layout.addStretch()

    def resizeEvent(self, event: QtGui.QResizeEvent):
        """Position the copy button at the top-right of the bubble."""
        super().resizeEvent(event)
        if self._copy_button:
            br = self.bubble.rect()
            x = br.right() - 20
            y = br.top() + 6
            self._copy_button.move(x, y)

    def enterEvent(self, event: QtCore.QEvent):
        if self._copy_button:
            self._copy_button.show()
        super().enterEvent(event)

    def leaveEvent(self, event: QtCore.QEvent):
        if self._copy_button:
            self._copy_button.hide()
        super().leaveEvent(event)

    def _set_rich_text(self, text: str):
        """Render plain text with light Markdown-like formatting to HTML."""
        html = self._basic_markdown_to_html(text)
        self.bubble.setText(html)
        self._apply_bubble_size()

    def set_text(self, text: str):
        """Replace the message content and refresh the bubble."""
        self.message.content = text
        self._set_rich_text(self.message.content)

    def append_text(self, text: str):
        """Append text to the message content and refresh the bubble."""
        if not text:
            return
        self.set_text(self.message.content + text)

    def set_max_bubble_width(self, max_width: int):
        """Set the maximum width for the bubble and reflow content."""
        if max_width <= 0:
            return
        if max_width == self._max_bubble_width:
            return
        self._max_bubble_width = max_width
        self._apply_bubble_size()

    def set_bubble_width_limits(self, min_width: int, max_width: int):
        changed = False
        if min_width > 0 and min_width != self._min_bubble_width:
            self._min_bubble_width = min_width
            changed = True
        if max_width > 0 and max_width != self._max_bubble_width:
            self._max_bubble_width = max_width
            changed = True
        if changed:
            self._apply_bubble_size()

    def _apply_bubble_size(self):
        """Pick a width based on content, clamped between min and max; allow auto-height."""
        try:
            max_width = max(200, int(self._max_bubble_width))
            min_width = max(120, int(self._min_bubble_width))
            if min_width > max_width:
                min_width = max_width

            # Measure content width using QTextDocument
            doc = QtGui.QTextDocument()
            doc.setDefaultFont(self.bubble.font())
            doc.setHtml(self.bubble.text())
            doc.setTextWidth(-1)  # no wrapping
            ideal = int(doc.idealWidth())
            content_width = max(min_width, min(max_width, ideal))

            self.bubble.setFixedWidth(content_width)
            self.bubble.adjustSize()  # compute proper height for the fixed width
        except Exception:
            self.bubble.setMaximumWidth(self._max_bubble_width)
            self.bubble.adjustSize()

    def copy_to_clipboard(self):
        clipboard = QtWidgets.QApplication.clipboard()
        clipboard.setText(self.message.content)

    def _show_context_menu(self, pos: QtCore.QPoint):
        menu = QtWidgets.QMenu(self)
        copy_action = menu.addAction("Copy")
        copy_md_action = menu.addAction("Copy as Markdown")
        action = menu.exec_(self.bubble.mapToGlobal(pos))
        if action == copy_action:
            self.copy_to_clipboard()
        elif action == copy_md_action:
            self.copy_to_clipboard()

    @staticmethod
    def _basic_markdown_to_html(text: str) -> str:
        """Very small subset of Markdown to HTML for nicer rendering.

        Supports:
        - Paragraphs and line breaks
        - Inline code using `backticks`
        - Code blocks fenced by triple backticks
        - Simple unordered lists (- or •)
        - Links starting with http(s)://
        """
        import html as _html
        import re as _re

        if not text:
            return ""

        # Normalize newlines
        text = text.replace('\r\n', '\n').replace('\r', '\n')

        # Extract fenced code blocks first
        code_blocks = []
        def _code_repl(match):
            lang = match.group(1) or ""
            code_body = match.group(2)
            code_blocks.append(code_body)
            return f"@@CODEBLOCK{len(code_blocks)-1}:{lang}@@"

        fenced = _re.compile(r"```\s*([a-zA-Z0-9_-]+)?\n([\s\S]*?)```", _re.MULTILINE)
        text = _re.sub(fenced, _code_repl, text)

        # Escape HTML on remaining text
        text = _html.escape(text)

        # Inline code
        text = _re.sub(r"`([^`]+)`", r"<code>\1</code>", text)

        # Links
        text = _re.sub(r"(https?://[\w\-\./?%&=#:+]+)", r"<a href=\"\1\">\1</a>", text)

        # Lists: convert lines starting with - or • into <ul><li>
        lines = text.split('\n')
        html_lines = []
        in_ul = False
        for line in lines:
            if line.strip().startswith('- ') or line.strip().startswith('• '):
                if not in_ul:
                    in_ul = True
                    html_lines.append('<ul>')
                item = line.strip()[2:]
                html_lines.append(f'<li>{item}</li>')
            else:
                if in_ul:
                    in_ul = False
                    html_lines.append('</ul>')
                if line.strip() == '':
                    html_lines.append('<br/>')
                else:
                    html_lines.append(line)
        if in_ul:
            html_lines.append('</ul>')

        text = '\n'.join(html_lines)

        # Restore code blocks
        def _restore_code_block(m):
            idx, lang = m.group(1), m.group(2)
            code = code_blocks[int(idx)]
            code = _html.escape(code)
            # Light inline styles so it looks good in both themes
            return (
                f"<pre style=\"background: rgba(0,0,0,0.25); padding:8px; border-radius:6px;\">"
                f"<code>{code}</code>"
                f"</pre>"
            )

        text = _re.sub(r"@@CODEBLOCK(\d+):([a-zA-Z0-9_-]*)@@", _restore_code_block, text)

        # Wrap in a simple container to constrain width
        return f"<div style=\"white-space: normal; word-wrap: break-word;\">{text}</div>"


class AIWorker(QThread):
    """Worker thread for AI operations."""
    
    response_received = pyqtSignal(AIResponse)
    streaming_chunk = pyqtSignal(str)
    error_occurred = pyqtSignal(str)
    
    def __init__(self, ai_manager: AIManager, message: str, context: str = "", logger=None):
        super().__init__()
        self.ai_manager = ai_manager
        self.message = message
        self.context = context
        self.streaming = False
        self.logger = logger or logging.getLogger(__name__)
        self._cancel_requested = False
    
    def request_cancel(self):
        """Request cancellation of the running task."""
        self._cancel_requested = True
    
    def run(self):
        """Run the AI request in a separate thread."""
        # Each thread needs its own event loop
        loop = None
        
        try:
            # Create a new event loop for this thread
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            
            if self.streaming:
                self._handle_streaming_response(loop)
            else:
                self._handle_complete_response(loop)
                
        except Exception as e:
            self.error_occurred.emit(f"Thread error: {str(e)}")
            self.logger.error(f"Thread error: {str(e)}")
        finally:
            # Make sure to clean up the event loop properly
            if loop is not None:
                self._cleanup_loop(loop)
    
    def _handle_streaming_response(self, loop):
        """Handle streaming response mode."""
        async def stream_response():
            try:
                agen = self.ai_manager.stream_response(self.message, self.context)
                async for chunk in agen:
                    self.streaming_chunk.emit(chunk)
                    if self._cancel_requested:
                        # Attempt to close the async generator gracefully
                        try:
                            await agen.aclose()  # type: ignore[attr-defined]
                        except Exception:
                            pass
                        break
            except Exception as e:
                self.error_occurred.emit(f"Streaming error: {str(e)}")
                self.logger.error(f"Streaming error: {str(e)}")
        
        # Create a task and run it to completion
        task = loop.create_task(stream_response())
        loop.run_until_complete(task)
    
    def _handle_complete_response(self, loop):
        """Handle complete response mode."""
        async def get_response():
            try:
                return await self.ai_manager.send_message(self.message, self.context)
            except Exception as e:
                self.error_occurred.emit(f"Response error: {str(e)}")
                self.logger.error(f"Response error: {str(e)}")
                return None
        
        # Create a task and run it to completion
        task = loop.create_task(get_response())
        response = loop.run_until_complete(task)
        
        if response:
            self.response_received.emit(response)
    
    def _cleanup_loop(self, loop):
        """Clean up event loop resources."""
        try:
            # Cancel any pending tasks
            pending = asyncio.all_tasks(loop)
            if pending:
                for task in pending:
                    task.cancel()
                
                # Run until all tasks are cancelled
                loop.run_until_complete(
                    asyncio.gather(*pending, return_exceptions=True)
                )
            
            # Close the loop
            loop.close()
        except Exception as e:
            self.logger.error(f"Error during event loop cleanup: {str(e)}")
        finally:
            # Always reset the thread's event loop to None
            asyncio.set_event_loop(None)


class AIChatWidget(QtWidgets.QWidget):
    """AI chat interface widget."""
    
    back_to_launcher = pyqtSignal()
    close_requested = pyqtSignal()
    
    def __init__(self, ai_manager: AIManager, parent=None, tool_manager=None):
        super().__init__(parent)
        
        self.logger = logging.getLogger(__name__)
        self.ai_manager = ai_manager
        self.tool_manager = tool_manager
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
        self._cancel_in_progress = False
        self._autoscroll_pinned = True
        
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
        self.chat_layout.setContentsMargins(16, 8, 16, 8)
        self.chat_layout.setSpacing(10)
        self.chat_layout.addStretch()  # Push messages to bottom
        
        self.chat_scroll.setWidget(self.chat_widget)
        self.main_layout.addWidget(self.chat_scroll)

        # Smart autoscroll and overlay button
        self.chat_scroll.verticalScrollBar().valueChanged.connect(self.on_scroll_value_changed)
        self.scroll_bottom_button = QtWidgets.QToolButton(self.chat_scroll.viewport())
        self.scroll_bottom_button.setText("↓")
        self.scroll_bottom_button.setToolTip("Scroll to latest message")
        self.scroll_bottom_button.setProperty("class", "chat-scroll-bottom")
        self.scroll_bottom_button.hide()
        self.scroll_bottom_button.clicked.connect(lambda: self.scroll_to_bottom(force=True))
        self._position_scroll_bottom_button()

        # Propagate viewport width to messages for responsive bubble sizing
        self.chat_scroll.viewport().installEventFilter(self)
    
    def setup_input_area(self):
        """Setup the input area."""
        input_layout = QtWidgets.QHBoxLayout()
        input_layout.setContentsMargins(0, 0, 0, 0)
        input_layout.setSpacing(8)
        
        # Input field (multi-line)
        self.input_field = QtWidgets.QTextEdit()
        self.input_field.setAcceptRichText(False)
        self.input_field.setPlaceholderText("Ask me anything… (Enter to send, Shift+Enter for newline)")
        # Default to 3 lines height
        fm = self.input_field.fontMetrics()
        default_h = int(3 * fm.lineSpacing() + 12)
        self.input_field.setFixedHeight(max(36, default_h))
        self.input_field.setProperty("class", "chat-input")
        self.input_field.textChanged.connect(self._update_input_height)
        self.input_field.installEventFilter(self)
        
        # Send button
        self.send_button = QtWidgets.QPushButton("Send")
        self.send_button.setFixedSize(60, 35)
        self.send_button.clicked.connect(self.send_message)
        self.send_button.setProperty("class", "chat-send-button")
        
        input_layout.addWidget(self.input_field, 1)
        input_layout.addWidget(self.send_button, 0)
        
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
        # Get message from input
        message = self.input_field.toPlainText().strip()
        if not message:
            return
            
        # Clear input field
        self.input_field.clear()
        
        # Keep input enabled; update status
        self.show_status("Thinking...")
        
        # Check if AI is available
        if not self.ai_manager.is_available():
            self.show_status("AI is not available. Please check your configuration.")
            self._set_streaming_ui(False)
            return

        # Slash command handling: /command text -> use system prompt from Prompt Commands tool
        context_prompt = ""
        outgoing_text = message
        try:
            if message.startswith('/'):
                parts = message[1:].strip().split(None, 1)
                command = parts[0] if parts else ""
                content_after = parts[1] if len(parts) > 1 else ""

                # Validate command per specification (letters, numbers, hyphen, underscore)
                import re as _re
                if not command or not _re.match(r"^[A-Za-z0-9_-]+$", command):
                    self.show_status("Invalid command. Use letters, numbers, '-' or '_' only.")
                    return

                # Obtain PromptCommands tool if available
                prompt_tool = None
                try:
                    if self.tool_manager:
                        prompt_tool = self.tool_manager.get_tool("prompt_commands")
                except Exception as e:
                    self.logger.error(f"Error accessing prompt commands tool: {e}")

                if not prompt_tool or not hasattr(prompt_tool, 'get_system_prompt'):
                    self.show_status("Prompt commands tool not available.")
                    return

                system_prompt = prompt_tool.get_system_prompt(command)
                if not system_prompt:
                    self.show_status(f"Unknown command: /{command}")
                    return

                if not content_after.strip():
                    self.show_status("Please provide text after the command, e.g. /translate Hola…")
                    return

                context_prompt = system_prompt
                outgoing_text = content_after.strip()
        except Exception as e:
            self.logger.error(f"Slash command handling error: {e}")
            # Fallback to raw message
            context_prompt = ""
            outgoing_text = message

        # Add (possibly transformed) user text to chat
        user_message = AIMessage(role="user", content=outgoing_text)
        self.add_message_to_chat(user_message)

        # Send message to AI in a separate thread, passing the system prompt if any
        self.send_to_ai(outgoing_text, context=context_prompt)
    
    def send_to_ai(self, message: str, context: str = ""):
        """Send message to AI in a separate thread."""
        # Prepare UI for streaming (non-blocking input, send->cancel)
        self._set_streaming_ui(True)
        self.show_status("Streaming response...")
        
        # Stop any existing worker thread
        if hasattr(self, 'current_worker') and self.current_worker and self.current_worker.isRunning():
            self.logger.info("Stopping previous AI worker thread")
            self.current_worker.quit()
            self.current_worker.wait(1000)  # Wait up to 1 second for thread to finish
            
            if self.current_worker.isRunning():
                self.logger.warning("Previous AI worker thread did not stop gracefully")
                self.current_worker.terminate()
            
            # Disconnect any existing connections to avoid signal cross-talk
            try:
                self.current_worker.response_received.disconnect()
                self.current_worker.error_occurred.disconnect()
                self.current_worker.streaming_chunk.disconnect()
                self.current_worker.finished.disconnect()
            except TypeError:
                # Signal was not connected
                pass
        
        # Create and start worker thread
        self.current_worker = AIWorker(self.ai_manager, message, context=context)
        # Enable streaming mode
        self.current_worker.streaming = True
        self.current_worker.response_received.connect(self.on_ai_response)
        self.current_worker.error_occurred.connect(self.on_ai_error)
        self.current_worker.streaming_chunk.connect(self.on_streaming_chunk)
        # Use thread finished signal to know when streaming completes
        self.current_worker.finished.connect(self.on_streaming_finished)
        
        # Create a placeholder assistant message to stream into
        placeholder_message = AIMessage(role="assistant", content="")
        self.streaming_message_widget = self.add_message_to_chat(placeholder_message)
        
        # Start worker
        self.is_waiting_for_response = True
        self.current_worker.start()
    
    def on_ai_response(self, response: AIResponse):
        """Handle AI response."""
        self._set_streaming_ui(False)
        
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
        self._set_streaming_ui(False)
        
        self.show_status(f"Error: {error}")
        
        # Show error message in chat
        error_message = AIMessage(
            role="assistant", 
            content=f"Sorry, I encountered an error: {error}"
        )
        self.add_message_to_chat(error_message)
        
        # Focus input
        self.input_field.setFocus()
    
    def on_streaming_chunk(self, chunk: str):
        """Append a streamed chunk to the assistant message bubble."""
        try:
            if self.streaming_message_widget is None:
                # Create if not already created (safety)
                placeholder_message = AIMessage(role="assistant", content="")
                self.streaming_message_widget = self.add_message_to_chat(placeholder_message)
            # Append text to the message bubble
            if hasattr(self.streaming_message_widget, "append_text"):
                self.streaming_message_widget.append_text(chunk)
                # Keep view pinned to bottom while streaming
                self.scroll_to_bottom()
            else:
                # Fallback: recreate widget (should not happen after update)
                current_text = getattr(self.streaming_message_widget, "message", AIMessage("assistant", "")).content
                new_message = AIMessage(role="assistant", content=current_text + chunk)
                self.streaming_message_widget = self.add_message_to_chat(new_message)
        except Exception as e:
            self.logger.error(f"Error updating streaming chunk: {e}")
    
    def on_streaming_finished(self):
        """Finalize UI after streaming completes."""
        self._set_streaming_ui(False)
        if self._cancel_in_progress:
            self.show_status("Cancelled")
        else:
            self.show_status("Response received")
        # Clear reference so next stream creates a new bubble
        self.streaming_message_widget = None
        self._cancel_in_progress = False

    def cancel_stream(self):
        """Cancel the current streaming response."""
        if self.current_worker and self.current_worker.isRunning():
            self.show_status("Cancelling...")
            try:
                self._cancel_in_progress = True
                self.current_worker.request_cancel()
            except Exception as e:
                self.logger.error(f"Error requesting cancel: {e}")
            # Do not immediately reset UI; wait for finished signal
        else:
            self.logger.info("No active stream to cancel")
    
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
        # Set bubble width limits relative to viewport (min 40%, max 60% of width)
        try:
            vp_width = self.chat_scroll.viewport().width()
            min_target = int(max(180, vp_width * 0.4))
            max_target = int(max(260, vp_width * 0.6))
            message_widget.set_max_bubble_width(max_target)
            # Also enforce a sensible minimum width for long skinny paragraphs
            if hasattr(message_widget, 'set_bubble_width_limits'):
                message_widget.set_bubble_width_limits(min_target, max_target)
        except Exception:
            pass
        self.chat_layout.addWidget(message_widget)
        
        # Add stretch back at the end
        self.chat_layout.addStretch()
        
        # Scroll to bottom
        QtCore.QTimer.singleShot(100, self.scroll_to_bottom)
        return message_widget
    
    def scroll_to_bottom(self, force: bool = False):
        """Scroll chat to the bottom if pinned or forced."""
        scrollbar = self.chat_scroll.verticalScrollBar()
        if force or self._autoscroll_pinned:
            scrollbar.setValue(scrollbar.maximum())
            self._autoscroll_pinned = True
            self.scroll_bottom_button.hide()
    
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
        else:
            super().keyPressEvent(event)

    def closeEvent(self, event):
        """Handle close event."""
        # Stop any running worker
        if self.current_worker and self.current_worker.isRunning():
            try:
                self.current_worker.request_cancel()
            except Exception:
                pass
            self.current_worker.quit()
            self.current_worker.wait()
        
        super().closeEvent(event)

    def _set_streaming_ui(self, on: bool):
        """Toggle UI state for streaming mode.
        - Keep input enabled so user can type while streaming
        - Disable sending new messages via Enter while streaming
        - Change Send button to Cancel (and back)
        """
        self.is_waiting_for_response = on
        # Always keep input enabled per user request
        self.input_field.setEnabled(True)

        # Update Send button behavior
        try:
            self.send_button.clicked.disconnect(self.send_message)
        except TypeError:
            pass
        try:
            self.send_button.clicked.disconnect(self.cancel_stream)
        except TypeError:
            pass
        
        if on:
            self.send_button.setText("Cancel")
            self.send_button.clicked.connect(self.cancel_stream)
        else:
            self.send_button.setText("Send")
            self.send_button.clicked.connect(self.send_message)

    def on_scroll_value_changed(self):
        """Track whether user has scrolled up and toggle overlay button."""
        scrollbar = self.chat_scroll.verticalScrollBar()
        at_bottom = scrollbar.maximum() - scrollbar.value() <= 8
        self._autoscroll_pinned = at_bottom
        if at_bottom:
            self.scroll_bottom_button.hide()
        else:
            self.scroll_bottom_button.show()
            self._position_scroll_bottom_button()

    def _position_scroll_bottom_button(self):
        try:
            vp = self.chat_scroll.viewport()
            x = vp.width() - 36
            y = vp.height() - 36
            self.scroll_bottom_button.move(x, y)
        except Exception:
            pass

    def resizeEvent(self, event: QtGui.QResizeEvent):
        super().resizeEvent(event)
        self._position_scroll_bottom_button()
        # Update bubble widths for all messages when container resizes
        try:
            vp_width = self.chat_scroll.viewport().width()
            min_target = int(max(180, vp_width * 0.4))
            max_target = int(max(260, vp_width * 0.6))
            for i in range(self.chat_layout.count()):
                item = self.chat_layout.itemAt(i)
                w = item.widget()
                if isinstance(w, MessageWidget):
                    w.set_max_bubble_width(max_target)
                    if hasattr(w, 'set_bubble_width_limits'):
                        w.set_bubble_width_limits(min_target, max_target)
        except Exception:
            pass

    def eventFilter(self, source, event):
        """Intercept Enter in input to send or create newline."""
        if source is self.input_field and event.type() == QtCore.QEvent.KeyPress:
            if event.key() in (Qt.Key_Return, Qt.Key_Enter):
                if self.is_waiting_for_response:
                    # Ignore Enter while streaming to avoid accidental cancel
                    return True
                if event.modifiers() & Qt.ShiftModifier:
                    cursor = self.input_field.textCursor()
                    cursor.insertText("\n")
                    return True
                else:
                    self.send_message()
                    return True
        # When the viewport resizes, adjust bubbles
        if source is self.chat_scroll.viewport() and event.type() in (QtCore.QEvent.Resize, QtCore.QEvent.Show):
            try:
                vp_width = self.chat_scroll.viewport().width()
                min_target = int(max(180, vp_width * 0.4))
                max_target = int(max(260, vp_width * 0.6))
                for i in range(self.chat_layout.count()):
                    item = self.chat_layout.itemAt(i)
                    w = item.widget()
                    if isinstance(w, MessageWidget):
                        w.set_max_bubble_width(max_target)
                        if hasattr(w, 'set_bubble_width_limits'):
                            w.set_bubble_width_limits(min_target, max_target)
            except Exception:
                pass
        return super().eventFilter(source, event)

    def _update_input_height(self):
        """Auto-resize the input height with a 3–6 line clamp."""
        try:
            text = self.input_field.toPlainText()
            lines = text.count('\n') + 1
            max_lines = 6
            min_lines = 3
            lines = max(min_lines, min(max_lines, lines))
            fm = self.input_field.fontMetrics()
            height = int(lines * fm.lineSpacing() + 12)
            self.input_field.setFixedHeight(max(36, height))
        except Exception:
            pass
    
    # NOTE: Removed stray top-level duplicates accidentally introduced earlier.