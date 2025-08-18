"""AI Chat widget for Magic Tools."""

import logging
import asyncio
import time
from typing import Optional, List
from PyQt5 import QtWidgets, QtCore, QtGui
from PyQt5.QtCore import Qt, pyqtSignal, QThread, QTimer

from ..ai import AIManager
from ..ai.models import AIMessage, AIResponse
from ..config.settings import UISettings
from .style import StyleManager
from ..core.chat_storage import ChatStorageManager, Chat
from .chat_manager_widget import ChatManagerWidget


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

        # Optional badge overlay positioned relative to the bubble (top-right for user)
        self._badge_label = None
        if getattr(self.message, 'badge', None):
            try:
                self._badge_label = QtWidgets.QLabel(self.bubble)
                self._badge_label.setText(self._build_badge_html(self.message.badge))
                self._badge_label.setTextFormat(Qt.RichText)
                self._badge_label.setProperty("class", "chat-badge")
                self._badge_label.setAttribute(Qt.WA_TransparentForMouseEvents, True)
                self._badge_label.hide()  # will be positioned and shown in resizeEvent
            except Exception:
                self._badge_label = None

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
            # Nudge the copy button down a bit when a badge is present to avoid overlap
            if self._badge_label and self.message.role == "user":
                y += 14
            self._copy_button.move(x, y)
        # Position badge at top-right, slightly overlapping the user bubble
        if self._badge_label and self.message.role == "user":
            try:
                self._badge_label.adjustSize()
                br = self.bubble.rect()
                badge_w = self._badge_label.width()
                badge_h = self._badge_label.height()
                # Place fully within the bubble near the top-right corner
                # Small inset so it's visually attached but not clipped by rounded corner
                x = max(6, br.width() - badge_w - 10)
                y = max(4, 4)
                self._badge_label.move(x, y)
                self._badge_label.show()
            except Exception:
                pass

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

    @staticmethod
    def _build_badge_html(text: str) -> str:
        t = (text or "").strip()
        if not t:
            return ""
        return (
            "<span style=\""
            "display:inline-block;"
            "padding:1px 6px;"
            "font-size:9px;"
            "border-radius:8px;"
            "background:#2ecc71;"
            "color:white;"
            "border:1px solid rgba(0,0,0,0.08);"
            "box-shadow:0 1px 1px rgba(0,0,0,0.12);"
            "opacity:0.92;"
            "\">" + QtGui.QGuiApplication.translate("", t) + "</span>"
        )


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
    
    def __init__(self, ai_manager: AIManager, parent=None, tool_manager=None, config_manager=None):
        super().__init__(parent)
        
        self.logger = logging.getLogger(__name__)
        self.ai_manager = ai_manager
        self.tool_manager = tool_manager
        self.config_manager = config_manager
        self.ui_settings = None
        
        # Initialize chat storage
        self.chat_storage = None
        if config_manager:
            self.chat_storage = ChatStorageManager(config_manager)
        
        # Current chat state
        self.current_chat = None  # type: Optional[Chat]
        self.chat_modified = False  # Track if current chat has unsaved changes
        
        # Initialize style manager
        self.style_manager = StyleManager()
        
        # UI components
        self.chat_display = None
        self.input_field = None
        self.send_button = None
        self.status_label = None
        self.chat_manager_dialog = None
        
        # Chat state
        self.is_waiting_for_response = False
        self.current_worker = None
        self.streaming_message_widget = None
        self._cancel_in_progress = False
        self._autoscroll_pinned = True
        # Slash-command UX state
        self.selected_command = None  # type: Optional[str]
        self.command_popup = None
        self.suggestion_list = None
        self.command_badge = None
        self.command_badge_label = None
        self.command_badge_close = None
        
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
        header_layout = QtWidgets.QVBoxLayout()
        
        # Top row: Back button, title, AI status
        top_row = QtWidgets.QHBoxLayout()
        
        # Back button
        back_button = QtWidgets.QPushButton("← Back")
        back_button.setFixedSize(60, 30)
        back_button.clicked.connect(self.back_to_launcher.emit)
        back_button.setProperty("class", "chat-back-button")
        
        # Title and chat name
        title_container = QtWidgets.QVBoxLayout()
        title_container.setSpacing(2)
        
        title_label = QtWidgets.QLabel("AI Assistant")
        title_label.setAlignment(Qt.AlignCenter)
        title_label.setProperty("class", "chat-title")
        
        self.chat_name_label = QtWidgets.QLabel("New Chat")
        self.chat_name_label.setAlignment(Qt.AlignCenter)
        self.chat_name_label.setProperty("class", "chat-name-label")
        font = self.chat_name_label.font()
        font.setPointSize(font.pointSize() - 1)
        self.chat_name_label.setFont(font)
        
        title_container.addWidget(title_label)
        title_container.addWidget(self.chat_name_label)
        
        # AI status
        ai_status = "🟢 Connected" if self.ai_manager.is_available() else "🔴 Disconnected"
        self.ai_status_label = QtWidgets.QLabel(ai_status)
        self.ai_status_label.setAlignment(Qt.AlignRight)
        self.ai_status_label.setProperty("class", "chat-ai-status")
        
        top_row.addWidget(back_button)
        top_row.addLayout(title_container)
        top_row.addWidget(self.ai_status_label)
        
        # Chat management buttons (only if chat storage is available)
        if self.chat_storage:
            chat_controls = QtWidgets.QHBoxLayout()
            chat_controls.setSpacing(8)
            
            # New chat button
            self.new_chat_button = QtWidgets.QPushButton("New")
            self.new_chat_button.setFixedSize(50, 25)
            self.new_chat_button.clicked.connect(self.new_chat)
            self.new_chat_button.setProperty("class", "chat-control-button")
            self.new_chat_button.setToolTip("Create a new chat")
            
            # Save chat button
            self.save_chat_button = QtWidgets.QPushButton("Save")
            self.save_chat_button.setFixedSize(50, 25)
            self.save_chat_button.clicked.connect(self.save_current_chat)
            self.save_chat_button.setProperty("class", "chat-control-button")
            self.save_chat_button.setToolTip("Save current chat")
            
            # Load/Manage chats button
            self.manage_chats_button = QtWidgets.QPushButton("Chats")
            self.manage_chats_button.setFixedSize(50, 25)
            self.manage_chats_button.clicked.connect(self.show_chat_manager)
            self.manage_chats_button.setProperty("class", "chat-control-button")
            self.manage_chats_button.setToolTip("Manage saved chats")
            
            # Chat modified indicator
            self.modified_indicator = QtWidgets.QLabel("●")
            self.modified_indicator.setProperty("class", "chat-modified-indicator")
            self.modified_indicator.setFixedSize(12, 12)
            self.modified_indicator.setAlignment(Qt.AlignCenter)
            self.modified_indicator.setToolTip("Chat has unsaved changes")
            self.modified_indicator.hide()
            
            chat_controls.addStretch()
            chat_controls.addWidget(self.new_chat_button)
            chat_controls.addWidget(self.save_chat_button)
            chat_controls.addWidget(self.manage_chats_button)
            chat_controls.addWidget(self.modified_indicator)
            chat_controls.addStretch()
            
            header_layout.addLayout(top_row)
            header_layout.addLayout(chat_controls)
        else:
            header_layout.addLayout(top_row)
        
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
        
        # Input container to host badge + input
        self.input_container = QtWidgets.QFrame()
        self.input_container.setFrameShape(QtWidgets.QFrame.NoFrame)
        container_layout = QtWidgets.QHBoxLayout(self.input_container)
        container_layout.setContentsMargins(0, 0, 0, 0)
        container_layout.setSpacing(6)

        # Command badge (hidden until a command is selected)
        self.command_badge = QtWidgets.QFrame()
        self.command_badge.setFrameShape(QtWidgets.QFrame.NoFrame)
        self.command_badge.setProperty("class", "chat-command-badge")
        self.command_badge.setFixedHeight(28)  # Set fixed height for consistent appearance
        badge_layout = QtWidgets.QHBoxLayout(self.command_badge)
        badge_layout.setContentsMargins(8, 4, 6, 4)
        badge_layout.setSpacing(4)
        
        self.command_badge_label = QtWidgets.QLabel("")
        self.command_badge_label.setProperty("class", "chat-command-badge-label")
        self.command_badge_label.setAlignment(Qt.AlignCenter)
        
        self.command_badge_close = QtWidgets.QToolButton()
        self.command_badge_close.setText("×")
        self.command_badge_close.setCursor(Qt.PointingHandCursor)
        self.command_badge_close.setProperty("class", "chat-command-badge-close")
        self.command_badge_close.setFixedSize(16, 16)
        
        badge_layout.addWidget(self.command_badge_label)
        badge_layout.addWidget(self.command_badge_close)
        self.command_badge.hide()

        # Input field (multi-line)
        self.input_field = QtWidgets.QTextEdit()
        self.input_field.setAcceptRichText(False)
        self.input_field.setPlaceholderText("Ask me anything… (Enter to send, Shift+Enter for newline)")
        # Default to 3 lines height
        fm = self.input_field.fontMetrics()
        default_h = int(3 * fm.lineSpacing() + 12)
        self.input_field.setFixedHeight(max(36, default_h))
        self.input_field.setProperty("class", "chat-input")
        self.input_field.textChanged.connect(self._on_input_text_changed)
        self.input_field.textChanged.connect(self._update_input_height)
        self.input_field.installEventFilter(self)

        container_layout.addWidget(self.command_badge, 0)
        container_layout.addWidget(self.input_field, 1)
        
        # Send button
        self.send_button = QtWidgets.QPushButton("Send")
        self.send_button.setFixedSize(60, 35)
        self.send_button.clicked.connect(self.send_message)
        self.send_button.setProperty("class", "chat-send-button")
        
        input_layout.addWidget(self.input_container, 1)
        input_layout.addWidget(self.send_button, 0)
        
        self.main_layout.addLayout(input_layout)

        # Build the non-blocking command suggestion popup (hidden by default)
        self._build_command_popup()

        # Badge clear handler
        self.command_badge_close.clicked.connect(self.clear_selected_command)
    
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
        # Get the current theme from ui_settings if available
        current_theme = self.ui_settings.theme if self.ui_settings else "dark"
        self.style_manager.set_theme(current_theme)
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

        # Command badge handling: if a command was explicitly selected, apply it; otherwise treat as plain text
        context_prompt = ""
        outgoing_text = message
        badge = ""
        try:
            if self.selected_command:
                # Obtain PromptCommands tool if available
                prompt_tool = None
                try:
                    if self.tool_manager:
                        prompt_tool = self.tool_manager.get_tool("prompt_commands")
                except Exception as e:
                    self.logger.error(f"Error accessing prompt commands tool: {e}")

                if not prompt_tool or not hasattr(prompt_tool, 'get_system_prompt'):
                    # Fallback: send as plain text
                    self.show_status("Prompt commands tool not available. Sending as plain text.")
                else:
                    system_prompt = prompt_tool.get_system_prompt(self.selected_command)
                    if not system_prompt:
                        # Unknown command; clear and send as plain text
                        self.clear_selected_command()
                    else:
                        context_prompt = system_prompt
                        badge = f"/{self.selected_command}"
        except Exception as e:
            self.logger.error(f"Command badge handling error: {e}")

        # Add (possibly transformed) user text to chat/UI and history
        user_message = AIMessage(role="user", content=outgoing_text, badge=badge, timestamp=time.time())
        self.add_message_to_chat(user_message)
        try:
            # Ensure the AI conversation history includes the just-sent user message
            if not self.ai_manager.conversation_history or \
               self.ai_manager.conversation_history[-1].role != "user" or \
               self.ai_manager.conversation_history[-1].content != outgoing_text:
                self.ai_manager.conversation_history.append(user_message)
        except Exception:
            pass

        # Ensure a chat exists; create on first user message (not before)
        if self.chat_storage:
            try:
                needs_creation = (
                    self.current_chat is None or
                    not getattr(self.current_chat.metadata, "id", None)
                )
                if needs_creation:
                    # Preserve any preselected name (from manager) if available
                    desired_name = None
                    try:
                        if self.current_chat and getattr(self.current_chat, "metadata", None):
                            desired_name = self.current_chat.metadata.name
                        if (not desired_name) and hasattr(self, "chat_name_label"):
                            label_text = self.chat_name_label.text().strip()
                            if label_text and label_text.lower() != "new chat":
                                desired_name = label_text
                    except Exception:
                        pass
                    created = self.chat_storage.create_chat(name=desired_name, persist=False)
                    self.current_chat = created
                    # Update UI name
                    self.chat_name_label.setText(self.current_chat.metadata.name)
                    self._update_modified_indicator()
            except Exception as e:
                self.logger.error(f"Failed to create chat on first message: {e}")

        # Save after sending the user message (always)
        try:
            self.save_current_chat()
        except Exception as e:
            self.logger.error(f"Auto-save after user send failed: {e}")

        # Send message to AI in a separate thread, passing the system prompt if any
        self.send_to_ai(outgoing_text, context=context_prompt)

        # Clear command selection after send
        self.clear_selected_command()
    
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
        placeholder_message = AIMessage(role="assistant", content="", timestamp=time.time())
        self.streaming_message_widget = self.add_message_to_chat(placeholder_message)
        
        # Start worker
        self.is_waiting_for_response = True
        self.current_worker.start()
    
    def on_ai_response(self, response: AIResponse):
        """Handle AI response."""
        self._set_streaming_ui(False)
        
        if response.success:
            # Add AI response to chat
            ai_message = AIMessage(role="assistant", content=response.content, timestamp=time.time())
            self.add_message_to_chat(ai_message)
            
            # Update status
            tokens_info = f"({response.tokens_used} tokens)" if response.tokens_used else ""
            self.show_status(f"Response received {tokens_info}")

            # Save only if there is content
            try:
                if response.content and response.content.strip():
                    self.save_current_chat()
            except Exception as e:
                self.logger.error(f"Auto-save after assistant response failed: {e}")
        else:
            self.show_status(f"Error: {response.error}")
            
            # Show error message in chat
            error_message = AIMessage(
                role="assistant", 
                content=f"Sorry, I encountered an error: {response.error}",
                timestamp=time.time()
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
            content=f"Sorry, I encountered an error: {error}",
            timestamp=time.time()
        )
        self.add_message_to_chat(error_message)
        
        # Focus input
        self.input_field.setFocus()
    
    def on_streaming_chunk(self, chunk: str):
        """Append a streamed chunk to the assistant message bubble."""
        try:
            if self.streaming_message_widget is None:
                # Create if not already created (safety)
                placeholder_message = AIMessage(role="assistant", content="", timestamp=time.time())
                self.streaming_message_widget = self.add_message_to_chat(placeholder_message)
            # Append text to the message bubble
            if hasattr(self.streaming_message_widget, "append_text"):
                self.streaming_message_widget.append_text(chunk)
                # Keep view pinned to bottom while streaming
                self.scroll_to_bottom()
            else:
                # Fallback: recreate widget (should not happen after update)
                current_text = getattr(self.streaming_message_widget, "message", AIMessage("assistant", "")).content
                new_message = AIMessage(role="assistant", content=current_text + chunk, timestamp=time.time())
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

        # Save only if the last assistant message has content
        try:
            history = self.ai_manager.get_conversation_history()
            if history:
                last = history[-1]
                if last.role == "assistant" and last.content and last.content.strip():
                    self.save_current_chat()
        except Exception as e:
            self.logger.error(f"Auto-save after streaming finished failed: {e}")

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
        # Set timestamp if not already set
        if message.timestamp == 0.0:
            message.timestamp = time.time()
        
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
        
        # Mark chat as modified (except for welcome message)
        if message.content != """👋 Welcome to Magic Tools AI Assistant!

I'm here to help you with:
• Answering questions
• Providing information
• Assisting with tasks
• General conversation

How can I help you today?""":
            self._mark_chat_modified()
        
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
    
    def clear_chat(self, skip_confirmation=False):
        """Clear the chat history."""
        # Check for unsaved changes if not skipping confirmation
        if not skip_confirmation and self.chat_modified and self.current_chat:
            reply = QtWidgets.QMessageBox.question(
                self, "Unsaved Changes",
                "The current chat has unsaved changes. Do you want to save before clearing?",
                QtWidgets.QMessageBox.Save | QtWidgets.QMessageBox.Discard | QtWidgets.QMessageBox.Cancel
            )
            
            if reply == QtWidgets.QMessageBox.Cancel:
                return
            elif reply == QtWidgets.QMessageBox.Save:
                if not self.save_current_chat():
                    return  # Save failed, don't proceed
        
        # Clear widgets
        for i in reversed(range(self.chat_layout.count())):
            item = self.chat_layout.takeAt(i)
            if item.widget():
                item.widget().deleteLater()
        
        # Clear AI conversation history
        self.ai_manager.clear_conversation()
        
        # Reset chat state
        if not skip_confirmation:  # Only reset when manually clearing, not when loading
            self.current_chat = None
            self.chat_modified = False
            self.chat_name_label.setText("New Chat")
            self._update_modified_indicator()
        
        # Add stretch back
        self.chat_layout.addStretch()
        
        # Show welcome message again
        self.show_welcome_message()
        
        if not skip_confirmation:
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
    
    # Chat Management Methods
    
    def new_chat(self):
        """Create a new chat conversation."""
        if not self.chat_storage:
            return
        
        # Check if current chat has unsaved changes
        if self.chat_modified and self.current_chat:
            reply = QtWidgets.QMessageBox.question(
                self, "Unsaved Changes",
                "The current chat has unsaved changes. Do you want to save before creating a new chat?",
                QtWidgets.QMessageBox.Save | QtWidgets.QMessageBox.Discard | QtWidgets.QMessageBox.Cancel
            )
            
            if reply == QtWidgets.QMessageBox.Cancel:
                return
            elif reply == QtWidgets.QMessageBox.Save:
                if not self.save_current_chat():
                    return  # Save failed, don't proceed
        
        # Start a fresh UI state without creating/persisting any chat yet.
        # Actual chat creation will happen on the first user message.
        try:
            self.clear_chat(skip_confirmation=True)
            self.current_chat = None
            self.chat_name_label.setText("New Chat")
            self._update_modified_indicator()
            self.show_status("New chat started")
        except Exception as e:
            self.logger.error(f"Failed to start new chat: {e}")
            QtWidgets.QMessageBox.warning(self, "Error", f"Failed to start new chat: {str(e)}")
    
    def save_current_chat(self) -> bool:
        """Save the current chat conversation."""
        if not self.chat_storage or not self.current_chat:
            return False
        
        try:
            # Update current chat with messages from UI
            self.current_chat.messages = self._get_current_messages()
            
            # Save to storage
            if self.chat_storage.save_chat(self.current_chat):
                self.chat_modified = False
                self._update_modified_indicator()
                self.show_status(f"Chat '{self.current_chat.metadata.name}' saved")
                return True
            else:
                QtWidgets.QMessageBox.warning(self, "Error", "Failed to save chat")
                return False
                
        except Exception as e:
            self.logger.error(f"Failed to save chat: {e}")
            QtWidgets.QMessageBox.warning(self, "Error", f"Failed to save chat: {str(e)}")
            return False
    
    def show_chat_manager(self):
        """Show the chat management dialog."""
        if not self.chat_storage:
            return
        
        try:
            if not self.chat_manager_dialog:
                self.chat_manager_dialog = ChatManagerWidget(self.chat_storage, self)
                self.chat_manager_dialog.chat_selected.connect(self.load_chat)
                self.chat_manager_dialog.new_chat_requested.connect(self.new_chat)
            
            # Refresh the dialog and show it
            self.chat_manager_dialog.refresh_chat_list()
            self.chat_manager_dialog.exec_()
            
        except Exception as e:
            self.logger.error(f"Failed to show chat manager: {e}")
            QtWidgets.QMessageBox.warning(self, "Error", f"Failed to open chat manager: {str(e)}")
    
    def load_chat(self, chat: Chat):
        """Load a chat conversation into the UI."""
        try:
            # Check if current chat has unsaved changes
            if self.chat_modified and self.current_chat:
                reply = QtWidgets.QMessageBox.question(
                    self, "Unsaved Changes",
                    "The current chat has unsaved changes. Do you want to save before loading another chat?",
                    QtWidgets.QMessageBox.Save | QtWidgets.QMessageBox.Discard | QtWidgets.QMessageBox.Cancel
                )
                
                if reply == QtWidgets.QMessageBox.Cancel:
                    return
                elif reply == QtWidgets.QMessageBox.Save:
                    if not self.save_current_chat():
                        return  # Save failed, don't proceed
            
            # Clear current chat display
            self.clear_chat(skip_confirmation=True)
            
            # Set new current chat
            self.current_chat = chat
            self.chat_modified = False
            
            # Update UI
            self.chat_name_label.setText(chat.metadata.name)
            self._update_modified_indicator()
            
            # Load messages into AI manager and UI
            self.ai_manager.clear_conversation()
            
            for message in chat.messages:
                # Add to AI manager conversation history
                self.ai_manager.conversation_history.append(message)
                # Add to UI display
                self.add_message_to_chat(message)
            
            self.show_status(f"Chat '{chat.metadata.name}' loaded")
            
        except Exception as e:
            self.logger.error(f"Failed to load chat: {e}")
            QtWidgets.QMessageBox.warning(self, "Error", f"Failed to load chat: {str(e)}")
    
    def _get_current_messages(self) -> List[AIMessage]:
        """Get current messages from the AI manager."""
        return list(self.ai_manager.conversation_history)
    
    def _update_modified_indicator(self):
        """Update the modified indicator visibility."""
        if hasattr(self, 'modified_indicator'):
            if self.chat_modified:
                self.modified_indicator.show()
            else:
                self.modified_indicator.hide()
    
    def _mark_chat_modified(self):
        """Mark the current chat as modified."""
        if self.current_chat:
            self.chat_modified = True
            self._update_modified_indicator()
    
    def keyPressEvent(self, event):
        """Handle key press events."""
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
        # Reposition command popup if visible
        try:
            if self.command_popup and self.command_popup.isVisible():
                self._position_command_popup()
        except Exception:
            pass

    def eventFilter(self, source, event):
        """Intercept Enter in input to send or create newline."""
        if source is self.input_field and event.type() == QtCore.QEvent.KeyPress:
            # Handle suggestion navigation without stealing focus
            if self.command_popup and self.command_popup.isVisible():
                if event.key() in (Qt.Key_Up, Qt.Key_Down):
                    self._move_suggestion_selection(-1 if event.key() == Qt.Key_Up else 1)
                    return True
                if event.key() in (Qt.Key_Tab, Qt.Key_Return, Qt.Key_Enter):
                    if self._accept_current_suggestion():
                        return True
                if event.key() == Qt.Key_Escape:
                    self._hide_command_popup()
                    return True
            # Normal Enter handling
            if event.key() in (Qt.Key_Return, Qt.Key_Enter):
                if self.is_waiting_for_response:
                    return True
                if event.modifiers() & Qt.ShiftModifier:
                    cursor = self.input_field.textCursor()
                    cursor.insertText("\n")
                    return True
                else:
                    self.send_message()
                    return True
            # If Backspace at start and no text, remove badge
            if event.key() == Qt.Key_Backspace:
                cursor = self.input_field.textCursor()
                if not cursor.hasSelection() and cursor.position() == 0 and self.selected_command:
                    self.clear_selected_command()
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

    # -----------------------------
    # Slash Command Suggestion UX
    # -----------------------------
    def _build_command_popup(self):
        try:
            # Create popup as child of main widget for proper positioning
            self.command_popup = QtWidgets.QFrame(self)
            self.command_popup.setFrameShape(QtWidgets.QFrame.NoFrame)
            self.command_popup.setProperty("class", "chat-command-popup")
            
            # Set window flags to make it a floating popup that doesn't steal focus
            self.command_popup.setWindowFlags(Qt.Tool | Qt.FramelessWindowHint | Qt.WindowStaysOnTopHint)
            self.command_popup.setAttribute(Qt.WA_ShowWithoutActivating, True)
            
            popup_layout = QtWidgets.QVBoxLayout(self.command_popup)
            popup_layout.setContentsMargins(2, 2, 2, 2)
            popup_layout.setSpacing(0)
            
            self.suggestion_list = QtWidgets.QListWidget(self.command_popup)
            self.suggestion_list.setProperty("class", "chat-command-list")
            self.suggestion_list.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
            self.suggestion_list.setVerticalScrollBarPolicy(Qt.ScrollBarAsNeeded)
            self.suggestion_list.setSelectionMode(QtWidgets.QAbstractItemView.SingleSelection)
            self.suggestion_list.setFocusPolicy(Qt.NoFocus)
            
            popup_layout.addWidget(self.suggestion_list)
            self.command_popup.hide()

            # Mouse selection
            self.suggestion_list.itemClicked.connect(lambda _: self._accept_current_suggestion())
        except Exception as e:
            self.logger.error(f"Failed to build command popup: {e}")

    def _position_command_popup(self):
        try:
            if not self.command_popup:
                return
            
            # Position directly under the input field using global coordinates
            input_g = self.input_field.geometry()
            
            # Map input field position to global coordinates
            global_pos = self.input_field.mapToGlobal(QtCore.QPoint(0, 0))
            
            x = global_pos.x()
            y = global_pos.y() + input_g.height() + 4  # Position below the input field
            width = input_g.width()  # Match input field width
            
            self.command_popup.setFixedWidth(width)
            
            # Calculate height based on number of items (max 8 visible items)
            item_count = self.suggestion_list.count()
            if item_count > 0:
                row_height = max(28, self.suggestion_list.sizeHintForRow(0) or 28)
                visible_rows = min(8, item_count)
                popup_height = visible_rows * row_height + 8  # +8 for borders and margins
                self.command_popup.setFixedHeight(popup_height)
            else:
                self.command_popup.setFixedHeight(50)
            
            self.command_popup.move(x, y)
        except Exception as e:
            self.logger.error(f"Error positioning command popup: {e}")

    def _show_command_popup(self, items):
        try:
            if not self.command_popup:
                return
            self.suggestion_list.clear()
            for name, desc in items:
                it = QtWidgets.QListWidgetItem(f"/{name}  —  {desc}")
                it.setData(Qt.UserRole, name)
                self.suggestion_list.addItem(it)
            if self.suggestion_list.count() > 0:
                self.suggestion_list.setCurrentRow(0)
            
            # Apply current theme styles to the popup
            self.apply_styles()
            
            self._position_command_popup()
            self.command_popup.show()
        except Exception as e:
            self.logger.error(f"Failed to show command popup: {e}")

    def _hide_command_popup(self):
        try:
            if self.command_popup:
                self.command_popup.hide()
        except Exception:
            pass

    def _move_suggestion_selection(self, delta: int):
        try:
            if not (self.suggestion_list and self.suggestion_list.count()):
                return
            row = self.suggestion_list.currentRow()
            row = (row + delta) % self.suggestion_list.count()
            self.suggestion_list.setCurrentRow(row)
        except Exception:
            pass

    def _accept_current_suggestion(self) -> bool:
        try:
            if not (self.command_popup and self.command_popup.isVisible() and self.suggestion_list):
                return False
            item = self.suggestion_list.currentItem()
            if not item:
                return False
            name = item.data(Qt.UserRole)
            if not name:
                return False
            # Set command selection and update input
            self._set_selected_command(name)
            self._hide_command_popup()
            return True
        except Exception:
            return False

    def _set_selected_command(self, name: str):
        try:
            normalized = (name or "").strip()
            if not normalized:
                return
            self.selected_command = normalized
            # Update badge
            if self.command_badge_label:
                self.command_badge_label.setText(f"/{normalized}")
            if self.command_badge:
                self.command_badge.show()
                # Ensure proper sizing
                self.command_badge.adjustSize()
            # Remove any leading '/token' + optional space from the input text
            text = self.input_field.toPlainText()
            if text.startswith('/'):
                import re as _re
                new_text = _re.sub(r"^/\S+\s*", "", text, count=1)
                self.input_field.blockSignals(True)
                self.input_field.setPlainText(new_text)
                self.input_field.blockSignals(False)
                # Move cursor to end
                cursor = self.input_field.textCursor()
                cursor.movePosition(QtGui.QTextCursor.End)
                self.input_field.setTextCursor(cursor)
            # Focus back to input
            self.input_field.setFocus()
        except Exception as e:
            self.logger.error(f"Failed to set selected command: {e}")

    def clear_selected_command(self):
        try:
            self.selected_command = None
            if self.command_badge:
                self.command_badge.hide()
        except Exception:
            pass

    def _on_input_text_changed(self):
        try:
            # Keep height updated (already connected, but ensure smoothness)
            # Manage suggestion popup only when no command is already set
            if self.selected_command:
                self._hide_command_popup()
                return

            raw = self.input_field.toPlainText()
            if not raw:
                self._hide_command_popup()
                return

            # Consider only first line and first token
            first_line = raw.split('\n', 1)[0]
            if not first_line.startswith('/'):
                self._hide_command_popup()
                return

            # Extract token after '/'
            import re as _re
            m = _re.match(r"/(\S+)", first_line)
            token = m.group(1) if m else ""
            # If there's a space in first token, user ended token without selection -> plain text
            if ' ' in first_line:
                # If user typed a space after /something and didn't select, hide suggestions
                if _re.match(r"^/\S+\s", first_line):
                    self._hide_command_popup()
                    return

            # Build suggestions based on token prefix
            prompt_tool = None
            try:
                if self.tool_manager:
                    prompt_tool = self.tool_manager.get_tool("prompt_commands")
            except Exception as e:
                self.logger.error(f"Error accessing prompt commands tool: {e}")
                prompt_tool = None

            if not prompt_tool or not hasattr(prompt_tool, 'list_commands'):
                self._hide_command_popup()
                return

            all_cmds = getattr(prompt_tool, 'list_commands')() or []
            # Get descriptions for display
            items = []
            for name in all_cmds:
                if not token or name.startswith(token.lower()):
                    desc = getattr(prompt_tool, 'get_description')(name) or name
                    items.append((name, desc))
            items = sorted(items, key=lambda x: x[0])[:10]

            if items:
                self._show_command_popup(items)
            else:
                self._hide_command_popup()
        except Exception as e:
            self.logger.error(f"Input change handler error: {e}")
    
    # NOTE: Removed stray top-level duplicates accidentally introduced earlier.