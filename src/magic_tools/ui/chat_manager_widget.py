"""Chat management widget for Magic Tools."""

import logging
from typing import Optional, List
from PyQt5 import QtWidgets, QtCore, QtGui
from PyQt5.QtCore import Qt, pyqtSignal
from datetime import datetime

from ..core.chat_storage import ChatStorageManager, ChatMetadata, Chat


class ChatListItem(QtWidgets.QListWidgetItem):
    """Custom list item for chat entries."""
    
    def __init__(self, metadata: ChatMetadata):
        super().__init__()
        self.metadata = metadata
        self.update_display()
    
    def update_display(self):
        """Update the display text for this item."""
        updated_time = datetime.fromtimestamp(self.metadata.updated_at)
        time_str = updated_time.strftime("%Y-%m-%d %H:%M")
        
        display_text = f"{self.metadata.name}\n"
        display_text += f"Messages: {self.metadata.message_count} • {time_str}"
        
        if self.metadata.last_message_preview:
            display_text += f"\n{self.metadata.last_message_preview}"
        
        self.setText(display_text)
        self.setToolTip(f"Chat ID: {self.metadata.id}\nCreated: {datetime.fromtimestamp(self.metadata.created_at).strftime('%Y-%m-%d %H:%M')}")


class ChatManagerWidget(QtWidgets.QDialog):
    """Widget for managing chat conversations."""
    
    chat_selected = pyqtSignal(Chat)  # Emitted when a chat is selected to load
    new_chat_requested = pyqtSignal()  # Emitted when new chat is requested
    
    def __init__(self, chat_storage: ChatStorageManager, parent=None):
        super().__init__(parent)
        self.chat_storage = chat_storage
        self.logger = logging.getLogger(__name__)
        
        self.current_chat_id = None  # Currently selected chat ID
        
        self.setup_ui()
        self.refresh_chat_list()
        
        # Connect signals
        self.setup_signals()
    
    def setup_ui(self):
        """Setup the chat manager UI."""
        self.setWindowTitle("Chat Manager")
        self.setModal(True)
        self.resize(600, 500)
        
        # Main layout
        layout = QtWidgets.QVBoxLayout(self)
        layout.setSpacing(10)
        
        # Header
        header_layout = QtWidgets.QHBoxLayout()
        
        title_label = QtWidgets.QLabel("Manage Chats")
        title_label.setProperty("class", "chat-manager-title")
        font = title_label.font()
        font.setPointSize(16)
        font.setBold(True)
        title_label.setFont(font)
        
        header_layout.addWidget(title_label)
        header_layout.addStretch()
        
        # Statistics
        self.stats_label = QtWidgets.QLabel("")
        self.stats_label.setProperty("class", "chat-manager-stats")
        header_layout.addWidget(self.stats_label)
        
        layout.addLayout(header_layout)
        
        # Search/filter
        search_layout = QtWidgets.QHBoxLayout()
        search_label = QtWidgets.QLabel("Search:")
        self.search_field = QtWidgets.QLineEdit()
        self.search_field.setPlaceholderText("Search chats by name or content...")
        self.search_field.textChanged.connect(self.filter_chats)
        
        search_layout.addWidget(search_label)
        search_layout.addWidget(self.search_field)
        layout.addLayout(search_layout)
        
        # Chat list
        self.chat_list = QtWidgets.QListWidget()
        self.chat_list.setSelectionMode(QtWidgets.QAbstractItemView.SingleSelection)
        self.chat_list.itemDoubleClicked.connect(self.load_selected_chat)
        self.chat_list.itemSelectionChanged.connect(self.on_selection_changed)
        
        # Custom context menu
        self.chat_list.setContextMenuPolicy(Qt.CustomContextMenu)
        self.chat_list.customContextMenuRequested.connect(self.show_context_menu)
        
        layout.addWidget(self.chat_list)
        
        # Action buttons
        button_layout = QtWidgets.QHBoxLayout()
        
        self.new_button = QtWidgets.QPushButton("New Chat")
        self.new_button.clicked.connect(self.create_new_chat)
        
        self.load_button = QtWidgets.QPushButton("Load Selected")
        self.load_button.clicked.connect(self.load_selected_chat)
        self.load_button.setEnabled(False)
        
        self.rename_button = QtWidgets.QPushButton("Rename")
        self.rename_button.clicked.connect(self.rename_selected_chat)
        self.rename_button.setEnabled(False)
        
        self.delete_button = QtWidgets.QPushButton("Delete")
        self.delete_button.clicked.connect(self.delete_selected_chat)
        self.delete_button.setEnabled(False)
        self.delete_button.setProperty("class", "danger-button")
        
        button_layout.addWidget(self.new_button)
        button_layout.addStretch()
        button_layout.addWidget(self.load_button)
        button_layout.addWidget(self.rename_button)
        button_layout.addWidget(self.delete_button)
        
        layout.addLayout(button_layout)
        
        # Close button
        close_layout = QtWidgets.QHBoxLayout()
        close_layout.addStretch()
        
        self.close_button = QtWidgets.QPushButton("Close")
        self.close_button.clicked.connect(self.close)
        close_layout.addWidget(self.close_button)
        
        layout.addLayout(close_layout)
        
        # Update stats
        self.update_stats()
    
    def setup_signals(self):
        """Setup signal connections."""
        pass
    
    def refresh_chat_list(self):
        """Refresh the chat list from storage."""
        try:
            self.chat_list.clear()
            chats = self.chat_storage.list_chats()
            
            for metadata in chats:
                item = ChatListItem(metadata)
                self.chat_list.addItem(item)
            
            self.update_stats()
            
        except Exception as e:
            self.logger.error(f"Failed to refresh chat list: {e}")
            QtWidgets.QMessageBox.warning(self, "Error", f"Failed to load chats: {str(e)}")
    
    def filter_chats(self):
        """Filter chats based on search text."""
        search_text = self.search_field.text().lower()
        
        for i in range(self.chat_list.count()):
            item = self.chat_list.item(i)
            if isinstance(item, ChatListItem):
                # Search in name and preview
                visible = (
                    search_text in item.metadata.name.lower() or
                    search_text in item.metadata.last_message_preview.lower()
                )
                item.setHidden(not visible)
    
    def on_selection_changed(self):
        """Handle selection change in chat list."""
        current_item = self.chat_list.currentItem()
        has_selection = current_item is not None and not current_item.isHidden()
        
        self.load_button.setEnabled(has_selection)
        self.rename_button.setEnabled(has_selection)
        self.delete_button.setEnabled(has_selection)
        
        if has_selection and isinstance(current_item, ChatListItem):
            self.current_chat_id = current_item.metadata.id
        else:
            self.current_chat_id = None
    
    def create_new_chat(self):
        """Create a new chat (keep in memory until first message)."""
        try:
            name, ok = QtWidgets.QInputDialog.getText(
                self, "New Chat", "Enter chat name:", 
                text=f"Chat {datetime.now().strftime('%Y-%m-%d %H:%M')}"
            )
            
            if ok and name.strip():
                # Do not create/persist here. Just instruct the main widget to start a new chat.
                reply = QtWidgets.QMessageBox.question(
                    self, "Start New Chat", 
                    f"Start a new chat named '{name}' now? It will be saved after you send the first message.",
                    QtWidgets.QMessageBox.Yes | QtWidgets.QMessageBox.No
                )
                if reply == QtWidgets.QMessageBox.Yes:
                    # Emit a temporary in-memory Chat object so the main widget can set the label.
                    # It won't be persisted until the first message is sent.
                    temp_chat = Chat(
                        metadata=ChatMetadata(
                            id="",  # placeholder; real id will be assigned on create/save
                            name=name.strip(),
                            created_at=0.0,
                            updated_at=0.0,
                            message_count=0,
                            last_message_preview="",
                        ),
                        messages=[]
                    )
                    self.chat_selected.emit(temp_chat)
                    self.close()
                    
        except Exception as e:
            self.logger.error(f"Failed to create new chat: {e}")
            QtWidgets.QMessageBox.warning(self, "Error", f"Failed to create chat: {str(e)}")
    
    def load_selected_chat(self):
        """Load the selected chat."""
        if not self.current_chat_id:
            return
        
        try:
            chat = self.chat_storage.load_chat(self.current_chat_id)
            if chat:
                self.chat_selected.emit(chat)
                self.close()
            else:
                QtWidgets.QMessageBox.warning(self, "Error", "Failed to load selected chat.")
                
        except Exception as e:
            self.logger.error(f"Failed to load chat: {e}")
            QtWidgets.QMessageBox.warning(self, "Error", f"Failed to load chat: {str(e)}")
    
    def rename_selected_chat(self):
        """Rename the selected chat."""
        if not self.current_chat_id:
            return
        
        try:
            current_item = self.chat_list.currentItem()
            if not isinstance(current_item, ChatListItem):
                return
            
            current_name = current_item.metadata.name
            name, ok = QtWidgets.QInputDialog.getText(
                self, "Rename Chat", "Enter new name:", text=current_name
            )
            
            if ok and name.strip() and name.strip() != current_name:
                if self.chat_storage.rename_chat(self.current_chat_id, name.strip()):
                    self.refresh_chat_list()
                    QtWidgets.QMessageBox.information(self, "Success", "Chat renamed successfully.")
                else:
                    QtWidgets.QMessageBox.warning(self, "Error", "Failed to rename chat.")
                    
        except Exception as e:
            self.logger.error(f"Failed to rename chat: {e}")
            QtWidgets.QMessageBox.warning(self, "Error", f"Failed to rename chat: {str(e)}")
    
    def delete_selected_chat(self):
        """Delete the selected chat."""
        if not self.current_chat_id:
            return
        
        try:
            current_item = self.chat_list.currentItem()
            if not isinstance(current_item, ChatListItem):
                return
            
            chat_name = current_item.metadata.name
            reply = QtWidgets.QMessageBox.question(
                self, "Delete Chat", 
                f"Are you sure you want to delete the chat '{chat_name}'?\n\nThis action cannot be undone.",
                QtWidgets.QMessageBox.Yes | QtWidgets.QMessageBox.No,
                QtWidgets.QMessageBox.No
            )
            
            if reply == QtWidgets.QMessageBox.Yes:
                if self.chat_storage.delete_chat(self.current_chat_id):
                    self.refresh_chat_list()
                    QtWidgets.QMessageBox.information(self, "Success", "Chat deleted successfully.")
                else:
                    QtWidgets.QMessageBox.warning(self, "Error", "Failed to delete chat.")
                    
        except Exception as e:
            self.logger.error(f"Failed to delete chat: {e}")
            QtWidgets.QMessageBox.warning(self, "Error", f"Failed to delete chat: {str(e)}")
    
    def show_context_menu(self, position):
        """Show context menu for chat list."""
        item = self.chat_list.itemAt(position)
        if not isinstance(item, ChatListItem):
            return
        
        menu = QtWidgets.QMenu(self)
        
        load_action = menu.addAction("Load Chat")
        load_action.triggered.connect(self.load_selected_chat)
        
        menu.addSeparator()
        
        rename_action = menu.addAction("Rename")
        rename_action.triggered.connect(self.rename_selected_chat)
        
        delete_action = menu.addAction("Delete")
        delete_action.triggered.connect(self.delete_selected_chat)
        
        menu.exec_(self.chat_list.mapToGlobal(position))
    
    def update_stats(self):
        """Update statistics display."""
        try:
            stats = self.chat_storage.get_storage_stats()
            total_chats = stats.get("total_chats", 0)
            storage_size = stats.get("storage_size_bytes", 0)
            
            # Convert bytes to human readable format
            if storage_size < 1024:
                size_str = f"{storage_size} B"
            elif storage_size < 1024 * 1024:
                size_str = f"{storage_size / 1024:.1f} KB"
            else:
                size_str = f"{storage_size / (1024 * 1024):.1f} MB"
            
            self.stats_label.setText(f"{total_chats} chats • {size_str}")
            
        except Exception as e:
            self.logger.error(f"Failed to update stats: {e}")
            self.stats_label.setText("Statistics unavailable")
