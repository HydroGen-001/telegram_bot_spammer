"""
SQLite database with optimization for message history
"""

import aiosqlite
from pathlib import Path
from typing import Optional, List, Dict, Any
from datetime import datetime, date


class Database:
    """SQLite database manager with WAL mode optimization"""
    
    def __init__(self, db_path: str = "database/automation.db"):
        self.db_path = Path(db_path)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._connection: Optional[aiosqlite.Connection] = None
    
    async def connect(self, wal_mode: bool = True) -> None:
        """Initialize database connection and create tables"""
        self._connection = await aiosqlite.connect(str(self.db_path))
        
        # Enable WAL mode for better performance
        if wal_mode:
            await self._connection.execute("PRAGMA journal_mode=WAL")
            await self._connection.execute("PRAGMA synchronous=NORMAL")
            await self._connection.execute("PRAGMA cache_size=10000")
        
        await self._create_tables()
        await self._create_indexes()
        await self._connection.commit()
    
    async def _create_tables(self) -> None:
        """Create database tables"""
        await self._connection.execute("""
            CREATE TABLE IF NOT EXISTS messages (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                chat_id TEXT NOT NULL,
                chat_name TEXT,
                message_text TEXT NOT NULL,
                template_id INTEGER,
                status TEXT DEFAULT 'sent',
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        
        await self._connection.execute("""
            CREATE TABLE IF NOT EXISTS incoming (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                chat_id TEXT NOT NULL,
                chat_name TEXT,
                sender_id INTEGER,
                sender_name TEXT,
                message_text TEXT NOT NULL,
                replied INTEGER DEFAULT 0,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        
        await self._connection.execute("""
            CREATE TABLE IF NOT EXISTS stats (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                date TEXT UNIQUE NOT NULL,
                messages_sent INTEGER DEFAULT 0,
                messages_received INTEGER DEFAULT 0,
                errors INTEGER DEFAULT 0,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        
        await self._connection.execute("""
            CREATE TABLE IF NOT EXISTS errors (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                error_type TEXT NOT NULL,
                error_message TEXT,
                context TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
    
    async def _create_indexes(self) -> None:
        """Create indexes for optimized queries"""
        indexes = [
            "CREATE INDEX IF NOT EXISTS idx_messages_chat_id ON messages(chat_id)",
            "CREATE INDEX IF NOT EXISTS idx_messages_created_at ON messages(created_at)",
            "CREATE INDEX IF NOT EXISTS idx_incoming_chat_id ON incoming(chat_id)",
            "CREATE INDEX IF NOT EXISTS idx_incoming_created_at ON incoming(created_at)",
            "CREATE INDEX IF NOT EXISTS idx_stats_date ON stats(date)",
            "CREATE INDEX IF NOT EXISTS idx_errors_created_at ON errors(created_at)"
        ]
        
        for index_sql in indexes:
            await self._connection.execute(index_sql)
    
    async def log_message_sent(
        self,
        chat_id: str,
        chat_name: str,
        message_text: str,
        template_id: Optional[int] = None
    ) -> None:
        """Log sent message"""
        await self._connection.execute(
            """
            INSERT INTO messages (chat_id, chat_name, message_text, template_id, status)
            VALUES (?, ?, ?, ?, 'sent')
            """,
            (chat_id, chat_name, message_text, template_id)
        )
        await self._update_daily_stat('messages_sent')
        await self._connection.commit()
    
    async def log_message_received(
        self,
        chat_id: str,
        chat_name: str,
        sender_id: int,
        sender_name: str,
        message_text: str
    ) -> None:
        """Log received message"""
        await self._connection.execute(
            """
            INSERT INTO incoming (chat_id, chat_name, sender_id, sender_name, message_text)
            VALUES (?, ?, ?, ?, ?)
            """,
            (chat_id, chat_name, sender_id, sender_name, message_text)
        )
        await self._update_daily_stat('messages_received')
        await self._connection.commit()
    
    async def log_error(
        self,
        error_type: str,
        error_message: str,
        context: Optional[str] = None
    ) -> None:
        """Log error"""
        await self._connection.execute(
            """
            INSERT INTO errors (error_type, error_message, context)
            VALUES (?, ?, ?)
            """,
            (error_type, error_message, context)
        )
        await self._update_daily_stat('errors')
        await self._connection.commit()
    
    async def _update_daily_stat(self, field: str) -> None:
        """Update daily statistics"""
        today = date.today().isoformat()
        
        await self._connection.execute(
            """
            INSERT INTO stats (date, {})
            VALUES (?, 1)
            ON CONFLICT(date) DO UPDATE SET
                {} = {} + 1,
                updated_at = CURRENT_TIMESTAMP
            """.format(field, field, field),
            (today,)
        )
    
    async def get_today_stats(self) -> Dict[str, int]:
        """Get statistics for today"""
        today = date.today().isoformat()
        
        cursor = await self._connection.execute(
            "SELECT messages_sent, messages_received, errors FROM stats WHERE date = ?",
            (today,)
        )
        row = await cursor.fetchone()
        
        if row:
            return {
                'messages_sent': row[0],
                'messages_received': row[1],
                'errors': row[2]
            }
        
        return {'messages_sent': 0, 'messages_received': 0, 'errors': 0}
    
    async def get_messages_count_today(self) -> int:
        """Get count of messages sent today"""
        stats = await self.get_today_stats()
        return stats['messages_sent']
    
    async def mark_replied(self, incoming_id: int) -> None:
        """Mark incoming message as replied"""
        await self._connection.execute(
            "UPDATE incoming SET replied = 1 WHERE id = ?",
            (incoming_id,)
        )
        await self._connection.commit()
    
    async def get_recent_incoming(self, limit: int = 10) -> List[Dict[str, Any]]:
        """Get recent incoming messages"""
        cursor = await self._connection.execute(
            """
            SELECT id, chat_id, chat_name, sender_id, sender_name, message_text, replied, created_at
            FROM incoming
            ORDER BY created_at DESC
            LIMIT ?
            """,
            (limit,)
        )
        
        rows = await cursor.fetchall()
        return [
            {
                'id': row[0],
                'chat_id': row[1],
                'chat_name': row[2],
                'sender_id': row[3],
                'sender_name': row[4],
                'message_text': row[5],
                'replied': row[6],
                'created_at': row[7]
            }
            for row in rows
        ]
    
    async def close(self) -> None:
        """Close database connection"""
        if self._connection:
            await self._connection.close()
