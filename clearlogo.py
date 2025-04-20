# --- Imports ---
import json
import sys
import plexapi

from plexapi.server import PlexServer
from plexapi.exceptions import NotFound, BadRequest

# --- Configuration ---
CONFIG_FILE = 'config.json'

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

def select_media_section(plex):
    """Lists Movie and TV show sections and lets the user select one."""
    try:
        media_sections = [s for s in plex.library.sections() if s.type in ('show', 'movie')]
    except Exception as e:
        print(f"Error fetching library sections: {e}")
        return None
    if not media_sections:
        print("Error: No Movie or TV Show libraries found.")
        return None

    print("\nAvailable Movie and TV Show Libraries:")
    for i, section in enumerate(media_sections):
        print(f"{i + 1}: {section.title} ({section.type.capitalize()})")

    while True:
        try:
            choice = input(f"Select the library number (1-{len(media_sections)}) (or press Enter to exit): ")
            if not choice: return None
            index = int(choice) - 1
            if 0 <= index < len(media_sections):
                selected_section = media_sections[index]
                print(f"Selected library: '{selected_section.title}' ({selected_section.type.capitalize()})")
                return selected_section
            else:
                print(f"Invalid choice (1-{len(media_sections)}).")
        except ValueError:
            print("Invalid input. Please enter a number.")
        except KeyboardInterrupt:
            print("\nOperation cancelled by user.")
            return None

# --- THIS FUNCTION IS UPDATED ---
def find_and_confirm_item(section):
    """Gets item name, searches Plex, allows selection from multiple results, confirms single results, and proceeds directly after list selection.""" # Updated docstring
    while True:
        try:
            item_name = input("Enter Movie or TV Show name (partial name OK, Enter to go back): ").strip()
            if not item_name: return None
            year_input = input("Enter the release year (optional, press Enter to skip): ").strip()
            item_year = None
            if year_input:
                try: item_year = int(year_input)
                except ValueError: print("Invalid year format."); continue

            print(f"\nSearching for items containing '{item_name}'" + (f" ({item_year})" if item_year else "") + f" in '{section.title}'...")
            search_kwargs = {'title__icontains': item_name}
            if item_year: search_kwargs['year'] = item_year
            results = section.search(**search_kwargs)

            if not results:
                print("No items found containing those details.")
                if not ask_try_again("search again"): return None
                continue

            elif len(results) == 1: # Exactly one result - KEEP Confirmation here
                target_item = results[0]
                yr = getattr(target_item, 'year', "N/A")
                item_type = getattr(target_item, 'type', 'Unknown').capitalize()
                print(f"\nFound {item_type}: {target_item.title} ({yr})")
                while True: # Confirmation loop for single result
                    confirm = input("Is this correct? (y/n): ").lower()
                    if confirm == 'y': return target_item
                    if confirm == 'n': print("Okay, item not confirmed."); return None
                    print("Please enter 'y' or 'n'.")

            else: # --- Multiple results - REMOVED INNER CONFIRMATION ---
                print(f"\nFound {len(results)} possible matches:")
                max_display = 15
                displayed_results = results[:max_display]

                for i, item in enumerate(displayed_results):
                    yr = getattr(item, 'year', "N/A")
                    item_type = getattr(item, 'type', 'Unknown').capitalize()
                    print(f"  {i + 1}. {item.title} ({yr}) [{item_type}]")
                if len(results) > max_display:
                    print(f"  ... ({len(results) - max_display} more not shown)")

                search_again_option_num = len(displayed_results) + 1
                print(f"  {search_again_option_num}. Search Again / Refine Search")

                # Loop to get a valid selection from the list
                while True:
                    try:
                        choice_input = input(f"Select number (1-{search_again_option_num}) or press Enter to go back: ")
                        if not choice_input: return None

                        choice_num = int(choice_input)

                        if 1 <= choice_num <= len(displayed_results):
                            # User selected a specific item from the list
                            selected_item = displayed_results[choice_num - 1]
                            yr = getattr(selected_item, 'year', "N/A")
                            item_type = getattr(selected_item, 'type', 'Unknown').capitalize()
                            # Print selection, but proceed directly without asking for confirmation again
                            print(f"\nYou selected: {selected_item.title} ({yr}) [{item_type}]")
                            # --- Confirmation Removed ---
                            return selected_item # Return the chosen item immediately

                        elif choice_num == search_again_option_num:
                            # User chose to search again
                            print("Okay, preparing to search again...")
                            break # Break selection loop to re-prompt search terms

                        else:
                            # Input number was out of range
                            print(f"Invalid choice. Please enter a number between 1 and {search_again_option_num}.")
                            # Loop continues to ask for selection number

                    except ValueError:
                        print("Invalid input. Please enter a number.")
                    # Let KeyboardInterrupt be caught by the outer handler

                # If the selection loop was broken (by choosing Search Again),
                # continue the main outer loop to re-prompt for search terms
                continue
            # --- End of multiple results logic ---

        except KeyboardInterrupt:
            print("\nOperation cancelled by user.")
            return None
        except Exception as e:
            print(f"An unexpected error occurred during search: {e}")
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
            return True # Indicate success

        except BadRequest as e:
            print(f"\nError applying logo: {e}")
            print("This often means the URL was invalid, image format unsupported, or fetch failed.")
            if not ask_try_again("try a different URL"): return False

        except AttributeError as e:
             if 'uploadLogo' in str(e):
                 item_type = getattr(item, 'type', 'item')
                 print(f"\n*** Failed: It seems '{item_type}' objects might not support '.uploadLogo()' in your plexapi version. ***")
             else:
                 print(f"\nError during upload: {e}")
                 print("\n*** AttributeError occurred. Please check your plexapi version. ***")
             return False

        except KeyboardInterrupt:
            print("\nOperation cancelled by user.")
            return False

        except Exception as e:
            print(f"\nAn unexpected error occurred during logo upload: {e}")
            if not ask_try_again("try applying the logo again"): return False


def main():
    """Main execution function with loop, supporting Movies and TV Shows."""
    print("--- Plex Logo Updater (Movies & TV Shows) ---")

    plex_url, plex_token = load_config()
    if not plex_url or not plex_token: sys.exit(1)

    plex = connect_plex(plex_url, plex_token)
    if not plex: sys.exit(1)

    while True:
        print("\n" + "="*40)
        print("Starting new update cycle...")
        section = select_media_section(plex)
        if not section: print("\nNo library selected or operation cancelled."); break
        item = find_and_confirm_item(section)
        if not item: print("\nNo item selected or confirmed, returning to library selection..."); continue
        success = update_logo(item)
        if success:
            print(f"\nLogo updated successfully for '{item.title}'.")
            if not ask_try_again("update another logo"): break
        else:
            print(f"\nLogo update did not complete for '{item.title}'.")
            if not ask_try_again("try another update (select library/item)"): break

    print("\n--- Script Finished ---")


# --- Script Entry Point ---
if __name__ == "__main__":
    main()
