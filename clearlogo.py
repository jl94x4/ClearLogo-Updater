# --- Imports ---
import json
import sys
import plexapi

from plexapi.server import PlexServer
from plexapi.exceptions import NotFound, BadRequest

# --- Configuration ---
CONFIG_FILE = 'config.json'
MAX_SEARCH_RESULTS_DISPLAY = 30 # <<< Increased display limit for multiple results

# --- Functions ---

def load_config():
    """Loads Plex URL and Token from the JSON config file."""
    try:
        with open(CONFIG_FILE, 'r') as f:
            config_data = json.load(f)
        plex_url = config_data.get('plex_url')
        plex_token = config_data.get('plex_token')
        if not plex_url or not plex_token or plex_token == 'YOUR_PLEX_TOKEN_HERE':
             print(f"Error: Ensure 'plex_url' and 'plex_token' are correctly set in {CONFIG_FILE}.")
             return None, None
        return plex_url, plex_token
    except FileNotFoundError:
        print(f"Error: Configuration file '{CONFIG_FILE}' not found.")
        return None, None
    except json.JSONDecodeError:
        print(f"Error: Could not decode JSON from '{CONFIG_FILE}'. Check format.")
        return None, None
    except Exception as e:
        print(f"An unexpected error occurred reading config: {e}")
        return None, None

def connect_plex(url, token):
    """Connects to the Plex server."""
    try:
        print(f"Attempting to connect to Plex server at {url}...")
        plex = PlexServer(url, token, timeout=30)
        print(f"Successfully connected to Plex server: {plex.friendlyName} (Version: {plex.version})")
        return plex
    except Exception as e:
        print(f"\nError connecting to Plex server: {e}")
        print("Check URL, token, server status, and network connection.")
        return None

# --- THIS FUNCTION IS UPDATED (Uses MAX_SEARCH_RESULTS_DISPLAY) ---
def find_and_confirm_item(plex):
    """Gets item name, searches ALL relevant libraries, allows selection from multiple results, proceeds directly after list selection."""
    try:
        media_sections = [s for s in plex.library.sections() if s.type in ('show', 'movie')]
        if not media_sections:
            print("Error: No Movie or TV Show libraries found on the server.")
            return None
    except Exception as e:
        print(f"Error fetching library sections: {e}")
        return None

    while True:
        try:
            item_name = input("Enter Movie or TV Show name (partial name OK, Enter to exit): ").strip()
            if not item_name: return None
            year_input = input("Enter the release year (optional, press Enter to skip): ").strip()
            item_year = None
            if year_input:
                try: item_year = int(year_input)
                except ValueError: print("Invalid year format."); continue

            print(f"\nSearching ALL Movie/TV libraries for items containing '{item_name}'" + (f" ({item_year})" if item_year else "") + "...")
            all_results = []
            search_kwargs = {'title__icontains': item_name}
            if item_year: search_kwargs['year'] = item_year

            print("Searching...")
            for section in media_sections:
                try:
                    results_in_section = section.search(**search_kwargs)
                    all_results.extend(results_in_section)
                except Exception as e:
                    print(f"Warning: Error searching library '{section.title}': {e}")
                    continue
            print("Search complete.")

            if not all_results:
                print("No items found matching those details in any relevant library.")
                if not ask_try_again("search again with different terms"): return None
                continue

            elif len(all_results) == 1: # Exactly one result
                target_item = all_results[0]
                yr = getattr(target_item, 'year', "N/A")
                item_type = getattr(target_item, 'type', 'Unknown').capitalize()
                library_title = "Unknown Library"
                try: library_title = target_item.section().title
                except Exception: pass
                print(f"\nFound unique match: {target_item.title} ({yr}) [{item_type} in '{library_title}']")
                while True:
                    confirm = input("Is this correct? (y/n): ").lower()
                    if confirm == 'y': return target_item
                    if confirm == 'n': print("Okay, item not confirmed."); return None
                    print("Please enter 'y' or 'n'.")

            else: # Multiple results
                print(f"\nFound {len(all_results)} possible matches across all libraries:")
                # Use the constant for display limit
                displayed_results = all_results[:MAX_SEARCH_RESULTS_DISPLAY]

                for i, item in enumerate(displayed_results):
                    yr = getattr(item, 'year', "N/A")
                    item_type = getattr(item, 'type', 'Unknown').capitalize()
                    library_title = "Unknown Library"
                    try: library_title = item.section().title
                    except Exception: pass
                    print(f"  {i + 1}. {item.title} ({yr}) [{item_type} in '{library_title}']")

                # Check if results were truncated based on the constant
                if len(all_results) > MAX_SEARCH_RESULTS_DISPLAY:
                    print(f"  ... ({len(all_results) - MAX_SEARCH_RESULTS_DISPLAY} more not shown)")

                search_again_option_num = len(displayed_results) + 1
                print(f"  {search_again_option_num}. Search Again / Refine Search")

                while True: # Loop for selection
                    try:
                        choice_input = input(f"Select number (1-{search_again_option_num}) or press Enter to exit: ")
                        if not choice_input: return None

                        choice_num = int(choice_input)

                        if 1 <= choice_num <= len(displayed_results):
                            selected_item = displayed_results[choice_num - 1]
                            yr = getattr(selected_item, 'year', "N/A")
                            item_type = getattr(selected_item, 'type', 'Unknown').capitalize()
                            library_title = "Unknown Library"
                            try: library_title = selected_item.section().title
                            except Exception: pass
                            print(f"\nYou selected: {selected_item.title} ({yr}) [{item_type} in '{library_title}']")
                            return selected_item # Return directly

                        elif choice_num == search_again_option_num:
                            print("Okay, preparing to search again...")
                            break # Break selection loop to re-prompt search terms

                        else:
                            print(f"Invalid choice. Please enter a number between 1 and {search_again_option_num}.")

                    except ValueError: print("Invalid input. Please enter a number.")

                continue # Continue outer loop if 'Search Again' was chosen

        except KeyboardInterrupt:
            print("\nOperation cancelled by user.")
            return None
        except Exception as e:
            print(f"An unexpected error occurred: {e}")
            if not ask_try_again("try again"): return None
            continue


