#!/usr/bin/env python3
"""
P Logo Updater - Enhanced version with comprehensive improvements.

Features:
- Automatic and interactive modes
- Retry mechanism with exponential backoff
- Multi-threaded processing
- Database tracking
- Progress bars
- Statistics and CSV export
- Webhook notifications
- Backup system
- Support for collections and multiple artwork types
"""

import argparse
import csv
import json
import logging
import sys
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional, Tuple, Any
from urllib.parse import urlparse

import requests
from plexapi.server import PlexServer
from plexapi.exceptions import BadRequest, NotFound
from tenacity import (
    retry,
    stop_after_attempt,
    wait_exponential,
    retry_if_exception_type
)
from tqdm import tqdm

from utils import (
    setup_logging,
    load_config,
    connect_plex,
    sanitize_url_for_logging,
    format_statistics,
    ConfigurationError
)
from database import LogoDatabase
from notifications import send_completion_notification, send_error_notification

# --- Constants ---
FANART_API_BASE_URL = "http://webservice.fanart.tv/v3/"

ARTWORK_TYPES = {
    'clearlogo': ['hdclearlogo', 'clearlogo'],
    'background': ['moviebackground', 'showbackground'],
    'banner': ['moviebanner', 'tvbanner'],
    'poster': ['movieposter', 'tvposter']
}

logger = logging.getLogger(__name__)


# --- Classes ---

class Statistics:
    """Track processing statistics."""

    def __init__(self):
        self.processed = 0
        self.updated = 0
        self.skipped = 0
        self.failed = 0
        self.errors: List[str] = []
        self.start_time = time.time()

    def add_success(self):
        """Record successful update."""
        self.processed += 1
        self.updated += 1

    def add_skip(self):
        """Record skipped item."""
        self.processed += 1
        self.skipped += 1

    def add_failure(self, error_msg: str):
        """Record failed update."""
        self.processed += 1
        self.failed += 1
        self.errors.append(error_msg)

    def get_duration(self) -> float:
        """Get elapsed time in seconds."""
        return time.time() - self.start_time

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            'processed': self.processed,
            'updated': self.updated,
            'skipped': self.skipped,
            'failed': self.failed,
            'errors': self.errors,
            'duration': self.get_duration()
        }


