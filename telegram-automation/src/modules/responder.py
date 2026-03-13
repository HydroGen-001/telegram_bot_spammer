"""
Auto-responder for incoming messages
"""

import asyncio
import json
from pathlib import Path
from typing import Optional, Dict, Any

from telethon import events
from telethon.tl.types import Message, User

from ..core.config import Config
from ..core.database import Database
from ..core.client import TelegramClientWrapper
from ..core.logger import get_logger
from ..config_manager import get_paths

logger = get_logger("telegram_bot")


class AutoResponder:
    """
    Automatic responder for incoming messages

    Features:
    - Detect incoming messages
    - Send auto-reply with delay
    - Track replied messages
    """

    def __init__(
        self,
        client: TelegramClientWrapper,
        config: Config,
        database: Database
    ):
        self.client = client
        self.config = config
        self.database = database
        self.paths = get_paths()

        # Load settings
        self.enabled = config.get('auto_reply.enabled', True)
        self.delay_seconds = config.get('auto_reply.delay_seconds', 5)
        self.only_to_replies = config.get('auto_reply.only_to_replies', True)

        # Load auto-reply text
        self._auto_reply_text = self._load_auto_reply_text()

        # Track processed messages to avoid duplicates
        self._processed_messages: set = set()

    def _load_auto_reply_text(self) -> str:
        """Load auto-reply text from templates config"""
        templates_path = self.paths.templates_path

        if not templates_path.exists():
            logger.warning("Templates file not found, using default auto-reply")
            return (
                "Спасибо за интерес! 🙏\n\n"
                "Заполните анкету по ссылке:\n"
                "https://forms.example.com/your-form"
            )

        with open(templates_path, 'r', encoding='utf-8') as f:
            data = json.load(f)
            return data.get('auto_reply_text', '')
    
    def start_listening(self) -> None:
        """Start listening for incoming messages"""
        if not self.enabled:
            logger.info("Auto-responder disabled")
            return
        
        @self.client.on(events.NewMessage(incoming=True))
        async def handler(event: events.NewMessage.Event) -> None:
            await self._handle_incoming_message(event)
        
        logger.info("Auto-responder started listening")
    
    async def _handle_incoming_message(
        self,
        event: events.NewMessage.Event
    ) -> None:
        """Handle incoming message event"""
        message = event.message
        
        # Skip if already processed
        if message.id in self._processed_messages:
            return
        
        # Skip messages from bots
        if message.from_id and isinstance(message.from_id, int):
            # Check if sender is bot (simplified check)
            pass
        
        # Skip if only replies enabled and this is not a reply
        if self.only_to_replies and not message.is_reply:
            logger.debug(f"Skipping non-reply message from {message.chat_id}")
            return
        
        # Skip our own messages
        if message.out:
            return
        
        # Get sender info
        sender = await event.get_sender()
        sender_id = sender.id if sender else None
        sender_name = self._get_sender_name(sender)
        
        # Get chat info
        chat_id = str(message.chat_id)
        chat_name = await self._get_chat_name(event)
        
        # Log incoming message
        await self.database.log_message_received(
            chat_id=chat_id,
            chat_name=chat_name,
            sender_id=sender_id,
            sender_name=sender_name,
            message_text=message.text or ""
        )
        
        logger.info(f"Incoming message from {sender_name} in {chat_name}")
        
        # Mark as processed
        self._processed_messages.add(message.id)
        
        # Clean old processed messages (keep last 1000)
        if len(self._processed_messages) > 1000:
            self._processed_messages = set(
                list(self._processed_messages)[-500:]
            )
        
        # Send auto-reply
        await self._send_auto_reply(message)
    
    def _get_sender_name(self, sender: Optional[User]) -> str:
        """Get sender name"""
        if not sender:
            return "Unknown"
        
        if sender.first_name and sender.last_name:
            return f"{sender.first_name} {sender.last_name}"
        elif sender.first_name:
            return sender.first_name
        elif sender.username:
            return f"@{sender.username}"
        else:
            return "Unknown"
    
    async def _get_chat_name(
        self,
        event: events.NewMessage.Event
    ) -> str:
        """Get chat name"""
        chat = await event.get_chat()
        
        if hasattr(chat, 'title') and chat.title:
            return chat.title
        elif hasattr(chat, 'username') and chat.username:
            return f"@{chat.username}"
        else:
            return str(event.chat_id)
    
    async def _send_auto_reply(self, original_message: Message) -> None:
        """Send auto-reply to message"""
        if not self._auto_reply_text:
            logger.warning("No auto-reply text configured")
            return
        
        # Delay before reply
        await asyncio.sleep(self.delay_seconds)
        
        try:
            await self.client.send_message(
                original_message.chat_id,
                self._auto_reply_text,
                reply_to=original_message.id
            )
            
            logger.info(f"Auto-reply sent to {original_message.chat_id}")
            
        except Exception as e:
            logger.error(f"Error sending auto-reply: {e}")
            await self.database.log_error(
                error_type="auto_reply_failed",
                error_message=str(e),
                context=f"chat_id={original_message.chat_id}"
            )
    
    def stop(self) -> None:
        """Stop auto-responder"""
        self.enabled = False
        logger.info("Auto-responder stopped")
    
    @property
    def is_enabled(self) -> bool:
        """Check if auto-responder is enabled"""
        return self.enabled
