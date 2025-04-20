# --- Imports ---
import json
import sys
import plexapi # Import plexapi itself (optional, but allows version check)

from plexapi.server import PlexServer
from plexapi.exceptions import NotFound, BadRequest # Keep BadRequest for URL/fetch errors

# --- Configuration ---
CONFIG_FILE = 'config.json' # Reads config from config.json

# --- Functions ---

def load_config():
    """Loads Plex URL and Token from the JSON config file."""
    try:
        with open(CONFIG_FILE, 'r') as f:
            config_data = json.load(f)
        plex_url = config_data.get('plex_url')
        plex_token = config_data.get('plex_token')
        # Basic validation
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
        plex = PlexServer(url, token, timeout=30) # Added timeout
        # Optional: Print version upon connection
        # print(f"Using plexapi version: {plexapi.__version__}")
        print(f"Successfully connected to Plex server: {plex.friendlyName} (Version: {plex.version})")
        return plex
    except Exception as e:
        print(f"\nError connecting to Plex server: {e}")
        print("Check URL, token, server status, and network connection.")
        return None

def select_tv_section(plex):
    """Lists TV show sections and lets the user select one."""
    try:
        # Filter for TV Show libraries
        tv_sections = [s for s in plex.library.sections() if s.type == 'show']
    except Exception as e:
        print(f"Error fetching library sections: {e}")
        return None # Return None on error
    if not tv_sections:
        print("Error: No TV Show libraries found.")
        return None # Return None if no sections

    print("\nAvailable TV Show Libraries:")
    for i, section in enumerate(tv_sections):
        print(f"{i + 1}: {section.title}")

    # Loop for valid user input
    while True:
        try:
            choice = input(f"Select the library number (1-{len(tv_sections)}) (or press Enter to exit): ")
            if not choice: # Allow exiting by pressing Enter
                return None
            index = int(choice) - 1
            if 0 <= index < len(tv_sections):
                selected_section = tv_sections[index]
                print(f"Selected library: '{selected_section.title}'")
                return selected_section
            else:
                print(f"Invalid choice (1-{len(tv_sections)}).")
        except ValueError:
            print("Invalid input. Please enter a number.")
        except KeyboardInterrupt:
            print("\nOperation cancelled by user.")
            return None # Return None on Ctrl+C

# --- THIS FUNCTION IS UPDATED ---
def find_and_confirm_show(section):
    """Gets show name (allows partial), optional year, searches Plex using case-insensitive contains, and asks for confirmation.""" # Updated docstring
    while True:
        try:
            # Update prompt to reflect partial matching is okay
            show_name = input("Enter TV show name (partial name OK, Enter to go back): ").strip()
            if not show_name: # Allow returning to library selection
                return None
            year_input = input("Enter the release year (optional, press Enter to skip): ").strip()
            # Validate year if provided
            show_year = None
            if year_input:
                try:
                    show_year = int(year_input)
                except ValueError:
                    print("Invalid year format. Please enter a number or leave blank.")
                    continue

            # --- Use case-insensitive contains search ---
            print(f"\nSearching for shows containing '{show_name}'" + (f" ({show_year})" if show_year else "") + f" in '{section.title}'...")
            # Build search keyword arguments
            search_kwargs = {'title__icontains': show_name}
            if show_year:
                search_kwargs['year'] = show_year # Year still needs to be exact if provided
            # Perform the search using the modified filter
            results = section.search(**search_kwargs)
            # --------------------------------------------

            # Handle search results
            if not results:
                print("No shows found containing those details.")
                # Ask if user wants to try searching again (different terms)
                if not ask_try_again("search again"):
                     return None # If not, return to library select
                continue # If yes, loop back to ask for name/year

            elif len(results) == 1: # Exactly one result, proceed to confirmation
                target_show = results[0]
                yr = getattr(target_show, 'year', "N/A")
                print(f"\nFound show: {target_show.title} ({yr})")
                # Confirm with the user
                while True:
                    confirm = input("Is this correct? (y/n): ").lower()
                    if confirm == 'y':
                        return target_show # Return the confirmed show object
                    elif confirm == 'n':
                         print("Okay, show not confirmed.")
                         # If user says no, go back to library select
                         return None
                    else:
                        print("Please enter 'y' or 'n'.")

            else: # Multiple results found
                print(f"\nFound {len(results)} possible matches:")
                # Display the matches found (limit display if desired, e.g., max 15)
                for i, show in enumerate(results[:15]):
                    yr = getattr(show, 'year', "N/A")
                    print(f"  {i + 1}. {show.title} ({yr})")
                if len(results) > 15:
                    print(f"  ... and {len(results)-15} more.")

                print("Multiple matches found. Please try to be more specific")
                print("(e.g., add the year or more words from the title).")
                # Ask if user wants to refine search terms
                if not ask_try_again("refine your search"):
                    return None # If not, return to library select
                continue # If yes, loop back to ask for name/year

        # Handle potential errors during input/search
        except KeyboardInterrupt:
            print("\nOperation cancelled by user.")
            return None # Return None on Ctrl+C
        except Exception as e:
            print(f"An unexpected error occurred during search: {e}")
            if not ask_try_again("search again"):
                 return None
            continue # Allow retrying search

