"""
Multi-Account Telegram Broadcaster
Модуль для параллельной рассылки с нескольких аккаунтов
"""

from .config import Config, AccountConfig
from .manager import AccountManager
from .broadcaster import MultiAccountBroadcaster, AccountBroadcaster, BroadcasterStats
from .proxy_manager import ProxyManager, create_client_with_proxy, connect_account_with_proxy
from .chat_join import ChatJoinManager

__all__ = [
    'Config',
    'AccountConfig',
    'AccountManager',
    'MultiAccountBroadcaster',
    'AccountBroadcaster',
    'BroadcasterStats',
    'ProxyManager',
    'create_client_with_proxy',
    'connect_account_with_proxy',
    'ChatJoinManager'
]
