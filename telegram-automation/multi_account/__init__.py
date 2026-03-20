"""
Multi-Account Telegram Broadcaster
Модуль для параллельной рассылки с нескольких аккаунтов
"""

from .config import Config, AccountConfig
from .manager import AccountManager
from .broadcaster import MultiAccountBroadcaster, AccountBroadcaster, BroadcasterStats

__all__ = [
    'Config',
    'AccountConfig',
    'AccountManager',
    'MultiAccountBroadcaster',
    'AccountBroadcaster',
    'BroadcasterStats'
]
