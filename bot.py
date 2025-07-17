import os
import re
import io
import sqlite3
import discord
import google.generativeai as genai
from discord.ext import commands
from dotenv import load_dotenv
from youtube_transcript_api import YouTubeTranscriptApi, TranscriptsDisabled, NoTranscriptFound
from googleapiclient.discovery import build

# --- Environment and API Key Setup ---
load_dotenv()
DISCORD_BOT_TOKEN = os.getenv("DISCORD_BOT_TOKEN")
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")

# Configure the APIs
if GEMINI_API_KEY:
    genai.configure(api_key=GEMINI_API_KEY)
    youtube = build('youtube', 'v3', developerKey=GEMINI_API_KEY)
else:
    print("Error: GEMINI_API_KEY not found. Please set it in the .env file.")
    youtube = None

# --- Database Setup ---
def setup_database():
    """Initializes the SQLite database and creates the summaries table if it doesn't exist."""
    conn = sqlite3.connect('summaries.db')
    cursor = conn.cursor()
    # Create the table first to ensure it always exists
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS summaries (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            youtube_url TEXT NOT NULL UNIQUE,
            video_title TEXT,
            summary_text TEXT,
            status TEXT NOT NULL,
            requested_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')
    # Now, it's safe to clean up any 'processing' tasks from a previous run
    cursor.execute("UPDATE summaries SET status = 'failed' WHERE status = 'processing'")
    conn.commit()
    conn.close()
    print("Database initialized and cleaned successfully.")

# --- Bot Setup ---
intents = discord.Intents.default()
intents.message_content = True
bot = commands.Bot(command_prefix="/", intents=intents)

@bot.event
async def on_ready():
    """Prints a confirmation message when the bot is online and syncs commands."""
    print(f'Logged in as {bot.user}')
    try:
        synced = await bot.tree.sync()
        print(f"Synced {len(synced)} command(s)")
    except Exception as e:
        print(f"Failed to sync commands: {e}")

def get_video_id(url: str) -> str | None:
    """Extracts the YouTube video ID from various URL formats."""
    patterns = [
        r'(?:v=|\/)([0-9A-Za-z_-]{11}).*',
        r'youtu\.be\/([0-9A-Za-z_-]{11})'
    ]
    for pattern in patterns:
        match = re.search(pattern, url)
        if match:
            return match.group(1)
    return None

# --- Slash Command ---
@bot.tree.command(name="summarize", description="Summarizes a YouTube video from a URL.")
async def summarize(interaction: discord.Interaction, url: str):
    """The main command to summarize a YouTube video."""
    await interaction.response.defer(thinking=True)

    video_id = get_video_id(url)
    if not video_id:
        await interaction.followup.send("That doesn't look like a valid YouTube URL. Please try again.")
        return

    conn = sqlite3.connect('summaries.db')
    cursor = conn.cursor()

    # Check for existing summary
    cursor.execute("SELECT video_title, summary_text, status FROM summaries WHERE youtube_url = ?", (url,))
    result = cursor.fetchone()

    if result:
        video_title, summary_text, status = result
        if status == 'complete':
            print(f"Found existing summary for {url}")
            await interaction.edit_original_response(content="Found an existing summary for this video! Here it is:")

            # --- Create and Send Discord Embed for existing summary ---
            embed = discord.Embed(
                title=f"📄 Summary of: {video_title}",
                description=summary_text.split('\n\n')[0],
                color=discord.Color.green(), # Green for cached results
                url=url
            )
            embed.set_thumbnail(url=f"https://img.youtube.com/vi/{video_id}/hqdefault.jpg") # Add this line

            sections = re.findall(r"(\**.*?\**)\n(.*?)(?=\n\**|\Z)", summary_text, re.DOTALL)
            for section_title, section_content in sections:
                if section_content.strip() and len(section_content) < 1024:
                    embed.add_field(name=section_title.strip(), value=section_content.strip(), inline=False)

            embed.set_footer(text="This summary was retrieved from the cache.")
            
            summary_file = io.BytesIO(summary_text.encode('utf-8'))
            await interaction.followup.send(
                embed=embed, 
                files=[discord.File(summary_file, filename=f"summary-{video_id}.txt")]
            )
            conn.close()
            return
        elif status == 'failed':
            print(f"Retrying failed summary for {url}")
            cursor.execute("DELETE FROM summaries WHERE youtube_url = ?", (url,))
            conn.commit()
        elif status == 'processing':
            await interaction.followup.send("I'm already working on this video! Please wait a moment.")
            conn.close()
            return

    # Insert new record for processing
    try:
        cursor.execute("INSERT INTO summaries (youtube_url, status) VALUES (?, 'processing')", (url,))
        conn.commit()
        record_id = cursor.lastrowid
    except sqlite3.IntegrityError:
        await interaction.followup.send("I'm already working on this video! Please wait a moment.")
        conn.close()
        return

    # --- Main Processing Block ---
    try:
        # --- Get Title (Official API) ---
        await interaction.edit_original_response(content="⏳ Fetching video metadata...")
        
        request = youtube.videos().list(part="snippet", id=video_id)
        response = request.execute()
        
        if not response.get('items'):
            await interaction.edit_original_response(content=f"❌ Could not find a YouTube video with the ID: {video_id}")
            return
            
        video_title = response['items'][0]['snippet']['title']
        print(f"Successfully fetched title: {video_title}")

        # --- Get Transcript ---
        await interaction.edit_original_response(content="📜 Fetching video transcript...")
        transcript_list = YouTubeTranscriptApi.get_transcript(video_id)
        transcript = " ".join([item['text'] for item in transcript_list])

        # --- Gemini Summarization ---
        await interaction.edit_original_response(content=f"🧠 Summarizing {len(transcript):,} characters...")
        print("Generating summary...")
        model = genai.GenerativeModel('gemini-1.5-flash')
        prompt = f"""
        You are an expert video summarizer. Based on the following transcript, provide a detailed and structured summary.
        Start with a brief, one-paragraph overview.
        Then, create distinct sections with the following markdown headings: '**WHAT**', '**WHY**', '**WHO**', '**WHEN**', '**WHERE**', and '**HOW**'.
        If a section is not applicable, omit it.

        Transcript:
        {transcript}
        """
        summary_response = await model.generate_content_async(prompt)
        summary_text = summary_response.text

        # Update database with the complete summary and title
        cursor.execute("UPDATE summaries SET summary_text = ?, video_title = ?, status = 'complete' WHERE id = ?", (summary_text, video_title, record_id))
        conn.commit()
        print("Summary generated and saved to database.")

        # --- Create and Send Discord Embed ---
        embed = discord.Embed(
            title=f"📄 Summary of: {video_title}",
            description=summary_text.split('\n\n')[0],
            color=discord.Color.blue(),
            url=url
        )
        embed.set_thumbnail(url=f"https://img.youtube.com/vi/{video_id}/hqdefault.jpg") # Add this line
        sections = re.findall(r"(\*\*.*?\*\*)\n(.*?)(?=\n\*\*|\Z)", summary_text, re.DOTALL)
        for section_title, section_content in sections:
            if section_content.strip() and len(section_content) < 1024:
                embed.add_field(name=section_title.strip(), value=section_content.strip(), inline=False)
        embed.set_footer(text=f"Full summary attached as a text file.")
        summary_file = io.BytesIO(summary_text.encode('utf-8'))
        
        await interaction.edit_original_response(
            content="✅ Here is the summary for you!",
            embed=embed,
            attachments=[discord.File(summary_file, filename=f"summary-{video_id}.txt")]
        )

    except (TranscriptsDisabled, NoTranscriptFound):
        error_message = "❌ Sorry, transcripts are disabled or not available in English for this video."
        print(f"Transcript error for {url}: {error_message}")
        cursor.execute("UPDATE summaries SET status = 'failed' WHERE id = ?", (record_id,))
        conn.commit()
        await interaction.edit_original_response(content=error_message, embed=None, attachments=[])
    except Exception as e:
        error_message = "❌ An unexpected error occurred. Please check the console for details."
        print(f"Generic error for {url}: {e}")
        cursor.execute("UPDATE summaries SET status = 'failed' WHERE id = ?", (record_id,))
        conn.commit()
        await interaction.edit_original_response(content=error_message, embed=None, attachments=[])
    finally:
        conn.close()


# --- Main Execution ---
if __name__ == "__main__":
    if not DISCORD_BOT_TOKEN:
        print("Error: DISCORD_BOT_TOKEN not found. Please set it in the .env file.")
    else:
        setup_database()
        bot.run(DISCORD_BOT_TOKEN)