def ask_try_again(action="try again"):
    """Asks user if they want to try the specified action again."""
    while True:
        # Include option to cancel back to library selection
        retry = input(f"Do you want to {action}? (y/n): ").lower()
        if retry == 'y': return True
        if retry == 'n':
            print(f"Okay, cancelling {action}.")
            return False # Indicates user chose not to retry the specific action
        print("Please enter 'y' or 'n'.")

# --- Uses the Corrected uploadLogo Method ---
def update_logo(show):
    """Asks for logo URL and applies it using show.uploadLogo(). Returns True on success, False otherwise."""
    while True:
        try:
            logo_url = input(f"Enter the URL for the logo image for '{show.title}' (or press Enter to cancel): ").strip()
            if not logo_url: # Allow cancelling logo update
                print("Logo update cancelled.")
                return False
            # Basic URL validation
            if not logo_url.lower().startswith(('http://', 'https://')):
                 print("Invalid URL format. It should start with http:// or https://")
                 continue

            print(f"Applying logo from {logo_url} to '{show.title}'...")

            # --- Use the confirmed working uploadLogo method ---
            show.uploadLogo(url=logo_url)
            # --------------------------------------------------

            print(f"Logo for '{show.title}' update command sent successfully!")
            return True # Indicate success

        except BadRequest as e:
            # Handle errors like invalid URL, image format, or fetch failure
            print(f"\nError applying logo: {e}")
            print("This often means the URL was invalid, the image format is unsupported by Plex, or the fetch failed.")
            # Ask if user wants to retry this specific upload (different URL)
            if not ask_try_again("try a different URL"):
                return False # If not retrying, return False

        except AttributeError as e:
             # This error should NOT happen now if plexapi is updated correctly
             print(f"\nError during upload: {e}")
             print("\n*** AttributeError occurred even after updating plexapi. ***")
             print("This is unexpected. Please double-check the plexapi version ('pip show plexapi').")
             return False # Return False on unexpected error

        except KeyboardInterrupt:
            print("\nOperation cancelled by user.")
            return False # Return False on Ctrl+C

        except Exception as e:
            # Catch any other unexpected errors during upload
            print(f"\nAn unexpected error occurred during logo upload: {e}")
            # Ask if user wants to retry this specific upload
            if not ask_try_again("try applying the logo again"):
                 return False # If not retrying, return False


def main():
    """Main execution function with loop."""
    print("--- Plex Logo Updater ---")

    # Load config once
    plex_url, plex_token = load_config()
    if not plex_url or not plex_token:
        sys.exit(1) # Error message already printed

    # Connect to Plex once
    plex = connect_plex(plex_url, plex_token)
    if not plex:
        sys.exit(1) # Error message already printed

    # --- Main Loop ---
    while True:
        print("\n" + "="*40) # Separator for clarity between runs
        print("Starting new update cycle...")

        # 1. Select TV Show library
        section = select_tv_section(plex)
        if not section:
            # User likely cancelled section selection (pressed Enter or Ctrl+C)
            print("\nNo library selected or operation cancelled.")
            break # Exit the main loop

        # 2. Find and confirm the show within the selected library
        show = find_and_confirm_show(section)
        if not show:
            # User likely cancelled show finding/confirmation (pressed Enter or Ctrl+C or said 'n')
            print("\nNo show selected or confirmed, returning to library selection...")
            continue # Go to the start of the next loop iteration (select library)

        # 3. Update the logo for the confirmed show
        success = update_logo(show)
        if success:
            print(f"\nLogo updated successfully for '{show.title}'.")
            # Ask if user wants to continue with another show
            if not ask_try_again("update another logo"):
                 break # Exit the main loop if user says no
            # else: continue loop implicitly
        else:
            # Error/cancellation message printed within update_logo or ask_try_again
            print(f"\nLogo update did not complete for '{show.title}'.")
            # Ask if user wants to try again (which means selecting library/show)
            if not ask_try_again("try another update (select library/show)"):
                 break # Exit the main loop if user says no
            # else: continue loop implicitly

        # Loop continues here if user wants to update another or try again

    print("\n--- Script Finished ---") # Message when loop is broken


# --- Script Entry Point ---
if __name__ == "__main__":
    main()