class LogoUpdater:
    """Main logo updater class with all functionality."""

    def __init__(self, config: Dict[str, Any], dry_run: bool = False):
        """
        Initialize logo updater.

        Args:
            config: Configuration dictionary
            dry_run: If True, don't make actual changes
        """
        self.config = config
        self.dry_run = dry_run
        self.stats = Statistics()
        self.session = requests.Session()  # Connection pooling
        self.session.headers.update({
            'User-Agent': 'P-Logo-Updater/2.0'
        })

        # Initialize database if enabled
        self.db: Optional[LogoDatabase] = None
        if config.get('enable_database', True):
            try:
                self.db = LogoDatabase(config.get('database_path', 'logo_history.db'))
            except Exception as e:
                logger.warning(f"Could not initialize database: {e}")

        # Initialize backup directory if enabled
        if config.get('enable_backup', False):
            self.backup_dir = Path(config.get('backup_dir', 'backups'))
            self.backup_dir.mkdir(parents=True, exist_ok=True)
        else:
            self.backup_dir = None

    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=2, max=10),
        retry=retry_if_exception_type((requests.exceptions.RequestException,)),
        reraise=True
    )
    def get_fanart_logo_url(
        self,
        item: Any,
        api_key: str,
        artwork_type: str = 'clearlogo'
    ) -> Tuple[Optional[str], str]:
        """
        Find artwork URL for a Plex item with retry mechanism.

        Args:
            item: Plex item object
            api_key: Fanart.tv API key
            artwork_type: Type of artwork to fetch

        Returns:
            Tuple of (artwork_url, status_message)
        """
        item_type = 'movies' if item.type == 'movie' else 'tv'
        id_type_to_find = 'tvdb' if item_type == 'tv' else 'tmdb'

        # Extract media ID
        media_id = None
        for guid in item.guids:
            if id_type_to_find in guid.id:
                try:
                    media_id = guid.id.split('//')[1]
                    break
                except IndexError:
                    continue

        if not media_id:
            return None, f"Missing {id_type_to_find.upper()} ID"

        # Build URL with API key in header instead of query string for security
        url = f"{FANART_API_BASE_URL}{item_type}/{media_id}"
        headers = {'api-key': api_key}

        try:
            timeout = self.config.get('request_timeout', 10)
            response = self.session.get(url, headers=headers, timeout=timeout)
            response.raise_for_status()
            data = response.json()

            # Get artwork URLs based on type
            artwork_keys = ARTWORK_TYPES.get(artwork_type, ['hdclearlogo', 'clearlogo'])
            artworks = []
            for key in artwork_keys:
                artworks.extend(data.get(key, []))

            if not artworks:
                return None, f"No {artwork_type} found in Fanart.tv response"

            # Sort by popularity (likes)
            artworks.sort(key=lambda x: int(x.get('likes', 0) or 0), reverse=True)
            return artworks[0]['url'], f"{artwork_type.capitalize()} found"

        except requests.exceptions.Timeout:
            return None, "Request timeout"
        except requests.exceptions.HTTPError as e:
            if e.response and e.response.status_code == 404:
                return None, "Not found on Fanart.tv"
            elif e.response and e.response.status_code == 429:
                logger.warning("Rate limited by Fanart.tv")
                return None, "Rate limited"
            return None, f"HTTP error: {e.response.status_code if e.response else 'unknown'}"
        except requests.exceptions.RequestException as e:
            safe_url = sanitize_url_for_logging(url)
            logger.debug(f"API error for {safe_url}: {e}")
            raise  # Let retry mechanism handle it
        except (KeyError, IndexError, ValueError, TypeError) as e:
            return None, f"Invalid data from Fanart.tv: {e}"

    def backup_existing_logo(self, item: Any) -> Optional[Path]:
        """
        Backup existing logo before replacing.

        Args:
            item: Plex item

        Returns:
            Path to backup file or None
        """
        if not self.backup_dir or self.dry_run:
            return None

        try:
            # Check if item has existing logo
            has_logo = any(img.type == 'clearLogo' for img in item.images)
            if not has_logo:
                return None

            # Create backup directory for this item
            item_backup_dir = self.backup_dir / item.type / item.title[:50]  # Limit length
            item_backup_dir.mkdir(parents=True, exist_ok=True)

            # Generate backup filename with timestamp
            timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
            backup_file = item_backup_dir / f"logo_{timestamp}.png"

            # Download existing logo
            if item.thumb:
                response = self.session.get(item.thumb, timeout=10)
                response.raise_for_status()
                backup_file.write_bytes(response.content)
                logger.debug(f"Backed up logo for {item.title} to {backup_file}")
                return backup_file

        except Exception as e:
            logger.warning(f"Could not backup logo for {item.title}: {e}")

        return None

    def update_plex_item_logo(self, item: Any, logo_url: str) -> Tuple[bool, str]:
        """
        Apply logo to a Plex item.

        Args:
            item: Plex item object
            logo_url: URL of logo to apply

        Returns:
            Tuple of (success, message)
        """
        if self.dry_run:
            return True, "[DRY RUN] Would update logo"

        try:
            # Backup existing logo if enabled
            if self.config.get('enable_backup', False):
                self.backup_existing_logo(item)

            item.uploadLogo(url=logo_url)
            return True, "Logo updated successfully"
        except BadRequest as e:
            return False, f"Bad request: {e}"
        except Exception as e:
            return False, f"Could not apply logo: {e}"

    def process_item(
        self,
        item: Any,
        api_key: str,
        skip_existing: bool = True,
        artwork_type: str = 'clearlogo'
    ) -> Dict[str, Any]:
        """
        Process a single item.

        Args:
            item: Plex item to process
            api_key: Fanart.tv API key
            skip_existing: Skip items with existing logos
            artwork_type: Type of artwork to apply

        Returns:
            Dictionary with processing result
        """
        result = {
            'item': item,
            'title': item.title,
            'type': item.type,
            'status': 'unknown',
            'message': '',
            'logo_url': None
        }

        try:
            # Check if already has logo
            has_logo = any(img.type == 'clearLogo' for img in item.images)
            if has_logo and skip_existing:
                result['status'] = 'skipped'
                result['message'] = 'Already has logo'
                return result

            # Check database to avoid reprocessing
            if self.db and self.db.was_processed(str(item.ratingKey), max_age_days=30):
                result['status'] = 'skipped'
                result['message'] = 'Recently processed'
                return result

            # Get logo URL from Fanart.tv
            logo_url, status_msg = self.get_fanart_logo_url(item, api_key, artwork_type)
            result['logo_url'] = logo_url
            result['message'] = status_msg

            if not logo_url:
                result['status'] = 'skipped'
                return result

            # Apply logo
            success, update_msg = self.update_plex_item_logo(item, logo_url)
            result['status'] = 'success' if success else 'failed'
            result['message'] = update_msg

            # Record in database
            if self.db:
                self.db.record_item(
                    str(item.ratingKey),
                    item.title,
                    item.type,
                    logo_url,
                    result['status'],
                    None if success else update_msg
                )

        except Exception as e:
            logger.error(f"Error processing {item.title}: {e}")
            result['status'] = 'failed'
            result['message'] = str(e)

            if self.db:
                self.db.record_item(
                    str(item.ratingKey),
                    item.title,
                    item.type,
                    None,
                    'failed',
                    str(e)
                )

        return result

    def process_items_parallel(
        self,
        items: List[Any],
        api_key: str,
        throttle_delay: float,
        skip_existing: bool = True,
        show_progress: bool = True
    ) -> None:
        """
        Process multiple items in parallel with progress bar.

        Args:
            items: List of items to process
            api_key: Fanart.tv API key
            throttle_delay: Delay between API requests
            skip_existing: Skip items with existing logos
            show_progress: Show progress bar
        """
        max_workers = self.config.get('max_workers', 5)

        # Use progress bar if enabled
        if show_progress:
            progress = tqdm(total=len(items), desc="Processing items", unit="item")
        else:
            progress = None

        with ThreadPoolExecutor(max_workers=max_workers) as executor:
            # Submit tasks
            future_to_item = {
                executor.submit(
                    self.process_item,
                    item,
                    api_key,
                    skip_existing
                ): item for item in items
            }

            # Process completed tasks
            for future in as_completed(future_to_item):
                # Apply throttle delay
                time.sleep(throttle_delay)

                try:
                    result = future.result()

                    if result['status'] == 'success':
                        self.stats.add_success()
                        logger.info(f"✓ {result['title']}")
                    elif result['status'] == 'skipped':
                        self.stats.add_skip()
                        logger.debug(f"- {result['title']}: {result['message']}")
                    else:
                        self.stats.add_failure(f"{result['title']}: {result['message']}")
                        logger.warning(f"✗ {result['title']}: {result['message']}")

                except Exception as e:
                    item = future_to_item[future]
                    self.stats.add_failure(f"{item.title}: {e}")
                    logger.error(f"Exception processing {item.title}: {e}")

                if progress:
                    progress.update(1)

        if progress:
            progress.close()

    def run_automatic_mode(
        self,
        plex: PlexServer,
        api_key: str,
        throttle_delay: float,
        libraries: Optional[List[str]] = None,
        skip_existing: bool = True,
        process_collections: bool = False
    ) -> None:
        """
        Scan libraries and automatically update logos.

        Args:
            plex: Plex server instance
            api_key: Fanart.tv API key
            throttle_delay: Delay between API requests
            libraries: Optional list of library names to process
            skip_existing: Skip items with existing logos
            process_collections: Also process collections
        """
        logger.info("=== Running in Automatic Mode ===")

        try:
            all_sections = plex.library.sections()

            # Filter sections if specific libraries requested
            if libraries:
                media_sections = [s for s in all_sections if s.title in libraries]
                if not media_sections:
                    logger.error(f"Could not find any of the specified libraries: {', '.join(libraries)}")
                    logger.info(f"Available libraries: {[s.title for s in all_sections]}")
                    return
            else:
                media_sections = [s for s in all_sections if s.type in ('show', 'movie')]

            # Process each section
            for section in media_sections:
                logger.info(f"\nProcessing library: '{section.title}' ({section.type})")

                try:
                    items = section.all()
                    logger.info(f"Found {len(items)} items")

                    self.process_items_parallel(
                        items,
                        api_key,
                        throttle_delay,
                        skip_existing,
                        show_progress=True
                    )

                except Exception as e:
                    logger.error(f"Error processing library '{section.title}': {e}")

            # Process collections if requested
            if process_collections:
                logger.info("\nProcessing collections...")
                try:
                    collections = plex.library.collections()
                    logger.info(f"Found {len(collections)} collections")

                    self.process_items_parallel(
                        collections,
                        api_key,
                        throttle_delay,
                        skip_existing,
                        show_progress=True
                    )
                except Exception as e:
                    logger.error(f"Error processing collections: {e}")

        except Exception as e:
            logger.error(f"Error in automatic mode: {e}")

    def run_interactive_mode(
        self,
        plex: PlexServer,
        api_key: str,
        throttle_delay: float
    ) -> None:
        """
        Interactive mode for manual item selection.

        Args:
            plex: Plex server instance
            api_key: Fanart.tv API key
            throttle_delay: Delay between API requests
        """
        logger.info("=== Running in Interactive Mode ===")
        print("Enter movie or TV show name to search, or press Enter to exit.\n")

        while True:
            try:
                item_name = input("Search: ").strip()
                if not item_name:
                    break

                # Search for items
                results = plex.search(item_name)
                media_results = [r for r in results if r.type in ('movie', 'show')]

                if not media_results:
                    print("No items found matching that name.\n")
                    continue

                # Display results
                print("\nFound matches:")
                for i, item in enumerate(media_results):
                    year = getattr(item, 'year', 'Unknown')
                    print(f"  {i + 1}. {item.title} ({year}) [{item.type.capitalize()}]")

                # Get user selection
                try:
                    choice = int(input(f"\nSelect (1-{len(media_results)}, or 0 to search again): "))
                    if choice == 0:
                        continue
                    if choice < 1 or choice > len(media_results):
                        print("Invalid selection.\n")
                        continue
                    selected_item = media_results[choice - 1]
                except (ValueError, IndexError):
                    print("Invalid input.\n")
                    continue

                # Get logo
                print(f"\nSearching for logo: '{selected_item.title}'...")
                time.sleep(throttle_delay)

                # FIX: Properly unpack tuple return value
                logo_url, status_msg = self.get_fanart_logo_url(selected_item, api_key)

                if not logo_url:
                    print(f"Could not find logo: {status_msg}\n")
                    continue

                print(f"Found logo: {logo_url}")

                # Confirm application
                confirm = input("Apply this logo? (y/n): ").lower()
                if confirm == 'y':
                    # FIX: Capture and display result
                    success, update_msg = self.update_plex_item_logo(selected_item, logo_url)
                    if success:
                        print(f"✓ {update_msg}\n")
                        self.stats.add_success()
                    else:
                        print(f"✗ {update_msg}\n")
                        self.stats.add_failure(update_msg)

                # Continue or exit
                if input("Update another item? (y/n): ").lower() != 'y':
                    break

            except (KeyboardInterrupt, EOFError):
                print("\n")
                break

        logger.info("Exiting interactive mode")

    def export_to_csv(self, output_file: str = 'logo_update_results.csv') -> None:
        """
        Export processing results to CSV.

        Args:
            output_file: Output CSV file path
        """
        try:
            if not self.db:
                logger.warning("Database not available for CSV export")
                return

            # Get recent records from database
            conn = self.db.conn
            if not conn:
                return

            cursor = conn.execute('''
                SELECT item_title, item_type, processed_at, logo_url, status, error_message
                FROM processed_items
                WHERE date(processed_at) = date('now')
                ORDER BY processed_at DESC
            ''')

            with open(output_file, 'w', newline='', encoding='utf-8') as f:
                writer = csv.writer(f)
                writer.writerow(['Title', 'Type', 'Processed At', 'Logo URL', 'Status', 'Error'])

                for row in cursor:
                    writer.writerow(row)

            logger.info(f"Exported results to {output_file}")

        except Exception as e:
            logger.error(f"Error exporting to CSV: {e}")

    def cleanup(self) -> None:
        """Clean up resources."""
        if self.session:
            self.session.close()
        if self.db:
            self.db.close()


