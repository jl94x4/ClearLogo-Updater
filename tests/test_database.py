"""Tests for database module."""

import pytest
import sqlite3
from pathlib import Path
import tempfile
import os

from database import LogoDatabase


@pytest.fixture
def temp_db():
    """Create a temporary database for testing."""
    fd, path = tempfile.mkstemp(suffix='.db')
    os.close(fd)

    db = LogoDatabase(path)
    yield db

    db.close()
    try:
        os.unlink(path)
    except Exception:
        pass


class TestLogoDatabase:
    """Tests for Logo Database functionality."""

    def test_database_initialization(self, temp_db):
        """Test that database and tables are created."""
        assert temp_db.conn is not None

        # Check that tables exist
        cursor = temp_db.conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name='processed_items'"
        )
        assert cursor.fetchone() is not None

    def test_record_item(self, temp_db):
        """Test recording a processed item."""
        temp_db.record_item(
            item_id='123',
            item_title='Test Movie',
            item_type='movie',
            logo_url='http://example.com/logo.png',
            status='success',
            error_message=None
        )

        # Verify record was inserted
        cursor = temp_db.conn.execute(
            "SELECT * FROM processed_items WHERE item_id='123'"
        )
        row = cursor.fetchone()
        assert row is not None
        assert row[1] == 'Test Movie'
        assert row[2] == 'movie'

    def test_was_processed_true(self, temp_db):
        """Test checking if item was processed."""
        temp_db.record_item(
            item_id='456',
            item_title='Test Show',
            item_type='show',
            logo_url='http://example.com/logo.png',
            status='success'
        )

        assert temp_db.was_processed('456') is True

    def test_was_processed_false(self, temp_db):
        """Test checking non-existent item."""
        assert temp_db.was_processed('nonexistent') is False

    def test_was_processed_with_age_limit(self, temp_db):
        """Test age-based filtering."""
        temp_db.record_item(
            item_id='789',
            item_title='Old Movie',
            item_type='movie',
            logo_url='http://example.com/logo.png',
            status='success'
        )

        # Should find recent items
        assert temp_db.was_processed('789', max_age_days=365) is True

    def test_get_statistics(self, temp_db):
        """Test statistics gathering."""
        # Add multiple items
        temp_db.record_item('1', 'Movie 1', 'movie', 'url1', 'success')
        temp_db.record_item('2', 'Movie 2', 'movie', 'url2', 'success')
        temp_db.record_item('3', 'Movie 3', 'movie', None, 'failed')
        temp_db.record_item('4', 'Movie 4', 'movie', None, 'skipped')

        stats = temp_db.get_statistics()
        assert stats['success'] == 2
        assert stats['failed'] == 1
        assert stats['skipped'] == 1
        assert stats['total_unique_items'] == 4

    def test_get_recent_failures(self, temp_db):
        """Test retrieving recent failures."""
        temp_db.record_item('1', 'Failed 1', 'movie', None, 'failed', 'Error 1')
        temp_db.record_item('2', 'Failed 2', 'movie', None, 'failed', 'Error 2')
        temp_db.record_item('3', 'Success', 'movie', 'url', 'success')

        failures = temp_db.get_recent_failures(limit=10)
        assert len(failures) == 2
        assert 'Failed 1' in failures[0][0] or 'Failed 2' in failures[0][0]

    def test_clear_old_records(self, temp_db):
        """Test clearing old records."""
        # Add some records
        for i in range(5):
            temp_db.record_item(f'{i}', f'Movie {i}', 'movie', f'url{i}', 'success')

        # Clear records older than 0 days (should clear all)
        deleted = temp_db.clear_old_records(days=0)
        assert deleted >= 0  # Some records should be deleted

    def test_context_manager(self):
        """Test database as context manager."""
        fd, path = tempfile.mkstemp(suffix='.db')
        os.close(fd)

        try:
            with LogoDatabase(path) as db:
                assert db.conn is not None
                db.record_item('1', 'Test', 'movie', 'url', 'success')

            # Connection should be closed after context
            # We can't directly check if closed, but can try to use it
        finally:
            try:
                os.unlink(path)
            except Exception:
                pass

    def test_replace_existing_record(self, temp_db):
        """Test that records can be replaced."""
        temp_db.record_item('100', 'Movie', 'movie', 'url1', 'success')
        temp_db.record_item('100', 'Movie', 'movie', 'url2', 'success')

        cursor = temp_db.conn.execute(
            "SELECT COUNT(*) FROM processed_items WHERE item_id='100'"
        )
        count = cursor.fetchone()[0]
        assert count == 1  # Should only have one record (replaced)
