"""Tests for utils module."""

import pytest
import json
from pathlib import Path
from unittest.mock import mock_open, patch, MagicMock

from utils import (
    validate_url,
    validate_config,
    load_config,
    sanitize_url_for_logging,
    format_statistics,
    ConfigurationError
)


class TestValidateUrl:
    """Tests for URL validation."""

    def test_valid_http_url(self):
        assert validate_url("http://localhost:32400") is True

    def test_valid_https_url(self):
        assert validate_url("https://plex.example.com:32400") is True

    def test_invalid_url_no_scheme(self):
        assert validate_url("localhost:32400") is False

    def test_invalid_url_empty(self):
        assert validate_url("") is False

    def test_invalid_url_malformed(self):
        assert validate_url("not a url at all") is False


class TestValidateConfig:
    """Tests for configuration validation."""

    def test_valid_config(self):
        config = {
            'plex_url': 'http://localhost:32400',
            'plex_token': 'valid_token_123'
        }
        # Should not raise exception
        validate_config(config)

    def test_missing_plex_url(self):
        config = {'plex_token': 'token'}
        with pytest.raises(ConfigurationError, match="Missing required config fields"):
            validate_config(config)

    def test_missing_plex_token(self):
        config = {'plex_url': 'http://localhost:32400'}
        with pytest.raises(ConfigurationError, match="Missing required config fields"):
            validate_config(config)

    def test_invalid_plex_url_format(self):
        config = {
            'plex_url': 'not_a_valid_url',
            'plex_token': 'token'
        }
        with pytest.raises(ConfigurationError, match="Invalid plex_url"):
            validate_config(config)

    def test_placeholder_token(self):
        config = {
            'plex_url': 'http://localhost:32400',
            'plex_token': 'YOUR_PLEX_TOKEN'
        }
        with pytest.raises(ConfigurationError, match="placeholder value"):
            validate_config(config)

    def test_invalid_fanart_key_type(self):
        config = {
            'plex_url': 'http://localhost:32400',
            'plex_token': 'valid_token',
            'fanart_key_type': 'invalid_type'
        }
        with pytest.raises(ConfigurationError, match="Invalid fanart_key_type"):
            validate_config(config)

    def test_valid_fanart_key_type_free(self):
        config = {
            'plex_url': 'http://localhost:32400',
            'plex_token': 'valid_token',
            'fanart_key_type': 'free'
        }
        validate_config(config)

    def test_valid_fanart_key_type_paid(self):
        config = {
            'plex_url': 'http://localhost:32400',
            'plex_token': 'valid_token',
            'fanart_key_type': 'paid'
        }
        validate_config(config)


class TestLoadConfig:
    """Tests for configuration loading."""

    def test_load_from_file(self):
        config_data = {
            'plex_url': 'http://localhost:32400',
            'plex_token': 'test_token'
        }

        m = mock_open(read_data=json.dumps(config_data))
        with patch('builtins.open', m), patch('pathlib.Path.exists', return_value=True):
            config = load_config('test_config.json')

        assert config['plex_url'] == 'http://localhost:32400'
        assert config['plex_token'] == 'test_token'
        # Check defaults
        assert config['fanart_key_type'] == 'free'
        assert config['connection_timeout'] == 60

    def test_load_from_env_vars(self):
        with patch.dict('os.environ', {
            'PLEX_URL': 'http://env.test:32400',
            'PLEX_TOKEN': 'env_token'
        }), patch('pathlib.Path.exists', return_value=False):
            config = load_config('nonexistent.json')

        assert config['plex_url'] == 'http://env.test:32400'
        assert config['plex_token'] == 'env_token'

    def test_file_not_found_no_env(self):
        with patch('pathlib.Path.exists', return_value=False), \
             patch.dict('os.environ', {}, clear=True):
            with pytest.raises(ConfigurationError, match="not found"):
                load_config('nonexistent.json')

    def test_invalid_json(self):
        m = mock_open(read_data="invalid json {")
        with patch('builtins.open', m), patch('pathlib.Path.exists', return_value=True):
            with pytest.raises(ConfigurationError, match="Invalid JSON"):
                load_config('test_config.json')


class TestSanitizeUrl:
    """Tests for URL sanitization."""

    def test_sanitize_api_key(self):
        url = "http://example.com/api?api_key=secret123&other=param"
        sanitized = sanitize_url_for_logging(url)
        assert "secret123" not in sanitized
        assert "***REDACTED***" in sanitized

    def test_no_api_key(self):
        url = "http://example.com/api?other=param"
        sanitized = sanitize_url_for_logging(url)
        assert sanitized == url


class TestFormatStatistics:
    """Tests for statistics formatting."""

    def test_format_basic_stats(self):
        stats = {
            'processed': 100,
            'updated': 75,
            'skipped': 20,
            'failed': 5
        }
        output = format_statistics(stats)

        assert "100" in output
        assert "75" in output
        assert "75.0%" in output  # Success rate

    def test_format_with_errors(self):
        stats = {
            'processed': 10,
            'updated': 5,
            'skipped': 3,
            'failed': 2,
            'errors': ['Error 1', 'Error 2', 'Error 3']
        }
        output = format_statistics(stats)

        assert "Error 1" in output
        assert "Error 2" in output

    def test_zero_processed(self):
        stats = {'processed': 0, 'updated': 0, 'skipped': 0, 'failed': 0}
        output = format_statistics(stats)
        assert "0.0%" in output  # Should handle division by zero
