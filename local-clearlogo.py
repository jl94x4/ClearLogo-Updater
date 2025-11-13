#!/usr/bin/env python3
"""
P Logo Updater - Local File Version (Enhanced)

Uses local logo files instead of fanart.tv API.
"""

import argparse
import json
import logging
import os
import sys
import time
from pathlib import Path
from typing import Dict, List, Optional, Tuple, Any

from plexapi.server import PlexServer
from plexapi.exceptions import NotFound, BadRequest
from tqdm import tqdm

from utils import setup_logging, load_config, connect_plex, ConfigurationError
from database import LogoDatabase

# --- Configuration ---
MAPPING_FILE = 'local-mapping.json'
UPLOAD_DELAY = 0.05

logger = logging.getLogger(__name__)


class LocalLogoUpdater:
    """Local file-based logo updater."""

    def __init__(
        self,
        config: Dict[str, Any],
        mapping_file: str = MAPPING_FILE,
        dry_run: bool = False
    ):
        """
        Initialize local logo updater.

        Args:
            config: Configuration dictionary
            mapping_file: Path to mapping JSON file
            dry_run: If True, don't make actual changes
        """
        self.config = config
        self.mapping_file = mapping_file
        self.dry_run = dry_run
        self.location_map: Dict[str, str] = {}
        self.stats = {
            'total': 0,
            'matched': 0,
            'uploaded': 0,
            'errors': []
        }

        # Initialize database if enabled
        self.db: Optional[LogoDatabase] = None
        if config.get('enable_database', True):
            try:
                self.db = LogoDatabase(config.get('database_path', 'logo_history.db'))
            except Exception as e:
                logger.warning(f"Could not initialize database: {e}")

    def load_or_create_mapping(
        self,
        plex: PlexServer,
        clear_existing: bool = False
    ) -> bool:
        """
        Load existing mapping or create new one interactively.

        Args:
            plex: Plex server instance
            clear_existing: Clear existing mapping

        Returns:
            True if mapping loaded/created successfully
        """
        mapping_path = Path(self.mapping_file)

        if mapping_path.exists() and not clear_existing:
            try:
                with open(mapping_path, 'r', encoding='utf-8') as f:
                    self.location_map = json.load(f)
                logger.info(f"Loaded mappings from {self.mapping_file}")
                # Sort by key length (descending) to match longer paths first
                self.location_map = dict(
                    sorted(self.location_map.items(), key=lambda item: len(item[0]), reverse=True)
                )
                return True
            except Exception as e:
                logger.error(f"Error loading mapping file: {e}")
                return False
        else:
            if clear_existing and mapping_path.exists():
                try:
                    os.remove(mapping_path)
                    logger.info(f"Cleared mapping file: {self.mapping_file}")
                except Exception as e:
                    logger.error(f"Error clearing mapping file: {e}")

            return self._create_mapping_interactive(plex)

    def _create_mapping_interactive(self, plex: PlexServer) -> bool:
        """
        Create mapping interactively by asking user for local paths.

        Args:
            plex: Plex server instance

        Returns:
            True if mapping created successfully
        """
        self.location_map = {}

        print("\nEnter the local folder path corresponding to each Plex library location:")
        print("(These are the folders where your logo files are stored)\n")

        try:
            for section in plex.library.sections():
                if section.type not in ['movie', 'show']:
                    continue

                for plex_location in section.locations:
                    if plex_location in self.location_map:
                        continue

                    print(f"Plex location: {plex_location}")
                    user_input = input("  Local folder path (or press Enter to skip): ").strip()

                    if not user_input:
                        logger.info(f"Skipping: {plex_location}")
                        continue

                    local_path = Path(user_input)

                    if not local_path.exists() or not local_path.is_dir():
                        print(f"  Warning: Invalid folder path. Skipping this location.\n")
                        continue

                    self.location_map[plex_location] = str(local_path)
                    print()

            # Save mappings
            if self.location_map:
                with open(self.mapping_file, 'w', encoding='utf-8') as f:
                    json.dump(self.location_map, f, indent=2)
                logger.info(f"Saved mappings to {self.mapping_file}")

                # Sort by key length
                self.location_map = dict(
                    sorted(self.location_map.items(), key=lambda item: len(item[0]), reverse=True)
                )
                return True
            else:
                logger.warning("No mappings created")
                return False

        except (KeyboardInterrupt, EOFError):
            print("\nMapping creation cancelled")
            return False

    def find_local_logo(self, item_folder: Path) -> Optional[Path]:
        """
        Find logo file in local folder.

        Args:
            item_folder: Folder to search

        Returns:
            Path to logo file or None
        """
        supported_prefixes = ['logo', 'clearlogo']
        supported_extensions = ['.png', '.jpg', '.jpeg']

        for prefix in supported_prefixes:
            for ext in supported_extensions:
                candidate = item_folder / f"{prefix}{ext}"
                if candidate.exists():
                    return candidate

        return None

    def get_local_folder_for_item(self, item: Any) -> Optional[Path]:
        """
        Get local folder path for a Plex item.

        Args:
            item: Plex item

        Returns:
            Local folder path or None
        """
        try:
            # Get remote path based on item type
            if item.type == 'movie':
                media_parts = item.media[0].parts
                if not media_parts:
                    return None
                remote_path = media_parts[0].file
                # For movies, logo is in the same folder as the file
                item_folder_remote = Path(remote_path).parent
            elif item.type == 'show':
                if not item.locations:
                    return None
                # For shows, logo is in the show's root folder
                remote_path = item.locations[0]
                item_folder_remote = Path(remote_path)
            else:
                return None

            # Find matching location in mapping
            matched_location = None
            for plex_location_key in self.location_map:
                if str(item_folder_remote).startswith(plex_location_key) or remote_path.startswith(plex_location_key):
                    matched_location = plex_location_key
                    break

            if not matched_location:
                logger.debug(f"No mapping match for: {item.title}")
                return None

            # Calculate relative path (FIX: Proper path calculation)
            try:
                if item.type == 'movie':
                    # For movies, get the folder containing the movie file
                    relative_folder = Path(remote_path).parent.relative_to(matched_location)
                else:
                    # For shows, get the show's folder
                    relative_folder = item_folder_remote.relative_to(matched_location)

            except ValueError:
                # Fallback: use the parent folder name (FIX: Use parent.name, not name)
                if item.type == 'movie':
                    relative_folder = Path(Path(remote_path).parent.name)
                else:
                    relative_folder = Path(item_folder_remote.name)

            # Build local folder path
            local_base = Path(self.location_map[matched_location])
            local_folder = local_base / relative_folder

            return local_folder

        except Exception as e:
            logger.debug(f"Error getting local folder for {item.title}: {e}")
            return None

    def process_item(self, item: Any, skip_existing: bool = True) -> Tuple[str, str]:
        """
        Process a single item.

        Args:
            item: Plex item to process
            skip_existing: Skip items with existing logos

        Returns:
            Tuple of (status, message)
        """
        self.stats['total'] += 1

        try:
            # Check if already has logo
            has_logo = any(img.type == 'clearLogo' for img in item.images)

            if has_logo and skip_existing:
                return 'skipped', 'Already has logo'

            # Get local folder
            local_folder = self.get_local_folder_for_item(item)
            if not local_folder:
                return 'skipped', 'No mapped folder'

            # Find logo file
            logo_path = self.find_local_logo(local_folder)
            if not logo_path:
                return 'skipped', 'No logo file found'

            if not logo_path.exists():
                return 'skipped', 'Logo file does not exist'

            self.stats['matched'] += 1

            # Upload logo
            if self.dry_run:
                logger.debug(f"[DRY RUN] Would upload: {logo_path}")
                return 'success', f'[DRY RUN] Would upload from {logo_path}'
            else:
                try:
                    item.uploadLogo(filepath=str(logo_path))
                    time.sleep(UPLOAD_DELAY)
                    # FIX: Only increment if not dry run
                    self.stats['uploaded'] += 1

                    # Record in database
                    if self.db:
                        self.db.record_item(
                            str(item.ratingKey),
                            item.title,
                            item.type,
                            str(logo_path),
                            'success',
                            None
                        )

                    return 'success', f'Uploaded from {logo_path}'

                except BadRequest as e:
                    error = f'Bad request: {e}'
                    self.stats['errors'].append(f"{item.title}: {error}")
                    if self.db:
                        self.db.record_item(
                            str(item.ratingKey),
                            item.title,
                            item.type,
                            str(logo_path),
                            'failed',
                            error
                        )
                    return 'failed', error

                except AttributeError as e:
                    if 'uploadLogo' in str(e):
                        error = f"uploadLogo not supported for {item.type}"
                    else:
                        error = f"Attribute error: {e}"
                    self.stats['errors'].append(f"{item.title}: {error}")
                    if self.db:
                        self.db.record_item(
                            str(item.ratingKey),
                            item.title,
                            item.type,
                            str(logo_path),
                            'failed',
                            error
                        )
                    return 'failed', error

                except Exception as e:
                    error = f'Upload failed: {e}'
                    self.stats['errors'].append(f"{item.title}: {error}")
                    if self.db:
                        self.db.record_item(
                            str(item.ratingKey),
                            item.title,
                            item.type,
                            str(logo_path),
                            'failed',
                            error
                        )
                    return 'failed', error

        except Exception as e:
            error = f'Processing error: {e}'
            self.stats['errors'].append(f"{item.title}: {error}")
            return 'failed', error

    def run(
        self,
        plex: PlexServer,
        skip_existing: bool = True,
        verbose: bool = False
    ) -> None:
        """
        Process all items in Plex libraries.

        Args:
            plex: Plex server instance
            skip_existing: Skip items with existing logos
            verbose: Enable verbose output
        """
        logger.info("Starting local logo upload process...")

        try:
            for section in plex.library.sections():
                if section.type not in ['movie', 'show']:
                    continue

                logger.info(f"Processing library: {section.title} ({section.type})")
                items = section.all()

                # Use progress bar
                for item in tqdm(items, desc=f"  {section.title}", unit="item"):
                    status, message = self.process_item(item, skip_existing)

                    if verbose:
                        if status == 'success':
                            logger.info(f"  ✓ {item.title}")
                        elif status == 'failed':
                            logger.warning(f"  ✗ {item.title}: {message}")
                        elif verbose and status == 'skipped':
                            logger.debug(f"  - {item.title}: {message}")

        except Exception as e:
            logger.error(f"Error during processing: {e}")

    def print_summary(self) -> None:
        """Print processing summary."""
        print("\n=== SUMMARY ===")
        print(f"Total items scanned:          {self.stats['total']}")
        print(f"Items with logo file found:   {self.stats['matched']}")
        print(f"Logos uploaded:               {self.stats['uploaded']}")

        if self.dry_run:
            print("\nℹ️  No changes made (dry run mode)")
        else:
            print("\n✓ Processing complete")

        if self.stats['errors']:
            print(f"\n⚠️  {len(self.stats['errors'])} errors encountered")
            for error in self.stats['errors'][:5]:
                print(f"  - {error}")
            if len(self.stats['errors']) > 5:
                print(f"  ... and {len(self.stats['errors']) - 5} more")

    def cleanup(self) -> None:
        """Clean up resources."""
        if self.db:
            self.db.close()


