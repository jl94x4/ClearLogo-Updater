# P Logo Updater (Dockerized)

This tool automatically scans your Plex libraries and uploads clearlogo images to your movies and TV shows using the [fanart.tv](https://fanart.tv/) API.

## Features

-   **Fully Automated:** Runs on a schedule to find and apply new clearlogos.
-   **Fanart.tv Integration:** Fetches high-quality logos from a comprehensive database.
-   **Accurate Matching:** Verifies logos against Plex metadata (title, year, and TVDB/TMDB ID) to ensure accuracy and prevent mismatches.
-   **Smart Throttling:** Automatically adjusts API request speed based on your fanart.tv API key type (`free` or `paid`) to respect rate limits.
-   **Simple Setup:** Uses Docker Compose for easy configuration and deployment.

## Prerequisites

-   [Docker](https://docs.docker.com/get-docker/)
-   [Docker Compose](https://docs.docker.com/compose/install/)
-   A free [fanart.tv API Key](https://fanart.tv/get-an-api-key/).

## Setup

1.  **Clone the repository:**
    ```bash
    git clone https://github.com/your-username/p-logo-updater.git
    cd p-logo-updater
    ```

2.  **Create the Configuration File:**
    Create a file named `config.json` in the project root (`/home/ubuntu/appdata/p-logo-updater/config.json` if running from the user's appdata directory).

3.  **Edit `config.json`:**
    Add your Plex and fanart.tv credentials to the `config.json` file.

    ```json
    {
        "plex_url": "YOUR_PLEX_URL",
        "plex_token": "YOUR_PLEX_TOKEN",
        "fanart_api_key": "YOUR_FANART_API_KEY",
        "fanart_key_type": "free"
    }
    ```
    -   `plex_url`: The full URL to your Plex server.
    -   `plex_token`: Your Plex API token. [Find it here](https://support.plex.tv/articles/204059436-finding-an-authentication-token-x-plex-token/).
    -   `fanart_api_key`: Your personal API key from fanart.tv.
    -   `fanart_key_type`: Set to `"free"` (1s delay per request) or `"paid"` (0.5s delay per request) depending on your fanart.tv account status. Defaults to `"free"` if omitted.

4.  **Configure `docker-compose.yml`:**
    Open `docker-compose.yml` and map the path to your `config.json` file.

    ```yaml
    volumes:
      - /path/to/your/config.json:/app/config.json
    ```
    For example:
    ```yaml
    volumes:
      - /home/ubuntu/appdata/p-logo-updater/config.json:/app/config.json
    ```

## Usage

-   **Build and Start the Container:**
    This command builds the image and starts the container in detached mode. The cron job will run the script automatically on the schedule defined in `docker-compose.yml`.
    ```bash
    docker-compose up --build -d
    ```

-   **View Logs:**
    To see the output from the script (either from a scheduled run or a manual run):
    ```bash
    docker logs -f p-logo-updater
    ```

-   **Run the Script Manually:**
    To trigger the automatic logo update process immediately, you can execute the script inside the running container.
    ```bash
    docker exec p-logo-updater python /app/clearlogo.py
    ```
    You can also specify which libraries to scan by adding the `--libraries` argument, followed by the names of your libraries:
    ```bash
    docker exec p-logo-updater python /app/clearlogo.py --libraries "Movies" "TV Shows"
    ```

## Configuration

-   **Schedule:** You can change the cron schedule by editing the `CRON_SCHEDULE` environment variable in the `docker-compose.yml` file. The default is `0 3 * * *` (3:00 AM daily). Use [crontab.guru](https://crontab.guru/) to generate schedules.
-   **Script Arguments:** You can pass arguments to the `clearlogo.py` script by editing the `ARGS` environment variable in `docker-compose.yml`. For example, to limit the script to specific libraries:
    ```yaml
    environment:
      - CRON_SCHEDULE=0 3 * * *
      - ARGS=--libraries "Movies" "TV Shows"
    ```

## Legacy Local-Only Script

This project also contains `local-clearlogo.py`, a legacy script designed to work with local logo image files instead of the fanart.tv API. This script is no longer the default but is kept for users who prefer to manage their own logo files. To use it, you must update the `entrypoint` in `docker-compose.yml` to run `local-clearlogo.py` and configure local file volume mappings as described in previous versions of this README.