# --- Main Function ---

def main():
    """Main execution function."""
    parser = argparse.ArgumentParser(
        description="P Logo Updater - Automatically update Plex logos from Fanart.tv",
        formatter_class=argparse.RawDescriptionHelpFormatter
    )

    # Mode selection
    parser.add_argument(
        '--interactive',
        action='store_true',
        help='Run in interactive mode for manual selection'
    )

    # Library selection
    parser.add_argument(
        '--libraries',
        nargs='+',
        help='Specific Plex library names to scan (default: all movie/TV libraries)'
    )

    # Processing options
    parser.add_argument(
        '--force',
        action='store_true',
        help='Update all items, even those with existing logos'
    )
    parser.add_argument(
        '--collections',
        action='store_true',
        help='Also process Plex collections'
    )
    parser.add_argument(
        '--dry-run',
        action='store_true',
        help='Show what would be updated without making changes'
    )

    # Output options
    parser.add_argument(
        '--verbose',
        '-v',
        action='store_true',
        help='Enable verbose debug logging'
    )
    parser.add_argument(
        '--log-file',
        help='Write logs to specified file'
    )
    parser.add_argument(
        '--export-csv',
        action='store_true',
        help='Export results to CSV file'
    )

    # Configuration
    parser.add_argument(
        '--config',
        default='config.json',
        help='Path to configuration file (default: config.json)'
    )

    args = parser.parse_args()

    # Setup logging
    setup_logging(verbose=args.verbose, log_file=args.log_file)

    logger.info("=== P Logo Updater v2.0 ===")
    if args.dry_run:
        logger.info("DRY RUN MODE - No changes will be made")

    # Load configuration
    try:
        config = load_config(args.config)
        fanart_api_key = config.get('fanart_api_key')
        if not fanart_api_key:
            logger.error("fanart_api_key not found in configuration")
            logger.error("Please add your Fanart.tv API key to config.json")
            sys.exit(1)

        fanart_key_type = config.get('fanart_key_type', 'free').lower()
        throttle_delay = 0.5 if fanart_key_type == 'paid' else 1.0
        logger.info(f"API throttle: {throttle_delay}s per request ({fanart_key_type} tier)")

    except ConfigurationError as e:
        logger.error(f"Configuration error: {e}")
        sys.exit(1)

    # Connect to Plex
    plex = connect_plex(
        config['plex_url'],
        config['plex_token'],
        timeout=config.get('connection_timeout', 60)
    )
    if not plex:
        sys.exit(1)

    # Initialize updater
    updater = LogoUpdater(config, dry_run=args.dry_run)

    try:
        # Run appropriate mode
        if args.interactive:
            updater.run_interactive_mode(plex, fanart_api_key, throttle_delay)
        else:
            updater.run_automatic_mode(
                plex,
                fanart_api_key,
                throttle_delay,
                libraries=args.libraries,
                skip_existing=not args.force,
                process_collections=args.collections
            )

        # Display statistics
        logger.info(format_statistics(updater.stats.to_dict()))

        # Export to CSV if requested
        if args.export_csv:
            updater.export_to_csv()

        # Send webhook notification if configured
        webhook_url = config.get('webhook_url')
        if webhook_url:
            send_completion_notification(
                webhook_url,
                updater.stats.to_dict(),
                updater.stats.get_duration()
            )

        logger.info("\n=== Script Finished ===")

    except KeyboardInterrupt:
        logger.info("\n\nInterrupted by user")
        sys.exit(130)
    except Exception as e:
        logger.error(f"Unexpected error: {e}", exc_info=True)

        # Send error notification if configured
        webhook_url = config.get('webhook_url')
        if webhook_url:
            send_error_notification(webhook_url, str(e))

        sys.exit(1)
    finally:
        updater.cleanup()


if __name__ == "__main__":
    main()
