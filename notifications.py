"""Notification module for webhooks and alerts."""

import logging
from typing import Dict, Any, Optional
import requests

logger = logging.getLogger(__name__)


class NotificationError(Exception):
    """Raised when notification fails."""
    pass


def send_webhook(
    webhook_url: str,
    message: str,
    stats: Optional[Dict[str, Any]] = None,
    timeout: int = 10
) -> bool:
    """
    Send notification to webhook endpoint.

    Supports Discord, Slack, and generic webhooks.

    Args:
        webhook_url: Webhook URL
        message: Message to send
        stats: Optional statistics dictionary
        timeout: Request timeout in seconds

    Returns:
        True if successful, False otherwise
    """
    if not webhook_url:
        return False

    try:
        # Detect webhook type and format accordingly
        if 'discord.com' in webhook_url:
            payload = _format_discord_message(message, stats)
        elif 'slack.com' in webhook_url:
            payload = _format_slack_message(message, stats)
        else:
            payload = {'text': message}

        response = requests.post(
            webhook_url,
            json=payload,
            timeout=timeout,
            headers={'Content-Type': 'application/json'}
        )
        response.raise_for_status()
        logger.info("Notification sent successfully")
        return True

    except requests.exceptions.RequestException as e:
        logger.error(f"Failed to send notification: {e}")
        return False
    except Exception as e:
        logger.error(f"Unexpected error sending notification: {e}")
        return False


def _format_discord_message(message: str, stats: Optional[Dict[str, Any]] = None) -> Dict:
    """Format message for Discord webhook."""
    embed = {
        "title": "P Logo Updater",
        "description": message,
        "color": 3447003  # Blue
    }

    if stats:
        fields = []
        if 'processed' in stats:
            fields.append({
                "name": "Processed",
                "value": str(stats['processed']),
                "inline": True
            })
        if 'updated' in stats:
            fields.append({
                "name": "Updated",
                "value": str(stats['updated']),
                "inline": True
            })
        if 'failed' in stats:
            fields.append({
                "name": "Failed",
                "value": str(stats['failed']),
                "inline": True
            })

        if fields:
            embed["fields"] = fields

    return {"embeds": [embed]}


def _format_slack_message(message: str, stats: Optional[Dict[str, Any]] = None) -> Dict:
    """Format message for Slack webhook."""
    payload = {
        "text": message,
        "username": "P Logo Updater"
    }

    if stats:
        blocks = [
            {
                "type": "section",
                "text": {
                    "type": "mrkdwn",
                    "text": message
                }
            }
        ]

        fields = []
        if 'processed' in stats:
            fields.append({
                "type": "mrkdwn",
                "text": f"*Processed:*\n{stats['processed']}"
            })
        if 'updated' in stats:
            fields.append({
                "type": "mrkdwn",
                "text": f"*Updated:*\n{stats['updated']}"
            })
        if 'failed' in stats:
            fields.append({
                "type": "mrkdwn",
                "text": f"*Failed:*\n{stats['failed']}"
            })

        if fields:
            blocks.append({
                "type": "section",
                "fields": fields
            })

        payload["blocks"] = blocks

    return payload


def send_completion_notification(
    webhook_url: str,
    stats: Dict[str, Any],
    duration: float
) -> bool:
    """
    Send completion notification with statistics.

    Args:
        webhook_url: Webhook URL
        stats: Statistics dictionary
        duration: Execution duration in seconds

    Returns:
        True if successful, False otherwise
    """
    total = stats.get('processed', 0)
    success_rate = (stats.get('updated', 0) / total * 100) if total > 0 else 0

    message = (
        f"Logo update completed in {duration:.1f}s\n"
        f"Success rate: {success_rate:.1f}%"
    )

    return send_webhook(webhook_url, message, stats)


def send_error_notification(
    webhook_url: str,
    error_message: str
) -> bool:
    """
    Send error notification.

    Args:
        webhook_url: Webhook URL
        error_message: Error message

    Returns:
        True if successful, False otherwise
    """
    message = f"⚠️ Error in P Logo Updater: {error_message}"
    return send_webhook(webhook_url, message)
