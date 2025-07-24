# Bulk YouTube Summarizer Discord Bot

This Discord bot, powered by Google's Gemini API, provides on-demand, time-stamped summaries of YouTube videos. It can handle single videos, multiple videos in one command, and entire playlists.

## Key Features

- **AI-Powered Summaries:** Utilizes the Gemini 1.5 Flash model to generate intelligent, structured summaries of video transcripts.
- **Bulk Processing:**
    - **Multiple URLs:** Summarize several videos at once by pasting multiple URLs in a single command.
    - **Playlist Support:** Provide a playlist URL to summarize every video in it.
- **Smart Caching:** Stores summaries in a local SQLite database (`summaries.db`) to provide instant results for previously summarized videos, saving API quota.
- **User Rate Limiting:** Prevents API abuse with a configurable daily summary limit per user.
- **Dynamic Summary Formatting:** The bot analyzes the video content and automatically formats the summary as either "News & Informational" or "Tutorial & How-To".
- **Detailed Output:** Summaries are delivered as a clean Discord embed, including:
    - Video metadata (Channel, Upload Date, Duration).
    - Estimated reading time.
    - A full, downloadable `.txt` file of the summary.

## Setup & Installation

### 1. Prerequisites
- Python 3.9 or higher.
- A Discord Bot Token.
- A Google Gemini API Key.

### 2. Clone the Repository
```bash
git clone https://github.com/jeholymoly/Bulk-Youtube-Summarizer.git
cd Bulk-Youtube-Summarizer
```

### 3. Install Dependencies
```bash
pip install -r requirements.txt
```

### 4. Configure Environment Variables
Create a file named `.env` in the project root directory and add your API keys and settings:

```env
# .env
DISCORD_BOT_TOKEN="YOUR_DISCORD_BOT_TOKEN_HERE"
GEMINI_API_KEY="YOUR_GEMINI_API_KEY_HERE"
USER_DAILY_LIMIT=20
```
- `USER_DAILY_LIMIT` is optional and defaults to 20 if not set.

### 5. Run the Bot
```bash
python bot.py
```

## Bot Commands

The bot uses Discord's slash commands.

- `/summarize urls: <video_urls>`
  - Summarizes one or more YouTube videos. Separate multiple URLs with a space.
  - **Example:** `/summarize urls: https://www.youtube.com/watch?v=... https://www.youtube.com/watch?v=...`

- `/summarize_playlist playlist_url: <playlist_url>`
  - Summarizes all videos in the specified YouTube playlist.
  - **Example:** `/summarize_playlist playlist_url: https://www.youtube.com/playlist?list=...`

- `/sync` (Admin Only)
  - A utility command for server administrators to manually sync the bot's slash commands with Discord. This helps resolve any issues with commands not appearing correctly.

## Running on Android with Termux

This bot can be run on an Android device using Termux.

1.  **Install Termux:** Get the latest version from F-Droid.
2.  **Install Python & Git:**
    ```bash
    pkg update && pkg upgrade
    pkg install python git
    ```
3.  **Clone the Repository:**
    ```bash
    git clone https://github.com/jeholymoly/Bulk-Youtube-Summarizer.git
    cd Bulk-Youtube-Summarizer
    ```
    *Note: If your repository is private, you will need to use an SSH key or a Personal Access Token to clone.*
4.  **Install Dependencies:**
    ```bash
    pip install -r requirements.txt
    ```
5.  **Create `.env` file:**
    Use a text editor like `nano` (`pkg install nano`) to create your `.env` file with your API keys.
    ```bash
    nano .env
    ```
6.  **Run the Bot:**
    ```bash
    python bot.py
    ```