"""
Anti-ban protection manager
Controls message limits, delays, and patterns
"""

import asyncio
import random
from datetime import datetime, timedelta
from typing import Optional
from dataclasses import dataclass, field

from ..core.config import Config
from ..core.database import Database
from ..core.logger import get_logger

logger = get_logger("telegram_bot")


@dataclass
class RateLimitState:
    """Current rate limit state"""
    messages_today: int = 0
    messages_this_hour: int = 0
    messages_in_series: int = 0
    last_message_time: Optional[datetime] = None
    pause_until: Optional[datetime] = None


class ProtectionManager:
    """
    Anti-ban protection manager
    
    Implements:
    - Daily/hourly message limits
    - Random delays between messages
    - Series pauses
    - Pattern randomization
    """
    
    def __init__(self, config: Config, database: Database):
        self.config = config
        self.database = database
        self.state = RateLimitState()
        
        # Load limits from config
        self.daily_limit = config.get('message_limits.daily_limit', 80)
        self.hourly_limit = config.get('message_limits.hourly_limit', 25)
        self.messages_before_pause = config.get('message_limits.messages_before_pause', 10)
        self.pause_after_series_minutes = config.get('message_limits.pause_after_series_minutes', 15)
        
        # Load delays from config
        self.min_delay = config.get('delays.min_delay_seconds', 45)
        self.max_delay = config.get('delays.max_delay_seconds', 120)
        self.startup_delay = config.get('delays.startup_delay_seconds', 10)
    
    async def initialize(self) -> None:
        """Initialize protection manager state"""
        # Load today's stats from database
        stats = await self.database.get_today_stats()
        self.state.messages_today = stats['messages_sent']
        
        logger.info(
            f"Protection initialized: {self.state.messages_today}/{self.daily_limit} messages today"
        )
    
    async def can_send_message(self) -> tuple[bool, str]:
        """
        Check if message can be sent
        
        Returns:
            Tuple of (can_send, reason)
        """
        now = datetime.now()
        
        # Check if in pause after series
        if self.state.pause_until:
            if now < self.state.pause_until:
                remaining = (self.state.pause_until - now).seconds
                return False, f"Pause after series: {remaining}s remaining"
            else:
                # Pause ended, reset series counter
                self.state.pause_until = None
                self.state.messages_in_series = 0
                logger.info("Series pause ended, resuming")
        
        # Check daily limit
        if self.state.messages_today >= self.daily_limit:
            return False, f"Daily limit reached: {self.state.messages_today}/{self.daily_limit}"
        
        # Check hourly limit
        if self.state.messages_this_hour >= self.hourly_limit:
            # Reset hourly counter if hour passed
            if self.state.last_message_time:
                hour_ago = now - timedelta(hours=1)
                if self.state.last_message_time < hour_ago:
                    self.state.messages_this_hour = 0
                else:
                    return False, f"Hourly limit reached: {self.state.messages_this_hour}/{self.hourly_limit}"
        
        # Check if delay passed since last message
        if self.state.last_message_time:
            time_since_last = (now - self.state.last_message_time).total_seconds()
            if time_since_last < self.min_delay:
                return False, f"Delay not passed: {time_since_last:.0f}s/{self.min_delay}s"
        
        return True, "OK"
    
    async def wait_if_needed(self) -> None:
        """Wait until message can be sent"""
        while True:
            can_send, reason = await self.can_send_message()
            if can_send:
                break
            
            logger.debug(f"Waiting: {reason}")
            
            # Calculate wait time
            if "Pause after series" in reason:
                wait_time = 10
            elif "Delay not passed" in reason:
                wait_time = self.min_delay
            else:
                wait_time = 60  # Check again in a minute for limits
            
            await asyncio.sleep(wait_time)
    
    async def record_message_sent(self) -> None:
        """Record that a message was sent"""
        now = datetime.now()
        
        self.state.messages_today += 1
        self.state.messages_this_hour += 1
        self.state.messages_in_series += 1
        self.state.last_message_time = now
        
        # Check if pause needed after series
        if self.state.messages_in_series >= self.messages_before_pause:
            pause_until = now + timedelta(minutes=self.pause_after_series_minutes)
            self.state.pause_until = pause_until
            logger.info(
                f"Series pause started until {pause_until.strftime('%H:%M:%S')}"
            )
        
        logger.info(
            f"Message sent: {self.state.messages_today}/{self.daily_limit} today, "
            f"{self.state.messages_this_hour}/{self.hourly_limit} this hour"
        )
    
    def get_random_delay(self) -> float:
        """Get random delay in seconds"""
        return random.uniform(self.min_delay, self.max_delay)
    
    async def apply_random_delay(self) -> None:
        """Wait for random delay"""
        delay = self.get_random_delay()
        logger.debug(f"Random delay: {delay:.1f}s")
        await asyncio.sleep(delay)
    
    def get_template_index(self, templates_count: int) -> int:
        """Get random template index"""
        return random.randint(0, templates_count - 1)
    
    def shuffle_chats(self, chats: list) -> list:
        """Return shuffled list of chats"""
        shuffled = chats.copy()
        random.shuffle(shuffled)
        return shuffled
    
    def get_status(self) -> dict:
        """Get current protection status"""
        return {
            'messages_today': self.state.messages_today,
            'daily_limit': self.daily_limit,
            'messages_this_hour': self.state.messages_this_hour,
            'hourly_limit': self.hourly_limit,
            'messages_in_series': self.state.messages_in_series,
            'pause_until': self.state.pause_until.isoformat() if self.state.pause_until else None,
            'last_message_time': self.state.last_message_time.isoformat() if self.state.last_message_time else None
        }
