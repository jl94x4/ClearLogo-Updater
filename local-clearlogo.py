# --- Imports ---
import json
import sys
import plexapi
import os
import time
import argparse

from plexapi.server import PlexServer
from plexapi.exceptions import NotFound, BadRequest
from pathlib import Path

# --- Configuration ---
CONFIG_FILE = 'config.json'            # JSON file containing Plex URL and Token
MAPPING_FILE = 'local-mapping.json'    # JSON file containing local folder mappings
UPLOAD_DELAY = 0.05                    # delay in seconds between uploads to avoid overwhelming the server

# --- Functions ---

def load_config():
    """Loads Plex URL and Token from the JSON config file."""
    try:
        with open(CONFIG_FILE, 'r') as f:
            config_data = json.load(f)
        plex_url = config_data.get('plex_url')
        plex_token = config_data.get('plex_token')
        if not plex_url or not plex_token or plex_token == 'YOUR_plex_token_HERE':
             print(f"❌ Error: Ensure 'plex_url' and 'plex_token' are correctly set in {CONFIG_FILE}.")
             return None, None
        return plex_url, plex_token
    except FileNotFoundError:
        print(f"❌ Error: Configuration file '{CONFIG_FILE}' not found.")
        return None, None
    except json.JSONDecodeError:
        print(f"❌ Error: Could not decode JSON from '{CONFIG_FILE}'. Check format.")
        return None, None
    except Exception as e:
        print(f"❌ An unexpected error occurred reading config: {e}")
        return None, None

def connect_plex(url, token):
    """Connects to the Plex server."""
    try:
        print(f"\n🔃 Attempting to connect to Plex server at {url}...")
        plex = PlexServer(url, token, timeout=30)
        print(f"✅ Successfully connected to Plex server: {plex.friendlyName} (Version: {plex.version})")
        return plex
    except Exception as e:
        print(f"❌ Error connecting to Plex server: {e}")
        print("Check URL, token, server status, and network connection.")
        return None

def parse_args():
    parser = argparse.ArgumentParser(description="Plex ClearLogo Updater")
    parser.add_argument('--verbose', '-v', action='store_true', help='Enable verbose output')
    parser.add_argument('--all', '-a', action='store_true', help='Upload images for all items (overrides existing logos)')
    parser.add_argument('--dry-run', '-d', action='store_true', help='Dry run (no changes will be made)')
    parser.add_argument('--clear-mapping', '-c', action='store_true', help=f'Clear the current mapping file ({MAPPING_FILE})')
    return parser.parse_args()