def ask_try_again(action="try again"):
    """Asks user if they want to try the specified action again."""
    while True:
        retry = input(f"Do you want to {action}? (y/n): ").lower()
        if retry == 'y': return True
        if retry == 'n': print(f"Okay, cancelling {action}."); return False
        print("Please enter 'y' or 'n'.")

def update_logo(item):
    """Asks for logo URL and applies it using item.uploadLogo(). Returns True on success, False otherwise."""
    while True:
        try:
            logo_url = input(f"Enter the URL for the logo image for '{item.title}' (or press Enter to cancel): ").strip()
            if not logo_url: print("Logo update cancelled."); return False
            if not logo_url.lower().startswith(('http://', 'https://')):
                 print("Invalid URL format."); continue

            print(f"Applying logo from {logo_url} to '{item.title}'...")
            item.uploadLogo(url=logo_url)
            print(f"Logo for '{item.title}' update command sent successfully!")
            return True

        except BadRequest as e:
            print(f"\nError applying logo: {e}")
            print("Check URL, image format, and server accessibility.")
            if not ask_try_again("try a different URL"): return False

        except AttributeError as e:
             if 'uploadLogo' in str(e):
                 item_type = getattr(item, 'type', 'item')
                 print(f"\n*** Failed: It seems '{item_type}' objects might not support '.uploadLogo()' in your plexapi version. ***")
             else:
                 print(f"\nError during upload: {e}")
             return False

        except KeyboardInterrupt:
            print("\nOperation cancelled by user.")
            return False

        except Exception as e:
            print(f"\nAn unexpected error occurred during logo upload: {e}")
            if not ask_try_again("try applying the logo again"): return False


def main():
    """Main execution function with loop, searching across all relevant libraries."""
    print("--- Plex Logo Updater (Movies & TV Shows - All Libraries) ---")

    plex_url, plex_token = load_config()
    if not plex_url or not plex_token: sys.exit(1)

    plex = connect_plex(plex_url, plex_token)
    if not plex: sys.exit(1)

    while True:
        print("\n" + "="*40)
        item = find_and_confirm_item(plex)
        if not item:
            print("\nNo item selected or operation cancelled.")
            break

        success = update_logo(item)
        if success:
            print(f"\nLogo updated successfully for '{item.title}'.")
            if not ask_try_again("update another logo"): break
        else:
            print(f"\nLogo update did not complete for '{item.title}'.")
            if not ask_try_again("try another update"): break

    print("\n--- Script Finished ---")


# --- Script Entry Point ---
if __name__ == "__main__":
    main()
