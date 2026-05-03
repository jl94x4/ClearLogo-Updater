# Plex ClearLogo Updater Scripts

This repository contains two Python scripts for updating ClearLogo (logo) images in your Plex Media Server:

- **clearlogo.py**: Interactive, per-show/movie logo updater using image URLs.
- **local-clearlogo.py**: Bulk updater that applies local logo image files to all Movies and TV Shows in your Plex libraries.

---

## Scripts Overview

### 1. `clearlogo.py` – Interactive Logo Updater

A command-line Python script that allows you to easily update the logo (often called ClearLogo) image for TV shows or movies in your Plex Media Server library by providing an image URL. It uses the `plexapi` library and an interactive prompt system.

![image](https://github.com/user-attachments/assets/bf2c4051-c6bc-407b-aa5d-0ee3164bfd7c)
![image](https://i.imgur.com/nlSvSGi.jpeg)

#### Features

* Interactive command-line interface.
* Connects to your Plex server securely using URL and token.
* Reads configuration from a simple `config.json` file (keeps your token out of the script).
* Searches for TV shows and Movies by name and optional year from all libraries.
* Partial matches for Shows (e.g., type "Planet" for "Planet Earth").
* Handles cases where multiple shows match the search.
* Requires user confirmation before applying changes.
* Updates the show's logo using a provided image URL via the `uploadLogo` method.
* Loops automatically after success or failure, allowing updates to multiple shows in one session.
* Basic error handling for connection, search, and upload issues.
* Allows cancellation at various stages (Ctrl+C or pressing Enter at specific prompts).

---

### 2. `local-clearlogo.py` – Bulk Local Logo Updater

A command-line Python script to **bulk update ClearLogo images for all Movies and TV Shows** in your Plex libraries using local image files. This script scans your media folders for `logo.png`, `logo.jpg`, `clearlogo.png`, or `clearlogo.jpg` files and uploads them to Plex for each matching item.

#### Features

* Bulk updates logos for all Movies and TV Shows in all Plex libraries.
* Uses local image files (`logo.png`, `clearlogo.png`, etc.) found in your media folders.
* Interactive mapping of Plex library paths to your local filesystem.
* Supports a dry-run mode to preview changes without uploading.
* Optionally uploads only missing logos, or overwrites all logos.
* Verbose mode for detailed output, or progress bar for concise feedback.
* Option to clear and rebuild the local mapping configuration.
* Reads Plex connection info from `config.json`.
* **Configurable upload delay** between logo uploads to avoid overwhelming your Plex server (see `UPLOAD_DELAY` in the script).

#### Example Usage

```bash
python local-clearlogo.py --verbose --dry-run
python local-clearlogo.py --all
python local-clearlogo.py --search
python local-clearlogo.py --search --max-results 15
```

**Parameters:**
- `-v`, `--verbose` : Enable detailed output.
- `-a`, `--all` : Upload images for all items (overwrite existing logos).
- `-d`, `--dry-run` : Preview what would be changed, but make no changes.
- `-c`, `--clear-mapping` : Clear the current mapping configuration file.
- `-s`, `--search` : Search for titles and upload logos for selected items.  
  Prompts you to search for a specific title, select it from the results, and upload a logo from your local folder. You can select a single item or update all search results at once. Useful for targeted updates without running the default bulk process.
- `-m`, `--max-results` : Maximum number of search results in search mode (default: 30).

---

## Requirements

* **Python 3.x:** (Developed with 3.12, should work on recent 3.x versions).
* **`pip`:** Python package installer (usually included with Python).
* **`plexapi` library:** Requires a **recent version** (e.g., 4.17.0 or later) that includes the `uploadLogo` method for `Show` objects.

---

## Installation & Setup

1.  **Get the scripts:**
    * Clone this repository:
        ```bash
        git clone https://github.com/jl94x4/ClearLogo-Updater.git
        cd ClearLogo-Updater
        ```
    * Or, download the `clearlogo.py` and/or `local-clearlogo.py` files directly.

2.  **Install/Upgrade `plexapi`:**
    * Open your terminal or command prompt in the script's directory.
    * Run the following command to ensure you have a recent version:
        ```bash
        pip install --upgrade plexapi
        ```
    * Or, run `pip install -r requirements.txt`

3.  **Create Configuration File:**
    * In the same directory as the scripts, create a file named `config.json`:
        ```json
        {
          "plex_url": "http://YOUR_PLEX_IP_OR_DOMAIN:32400",
          "plex_token": "YOUR_PLEX_TOKEN_HERE"
        }
        ```
    * Replace with your actual Plex URL and token.  
      [How to find your Plex token](https://support.plex.tv/articles/204059436-finding-an-authentication-token-x-plex-token/)

---

## Usage

### For `clearlogo.py` (Interactive):

```bash
python clearlogo.py
```
* Follow the prompts to search for a show/movie and provide a logo image URL.

### For `local-clearlogo.py` (Bulk Local):

```bash
python local-clearlogo.py [options]
```
* The first run will prompt you to map your Plex library folders to local folders.
* The script will scan your libraries and upload logos from local files.
* Use `--help` to see all options.

---

## Important Notes

* **`plexapi` Version:** These scripts critically depend on the `uploadLogo` method being available on `Show` objects in your installed `plexapi` version. Versions prior to approximately 4.16.0 or 4.17.0 (like 4.15.6) will **not** work and will produce an `AttributeError`. Always ensure `plexapi` is up-to-date (`pip install --upgrade plexapi`).
* **Plex Token:** Ensure the token used in `config.json` is valid and has permissions to edit metadata in your Plex library.
* **Image URLs:** For `clearlogo.py`, provide direct URLs to valid image files (e.g., `.png`, `.jpg`). URLs pointing to web pages or unsupported formats will likely cause errors during the upload attempt (`BadRequest` error). The Plex server needs to be able to access and process the image from the URL.
* **Image Files:** For `local-clearlogo.py`, ensure your logo images are named `logo.png`, `logo.jpg`, `clearlogo.png`, or `clearlogo.jpg` and are placed in the correct media folders.

## Configuration Notes

- **UPLOAD_DELAY:**  
  The `local-clearlogo.py` script includes an `UPLOAD_DELAY` setting (default: `0.05` seconds) to pause briefly between each logo upload. This helps prevent overwhelming your Plex server with too many requests in a short time.  
  You can adjust this value at the top of the script to increase or decrease the delay as needed for your server's performance.

---

## License

This project is licensed under the MIT License - see the `LICENSE` file for details.

## Contributing

Contributions are welcome! Please feel free to submit a pull request or open an issue if you find bugs or have suggestions for improvements.