def main():
    """Main execution function with loop, searching across all relevant libraries."""
    args = parse_args()
    verbose = args.verbose
    upload_all = args.all
    dry_run = args.dry_run
    clear_mapping = args.clear_mapping

    print("--- Plex Logo Updater (Movies & TV Shows - All Libraries) ---")

    print("\n⚙️  Running with options:")
    print(f"  Verbose: {verbose}")
    print(f"  Upload all: {upload_all}")
    print(f"  Dry run: {dry_run}")
    print(f"  Clear mapping: {clear_mapping}")

    # --- Clear mapping file if requested ---
    if clear_mapping:
        if Path(MAPPING_FILE).exists():
            try:
                os.remove(MAPPING_FILE)
                print(f"\n🗑️  Mapping file '{MAPPING_FILE}' has been deleted.")
            except Exception as e:
                print(f"\n❌ Failed to delete mapping file: {e}")
        else:
            print(f"\nℹ️  Mapping file '{MAPPING_FILE}' does not exist.")

    plex_url, plex_token = load_config()
    if not plex_url or not plex_token: sys.exit(1)

    plex = connect_plex(plex_url, plex_token)
    if not plex: sys.exit(1)

    # === LOAD OR BUILD MAPPING FILE ===
    if Path(MAPPING_FILE).exists() and not clear_mapping:
        with open(MAPPING_FILE, 'r', encoding='utf-8') as f:
            location_map = json.load(f)
        print(f"\n✅ Loaded mappings from {MAPPING_FILE}")
    else:
        location_map = {}

        print("\n📁 Enter the local folder path corresponding to each Plex library location:")

        for section in plex.library.sections():
            if section.type not in ['movie', 'show']:
                continue

            for plex_location in section.locations:
                if plex_location in location_map:
                    continue

                print(f"\n🔗 Plex location: {plex_location}")
                user_input = input("↳ Local folder path: ").strip()
                local_path = Path(user_input)

                if not local_path.exists() or not local_path.is_dir():
                    print("❌ Invalid folder. Skipping this location.")
                    continue

                location_map[plex_location] = str(local_path)

        # Save mappings
        with open(MAPPING_FILE, 'w', encoding='utf-8') as f:
            json.dump(location_map, f, indent=2)
            print(f"\n💾 Saved mappings to {MAPPING_FILE}")

    # === PROCESS ITEMS ===
    total = 0
    matched = 0
    uploaded = 0

    print("\n🚀 Starting logo upload process...\n")

    # sort the mapping by key length (descending) to match longer paths first
    location_map = dict(sorted(location_map.items(), key=lambda item: len(item[0]), reverse=True))

    for section in plex.library.sections():
        if section.type not in ['movie', 'show']:
            continue

        print(f"📂 Processing library: {section.title} ({section.type})")
        items = section.all()  # Fetch all items once per section

        num_items = len(items)
        for idx, item in enumerate(items, 1):
            if not verbose:
                print(f"\r  Progress: {idx}/{num_items} items", end='', flush=True)
            total += 1
            try:
                has_logo = False
                for image in item.images:
                    if image.type == 'clearLogo':
                        has_logo = True
                        break

                # Only skip if not --all and logo exists
                if has_logo and not upload_all:
                    if verbose:
                        print(f"  [!] Logo already exists for: {item.title}")
                    continue

                if section.type == 'movie':
                    media_parts = item.media[0].parts
                    if not media_parts:
                        continue
                    remote_path = media_parts[0].file
                    item_folder = Path(os.path.dirname(remote_path))
                elif section.type == 'show':
                    if not item.locations:
                        continue
                    # Use the first location as the show folder
                    remote_path = item.locations[0]
                    item_folder = Path(remote_path)
                else:
                    continue

                # Determine which mapped Plex location this item belongs to
                matched_location = None
                for plex_location_key in location_map:
                    if remote_path.startswith(plex_location_key):
                        matched_location = plex_location_key
                        break

                if not matched_location:
                    if verbose:
                        print(f"  [!] Could not match remote path for item: {item.title}")
                    continue

                item_folder = Path(os.path.dirname(remote_path))
                try:
                    relative_folder = item_folder.relative_to(matched_location)
                    if str(relative_folder) == '.' or relative_folder == Path('.'):
                        # fallback to using last folder name from full path
                        relative_folder = Path(remote_path).name
                        relative_folder = Path(relative_folder)
                except ValueError:
                    if verbose:
                        print(f"  [!] Could not calculate relative path for: {item.title}")
                    continue
                local_base = Path(location_map[matched_location])
                local_folder = local_base / relative_folder

                # === LOOK FOR SUPPORTED LOGO FILES ===
                supported_prefixes = ['logo', 'clearlogo']
                supported_extensions = ['.png', '.jpg']
                logo_path = None
                for prefix in supported_prefixes:
                    for ext in supported_extensions:
                        candidate = local_folder / f"{prefix}{ext}"
                        if candidate.exists():
                            logo_path = candidate
                            break
                    if logo_path:
                        break

                if logo_path is not None:
                    if logo_path.exists():
                        matched += 1
                        if dry_run:
                            if verbose:
                                print(f"  [DRY RUN] Would upload logo for: {item.title} from {logo_path}")
                        else:
                            try:
                                item.uploadLogo(filepath=logo_path)
                                if verbose:
                                    print(f"  [+] Uploaded logo for: {item.title}")
                                time.sleep(UPLOAD_DELAY)
                            except BadRequest as e:
                                if verbose:
                                    print(f"  [!] Error applying logo: {e}")
                                    print("Check filepath, image format, and server accessibility.")
                            except AttributeError as e:
                                if 'uploadLogo' in str(e):
                                    item_type = getattr(item, 'type', 'item')
                                    if verbose:
                                        print(f"  [!] *** Failed: It seems '{item_type}' objects might not support '.uploadLogo()' in your plexapi version. ***")
                                else:
                                    if verbose:
                                        print(f"  [!] Error during upload: {e}")
                            except Exception as e:
                                if verbose:
                                    print(f"  [!] Upload failed. Reason: {e}")
                            uploaded += 1
                    else:
                        if verbose:
                            print(f"  [!] Logo file does not exist for: {item.title}")
                else:
                    if verbose:
                        print(f"  [!] No supported logo files found for: {item.title}")
            except Exception as e:
                if verbose:
                    print(f"  [!] Error processing item: {item.title} → {e}")
        if not verbose:
            print()  # Newline after progress for this library

    # === SUMMARY ===
    print("\n=== SUMMARY ===")
    print("📦 Total items scanned:".ljust(35, ' ') + f"{total}")
    print("🖼️  Items with new logo file:".ljust(35, ' ') + f"{matched}")
    print("⬆️  Logos uploaded:".ljust(35, ' ') + f"{uploaded}")
    print(f"{'ℹ️  No changes made (dry run)' if dry_run else '✅ All applicable logos uploaded'}")

    print("\n--- Script Finished ---")


# --- Script Entry Point ---
if __name__ == "__main__":
    main()