def parse_args():
    """Parse command line arguments."""
    parser = argparse.ArgumentParser(
        description="P Logo Updater - Local File Version"
    )

    parser.add_argument(
        '--verbose', '-v',
        action='store_true',
        help='Enable verbose output'
    )
    parser.add_argument(
        '--all', '-a',
        action='store_true',
        help='Upload logos for all items (overrides existing logos)'
    )
    parser.add_argument(
        '--dry-run', '-d',
        action='store_true',
        help='Dry run (no changes will be made)'
    )
    parser.add_argument(
        '--clear-mapping', '-c',
        action='store_true',
        help=f'Clear the current mapping file ({MAPPING_FILE})'
    )
    parser.add_argument(
        '--config',
        default='config.json',
        help='Path to configuration file (default: config.json)'
    )
    parser.add_argument(
        '--log-file',
        help='Write logs to specified file'
    )

    return parser.parse_args()


def main():
    """Main execution function."""
    args = parse_args()

    # Setup logging
    setup_logging(verbose=args.verbose, log_file=args.log_file)

    logger.info("=== P Logo Updater (Local Files) v2.0 ===")

    if args.dry_run:
        logger.info("DRY RUN MODE - No changes will be made")

    logger.info(f"Options: verbose={args.verbose}, upload_all={args.all}, "
                f"dry_run={args.dry_run}, clear_mapping={args.clear_mapping}")

    # Load configuration
    try:
        config = load_config(args.config)
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
    updater = LocalLogoUpdater(config, dry_run=args.dry_run)

    try:
        # Load or create mapping
        if not updater.load_or_create_mapping(plex, clear_existing=args.clear_mapping):
            logger.error("Failed to load or create mapping. Exiting.")
            sys.exit(1)

        # Run processing
        updater.run(plex, skip_existing=not args.all, verbose=args.verbose)

        # Print summary
        updater.print_summary()

        logger.info("\n=== Script Finished ===")

    except KeyboardInterrupt:
        logger.info("\n\nInterrupted by user")
        sys.exit(130)
    except Exception as e:
        logger.error(f"Unexpected error: {e}", exc_info=True)
        sys.exit(1)
    finally:
        updater.cleanup()


if __name__ == "__main__":
    main()
