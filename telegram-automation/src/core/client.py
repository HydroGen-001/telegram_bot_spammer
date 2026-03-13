"""
Telegram client wrapper using Telethon
"""

import os
from pathlib import Path
from typing import Optional, List, Union
from dotenv import load_dotenv

from telethon import TelegramClient, events
from telethon.tl.types import Message, User, Chat, Channel

from .config import Config
from .logger import get_logger
from ..config_manager import get_paths

logger = get_logger("telegram_bot")


class TelegramClientWrapper:
    """Wrapper for TelegramClient with connection management"""

    def __init__(self, config: Config, session_name: str = 'userbot'):
        self.config = config
        self.session_name = session_name
        self._client: Optional[TelegramClient] = None
        
        # Get session path from config manager
        self._session_path = get_paths().session_path(session_name)

        # Load environment variables
        load_dotenv(str(get_paths().env_path()))
    
    async def connect(self) -> None:
        """Initialize and connect Telegram client"""
        # Get credentials from config or environment
        api_id = self.config.get('telegram.api_id')
        api_hash = self.config.get('telegram.api_hash')
        phone = self.config.get('telegram.phone')
        
        # Fallback to environment variables
        if not api_id or api_id == 0:
            api_id = int(os.getenv('API_ID', '0'))
        if not api_hash or api_hash == "":
            api_hash = os.getenv('API_HASH', '')
        if not phone or phone == "":
            phone = os.getenv('PHONE', '')
        
        if not api_id or not api_hash or not phone:
            raise ValueError(
                "Telegram credentials not found. "
                "Set them in config/config.json or .env file"
            )
        
        # Create session directory
        Path(self._session_path).parent.mkdir(parents=True, exist_ok=True)
        
        # Initialize client
        self._client = TelegramClient(
            self._session_path,
            api_id,
            api_hash,
            system_version='4.0.0',
            app_version='1.0.0',
            device_model='Desktop'
        )
        
        # Setup proxy if enabled
        proxy_config = self.config.get('proxy', {})
        if proxy_config.get('enabled', False):
            proxy_type = proxy_config.get('type', 'http')
            proxy_host = proxy_config.get('host', '')
            proxy_port = proxy_config.get('port', 0)
            proxy_username = proxy_config.get('username')
            proxy_password = proxy_config.get('password')
            
            if proxy_type == 'http' and proxy_host and proxy_port:
                from telethon.network.connection.tcphttp import ConnectionHttp
                self._client._connection = ConnectionHttp
                
                # Set proxy
                self._client._proxy = (
                    proxy_host,
                    proxy_port,
                    True,
                    proxy_username,
                    proxy_password
                )
        
        # Connect
        await self._client.start(phone=phone)
        
        # Get current user info
        me = await self._client.get_me()
        logger.info(f"Connected as {me.first_name} (@{me.username or 'no_username'})")
    
    async def disconnect(self) -> None:
        """Disconnect from Telegram"""
        if self._client:
            await self._client.disconnect()
            logger.info("Disconnected from Telegram")
    
    async def send_message(
        self,
        chat_id: Union[str, int],
        text: str,
        reply_to: Optional[int] = None
    ) -> Optional[Message]:
        """
        Send message to chat
        
        Args:
            chat_id: Chat ID or username
            text: Message text
            reply_to: Message ID to reply to
        
        Returns:
            Sent message or None
        """
        if not self._client:
            logger.error("Client not connected")
            return None
        
        try:
            message = await self._client.send_message(
                chat_id,
                text,
                reply_to=reply_to
            )
            logger.debug(f"Message sent to {chat_id}")
            return message
        except Exception as e:
            logger.error(f"Error sending message to {chat_id}: {e}")
            raise
    
    async def get_dialogs(
        self,
        limit: int = 100
    ) -> List[Union[User, Chat, Channel]]:
        """Get list of dialogs (chats)"""
        if not self._client:
            logger.error("Client not connected")
            return []
        
        dialogs = []
        async for dialog in self._client.iter_dialogs(limit=limit):
            dialogs.append(dialog)
        
        return dialogs
    
    async def get_chat_id(self, chat_username: str) -> Optional[int]:
        """Get numeric chat ID from username"""
        if not self._client:
            return None
        
        try:
            entity = await self._client.get_entity(chat_username)
            return entity.id
        except Exception as e:
            logger.error(f"Error getting chat ID for {chat_username}: {e}")
            return None
    
    def add_event_handler(
        self,
        callback,
        event=None
    ):
        """Add event handler"""
        if not self._client:
            raise RuntimeError("Client not connected")
        
        if event:
            self._client.add_event_handler(callback, event)
        else:
            self._client.add_event_handler(callback)
    
    def on(self, event):
        """Decorator for event handlers"""
        if not self._client:
            raise RuntimeError("Client not connected")
        
        return self._client.on(event)
    
    async def run_until_disconnected(self) -> None:
        """Run client until disconnected"""
        if not self._client:
            raise RuntimeError("Client not connected")
        
        await self._client.run_until_disconnected()
    
    @property
    def client(self) -> Optional[TelegramClient]:
        """Get raw TelegramClient instance"""
        return self._client
    
    @property
    def is_connected(self) -> bool:
        """Check if client is connected"""
        return self._client is not None and self._client.is_connected()
