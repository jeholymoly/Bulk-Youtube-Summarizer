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

This guide is separated into two main paths: **Windows** (for running with a GUI) and **Termux/Linux** (for running in a command-line environment, like on Android or a server).

> **Note on Repository Access:** For the `git clone` command to work, this repository must be public. If you are working with a private fork, you will need to use an SSH key or a Personal Access Token.

### 1. Windows Installation

This setup is intended for a standard Windows environment.

**A. Prerequisites**

1.  **Python:** Install Python 3.9 or higher from the [official Python website](https://www.python.org/downloads/). Make sure to check the box that says **"Add Python to PATH"** during installation.
2.  **Git:** Install Git for Windows from the [official Git website](https://git-scm.com/download/win).
3.  **FFmpeg:** The bot requires the FFmpeg program to process audio from videos.
    *   Download a release build from the [FFmpeg website](https://www.gyan.dev/ffmpeg/builds/).
    *   Extract the downloaded archive.
    *   Find the `bin` folder inside (it contains `ffmpeg.exe`).
    *   Add the full path to this `bin` folder to your Windows **System Environment Variables `Path`**. This allows the bot to find and use FFmpeg from any directory.

**B. Installation Steps**

1.  **Clone the Repository:** Open a Command Prompt or PowerShell and run:
    ```bash
    git clone https://github.com/jeholymoly/Bulk-Youtube-Summarizer.git
    cd Bulk-Youtube-Summarizer
    ```

2.  **Install Dependencies:**
    ```bash
    pip install -r requirements_windows.txt
    ```

3.  **Configure Environment Variables:** Create a file named `.env` in the project root directory and add your API keys and settings:
    ```env
    # .env
    DISCORD_BOT_TOKEN="YOUR_DISCORD_BOT_TOKEN_HERE"
    GEMINI_API_KEY="YOUR_GEMINI_API_KEY_HERE"
    USER_DAILY_LIMIT=20
    ```
    - `USER_DAILY_LIMIT` is optional and defaults to 20 if not set.

4.  **Run the Bot:**
    ```bash
    python bot.py
    ```
    > **Note:** The first time you run the bot, it will automatically create a `summaries.db` file in the project directory to store cached summaries.

### 2. Termux/Linux Installation

This setup is for running the bot in a headless environment like Termux on Android or a Linux server.

**A. Prerequisites & System Dependencies**

1.  **Install Core Tools:** Open your terminal and install the essential packages.
    
    *For Termux on Android:*
    ```bash
    pkg update && pkg upgrade
    pkg install python git ffmpeg rust libtool build-essential
    ```
    
    *For Debian/Ubuntu-based Linux:*
    ```bash
    sudo apt update && sudo apt upgrade
    sudo apt install python3 python3-pip git ffmpeg rustc libasound2-dev portaudio19-dev
    ```

    > **Why are these needed?**
    > - `rust`: The `grpcio` library (a dependency for Google's API) often needs to be compiled from source on ARM systems (like Android phones), which requires the Rust compiler.
    > - `libasound2-dev`, `portaudio19-dev`, `libtool`, `build-essential`: These are required to successfully build the `pyaudio` wheel from source, which is necessary for audio handling.
    > - `ffmpeg`: Required for audio extraction from videos.

2.  **Clone the Repository:**
    ```bash
    git clone https://github.com/jeholymoly/Bulk-Youtube-Summarizer.git
    cd Bulk-Youtube-Summarizer
    ```

3.  **Install Python Dependencies:**
    ```bash
    pip install -r requirements_termux.txt
    ```

4.  **Configure Environment Variables:** Use a text editor like `nano` or `vim` to create your `.env` file with your API keys.
    ```bash
    # Example using nano
    nano .env
    ```
    Paste your configuration into the file:
    ```env
    # .env
    DISCORD_BOT_TOKEN="YOUR_DISCORD_BOT_TOKEN_HERE"
    GEMINI_API_KEY="YOUR_GEMINI_API_KEY_HERE"
    USER_DAILY_LIMIT=20
    ```

5.  **Run the Bot:**
    ```bash
    python bot.py
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
