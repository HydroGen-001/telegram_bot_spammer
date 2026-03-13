"""
Telegram Automation System - Main Entry Point
"""

import asyncio
import signal
import sys
from pathlib import Path

# Add src to path
src_path = Path(__file__).parent
sys.path.insert(0, str(src_path))

from core.config import Config
from core.logger import setup_logger, get_logger
from core.database import Database
from core.client import TelegramClientWrapper
from modules.protection import ProtectionManager
from modules.sender import MessageSender
from modules.responder import AutoResponder
from modules.scheduler import TaskScheduler


class TelegramAutomation:
    """Main application controller"""
    
    def __init__(self):
        self.logger = None
        self.config = None
        self.database = None
        self.client = None
        self.protection = None
        self.sender = None
        self.responder = None
        self.scheduler = None
        self._shutdown = False
    
    async def initialize(self) -> None:
        """Initialize all components"""
        # Setup logger first
        self.logger = setup_logger()
        self.logger.info("=" * 50)
        self.logger.info("Telegram Automation System Starting...")
        self.logger.info("=" * 50)
        
        # Load configuration
        self.logger.info("Loading configuration...")
        self.config = Config()
        
        # Get logging config for proper initialization
        log_config = self.config.logging
        
        # Reinitialize logger with config settings
        self.logger = setup_logger(
            level=log_config.get('level', 'INFO'),
            max_file_size_mb=log_config.get('max_file_size_mb', 10),
            backup_count=log_config.get('backup_count', 5)
        )
        
        # Initialize database
        self.logger.info("Initializing database...")
        db_config = self.config.database
        self.database = Database(db_config.get('path', 'database/automation.db'))
        await self.database.connect(wal_mode=db_config.get('wal_mode', True))
        
        # Initialize Telegram client
        self.logger.info("Connecting to Telegram...")
        self.client = TelegramClientWrapper(self.config)
        await self.client.connect()
        
        # Initialize protection manager
        self.logger.info("Initializing protection manager...")
        self.protection = ProtectionManager(self.config, self.database)
        await self.protection.initialize()
        
        # Initialize message sender
        self.logger.info("Initializing message sender...")
        self.sender = MessageSender(
            self.client,
            self.config,
            self.database,
            self.protection
        )
        
        # Initialize auto-responder
        self.logger.info("Initializing auto-responder...")
        self.responder = AutoResponder(
            self.client,
            self.config,
            self.database
        )
        self.responder.start_listening()
        
        # Initialize scheduler
        self.logger.info("Initializing scheduler...")
        self.scheduler = TaskScheduler(self.config)
        await self.scheduler.start()
        
        self.logger.info("=" * 50)
        self.logger.info("Initialization Complete!")
        self.logger.info("=" * 50)
        
        # Print status
        self._print_status()
    
    def _print_status(self) -> None:
        """Print current system status"""
        self.logger.info(f"Templates loaded: {self.sender.templates_count}")
        self.logger.info(f"Chats configured: {self.sender.chats_count}")
        self.logger.info(f"Daily limit: {self.protection.daily_limit}")
        self.logger.info(f"Auto-reply: {'enabled' if self.responder.is_enabled else 'disabled'}")
    
    async def run_broadcast(self) -> None:
        """Run one broadcast cycle"""
        if self._shutdown:
            return
        
        self.logger.info("Starting broadcast cycle...")
        stats = await self.sender.send_to_all()
        self.logger.info(
            f"Broadcast cycle completed: {stats['sent']} sent, "
            f"{stats['failed']} failed"
        )
    
    async def run_interactive(self) -> None:
        """Run interactive mode with menu"""
        print("\n" + "=" * 50)
        print("TELEGRAM AUTOMATION - INTERACTIVE MODE")
        print("=" * 50)
        
        while not self._shutdown:
            print("\nMenu:")
            print("1. Run broadcast now")
            print("2. View status")
            print("3. View today's stats")
            print("4. Exit")
            
            choice = input("\nSelect option (1-4): ").strip()
            
            if choice == '1':
                await self.run_broadcast()
            elif choice == '2':
                self._print_status()
                protection_status = self.protection.get_status()
                print(f"\nProtection Status:")
                for key, value in protection_status.items():
                    print(f"  {key}: {value}")
            elif choice == '3':
                stats = await self.database.get_today_stats()
                print(f"\nToday's Stats:")
                print(f"  Messages sent: {stats['messages_sent']}")
                print(f"  Messages received: {stats['messages_received']}")
                print(f"  Errors: {stats['errors']}")
            elif choice == '4':
                break
            else:
                print("Invalid option")
    
    async def run_auto(self, interval_hours: int = 1) -> None:
        """
        Run automatic mode with scheduled broadcasts
        
        Args:
            interval_hours: Hours between broadcasts
        """
        self.logger.info(f"Starting automatic mode (interval: {interval_hours}h)")
        
        async def broadcast_job():
            await self.run_broadcast()
        
        await self.scheduler.schedule_periodic(
            name="broadcast",
            coro_func=broadcast_job,
            interval_seconds=interval_hours * 3600,
            delay_start=True
        )
    
    async def shutdown(self) -> None:
        """Graceful shutdown"""
        self.logger.info("Shutting down...")
        self._shutdown = True
        
        if self.scheduler:
            await self.scheduler.stop()
        
        if self.client:
            await self.client.disconnect()
        
        if self.database:
            await self.database.close()
        
        self.logger.info("Shutdown complete")
    
    def setup_signal_handlers(self) -> None:
        """Setup signal handlers for graceful shutdown"""
        loop = asyncio.get_event_loop()
        
        for sig in (signal.SIGINT, signal.SIGTERM):
            loop.add_signal_handler(
                sig,
                lambda: asyncio.create_task(self.shutdown())
            )


async def main():
    """Main entry point"""
    app = TelegramAutomation()
    
    try:
        # Initialize
        await app.initialize()
        
        # Setup signal handlers
        app.setup_signal_handlers()
        
        # Choose mode based on command line args
        mode = "interactive"  # Default mode
        
        if len(sys.argv) > 1:
            if sys.argv[1] == "--auto":
                mode = "auto"
            elif sys.argv[1] == "--broadcast":
                mode = "broadcast"
        
        # Run selected mode
        if mode == "interactive":
            await app.run_interactive()
        elif mode == "auto":
            await app.run_auto(interval_hours=1)
        elif mode == "broadcast":
            await app.run_broadcast()
        
    except KeyboardInterrupt:
        print("\nInterrupted by user")
    except Exception as e:
        if app.logger:
            app.logger.error(f"Fatal error: {e}", exc_info=True)
        else:
            print(f"Fatal error: {e}")
        raise
    finally:
        await app.shutdown()


if __name__ == "__main__":
    asyncio.run(main())
