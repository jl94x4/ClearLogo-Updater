# Plex TV Show Logo Updater

A command-line Python script that allows you to easily update the logo (often called ClearLogo) image for TV shows in your Plex Media Server library by providing an image URL. It uses the `plexapi` library and an interactive prompt system.

![image](https://github.com/user-attachments/assets/bf2c4051-c6bc-407b-aa5d-0ee3164bfd7c)

![image](https://i.imgur.com/nlSvSGi.jpeg)

## Features

* Interactive command-line interface.
* Connects to your Plex server securely using URL and token.
* Reads configuration from a simple `config.json` file (keeps your token out of the script).
* Searches for TV shows and Movies by name and optional year from all libraries.
* Partial matches for Shows (e.g you can type just a part of show name (e.g., "Planet" for "Planet Earth") and it should find matching shows containing that text.)
* Handles cases where multiple shows match the search.
* Requires user confirmation before applying changes.
* Updates the show's logo using a provided image URL via the `uploadLogo` method.
* Loops automatically after success or failure, allowing updates to multiple shows in one session.
* Basic error handling for connection, search, and upload issues.
* Allows cancellation at various stages (Ctrl+C or pressing Enter at specific prompts).

## Requirements

* **Python 3.x:** (Developed with 3.12, should work on recent 3.x versions).
* **`pip`:** Python package installer (usually included with Python).
* **`plexapi` library:** Requires a **recent version** (e.g., 4.17.0 or later) that includes the `uploadLogo` method for `Show` objects.

## Installation & Setup

1.  **Get the script:**
    * Clone this repository:
        ```bash
        git clone https://github.com/jl94x4/ClearLogo-Updater.git
        cd ClearLogo-Updater
        ```
    * Or, download the `clearlogo.py` file directly.

2.  **Install/Upgrade `plexapi`:**
    * Open your terminal or command prompt in the script's directory.
    * Run the following command to ensure you have a recent version:
        ```bash
        pip install --upgrade plexapi
        ```
    * Or, run `pip install -r requirements.txt`

3.  **Create Configuration File:**
    * In the same directory as `clearlogo.py`, create a file named `config.json`.
    * Add the following content to `config.json`:
        ```json
        {
          "plex_url": "http://YOUR_PLEX_IP_OR_DOMAIN:32400",
          "plex_token": "YOUR_PLEX_TOKEN_HERE"
        }
        ```
    * Or, download `config.json` file directly and edit accordingly  

4.  **Edit `config.json`:**
    * Replace `http://YOUR_PLEX_IP_OR_DOMAIN:32400` with the full URL to access your Plex server (including the port, usually 32400).
    * Replace `YOUR_PLEX_TOKEN_HERE` with a valid Plex authentication token. You can find instructions here: [Finding an Authentication Token | Plex Support](https://support.plex.tv/articles/204059436-finding-an-authentication-token-x-plex-token/)

## Usage

1.  Make sure your Plex Media Server is running.
2.  Open your terminal or command prompt.
3.  Navigate (`cd`) to the directory where you saved `clearlogo.py` and `config.json`.
4.  Run the script using:
    ```bash
    python clearlogo.py
    ```
5.  Follow the interactive prompts:
    * The script will attempt to connect to your Plex server.
    * Enter the name of the TV show or Movie you want to update.
    * Optionally, enter the release year of the show to refine the search. (significantly speeds up searching)
    * If a unique show is found, confirm it's the correct one (`y/n`). (Answering 'n' goes back to library selection).
    * Enter the full URL (starting with `http://` or `https://`) of the logo image you want to apply. (Press Enter without typing a URL to cancel the update for this specific show).
    * The script will attempt to upload the logo.
    * After success or failure, it will ask if you want to update another logo (`y/n`). Answering 'n' will exit the script.

## Important Notes

* **`plexapi` Version:** This script critically depends on the `uploadLogo` method being available on `Show` objects in your installed `plexapi` version. Versions prior to approximately 4.16.0 or 4.17.0 (like 4.15.6) will **not** work and will produce an `AttributeError`. Always ensure `plexapi` is up-to-date (`pip install --upgrade plexapi`).
* **Image URLs:** Provide direct URLs to valid image files (e.g., `.png`, `.jpg`). URLs pointing to web pages or unsupported formats will likely cause errors during the upload attempt (`BadRequest` error). The Plex server needs to be able to access and process the image from the URL.
* **Plex Token:** Ensure the token used in `config.json` is valid and has permissions to edit metadata in your Plex library.

## License

This project is licensed under the MIT License - see the `LICENSE` file for details (or choose another license if you prefer).

## Contributing

Contributions are welcome! Please feel free to submit a pull request or open an issue if you find bugs or have suggestions for improvements.
