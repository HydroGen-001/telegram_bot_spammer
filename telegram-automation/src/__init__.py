"""
Telegram Automation System
"""

from .core.config import Config
from .core.logger import setup_logger, get_logger
from .core.database import Database
from .core.client import TelegramClientWrapper
from .modules.protection import ProtectionManager
from .modules.sender import MessageSender
from .modules.responder import AutoResponder
from .modules.scheduler import TaskScheduler

__all__ = [
    'Config',
    'setup_logger',
    'get_logger',
    'Database',
    'TelegramClientWrapper',
    'ProtectionManager',
    'MessageSender',
    'AutoResponder',
    'TaskScheduler'
]
