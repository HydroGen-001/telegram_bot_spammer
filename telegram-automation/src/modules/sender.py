"""
Message sender module with protection
"""

import asyncio
import json
import random
from pathlib import Path
from typing import Optional, List, Dict, Any

from ..core.config import Config
from ..core.database import Database
from ..core.client import TelegramClientWrapper
from ..core.logger import get_logger
from ..config_manager import get_paths
from ..types import Template, Chat, BroadcastStats
from .protection import ProtectionManager

logger = get_logger("telegram_bot")


class MessageSender:
    """
    Message sender with anti-ban protection

    Features:
    - Send messages to chat list
    - Random template selection
    - Protection-aware sending
    """

    def __init__(
        self,
        client: TelegramClientWrapper,
        config: Config,
        database: Database,
        protection: ProtectionManager
    ):
        self.client = client
        self.config = config
        self.database = database
        self.protection = protection
        self.paths = get_paths()

        self._templates: List[Template] = []
        self._chats: List[Chat] = []
        self._auto_reply_text: str = ""

        self._load_templates()
        self._load_chats()

    def _load_templates(self) -> None:
        """Load message templates from config"""
        templates_path = self.paths.templates_path

        if not templates_path.exists():
            logger.warning("Templates file not found")
            return

        with open(templates_path, 'r', encoding='utf-8') as f:
            data = json.load(f)
            
            # Load templates
            templates_data = data.get('templates', [])
            self._templates = [Template.from_dict(t) for t in templates_data]
            
            # Load auto-reply text
            self._auto_reply_text = data.get('auto_reply_text', '')

        logger.info(f"Loaded {len(self._templates)} templates")

    def _load_chats(self) -> None:
        """Load chat list from config"""
        chats_path = self.paths.chats_path

        if not chats_path.exists():
            logger.warning("Chats file not found")
            return

        with open(chats_path, 'r', encoding='utf-8') as f:
            data = json.load(f)
            self._chats = [
                Chat.from_dict(chat) for chat in data.get('chats', [])
                if chat.get('enabled', True)
            ]

        logger.info(f"Loaded {len(self._chats)} enabled chats")
    
    def _get_random_template(self) -> Optional[str]:
        """Get random template text"""
        if not self._templates:
            return None

        index = self.protection.get_template_index(len(self._templates))
        return self._templates[index].text

    def get_template_with_photo(self) -> Optional[Template]:
        """Get template that has photo"""
        for template in self._templates:
            if template.has_photo:
                return template
        return self._templates[0] if self._templates else None

    @property
    def auto_reply_text(self) -> str:
        """Get auto-reply text"""
        return self._auto_reply_text

    @property
    def templates(self) -> List[Template]:
        """Get all templates"""
        return self._templates

    @property
    def chats(self) -> List[Chat]:
        """Get all chats"""
        return self._chats
    
    async def send_to_chat(
        self,
        chat: Dict[str, Any],
        text: Optional[str] = None
    ) -> bool:
        """
        Send message to specific chat
        
        Args:
            chat: Chat dict with 'id' and 'name'
            text: Optional custom text (uses random template if None)
        
        Returns:
            True if sent successfully
        """
        chat_id = chat.get('id')
        chat_name = chat.get('name', chat_id)
        
        # Wait if needed (protection)
        await self.protection.wait_if_needed()
        
        # Get message text
        if text is None:
            text = self._get_random_template()
        
        if not text:
            logger.error("No message text available")
            return False
        
        try:
            # Send message
            await self.client.send_message(chat_id, text)
            
            # Log to database
            template_id = None
            if self._templates:
                for t in self._templates:
                    if t['text'] == text:
                        template_id = t['id']
                        break
            
            await self.database.log_message_sent(
                chat_id=chat_id,
                chat_name=chat_name,
                message_text=text,
                template_id=template_id
            )
            
            # Record in protection
            await self.protection.record_message_sent()
            
            logger.info(f"Sent to {chat_name}")
            return True
            
        except Exception as e:
            logger.error(f"Error sending to {chat_name}: {e}")
            await self.database.log_error(
                error_type="send_failed",
                error_message=str(e),
                context=f"chat_id={chat_id}"
            )
            return False
    
    async def send_to_all(self) -> BroadcastStats:
        """
        Send messages to all enabled chats

        Returns:
            BroadcastStats with results
        """
        if not self._chats:
            logger.warning("No chats configured")
            return BroadcastStats()

        # Shuffle chats for randomization
        chats = self.protection.shuffle_chats(self._chats)
        stats = BroadcastStats(total=len(chats))

        logger.info(f"Starting broadcast to {len(chats)} chats")

        for i, chat in enumerate(chats, 1):
            # Check if can send before each message
            can_send, reason = await self.protection.can_send_message()

            if not can_send:
                if "Daily limit" in reason or "Hourly limit" in reason:
                    logger.info(f"Stopping broadcast: {reason}")
                    stats.skipped_limit = len(chats) - i + 1
                    break

            success = await self.send_to_chat(chat)

            if success:
                stats.sent += 1
            else:
                stats.failed += 1

            # Random delay after each message (except last)
            if i < len(chats):
                await self.protection.apply_random_delay()

        logger.info(
            f"Broadcast completed: {stats.sent} sent, "
            f"{stats.failed} failed"
        )

        return stats
    
    async def send_custom(
        self,
        chat_id: str,
        text: str,
        chat_name: Optional[str] = None
    ) -> bool:
        """
        Send custom message to chat
        
        Args:
            chat_id: Chat ID or username
            text: Message text
            chat_name: Optional chat name for logging
        
        Returns:
            True if sent successfully
        """
        chat = {'id': chat_id, 'name': chat_name or chat_id}
        return await self.send_to_chat(chat, text)
    
    @property
    def templates_count(self) -> int:
        """Get number of loaded templates"""
        return len(self._templates)

    @property
    def chats_count(self) -> int:
        """Get number of enabled chats"""
        return len(self._chats)


# Export for backward compatibility
__all__ = ['MessageSender']
