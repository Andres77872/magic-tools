"""Secure chat storage management for Magic Tools."""

import json
import os
import hashlib
import time
import logging
from pathlib import Path
from typing import List, Optional, Dict, Any
from dataclasses import dataclass, field, asdict
from datetime import datetime
import uuid

from ..ai.models import AIMessage


@dataclass
class ChatMetadata:
    """Metadata for a chat conversation."""
    id: str
    name: str
    created_at: float
    updated_at: float
    message_count: int = 0
    last_message_preview: str = ""


@dataclass 
class Chat:
    """Represents a complete chat conversation."""
    metadata: ChatMetadata
    messages: List[AIMessage] = field(default_factory=list)
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert chat to dictionary for JSON serialization."""
        return {
            "metadata": asdict(self.metadata),
            "messages": [
                {
                    "role": msg.role,
                    "content": msg.content,
                    "timestamp": msg.timestamp,
                    "badge": msg.badge
                } for msg in self.messages
            ]
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "Chat":
        """Create chat from dictionary."""
        metadata_dict = data.get("metadata", {})
        metadata = ChatMetadata(
            id=metadata_dict.get("id", str(uuid.uuid4())),
            name=metadata_dict.get("name", "Untitled Chat"),
            created_at=metadata_dict.get("created_at", time.time()),
            updated_at=metadata_dict.get("updated_at", time.time()),
            message_count=metadata_dict.get("message_count", 0),
            last_message_preview=metadata_dict.get("last_message_preview", "")
        )
        
        messages = []
        for msg_data in data.get("messages", []):
            message = AIMessage(
                role=msg_data.get("role", "user"),
                content=msg_data.get("content", ""),
                timestamp=msg_data.get("timestamp", 0.0),
                badge=msg_data.get("badge", "")
            )
            messages.append(message)
        
        return cls(metadata=metadata, messages=messages)


class ChatStorageManager:
    """Manages secure storage and retrieval of chat conversations."""
    
    def __init__(self, config_manager):
        """Initialize chat storage manager.
        
        Args:
            config_manager: Configuration manager instance
        """
        self.logger = logging.getLogger(__name__)
        self.config_manager = config_manager
        
        # Create chats directory in config folder
        self.chats_dir = config_manager.get_config_path() / "chats"
        self.chats_dir.mkdir(parents=True, exist_ok=True)
        
        # Chat index file for quick metadata access
        self.index_file = self.chats_dir / "index.json"
        
        # Load or create index
        self._chat_index = self._load_index()
    
    def _load_index(self) -> Dict[str, ChatMetadata]:
        """Load chat index from file."""
        try:
            if self.index_file.exists():
                with open(self.index_file, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                    index = {}
                    for chat_id, metadata_dict in data.items():
                        index[chat_id] = ChatMetadata(**metadata_dict)
                    return index
            else:
                return {}
        except Exception as e:
            self.logger.error(f"Failed to load chat index: {e}")
            return {}
    
    def _save_index(self) -> bool:
        """Save chat index to file."""
        try:
            data = {}
            for chat_id, metadata in self._chat_index.items():
                data[chat_id] = asdict(metadata)
            
            with open(self.index_file, 'w', encoding='utf-8') as f:
                json.dump(data, f, indent=2, ensure_ascii=False)
            return True
        except Exception as e:
            self.logger.error(f"Failed to save chat index: {e}")
            return False
    
    def _sanitize_filename(self, name: str) -> str:
        """Sanitize filename to prevent path traversal attacks."""
        # Remove dangerous characters and limit length
        sanitized = "".join(c for c in name if c.isalnum() or c in (' ', '-', '_')).strip()
        sanitized = sanitized[:50]  # Limit length
        if not sanitized:
            sanitized = "untitled"
        return sanitized
    
    def _get_chat_filename(self, chat_id: str) -> str:
        """Get secure filename for chat."""
        # Use hash of chat_id to prevent directory traversal
        safe_id = hashlib.sha256(chat_id.encode()).hexdigest()[:16]
        return f"chat_{safe_id}.json"
    
    def create_chat(self, name: str = None, persist: bool = False) -> Chat:
        """Create a new chat conversation.
        
        Args:
            name: Optional name for the chat
            persist: If True, immediately add to index and persist metadata. If False,
                     keep only in memory until explicitly saved.
            
        Returns:
            New chat instance
        """
        chat_id = str(uuid.uuid4())
        current_time = time.time()
        
        if not name:
            name = f"Chat {datetime.fromtimestamp(current_time).strftime('%Y-%m-%d %H:%M')}"
        
        metadata = ChatMetadata(
            id=chat_id,
            name=self._sanitize_filename(name),
            created_at=current_time,
            updated_at=current_time
        )
        
        chat = Chat(metadata=metadata)
        
        # Optionally persist immediately; otherwise defer until first save
        if persist:
            self._chat_index[chat_id] = metadata
            self._save_index()
            self.logger.info(f"Created new chat: {chat_id}")
        else:
            self.logger.info(f"Created new chat (in-memory): {chat_id}")
        return chat
    
    def save_chat(self, chat: Chat) -> bool:
        """Save a chat conversation to file.
        
        Args:
            chat: Chat to save
            
        Returns:
            True if saved successfully
        """
        try:
            # Avoid persisting completely empty chats (no messages)
            if not chat.messages:
                self.logger.info(f"Skip saving empty chat: {chat.metadata.id}")
                return False

            # Update metadata
            chat.metadata.updated_at = time.time()
            chat.metadata.message_count = len(chat.messages)
            
            # Get last message preview
            if chat.messages:
                last_msg = chat.messages[-1]
                preview = last_msg.content[:100]
                if len(last_msg.content) > 100:
                    preview += "..."
                chat.metadata.last_message_preview = preview
            
            # Save chat file
            filename = self._get_chat_filename(chat.metadata.id)
            chat_file = self.chats_dir / filename
            
            with open(chat_file, 'w', encoding='utf-8') as f:
                json.dump(chat.to_dict(), f, indent=2, ensure_ascii=False)
            
            # Update index
            self._chat_index[chat.metadata.id] = chat.metadata
            self._save_index()
            
            self.logger.info(f"Saved chat: {chat.metadata.id}")
            return True
            
        except Exception as e:
            self.logger.error(f"Failed to save chat {chat.metadata.id}: {e}")
            return False
    
    def load_chat(self, chat_id: str) -> Optional[Chat]:
        """Load a chat conversation from file.
        
        Args:
            chat_id: ID of chat to load
            
        Returns:
            Chat instance or None if not found
        """
        try:
            if chat_id not in self._chat_index:
                self.logger.warning(f"Chat not found in index: {chat_id}")
                return None
            
            filename = self._get_chat_filename(chat_id)
            chat_file = self.chats_dir / filename
            
            if not chat_file.exists():
                self.logger.warning(f"Chat file not found: {chat_file}")
                return None
            
            with open(chat_file, 'r', encoding='utf-8') as f:
                data = json.load(f)
                
            chat = Chat.from_dict(data)
            self.logger.info(f"Loaded chat: {chat_id}")
            return chat
            
        except Exception as e:
            self.logger.error(f"Failed to load chat {chat_id}: {e}")
            return None
    
    def list_chats(self) -> List[ChatMetadata]:
        """Get list of all chat metadata sorted by update time.
        
        Returns:
            List of chat metadata
        """
        chats = list(self._chat_index.values())
        # Sort by updated_at descending (newest first)
        chats.sort(key=lambda x: x.updated_at, reverse=True)
        return chats
    
    def delete_chat(self, chat_id: str) -> bool:
        """Delete a chat conversation.
        
        Args:
            chat_id: ID of chat to delete
            
        Returns:
            True if deleted successfully
        """
        try:
            if chat_id not in self._chat_index:
                return False
            
            # Delete file
            filename = self._get_chat_filename(chat_id)
            chat_file = self.chats_dir / filename
            if chat_file.exists():
                chat_file.unlink()
            
            # Remove from index
            del self._chat_index[chat_id]
            self._save_index()
            
            self.logger.info(f"Deleted chat: {chat_id}")
            return True
            
        except Exception as e:
            self.logger.error(f"Failed to delete chat {chat_id}: {e}")
            return False
    
    def rename_chat(self, chat_id: str, new_name: str) -> bool:
        """Rename a chat conversation.
        
        Args:
            chat_id: ID of chat to rename
            new_name: New name for the chat
            
        Returns:
            True if renamed successfully
        """
        try:
            if chat_id not in self._chat_index:
                return False
            
            # Update metadata
            self._chat_index[chat_id].name = self._sanitize_filename(new_name)
            self._chat_index[chat_id].updated_at = time.time()
            
            # Save index
            self._save_index()
            
            self.logger.info(f"Renamed chat {chat_id} to: {new_name}")
            return True
            
        except Exception as e:
            self.logger.error(f"Failed to rename chat {chat_id}: {e}")
            return False
    
    def get_storage_stats(self) -> Dict[str, Any]:
        """Get storage statistics.
        
        Returns:
            Dictionary with storage stats
        """
        try:
            total_chats = len(self._chat_index)
            total_size = 0
            
            for file in self.chats_dir.glob("chat_*.json"):
                total_size += file.stat().st_size
            
            return {
                "total_chats": total_chats,
                "storage_size_bytes": total_size,
                "storage_path": str(self.chats_dir)
            }
        except Exception as e:
            self.logger.error(f"Failed to get storage stats: {e}")
            return {"error": str(e)}
