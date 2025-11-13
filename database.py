"""Database module for tracking processed items."""

import logging
import sqlite3
from datetime import datetime
from pathlib import Path
from typing import Optional, List, Tuple

logger = logging.getLogger(__name__)


class LogoDatabase:
    """SQLite database for tracking logo updates."""

    def __init__(self, db_path: str = 'logo_history.db'):
        """
        Initialize database connection.

        Args:
            db_path: Path to SQLite database file
        """
        self.db_path = db_path
        self.conn: Optional[sqlite3.Connection] = None
        self._init_db()

    def _init_db(self) -> None:
        """Create database tables if they don't exist."""
        try:
            self.conn = sqlite3.connect(self.db_path)
            self.conn.execute('''
                CREATE TABLE IF NOT EXISTS processed_items (
                    item_id TEXT PRIMARY KEY,
                    item_title TEXT NOT NULL,
                    item_type TEXT NOT NULL,
                    processed_at TIMESTAMP NOT NULL,
                    logo_url TEXT,
                    status TEXT NOT NULL,
                    error_message TEXT
                )
            ''')
            self.conn.execute('''
                CREATE INDEX IF NOT EXISTS idx_processed_at
                ON processed_items(processed_at)
            ''')
            self.conn.execute('''
                CREATE INDEX IF NOT EXISTS idx_status
                ON processed_items(status)
            ''')
            self.conn.commit()
            logger.debug(f"Database initialized at {self.db_path}")
        except sqlite3.Error as e:
            logger.error(f"Database initialization error: {e}")
            raise

    def record_item(
        self,
        item_id: str,
        item_title: str,
        item_type: str,
        logo_url: Optional[str],
        status: str,
        error_message: Optional[str] = None
    ) -> None:
        """
        Record a processed item in the database.

        Args:
            item_id: Unique item identifier
            item_title: Item title
            item_type: Type of item (movie, show, etc.)
            logo_url: URL of applied logo
            status: Processing status (success, skipped, failed)
            error_message: Optional error message
        """
        if not self.conn:
            logger.warning("Database connection not available")
            return

        try:
            self.conn.execute('''
                INSERT OR REPLACE INTO processed_items
                (item_id, item_title, item_type, processed_at, logo_url, status, error_message)
                VALUES (?, ?, ?, ?, ?, ?, ?)
            ''', (
                item_id,
                item_title,
                item_type,
                datetime.now().isoformat(),
                logo_url,
                status,
                error_message
            ))
            self.conn.commit()
        except sqlite3.Error as e:
            logger.error(f"Error recording item: {e}")

    def was_processed(
        self,
        item_id: str,
        max_age_days: Optional[int] = None
    ) -> bool:
        """
        Check if an item was already processed.

        Args:
            item_id: Item identifier to check
            max_age_days: Optional max age in days to consider

        Returns:
            True if item was processed, False otherwise
        """
        if not self.conn:
            return False

        try:
            if max_age_days:
                query = '''
                    SELECT COUNT(*) FROM processed_items
                    WHERE item_id = ?
                    AND status = 'success'
                    AND datetime(processed_at) > datetime('now', '-' || ? || ' days')
                '''
                cursor = self.conn.execute(query, (item_id, max_age_days))
            else:
                query = '''
                    SELECT COUNT(*) FROM processed_items
                    WHERE item_id = ? AND status = 'success'
                '''
                cursor = self.conn.execute(query, (item_id,))

            count = cursor.fetchone()[0]
            return count > 0
        except sqlite3.Error as e:
            logger.error(f"Error checking if item was processed: {e}")
            return False

    def get_statistics(self) -> dict:
        """
        Get processing statistics from database.

        Returns:
            Dictionary with statistics
        """
        if not self.conn:
            return {}

        try:
            cursor = self.conn.execute('''
                SELECT
                    status,
                    COUNT(*) as count
                FROM processed_items
                GROUP BY status
            ''')
            stats = {row[0]: row[1] for row in cursor.fetchall()}

            cursor = self.conn.execute('''
                SELECT COUNT(DISTINCT item_id) as total
                FROM processed_items
            ''')
            stats['total_unique_items'] = cursor.fetchone()[0]

            return stats
        except sqlite3.Error as e:
            logger.error(f"Error getting statistics: {e}")
            return {}

    def get_recent_failures(self, limit: int = 10) -> List[Tuple[str, str, str]]:
        """
        Get recent failed items.

        Args:
            limit: Maximum number of failures to return

        Returns:
            List of (title, error_message, processed_at) tuples
        """
        if not self.conn:
            return []

        try:
            cursor = self.conn.execute('''
                SELECT item_title, error_message, processed_at
                FROM processed_items
                WHERE status = 'failed'
                ORDER BY processed_at DESC
                LIMIT ?
            ''', (limit,))
            return cursor.fetchall()
        except sqlite3.Error as e:
            logger.error(f"Error getting recent failures: {e}")
            return []

    def clear_old_records(self, days: int = 90) -> int:
        """
        Clear records older than specified days.

        Args:
            days: Age threshold in days

        Returns:
            Number of records deleted
        """
        if not self.conn:
            return 0

        try:
            cursor = self.conn.execute('''
                DELETE FROM processed_items
                WHERE datetime(processed_at) < datetime('now', '-' || ? || ' days')
            ''', (days,))
            self.conn.commit()
            deleted = cursor.rowcount
            logger.info(f"Cleared {deleted} records older than {days} days")
            return deleted
        except sqlite3.Error as e:
            logger.error(f"Error clearing old records: {e}")
            return 0

    def close(self) -> None:
        """Close database connection."""
        if self.conn:
            self.conn.close()
            logger.debug("Database connection closed")

    def __enter__(self):
        """Context manager entry."""
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        """Context manager exit."""
        self.close()
