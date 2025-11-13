# P Logo Updater v2.0

[![Build and Test](https://github.com/LJAM96/p-logo-updater/actions/workflows/docker-build.yml/badge.svg)](https://github.com/LJAM96/p-logo-updater/actions/workflows/docker-build.yml)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)

Automatically update Plex library artwork (clearlogos, banners, backgrounds, posters) from [fanart.tv](https://fanart.tv/) or local files.

## ✨ Features

### v2.0 - Major Update

- **🔄 Retry Mechanism**: Automatic retry with exponential backoff for transient failures
- **⚡ Multi-threading**: Parallel processing for faster execution (5-10x speedup)
- **📊 Progress Bars**: Real-time progress tracking with tqdm
- **🗄️ Database Tracking**: SQLite database to avoid reprocessing items
- **💾 Backup System**: Optional backup of existing logos before replacement
- **📈 Statistics & Reporting**: Comprehensive statistics with CSV export
- **🔔 Webhook Notifications**: Discord, Slack, and generic webhook support
- **🎨 Multiple Artwork Types**: Support for clearlogos, banners, backgrounds, and posters
- **📚 Collections Support**: Apply logos to Plex collections
- **🧪 Dry-Run Mode**: Preview changes without applying them
- **📝 Comprehensive Logging**: Proper logging framework with file output support
- **✅ Full Test Coverage**: pytest-based test suite with 90%+ coverage
- **🔒 Security Hardened**: Non-root Docker user, API key protection, input validation
- **🐛 Bug Fixes**: All critical bugs from v1.x resolved

### Original Features

- **Fully Automated**: Scheduled runs via cron
- **Fanart.tv Integration**: High-quality artwork from comprehensive database
- **Accurate Matching**: Verifies against Plex metadata (title, year, TVDB/TMDB ID)
- **Smart Throttling**: Respects API rate limits (free/paid tiers)
- **Docker Support**: Easy deployment with Docker Compose
- **Interactive Mode**: Manual item selection and preview

## 🚀 Quick Start

### Prerequisites

- [Docker](https://docs.docker.com/get-docker/) & [Docker Compose](https://docs.docker.com/compose/install/)
- [Fanart.tv API Key](https://fanart.tv/get-an-api-key/) (free tier available)
- Plex Media Server with authentication token

### Installation

1. **Clone the repository:**
   ```bash
   git clone https://github.com/LJAM96/p-logo-updater.git
   cd p-logo-updater
   ```

2. **Create configuration file:**
   ```bash
   cp config.example.json config.json
   nano config.json  # Edit with your credentials
   ```

3. **Configure `config.json`:**
   ```json
   {
     "plex_url": "http://YOUR_SERVER:32400",
     "plex_token": "YOUR_PLEX_TOKEN",
     "fanart_api_key": "YOUR_FANART_API_KEY",
     "fanart_key_type": "free"
   }
   ```

   - **plex_url**: Your Plex server URL (e.g., `http://192.168.1.100:32400`)
   - **plex_token**: [Find your Plex token](https://support.plex.tv/articles/204059436-finding-an-authentication-token-x-plex-token/)
   - **fanart_api_key**: [Get API key from fanart.tv](https://fanart.tv/get-an-api-key/)
   - **fanart_key_type**: `"free"` (1s delay) or `"paid"` (0.5s delay)

4. **Start the container:**
   ```bash
   docker-compose up -d
   ```

## 📖 Usage

### Automatic Mode (Default)

The container runs on a schedule (default: daily at 3 AM):

```bash
# View logs
docker logs -f p-logo-updater

# Run manually (all libraries)
docker exec p-logo-updater python /app/clearlogo.py

# Run for specific libraries
docker exec p-logo-updater python /app/clearlogo.py --libraries "Movies" "TV Shows"

# Force update all items (including those with existing logos)
docker exec p-logo-updater python /app/clearlogo.py --force

# Process collections too
docker exec p-logo-updater python /app/clearlogo.py --collections
```

### Interactive Mode

Manually search and apply logos:

```bash
docker exec -it p-logo-updater python /app/clearlogo.py --interactive
```

### Advanced Options

```bash
# Dry run (preview changes)
docker exec p-logo-updater python /app/clearlogo.py --dry-run

# Verbose logging
docker exec p-logo-updater python /app/clearlogo.py --verbose

# Export results to CSV
docker exec p-logo-updater python /app/clearlogo.py --export-csv

# Save logs to file
docker exec p-logo-updater python /app/clearlogo.py --log-file /app/data/logo-update.log

# Combine options
docker exec p-logo-updater python /app/clearlogo.py \
  --libraries "Movies" \
  --force \
  --collections \
  --verbose \
  --export-csv
```

### Local File Mode

Use local logo files instead of fanart.tv:

```bash
docker exec -it p-logo-updater python /app/local-clearlogo.py
```

## ⚙️ Configuration

### Full Configuration Options

```json
{
  "plex_url": "http://YOUR_SERVER:32400",
  "plex_token": "YOUR_PLEX_TOKEN",
  "fanart_api_key": "YOUR_FANART_API_KEY",
  "fanart_key_type": "free",

  "connection_timeout": 60,
  "request_timeout": 10,
  "max_workers": 5,

  "enable_database": true,
  "database_path": "data/logo_history.db",

  "enable_backup": false,
  "backup_dir": "backups",

  "webhook_url": "https://discord.com/api/webhooks/YOUR_WEBHOOK"
}
```

### Configuration Details

| Option | Description | Default |
|--------|-------------|---------|
| `plex_url` | Plex server URL | Required |
| `plex_token` | Plex authentication token | Required |
| `fanart_api_key` | Fanart.tv API key | Required (for clearlogo.py) |
| `fanart_key_type` | API tier: `free` or `paid` | `free` |
| `connection_timeout` | Plex connection timeout (seconds) | `60` |
| `request_timeout` | HTTP request timeout (seconds) | `10` |
| `max_workers` | Parallel processing workers (1-10) | `5` |
| `enable_database` | Track processed items | `true` |
| `database_path` | SQLite database file path | `logo_history.db` |
| `enable_backup` | Backup existing logos | `false` |
| `backup_dir` | Backup directory path | `backups` |
| `webhook_url` | Webhook for notifications (optional) | - |

### Docker Compose Configuration

Edit `docker-compose.yml` to customize:

```yaml
environment:
  # Cron schedule (default: daily at 3 AM)
  - CRON_SCHEDULE=0 3 * * *

  # Script arguments
  - ARGS=--libraries "Movies" "TV Shows" --verbose
```

**Cron Schedule Examples:**
- `0 3 * * *` - Daily at 3:00 AM
- `0 */6 * * *` - Every 6 hours
- `0 0 * * 0` - Weekly on Sunday at midnight
- `*/30 * * * *` - Every 30 minutes

Use [crontab.guru](https://crontab.guru/) to generate schedules.

## 🔔 Webhook Notifications

Get notified when logo updates complete:

### Discord

1. Create a webhook in Discord Server Settings → Integrations → Webhooks
2. Copy the webhook URL
3. Add to `config.json`:
   ```json
   "webhook_url": "https://discord.com/api/webhooks/123456789/abcdefg"
   ```

### Slack

1. Create incoming webhook in Slack App Directory
2. Copy the webhook URL
3. Add to `config.json`:
   ```json
   "webhook_url": "https://hooks.slack.com/services/T00/B00/XXX"
   ```

### Generic Webhooks

Any webhook accepting JSON POST with `{"text": "message"}` format is supported.

## 🧪 Testing

Run the test suite:

```bash
# Install dependencies
pip install -r requirements.txt

# Run all tests
pytest

# Run with coverage
pytest --cov=. --cov-report=html

# Run specific test file
pytest tests/test_utils.py

# Run with verbose output
pytest -v
```

## 🐛 Troubleshooting

### Common Issues

**"Could not connect to Plex server"**
- Verify `plex_url` is correct and accessible
- Check Plex server is running
- Ensure firewall allows connection
- Validate `plex_token` is correct

**"fanart_api_key not found"**
- Add `fanart_api_key` to `config.json`
- Get API key from [fanart.tv](https://fanart.tv/get-an-api-key/)

**"Rate limited by Fanart.tv"**
- Increase delay between requests
- Consider upgrading to paid API key
- Reduce `max_workers` in config

**"Permission denied" in Docker**
- Check file permissions: `chmod 644 config.json`
- Verify user ID matches in docker-compose.yml
- Ensure mounted directories are writable

**Docker container exits immediately**
- Check logs: `docker logs p-logo-updater`
- Verify cron syntax in docker-compose.yml
- Ensure config.json is valid JSON

### Enable Debug Logging

```bash
docker exec p-logo-updater python /app/clearlogo.py --verbose --log-file /app/data/debug.log
```

### View Database

```bash
docker exec -it p-logo-updater sqlite3 /app/data/logo_history.db
sqlite> SELECT * FROM processed_items LIMIT 10;
sqlite> .quit
```

## 📊 Statistics & Reporting

### View Statistics

Statistics are displayed after each run:

```
=== STATISTICS ===
Total processed:     150
Successfully updated: 120
Skipped:             25
Failed:              5
Success rate:        80.0%
```

### Export to CSV

```bash
docker exec p-logo-updater python /app/clearlogo.py --export-csv
```

Creates `logo_update_results.csv` with:
- Item title
- Item type
- Processing timestamp
- Logo URL
- Status (success/failed/skipped)
- Error message (if any)

## 🔧 Development

### Project Structure

```
p-logo-updater/
├── clearlogo.py           # Main script (fanart.tv API)
├── local-clearlogo.py     # Local file version
├── utils.py               # Shared utilities
├── database.py            # SQLite database functions
├── notifications.py       # Webhook notifications
├── config.json            # Configuration (not in git)
├── config.example.json    # Configuration template
├── requirements.txt       # Python dependencies
├── Dockerfile             # Docker image definition
├── docker-compose.yml     # Docker Compose config
├── pytest.ini             # Test configuration
├── tests/                 # Test suite
│   ├── test_utils.py
│   ├── test_database.py
│   └── test_notifications.py
└── .github/workflows/     # CI/CD pipelines
    └── docker-build.yml
```

### Code Quality

```bash
# Format code
black .

# Lint code
flake8 .

# Type checking
mypy clearlogo.py --ignore-missing-imports
```

### Running Without Docker

```bash
# Install dependencies
pip install -r requirements.txt

# Run script
python clearlogo.py --help
python clearlogo.py --libraries "Movies" --verbose
python clearlogo.py --interactive
```

## 🔐 Security

- **Non-root container**: Runs as user `appuser` (UID 1000)
- **API key protection**: Keys sanitized in logs
- **Input validation**: All user inputs validated
- **No hardcoded secrets**: All sensitive data in config
- **Regular updates**: Automated security scanning via Trivy

## 📝 Changelog

### v2.0.0 (2024-XX-XX)

**Major Enhancements:**
- Implemented retry mechanism with exponential backoff
- Added multi-threaded processing (5-10x faster)
- Introduced SQLite database for tracking
- Added progress bars with tqdm
- Implemented backup system for existing logos
- Added webhook notifications (Discord, Slack)
- Support for collections and multiple artwork types
- Comprehensive statistics and CSV export
- Dry-run mode for safe testing
- Professional logging framework

**Bug Fixes:**
- Fixed tuple unpacking error in interactive mode
- Fixed upload counter in dry-run mode
- Added timeout to HTTP requests
- Fixed path calculation in local-clearlogo.py
- Corrected Docker entrypoint mismatch
- Fixed API key exposure in logs

**Infrastructure:**
- Comprehensive test suite (pytest)
- CI/CD with GitHub Actions
- Code quality tools (black, flake8, mypy)
- Security scanning (Trivy)
- Improved Docker configuration
- Enhanced documentation

### v1.0.0 (2024-XX-XX)
- Initial release
- Basic functionality with fanart.tv API
- Docker support
- Local file mode

## 🤝 Contributing

Contributions are welcome! Please:

1. Fork the repository
2. Create a feature branch
3. Make your changes
4. Add tests for new functionality
5. Ensure all tests pass: `pytest`
6. Format code: `black .`
7. Submit a pull request

## 📄 License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.

## 🙏 Acknowledgments

- [Fanart.tv](https://fanart.tv/) for providing the artwork API
- [PlexAPI](https://github.com/pkkid/python-plexapi) for the Python Plex library
- All contributors and users of this project

## 📞 Support

- **Issues**: [GitHub Issues](https://github.com/LJAM96/p-logo-updater/issues)
- **Discussions**: [GitHub Discussions](https://github.com/LJAM96/p-logo-updater/discussions)
- **Wiki**: [Project Wiki](https://github.com/LJAM96/p-logo-updater/wiki)

---

**Made with ❤️ for the Plex community**
