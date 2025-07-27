# Bulk YouTube Summarizer Discord Bot

This Discord bot, powered by Google's Gemini API, provides on-demand, time-stamped summaries of YouTube videos. It can handle single videos, multiple videos in one command, and entire playlists.

## Key Features

- **AI-Powered Summaries:** Utilizes Google's Gemini models to generate intelligent, structured summaries of video transcripts.
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

The installation process is now much simpler as unused, heavy dependencies have been removed.

### 1. Prerequisites

You only need two things installed on your system:
- **Python** (Version 3.9 or higher)
- **Git**

**For Windows:**
You can use a package manager like [Winget](https://learn.microsoft.com/en-us/windows/package-manager/winget/) or [Chocolatey](https://chocolatey.org/) for a quick setup. Open PowerShell as Administrator and run one of the following:
```powershell
# Using Winget
winget install -e --id Python.Python && winget install -e --id Git.Git

# Using Chocolatey
choco install python git -y
```

**For Termux/Linux:**
Use your system's package manager.
```bash
# For base Termux
pkg install python git -y

# For Debian/Ubuntu (including proot-distro)
apt install python3 python3-pip python3-venv git -y
```

### 2. Installation Steps

1.  **Clone the Repository:**
    ```bash
    git clone https://github.com/jeholymoly/Bulk-Youtube-Summarizer.git
    cd Bulk-Youtube-Summarizer
    ```

2.  **Create a Virtual Environment (Recommended):**
    ```bash
    # For Windows
    python -m venv venv
    .\venv\Scripts\activate

    # For Termux/Linux
    python3 -m venv venv
    source venv/bin/activate
    ```

3.  **Install Dependencies:**
    Choose the requirements file for your OS.
    ```bash
    # For Windows
    pip install -r requirements_windows.txt

    # For Termux/Linux
    pip install -r requirements_termux.txt
    ```

4.  **Configure Environment Variables:**
    Create a file named `.env` in the project directory. You can use a text editor like `nano` on Linux or `notepad` on Windows.
    ```env
    # .env
    DISCORD_BOT_TOKEN="YOUR_DISCORD_BOT_TOKEN_HERE"
    GEMINI_API_KEY="YOUR_GEMINI_API_KEY_HERE"
    USER_DAILY_LIMIT=20
    ```
    - `USER_DAILY_LIMIT` is optional and defaults to 20 if not set.

5.  **Run the Bot:**
    ```bash
    # For Windows
    python bot.py

    # For Termux/Linux
    python3 bot.py
    ```
    > **Note:** The first time you run the bot, it will automatically create a `summaries.db` file in the project directory to store cached summaries.

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
