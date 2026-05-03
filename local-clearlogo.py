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
             print(f"[!] Error: Ensure 'plex_url' and 'plex_token' are correctly set in '{CONFIG_FILE}'.")
             return None, None
        return plex_url, plex_token
    except FileNotFoundError:
        print(f"[!] Error: Configuration file '{CONFIG_FILE}' not found.")
        return None, None
    except json.JSONDecodeError:
        print(f"[!] Error: Could not decode JSON from '{CONFIG_FILE}'. Check format.")
        return None, None
    except Exception as e:
        print(f"[!] An unexpected error occurred reading config: {e}")
        return None, None

def connect_plex(url, token):
    """Connects to the Plex server."""
    try:
        print(f"\nAttempting to connect to Plex server at {url}...")
        plex = PlexServer(url, token, timeout=30)
        print(f"[+] Successfully connected to Plex server: {plex.friendlyName} (Version: {plex.version})")
        return plex
    except Exception as e:
        print(f"[!] Error connecting to Plex server: {e}")
        print("[!] Check URL, token, server status, and network connection.")
        return None

def parse_args():
    parser = argparse.ArgumentParser(description="Plex ClearLogo Updater")
    parser.add_argument('--verbose', '-v', action='store_true', help='Enable verbose output')
    parser.add_argument('--all', '-a', action='store_true', help='Upload images for all items (overrides existing logos)')
    parser.add_argument('--search', '-s', action='store_true', help='Search for a title and upload a logo (overrides existing logos)')
    parser.add_argument('--dry-run', '-d', action='store_true', help='Dry run (no changes will be made)')
    parser.add_argument('--clear-mapping', '-c', action='store_true', help=f'Clear the current mapping file ({MAPPING_FILE})')
    parser.add_argument('--max-results', '-m', type=int, default=30, help='Maximum number of search results in search mode (default: 30)')
    return parser.parse_args()

def process_item(item, section, location_map, upload_all, dry_run, verbose, stats):
    """Process a single item: match local folder, find logo, and upload."""
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
            return stats

        if section.type == 'movie':
            media_parts = item.media[0].parts
            if not media_parts:
                return stats
            remote_path = media_parts[0].file
            item_folder = Path(os.path.dirname(remote_path))
        elif section.type == 'show':
            if not item.locations:
                return stats
            # Use the first location as the show folder
            remote_path = item.locations[0]
            item_folder = Path(remote_path)
        else:
            return stats

        # Determine which mapped Plex location this item belongs to
        matched_location = None
        for plex_location_key in location_map:
            if remote_path.startswith(plex_location_key):
                matched_location = plex_location_key
                break

        if not matched_location:
            if verbose:
                print(f"  [!] Could not match remote path for item: {item.title}")
            return stats

        item_folder = Path(os.path.dirname(remote_path))
        try:
            relative_folder = item_folder.relative_to(matched_location)
            if str(relative_folder) == '.' or relative_folder == Path('.'):
                # fallback to using last folder name from full path
                # fallback to using last folder name from full path
                relative_folder = Path(remote_path).name
                relative_folder = Path(relative_folder)
        except ValueError:
            if verbose:
                print(f"  [!] Could not calculate relative path for: {item.title}")
            return stats
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

        if logo_path is not None and logo_path.exists():
            stats["matched"] += 1
            if dry_run:
                if verbose:
                    print(f" [DRY RUN] Would upload logo for: {item.title} from {logo_path}")
            else:
                try:
                    item.uploadLogo(filepath=logo_path)
                    if verbose:
                        print(f"  [+] Uploaded logo for: {item.title}")
                    time.sleep(UPLOAD_DELAY)
                except BadRequest as e:
                    print(f"\n  [!] Error applying logo for Item: {item.title} → Filepath: {logo_path}:\n {e}")
                except AttributeError as e:
                    if 'uploadLogo' in str(e):
                        item_type = getattr(item, 'type', 'item')
                        print(f"\n  [!] *** Failed: It seems '{item_type}' objects might not support '.uploadLogo()' in your plexapi version. ***")
                    else:
                        print(f"\n  [!] Error during upload for Item: {item.title} → Filepath: {logo_path}:\n {e}")
                except Exception as e:
                    print(f"\n  [!] Upload failed for → Item: {item.title} → Filepath: {logo_path}:\n {e}")
                else:
                    stats["uploaded"] += 1
        else:
            if verbose:
                print(f"\n  [!] No supported logo files found for: {item.title}")
    except Exception as e:
        if verbose:
            print(f"\n  [!] Error processing item: {item.title} → {e}")
    return stats

