# --- Imports ---
import json
import os
import sys
import time
import argparse
import requests
from plexapi.server import PlexServer
from plexapi.exceptions import BadRequest, NotFound

# --- Configuration ---
CONFIG_FILE = 'config.json'
FANART_API_BASE_URL = "http://webservice.fanart.tv/v3/"

# --- Functions ---

def load_config():
    """Loads Plex URL, Token, and Fanart.tv API key from the JSON config file."""
    try:
        with open(CONFIG_FILE, 'r') as f:
            config_data = json.load(f)
        plex_url = config_data.get('plex_url')
        plex_token = config_data.get('plex_token')
        fanart_api_key = config_data.get('fanart_api_key')
        fanart_key_type = config_data.get('fanart_key_type', 'free').lower()
        if not all([plex_url, plex_token, fanart_api_key]):
            print(f"Error: Ensure 'plex_url', 'plex_token', and 'fanart_api_key' are set in {CONFIG_FILE}.")
            return None, None, None, None
        return plex_url, plex_token, fanart_api_key, fanart_key_type
    except FileNotFoundError:
        print(f"Error: Configuration file '{CONFIG_FILE}' not found.")
        return None, None, None, None
    except json.JSONDecodeError:
        print(f"Error: Could not decode JSON from '{CONFIG_FILE}'. Check format.")
        return None, None, None, None

def connect_plex(url, token):
    """Connects to the Plex server."""
    try:
        print(f"Connecting to Plex server at {url}...")
        return PlexServer(url, token, timeout=60)
    except Exception as e:
        print(f"Error connecting to Plex: {e}")
        return None

def get_fanart_logo_url(item, api_key):
    """Finds a clearlogo URL for a Plex item, returning the URL and a status message."""
    item_type = 'movies' if item.type == 'movie' else 'tv'
    
    media_id = None
    id_type_to_find = 'tvdb' if item_type == 'tv' else 'tmdb'
    
    for guid in item.guids:
        if id_type_to_find in guid.id:
            try:
                media_id = guid.id.split('//')[1]
                break
            except IndexError:
                continue

    if not media_id:
        return None, "Missing TVDB/TMDB ID"

    url = f"{FANART_API_BASE_URL}{item_type}/{media_id}?api_key={api_key}"
    
    try:
        response = requests.get(url)
        response.raise_for_status()
        data = response.json()

        logos = data.get('hdclearlogo', []) + data.get('clearlogo', [])
        if not logos:
            return None, "No logo found in Fanart.tv response"

        logos.sort(key=lambda x: int(x.get('likes', 0)), reverse=True)
        return logos[0]['url'], "Logo found"

    except requests.exceptions.RequestException as e:
        if e.response and e.response.status_code == 404:
            return None, "Not found on Fanart.tv"
        return None, f"API error: {e}"
    except (KeyError, IndexError, ValueError, TypeError):
        return None, "Invalid data from Fanart.tv"

def update_plex_item_logo(item, logo_url):
    """Applies a logo to a Plex item, returning success status and a message."""
    try:
        item.uploadLogo(url=logo_url)
        return True, "Logo updated successfully"
    except Exception as e:
        return False, f"Could not apply logo: {e}"

def run_automatic_mode(plex, fanart_api_key, throttle_delay, libraries=None, verbose=False):
    """Scans all libraries and automatically updates logos."""
    print("--- Running in Automatic Mode ---")
    try:
        all_sections = plex.library.sections()
        if libraries:
            media_sections = [s for s in all_sections if s.title in libraries]
            if not media_sections:
                print(f"Could not find any of the specified libraries: {', '.join(libraries)}")
                print(f"Available libraries: {[s.title for s in all_sections]}")
                return
        else:
            media_sections = [s for s in all_sections if s.type in ('show', 'movie')]
    except Exception as e:
        print(f"Error fetching library sections: {e}")
        return

    for section in media_sections:
        print(f"\nProcessing library: '{section.title}' ({section.type})")
        try:
            for item in section.all():
                time.sleep(throttle_delay)
                logo_url, status_msg = get_fanart_logo_url(item, fanart_api_key)

                if logo_url:
                    success, update_msg = update_plex_item_logo(item, logo_url)
                    if success:
                        print(f"  [SUCCESS] {item.title}")
                    else:
                        print(f"  [FAILED]  {item.title} ({update_msg})")
                elif verbose:
                    print(f"  [SKIPPED] {item.title} ({status_msg})")

        except Exception as e:
            print(f"  - Error processing items in '{section.title}': {e}")

def run_interactive_mode(plex, fanart_api_key, throttle_delay):
    """Allows a user to manually select an item and update its logo."""
    print("--- Running in Interactive Mode ---")
    while True:
        try:
            item_name = input("Enter Movie or TV Show name (or press Enter to exit): ").strip()
            if not item_name: break

            results = plex.search(item_name)
            media_results = [r for r in results if r.type in ('movie', 'show')]

            if not media_results:
                print("No items found matching that name.")
                continue

            print("\nFound possible matches:")
            for i, item in enumerate(media_results):
                print(f"  {i + 1}. {item.title} ({item.year}) [{item.type.capitalize()}]")

            try:
                choice = int(input(f"Select a number (1-{len(media_results)}) or 0 to search again: "))
                if choice == 0: continue
                selected_item = media_results[choice - 1]
            except (ValueError, IndexError):
                print("Invalid selection.")
                continue

            print(f"\nSelected: '{selected_item.title}'. Searching for logo on fanart.tv...")
            time.sleep(throttle_delay)
            logo_url = get_fanart_logo_url(selected_item, fanart_api_key)

            if not logo_url:
                print("Could not find a verified logo for this item on fanart.tv.")
                continue

            print(f"Found logo: {logo_url}")
            confirm = input("Do you want to apply this logo? (y/n): ").lower()
            if confirm == 'y':
                update_plex_item_logo(selected_item, logo_url)

            if input("\nUpdate another item? (y/n): ").lower() != 'y':
                break
        except (KeyboardInterrupt, EOFError):
            break
    print("\nExiting interactive mode.")

def main():
    """Main execution function."""
    parser = argparse.ArgumentParser(description="P Logo Updater")
    parser.add_argument('--interactive', action='store_true', help="Run in interactive mode.")
    parser.add_argument('--libraries', nargs='+', help="A list of Plex library names to scan.")
    parser.add_argument('--verbose', action='store_true', help="Enable detailed logging for skipped items.")
    args = parser.parse_args()

    plex_url, plex_token, fanart_api_key, fanart_key_type = load_config()
    if not all([plex_url, plex_token, fanart_api_key, fanart_key_type]):
        sys.exit(1)

    throttle_delay = 0.5 if fanart_key_type == 'paid' else 1.0
    print(f"Using a throttle delay of {throttle_delay} seconds between API requests.")

    plex = connect_plex(plex_url, plex_token)
    if not plex:
        sys.exit(1)
    print(f"Successfully connected to Plex server: {plex.friendlyName}")

    if args.interactive:
        run_interactive_mode(plex, fanart_api_key, throttle_delay)
    else:
        run_automatic_mode(plex, fanart_api_key, throttle_delay, args.libraries, args.verbose)

    print("\n--- Script Finished ---")

if __name__ == "__main__":
    main()
