"""Tests for notifications module."""

import pytest
from unittest.mock import patch, MagicMock
import requests

from notifications import (
    send_webhook,
    send_completion_notification,
    send_error_notification,
    _format_discord_message,
    _format_slack_message
)


class TestFormatMessages:
    """Tests for message formatting."""

    def test_format_discord_message_basic(self):
        """Test basic Discord message format."""
        message = "Test message"
        payload = _format_discord_message(message, None)

        assert 'embeds' in payload
        assert payload['embeds'][0]['description'] == message

    def test_format_discord_message_with_stats(self):
        """Test Discord message with statistics."""
        message = "Test message"
        stats = {
            'processed': 100,
            'updated': 75,
            'failed': 5
        }
        payload = _format_discord_message(message, stats)

        assert 'embeds' in payload
        assert 'fields' in payload['embeds'][0]
        fields = payload['embeds'][0]['fields']
        assert len(fields) == 3

    def test_format_slack_message_basic(self):
        """Test basic Slack message format."""
        message = "Test message"
        payload = _format_slack_message(message, None)

        assert payload['text'] == message
        assert payload['username'] == "P Logo Updater"

    def test_format_slack_message_with_stats(self):
        """Test Slack message with statistics."""
        message = "Test message"
        stats = {
            'processed': 100,
            'updated': 75,
            'failed': 5
        }
        payload = _format_slack_message(message, stats)

        assert 'blocks' in payload
        assert len(payload['blocks']) >= 2  # Text block + fields block


class TestSendWebhook:
    """Tests for webhook sending."""

    @patch('notifications.requests.post')
    def test_send_webhook_discord_success(self, mock_post):
        """Test successful Discord webhook."""
        mock_response = MagicMock()
        mock_response.raise_for_status = MagicMock()
        mock_post.return_value = mock_response

        url = "https://discord.com/api/webhooks/123/abc"
        result = send_webhook(url, "Test message")

        assert result is True
        mock_post.assert_called_once()

    @patch('notifications.requests.post')
    def test_send_webhook_slack_success(self, mock_post):
        """Test successful Slack webhook."""
        mock_response = MagicMock()
        mock_response.raise_for_status = MagicMock()
        mock_post.return_value = mock_response

        url = "https://hooks.slack.com/services/T00/B00/XXX"
        result = send_webhook(url, "Test message")

        assert result is True
        mock_post.assert_called_once()

    @patch('notifications.requests.post')
    def test_send_webhook_generic(self, mock_post):
        """Test generic webhook."""
        mock_response = MagicMock()
        mock_response.raise_for_status = MagicMock()
        mock_post.return_value = mock_response

        url = "https://example.com/webhook"
        result = send_webhook(url, "Test message")

        assert result is True
        # Check that payload has generic format
        call_args = mock_post.call_args
        assert 'text' in call_args[1]['json']

    @patch('notifications.requests.post')
    def test_send_webhook_failure(self, mock_post):
        """Test webhook failure handling."""
        mock_post.side_effect = requests.exceptions.RequestException("Network error")

        url = "https://example.com/webhook"
        result = send_webhook(url, "Test message")

        assert result is False

    def test_send_webhook_empty_url(self):
        """Test with empty URL."""
        result = send_webhook("", "Test message")
        assert result is False

    def test_send_webhook_none_url(self):
        """Test with None URL."""
        result = send_webhook(None, "Test message")
        assert result is False

    @patch('notifications.requests.post')
    def test_send_webhook_timeout(self, mock_post):
        """Test webhook timeout handling."""
        mock_post.side_effect = requests.exceptions.Timeout("Timeout")

        url = "https://example.com/webhook"
        result = send_webhook(url, "Test message", timeout=1)

        assert result is False


class TestNotificationHelpers:
    """Tests for notification helper functions."""

    @patch('notifications.send_webhook')
    def test_send_completion_notification(self, mock_send):
        """Test completion notification."""
        mock_send.return_value = True

        stats = {
            'processed': 100,
            'updated': 75,
            'skipped': 20,
            'failed': 5
        }

        result = send_completion_notification(
            "https://example.com/webhook",
            stats,
            duration=123.45
        )

        assert result is True
        mock_send.assert_called_once()

        # Check that call included stats
        call_args = mock_send.call_args
        assert call_args[0][1] is not None  # message
        assert call_args[0][2] == stats  # stats

    @patch('notifications.send_webhook')
    def test_send_error_notification(self, mock_send):
        """Test error notification."""
        mock_send.return_value = True

        result = send_error_notification(
            "https://example.com/webhook",
            "Something went wrong"
        )

        assert result is True
        mock_send.assert_called_once()

        # Check that message includes error
        call_args = mock_send.call_args
        message = call_args[0][1]
        assert "Something went wrong" in message
        assert "Error" in message or "⚠️" in message