# search mode functions
def search_titles(plex, query, max_results=30):
    """Search for titles in all libraries"""
    results = []
    for section in plex.library.sections():
        if section.type not in ['movie', 'show']:
            continue
        matches = section.search(query)
        for item in matches:
            if len(results) >= max_results:
                print(f"[!] Search result limit of {max_results} reached. Showing first {max_results} matches.")
                return results
            results.append({
                'title': item.title,
                'year': getattr(item, 'year', ''),
                'type': section.type,
                'library': section.title,
                'item': item
            })
    return results

def select_from_results(results, allow_all=False):
    """Prompt user to select a result from the search list.
    If allow_all is True the user may enter 'a' to select/update all results.
    Returns:
      - selected item object
      - 'ALL' string if user chose to operate on all results
      - None if user quits or invalid
    """
    if not results:
        print("[!] No results found.")
        return None
    print("\nSearch Results:")
    for idx, r in enumerate(results, 1):
        print(f"{idx}. {r['title']} ({r['year']}) [{r['type']}] - Library: {r['library']}")
    prompt = f"Select a title (1-{len(results)})"
    if allow_all:
        prompt += " | 'a' to update all results"
    prompt += " | 'q' to quit: "
    while True:
        choice = input(prompt).strip().lower()
        if choice == 'q':
            return None
        if allow_all and choice == 'a':
            return 'ALL'
        if choice.isdigit() and 1 <= int(choice) <= len(results):
            return results[int(choice)-1]['item']
        print("[!] Invalid selection. Try again.")

