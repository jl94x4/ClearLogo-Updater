"""Utility functions for P Logo Updater."""

import json
import logging
import os
import sys
from pathlib import Path
from typing import Dict, Optional, Tuple, Any
from urllib.parse import urlparse

from plexapi.server import PlexServer

logger = logging.getLogger(__name__)


class ConfigurationError(Exception):
    """Raised when configuration is invalid."""
    pass


def setup_logging(verbose: bool = False, log_file: Optional[str] = None) -> None:
    """
    Configure logging for the application.

    Args:
        verbose: Enable debug level logging
        log_file: Optional file path for log output
    """
    log_level = logging.DEBUG if verbose else logging.INFO
    log_format = '%(asctime)s - %(name)s - %(levelname)s - %(message)s'

    handlers = [logging.StreamHandler(sys.stdout)]
    if log_file:
        handlers.append(logging.FileHandler(log_file))

    logging.basicConfig(
        level=log_level,
        format=log_format,
        handlers=handlers
    )


def validate_url(url: str) -> bool:
    """
    Validate that a URL is properly formatted.

    Args:
        url: URL string to validate

    Returns:
        True if valid, False otherwise
    """
    try:
        result = urlparse(url)
        return all([result.scheme, result.netloc]) and result.scheme in ('http', 'https')
    except Exception:
        return False


def validate_config(config: Dict[str, Any]) -> None:
    """
    Validate configuration dictionary.

    Args:
        config: Configuration dictionary

    Raises:
        ConfigurationError: If configuration is invalid
    """
    required_fields = ['plex_url', 'plex_token']
    missing = [f for f in required_fields if not config.get(f)]

    if missing:
        raise ConfigurationError(f"Missing required config fields: {', '.join(missing)}")

    # Validate URL format
    if not validate_url(config['plex_url']):
        raise ConfigurationError(
            f"Invalid plex_url: {config['plex_url']}. Must start with http:// or https://"
        )

    # Check for placeholder values
    placeholder_values = ['YOUR_PLEX_TOKEN', 'YOUR_SERVER_URL', 'YOUR_PLEX_TOKEN_HERE']
    if any(config.get('plex_token') == placeholder for placeholder in placeholder_values):
        raise ConfigurationError(
            "plex_token still contains placeholder value. Please set actual token."
        )

    # Validate fanart_key_type if present
    if 'fanart_key_type' in config:
        valid_types = ['free', 'paid']
        if config['fanart_key_type'].lower() not in valid_types:
            raise ConfigurationError(
                f"Invalid fanart_key_type: {config['fanart_key_type']}. "
                f"Must be one of: {', '.join(valid_types)}"
            )


def load_config(config_file: str = 'config.json') -> Dict[str, Any]:
    """
    Load configuration from JSON file or environment variables.

    Args:
        config_file: Path to configuration file

    Returns:
        Configuration dictionary

    Raises:
        ConfigurationError: If configuration cannot be loaded or is invalid
    """
    config: Dict[str, Any] = {}

    # Try environment variables first
    plex_url = os.environ.get('PLEX_URL')
    plex_token = os.environ.get('PLEX_TOKEN')
    fanart_api_key = os.environ.get('FANART_API_KEY')

    if plex_url and plex_token:
        logger.info("Loaded Plex credentials from environment variables")
        config['plex_url'] = plex_url
        config['plex_token'] = plex_token
        if fanart_api_key:
            config['fanart_api_key'] = fanart_api_key

    # Load from file (can override or supplement env vars)
    try:
        config_path = Path(config_file)
        if config_path.exists():
            with open(config_path, 'r') as f:
                file_config = json.load(f)
                # File config takes precedence over env vars
                config.update(file_config)
            logger.info(f"Loaded configuration from {config_file}")
        elif not config:
            raise ConfigurationError(f"Configuration file '{config_file}' not found")
    except json.JSONDecodeError as e:
        raise ConfigurationError(f"Invalid JSON in '{config_file}': {e}")
    except Exception as e:
        if not config:  # Only raise if we don't have env var config
            raise ConfigurationError(f"Error reading config file: {e}")

    # Apply defaults
    config.setdefault('fanart_key_type', 'free')
    config.setdefault('connection_timeout', 60)
    config.setdefault('request_timeout', 10)
    config.setdefault('max_workers', 5)
    config.setdefault('enable_backup', False)
    config.setdefault('backup_dir', 'backups')

    # Validate configuration
    validate_config(config)

    return config


def connect_plex(url: str, token: str, timeout: int = 60) -> Optional[PlexServer]:
    """
    Connect to Plex server with error handling.

    Args:
        url: Plex server URL
        token: Plex authentication token
        timeout: Connection timeout in seconds

    Returns:
        PlexServer instance or None on failure
    """
    try:
        logger.info(f"Connecting to Plex server at {url}...")
        plex = PlexServer(url, token, timeout=timeout)
        logger.info(f"Successfully connected to Plex server: {plex.friendlyName}")
        return plex
    except Exception as e:
        logger.error(f"Error connecting to Plex: {e}")
        logger.error("Check URL, token, server status, and network connection.")
        return None


def sanitize_url_for_logging(url: str) -> str:
    """
    Remove sensitive information (API keys) from URLs for logging.

    Args:
        url: URL that may contain sensitive information

    Returns:
        Sanitized URL safe for logging
    """
    if 'api_key=' in url:
        return url.split('api_key=')[0] + 'api_key=***REDACTED***'
    return url


def format_statistics(stats: Dict[str, Any]) -> str:
    """
    Format statistics dictionary for display.

    Args:
        stats: Statistics dictionary

    Returns:
        Formatted string
    """
    total = stats.get('processed', 0)
    success_rate = (stats.get('updated', 0) / total * 100) if total > 0 else 0

    output = [
        "\n=== STATISTICS ===",
        f"Total processed:     {stats.get('processed', 0)}",
        f"Successfully updated: {stats.get('updated', 0)}",
        f"Skipped:             {stats.get('skipped', 0)}",
        f"Failed:              {stats.get('failed', 0)}",
        f"Success rate:        {success_rate:.1f}%",
    ]

    if stats.get('errors'):
        output.append(f"\nErrors encountered: {len(stats['errors'])}")
        for error in stats['errors'][:5]:  # Show first 5 errors
            output.append(f"  - {error}")
        if len(stats['errors']) > 5:
            output.append(f"  ... and {len(stats['errors']) - 5} more")

    return '\n'.join(output)
