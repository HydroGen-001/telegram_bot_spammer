"""
Task scheduler for automated broadcasting
"""

import asyncio
from datetime import datetime, timedelta
from typing import Optional, Callable, Awaitable

from ..core.config import Config
from ..core.logger import get_logger

logger = get_logger("telegram_bot")


class TaskScheduler:
    """
    Task scheduler for periodic broadcasting
    
    Features:
    - Schedule broadcast tasks
    - Run at specific times
    - Run with intervals
    """
    
    def __init__(self, config: Config):
        self.config = config
        self._tasks: list = []
        self._running = False
    
    async def start(self) -> None:
        """Start scheduler"""
        self._running = True
        logger.info("Task scheduler started")
    
    async def stop(self) -> None:
        """Stop scheduler and cancel all tasks"""
        self._running = False
        
        for task in self._tasks:
            if not task.done():
                task.cancel()
        
        if self._tasks:
            await asyncio.gather(*self._tasks, return_exceptions=True)
        
        logger.info("Task scheduler stopped")
    
    async def schedule_periodic(
        self,
        name: str,
        coro_func: Callable[[], Awaitable[None]],
        interval_seconds: int,
        delay_start: bool = True
    ) -> None:
        """
        Schedule periodic task
        
        Args:
            name: Task name
            coro_func: Async function to run
            interval_seconds: Interval between runs
            delay_start: Wait one interval before first run
        """
        if delay_start:
            logger.info(f"Task '{name}' scheduled every {interval_seconds}s (delayed start)")
            await asyncio.sleep(interval_seconds)
        else:
            logger.info(f"Task '{name}' scheduled every {interval_seconds}s")
        
        while self._running:
            try:
                logger.debug(f"Running task '{name}'")
                await coro_func()
            except asyncio.CancelledError:
                logger.info(f"Task '{name}' cancelled")
                break
            except Exception as e:
                logger.error(f"Task '{name}' error: {e}")
            
            # Wait until next run
            await asyncio.sleep(interval_seconds)
    
    async def schedule_at(
        self,
        name: str,
        coro_func: Callable[[], Awaitable[None]],
        time: datetime
    ) -> None:
        """
        Schedule task at specific time
        
        Args:
            name: Task name
            coro_func: Async function to run
            time: Time to run task
        """
        now = datetime.now()
        
        if time <= now:
            logger.warning(f"Task '{name}' time is in the past")
            return
        
        delay = (time - now).total_seconds()
        logger.info(f"Task '{name}' scheduled at {time.strftime('%H:%M:%S')} (in {delay:.0f}s)")
        
        await asyncio.sleep(delay)
        
        if not self._running:
            return
        
        try:
            await coro_func()
        except Exception as e:
            logger.error(f"Task '{name}' error: {e}")
    
    def create_task(
        self,
        coro_func: Callable[[], Awaitable[None]],
        name: Optional[str] = None
    ) -> asyncio.Task:
        """
        Create and track async task
        
        Args:
            coro_func: Async function to run
            name: Optional task name
        
        Returns:
            Created asyncio.Task
        """
        task = asyncio.create_task(coro_func())
        
        if name:
            task.set_name(name)
        
        self._tasks.append(task)
        
        # Clean up done tasks
        task.add_done_callback(lambda t: self._tasks.remove(t) if t in self._tasks else None)
        
        return task
    
    async def run_delayed(
        self,
        coro_func: Callable[[], Awaitable[None]],
        delay_seconds: int
    ) -> None:
        """
        Run task after delay
        
        Args:
            coro_func: Async function to run
            delay_seconds: Delay in seconds
        """
        logger.debug(f"Running task after {delay_seconds}s delay")
        await asyncio.sleep(delay_seconds)
        
        if not self._running:
            return
        
        try:
            await coro_func()
        except Exception as e:
            logger.error(f"Delayed task error: {e}")
    
    def get_active_tasks_count(self) -> int:
        """Get count of active tasks"""
        return len([t for t in self._tasks if not t.done()])
    
    @property
    def is_running(self) -> bool:
        """Check if scheduler is running"""
        return self._running