def main(stats=None):
    """Main execution function with loop, searching across all relevant libraries."""
    args = parse_args()
    verbose = args.verbose
    upload_all = args.all
    search_mode = args.search
    if search_mode:
        upload_all = True  # Always override existing logos in search mode
        verbose = True    # Always verbose in search mode
    dry_run = args.dry_run
    clear_mapping = args.clear_mapping

    if stats is None: # first run
        print("--- Plex Logo Updater (Movies & TV Shows - All Libraries) ---")
        print("\nRunning with options:")
        print(f"  [+] Verbose (-v, --verbose): {verbose}")
        print(f"  [+] Upload all (-a, --all): {upload_all}")
        print(f"  [+] Search mode (-s, --search): {search_mode}")
        print(f"  [+] Dry run (-d, --dry-run): {dry_run}")
        print(f"  [+] Clear mapping (-c, --clear-mapping): {clear_mapping}")
        print(f"  [+] Max results (-m, --max-results): {args.max_results}")

    if clear_mapping:
        if Path(MAPPING_FILE).exists():
            try:
                os.remove(MAPPING_FILE)
                print(f"\n[+] Mapping file '{MAPPING_FILE}' has been deleted.")
            except Exception as e:
                print(f"\n[!] Failed to delete mapping file: {e}")
        else:
            print(f"\n[!] Mapping file '{MAPPING_FILE}' does not exist.")

    plex_url, plex_token = load_config()
    if not plex_url or not plex_token: sys.exit(1)

    plex = connect_plex(plex_url, plex_token)
    if not plex: sys.exit(1)

    if Path(MAPPING_FILE).exists() and not clear_mapping:
        with open(MAPPING_FILE, 'r', encoding='utf-8') as f:
            location_map = json.load(f)
        print(f"\n[+] Loaded mappings from {MAPPING_FILE}")
    else:
        location_map = {}

        print("\nEnter the local folder path corresponding to each Plex library location:")

        for section in plex.library.sections():
            if section.type not in ['movie', 'show']:
                continue

            for plex_location in section.locations:
                if plex_location in location_map:
                    continue

                print(f"\n🗀  Plex location: {plex_location}")
                user_input = input("→ Local folder path: ").strip()
                local_path = Path(user_input)

                if not local_path.exists() or not local_path.is_dir():
                    print("[!] Invalid folder. Skipping this location.")
                    continue

                location_map[plex_location] = str(local_path)

        # Save mappings
        with open(MAPPING_FILE, 'w', encoding='utf-8') as f:
            json.dump(location_map, f, indent=2)
            print(f"\n[+] Saved mappings to {MAPPING_FILE}")

    # === PROCESS ITEMS ===
    if stats is None:
        stats = {"total":0, "matched":0, "uploaded":0}
    displaySummary = False # will be set True at end of single or bulk mode

    # sort the mapping by key length (descending) to match longer paths first
    location_map = dict(sorted(location_map.items(), key=lambda item: len(item[0]), reverse=True))

    if search_mode:
        # === SEARCH MODE ===
        query = input("\nEnter the title to search for: ").strip()
        results = search_titles(plex, query, max_results=args.max_results)
        if not results:
            print("[!] No results found for that query.")
        elif len(results) == 1:
            selected_item = results[0]['item']
            selected_section = next(s for s in plex.library.sections() if s.type == results[0]['type'] and s.title == results[0]['library'])
            stats["total"] += 1
            print(f"\nSelected: {selected_item.title} ({getattr(selected_item, 'year', '')})")
            stats = process_item(selected_item, selected_section, location_map, upload_all, dry_run, verbose, stats)
        else:
            choice = select_from_results(results, allow_all=True)
            if choice == 'ALL':
                # process all search results
                for r in results:
                    selected_item = r['item']
                    try:
                        selected_section = next(s for s in plex.library.sections() if s.type == r['type'] and s.title == r['library'])
                    except StopIteration:
                        if verbose:
                            print(f"[!] Could not find library section for: {r['title']} ({r['library']})")
                        continue
                    stats["total"] += 1
                    print(f"\nSelected: {selected_item.title} ({getattr(selected_item, 'year', '')})")
                    stats = process_item(selected_item, selected_section, location_map, upload_all, dry_run, verbose, stats)
            elif choice is None:
                print("[!] No item selected.")
            else:
                # single selection returned
                selected_item = choice
                selected_section = None
                for r in results:
                    if r['item'] == selected_item:
                        selected_section = next(s for s in plex.library.sections() if s.type == r['type'] and s.title == r['library'])
                        break
                stats["total"] += 1
                if selected_item and selected_section:
                    print(f"\nSelected: {selected_item.title} ({getattr(selected_item, 'year', '')})")
                    stats = process_item(selected_item, selected_section, location_map, upload_all, dry_run, verbose, stats)
                else:
                    print("[!] No item selected.")

        # Prompt if the user wants to update another logo
        again = input("\nDo you want to update another ClearLogo? (y/n): ").strip().lower()
        if again == "y":
            main(stats)  # Pass stats to next call
        else:
            displaySummary = True

    else:
        # === BULK MODE ===
        print("\nStarting logo upload process...\n")

        for section in plex.library.sections():
            if section.type not in ['movie', 'show']:
                continue

            print(f"🗀  Processing library: {section.title} ({section.type})")
            items = section.all()  # Fetch all items once per section

            num_items = len(items)
            for idx, item in enumerate(items, 1):
                if not verbose:
                    print(f"\r  Progress: {idx}/{num_items} items", end='', flush=True)
                stats["total"] += 1
                stats = process_item(item, section, location_map, upload_all, dry_run, verbose, stats)
            if not verbose:
                print()  # Newline after progress for this library
        displaySummary = True

    # === SUMMARY ===
    if displaySummary:
        print("\n=== SUMMARY ===")
        print("Total items scanned:".ljust(30, ' ') + f"{stats['total']}")
        print("Logos uploaded:".ljust(30, ' ') + f"{stats['uploaded']} of {stats['matched']} matched logos")
        if dry_run:
            print('[DRY RUN] No changes made')
        print("\n--- Script Finished ---")

# --- Script Entry Point ---
if __name__ == "__main__":
    main()
