import os
import asyncio
import io
import discord
import google.generativeai as genai
from datetime import datetime
from discord.ext import commands
from dotenv import load_dotenv
from googleapiclient.discovery import build
from youtube_transcript_api import TranscriptsDisabled, NoTranscriptFound
from youtube_utils import QuotaExceededError
from discord_utils import sanitize_title_for_markdown

# --- Local Imports ---
import db_utils
import youtube_utils
import discord_utils

# --- Environment and API Key Setup ---
load_dotenv()
DISCORD_BOT_TOKEN = os.getenv("DISCORD_BOT_TOKEN")
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
USER_DAILY_LIMIT = int(os.getenv("USER_DAILY_LIMIT", 20)) # Default to 20 if not set

# --- Bot Class for Async Setup ---
class SummarizerBot(commands.Bot):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.youtube_client = None
        # The "self.synced" flag is no longer needed, so we've removed it.

    async def setup_hook(self):
        """Asynchronous setup phase for the bot."""
        print("Bot logging in...")
        if GEMINI_API_KEY:
            genai.configure(api_key=GEMINI_API_KEY)
            try:
                self.youtube_client = await asyncio.to_thread(
                    build, 'youtube', 'v3', developerKey=GEMINI_API_KEY
                )
                print("YouTube API client initialized successfully.")
            except Exception as e:
                print(f"Fatal: Could not initialize YouTube API client: {e}")
        else:
            print("Fatal: GEMINI_API_KEY not found.")
        # The startup sync logic has been removed. The /sync command is now the only way to sync commands.


intents = discord.Intents.default()
intents.message_content = True
bot = SummarizerBot(command_prefix="/", intents=intents)

@bot.event
async def on_ready():
    """Prints a confirmation message when the bot is online."""
    print(f'Logged in as {bot.user}')

# --- Core Video Processing Logic ---
async def process_video(interaction: discord.Interaction, url: str, force_new: bool = False) -> tuple:
    """
    Handles the processing of a single video URL and returns a tuple of (status, data).
    'data' can be a dictionary with all summary details or an error message.
    """
    bot_instance = interaction.client
    user_id = interaction.user.id

    if not bot_instance.youtube_client:
        return 'error', "YouTube API client is not available. Please check the bot's console."

    video_id = youtube_utils.get_video_id(url)
    if not video_id:
        return 'invalid_url', f"'{url}' is not a valid YouTube URL."

    # --- Rate Limiting Check ---
    is_cached_and_complete = False
    if not force_new:
        cached_result = await asyncio.to_thread(db_utils.get_summary_from_db, url)
        if cached_result and cached_result[2] == 'complete':
            is_cached_and_complete = True

    if not is_cached_and_complete:
        current_usage = await asyncio.to_thread(db_utils.get_user_usage_today, user_id)
        if current_usage >= USER_DAILY_LIMIT:
            return 'limit_exceeded', f"You have reached your daily summary limit of **{USER_DAILY_LIMIT}**. Please try again tomorrow."

    if force_new:
        print(f"Forcing new summary for {url}, deleting existing record.")
        await asyncio.to_thread(db_utils.delete_summary_record, url)

    if is_cached_and_complete:
        video_title, summary_text, status, requested_at_str, channel_title = cached_result
        print(f"Found cached summary for {url}")
        details = await asyncio.to_thread(youtube_utils.get_video_details, video_id, bot_instance.youtube_client)
        reading_time = youtube_utils.estimate_reading_time(summary_text)
        
        if not channel_title and details:
            channel_title = details.get('channel_title', 'N/A')
        
        summary_created_at_formatted = requested_at_str
        if requested_at_str:
            try:
                dt_object = datetime.strptime(requested_at_str, '%Y-%m-%d %H:%M:%S')
                summary_created_at_formatted = dt_object.strftime("%B %d, %Y")
            except (ValueError, TypeError):
                pass

        return 'cached', {
            "video_title": video_title, "summary_text": summary_text, "video_id": video_id,
            "duration": details.get('duration', 'N/A') if details else 'N/A',
            "reading_time": reading_time, 
            "published_at": details.get('published_at', 'N/A') if details else 'N/A',
            "channel_title": channel_title or 'N/A',
            "summary_created_at": summary_created_at_formatted
        }
    
    cached_result = await asyncio.to_thread(db_utils.get_summary_from_db, url)
    if cached_result:
        status = cached_result[2]
        if status in ['failed', 'processing']:
            print(f"Retrying summary for {url} (status: {status})")
            await asyncio.to_thread(db_utils.delete_summary_record, url)

    record_id = await asyncio.to_thread(db_utils.insert_processing_record, url)
    if record_id is None:
        return 'in_progress', f"Already processing this video: {url}"

    video_title = "N/A"
    try:
        details = await asyncio.to_thread(youtube_utils.get_video_details, video_id, bot_instance.youtube_client)
        if not details:
            raise ValueError("Could not fetch video details.")
            
        video_title, duration, published_at, channel_title = details['title'], details['duration'], details['published_at'], details['channel_title']
        
        transcript_text, lang_code = await asyncio.to_thread(youtube_utils.get_transcript, video_id)
        summary_text = await youtube_utils.generate_summary(transcript_text, video_title, lang_code)
        reading_time = youtube_utils.estimate_reading_time(summary_text)
        
        await asyncio.to_thread(db_utils.add_summary_to_db, url, video_title, channel_title, summary_text)
        await asyncio.to_thread(db_utils.log_user_usage, user_id, url)
        print(f"Successfully summarized and saved for user {user_id}: {video_title}")
        
        return 'complete', {
            "video_title": video_title, "summary_text": summary_text, "video_id": video_id,
            "duration": duration, "reading_time": reading_time, "published_at": published_at,
            "channel_title": channel_title, "summary_created_at": None
        }
        
    except QuotaExceededError:
        error_message = "The global API quota has been hit."
        await asyncio.to_thread(db_utils.update_summary_status, url, 'failed')
        return 'quota_exceeded', (error_message, video_title)
    except (TranscriptsDisabled, NoTranscriptFound):
        error_message = f"Transcripts are disabled for this video."
        await asyncio.to_thread(db_utils.update_summary_status, url, 'failed')
        return 'error', (error_message, video_title)
    except Exception as e:
        print(f"Caught unhandled exception for '{video_title}': {e}") # Keep detailed log for admin
        error_message = "An unexpected error occurred. This could be due to a non-public transcript or an internal issue. The error has been logged."
        await asyncio.to_thread(db_utils.update_summary_status, url, 'failed')
        return 'error', (error_message, video_title)

# --- Slash Commands ---
async def handle_multiple_videos(interaction: discord.Interaction, url_list: list, force_new: bool = False):
    """Generic handler for processing a list of URLs and updating Discord with a final recap."""
    bot_instance = interaction.client
    if not bot_instance.youtube_client:
        await interaction.edit_original_response(content="YouTube API client is not available. Please check the bot's console.")
        return

    total = len(url_list)
    await interaction.edit_original_response(content=f"Found {total} videos. Starting process...")
    
    success_count = 0
    fail_count = 0
    cached_count = 0
    user_limit_hit = False
    quota_hit = False
    results_log = []

    for i, url in enumerate(url_list):
        video_title_for_log = url # Default to URL if title fetch fails
        
        # Handle skipped videos first
        if user_limit_hit:
            fail_count += 1
            results_log.append({'title': video_title_for_log, 'url': url, 'status': '⏩ Skipped'})
            continue
        if quota_hit:
            fail_count += 1
            results_log.append({'title': video_title_for_log, 'url': url, 'status': '⏩ Skipped'})
            continue

        # Try to get the proper video title for progress updates and logs
        video_id = youtube_utils.get_video_id(url)
        progress_title = url
        if video_id:
            try:
                details = await asyncio.to_thread(youtube_utils.get_video_details, video_id, bot_instance.youtube_client)
                if details:
                    progress_title = details['title']
                    video_title_for_log = progress_title # Update for log
            except Exception:
                pass

        await interaction.edit_original_response(content=f"⏳ Processing video {i+1}/{total}: **{progress_title}**")
        
        status, data = await process_video(interaction, url, force_new)

        if status == 'complete':
            success_count += 1
            results_log.append({'title': data['video_title'], 'url': url, 'status': '✅ Summarized'})
            await discord_utils.send_summary(interaction, url=url, cached=False, **data)
        elif status == 'cached':
            cached_count += 1
            results_log.append({'title': data['video_title'], 'url': url, 'status': '📄 Cached'})
            await discord_utils.send_summary(interaction, url=url, cached=True, **data)
        elif status == 'limit_exceeded':
            user_limit_hit = True
            fail_count += 1
            results_log.append({'title': video_title_for_log, 'url': url, 'status': '⚠️ Failed', 'reason': data})
            await interaction.followup.send(f"❌ {data}")
        elif status == 'quota_exceeded':
            quota_hit = True
            fail_count += 1
            error_message, video_title = data
            results_log.append({'title': video_title, 'url': url, 'status': '🛑 Failed', 'reason': error_message})
            await interaction.followup.send(f"🛑 **Global API Quota Reached**\nFailed on video: **{video_title}** ({url})\n\n{error_message} The rest of the batch has been cancelled. Please try again later.")
        else: # 'error', 'invalid_url', 'in_progress'
            fail_count += 1
            error_message, video_title = data
            results_log.append({'title': video_title, 'url': url, 'status': f'⚠️ Failed', 'reason': error_message})
            await interaction.followup.send(f"❌ Failed to process **{video_title}** ({url}):\n> {error_message}")

    # --- Final Recap Embed ---
    await interaction.edit_original_response(content=f"✅ Batch complete! See the report below.")

    recap_embed = discord.Embed(
        title="Batch Processing Report",
        color=discord.Color.gold()
    )
    recap_embed.add_field(
        name="Overall Stats",
        value=f"**New Summaries:** {success_count}\n"
              f"**From Cache:** {cached_count}\n"
              f"**Failed/Skipped:** {fail_count}",
        inline=False
    )
    
    recap_description_lines = []
    for result in results_log:
        # Sanitize title for markdown link to ensure it's always a valid link
        title = sanitize_title_for_markdown(result['title'])
        line = f"{result['status']}: [{title}]({result['url']})"
        if 'reason' in result:
            line += f"\n> {result['reason']}" # Add the reason on a new line, indented
        recap_description_lines.append(line)
    
    # Join lines and handle potential character limit for the embed field
    recap_description = "\n".join(recap_description_lines)
    if len(recap_description) > 4096: # Embed description limit
        recap_description = recap_description[:4090] + "\n..."

    recap_embed.add_field(
        name="Detailed Log",
        value=recap_description if recap_description else "No videos were processed.",
        inline=False
    )
    await interaction.followup.send(embed=recap_embed)


@bot.tree.command(name="summarize", description="Summarizes one or more YouTube video URLs (space-separated).")
async def summarize(interaction: discord.Interaction, urls: str, force_new: bool = False):
    """Summarizes one or more YouTube videos from space-separated URLs."""
    await interaction.response.defer(thinking=True)
    url_list = list(dict.fromkeys(urls.strip().split()))

    if not url_list:
        await interaction.edit_original_response(content="Please provide at least one URL.")
        return

    if len(url_list) == 1:
        url = url_list[0]
        status, data = await process_video(interaction, url, force_new)
        if status in ['complete', 'cached']:
            await discord_utils.send_summary(interaction=interaction, url=url, cached=(status == 'cached'), **data)
        else:
            # Handle various error statuses with appropriate messaging
            if isinstance(data, tuple) and len(data) == 2:
                error_message, video_title = data
                # Sanitize the title to make it safe for a markdown link
                sanitized_title = sanitize_title_for_markdown(video_title)
                await interaction.edit_original_response(content=f"❌ Failed to process [{sanitized_title}]({url}):\n> {error_message}")
            else:
                await interaction.edit_original_response(content=f"❌ Error: {data}")
    else:
        await handle_multiple_videos(interaction, url_list, force_new)


@bot.tree.command(name="summarize_playlist", description="Summarizes all videos in a YouTube playlist.")
async def summarize_playlist(interaction: discord.Interaction, playlist_url: str):
    """Fetches all videos from a playlist and summarizes them one by one."""
    bot_instance = interaction.client
    await interaction.response.defer(thinking=True)
    
    if not bot_instance.youtube_client:
        await interaction.edit_original_response(content="YouTube API client is not available. Please check the bot's console.")
        return
    
    if not youtube_utils.get_playlist_id(playlist_url):
        await interaction.edit_original_response(content="That doesn't look like a valid YouTube playlist URL.")
        return

    try:
        url_list = await asyncio.to_thread(youtube_utils.get_playlist_video_urls, playlist_url, bot_instance.youtube_client)
        if not url_list:
            await interaction.edit_original_response(content="This playlist seems to be empty or private.")
            return
        
        url_list = list(dict.fromkeys(url_list))
        await handle_multiple_videos(interaction, url_list)

    except Exception as e:
        await interaction.edit_original_response(content=f"❌ An unexpected error occurred while fetching the playlist: {e}")


@bot.tree.command(name="sync", description="Syncs commands and removes duplicates.")
@commands.has_permissions(administrator=True)
@commands.guild_only()
async def sync(interaction: discord.Interaction):
    await interaction.response.defer(ephemeral=True)
    try:
        # Step 1: Clear ALL guild-specific commands (this removes duplicates)
        bot.tree.clear_commands(guild=interaction.guild)
        await bot.tree.sync(guild=interaction.guild)
        
        # Step 2: Sync global commands
        synced_global = await bot.tree.sync()
        
        await interaction.followup.send(
            f"✅ Successfully cleaned up duplicates!\n"
            f"• Cleared guild duplicates\n"
            f"• Synced {len(synced_global)} global commands\n"
            f"Commands should appear only once now."
        )
        print(f"✅ Sync completed: {len(synced_global)} global commands")
        
    except Exception as e:
        await interaction.followup.send(f"❌ Sync failed: {str(e)}")
        print(f"❌ Sync error: {e}")


# --- Main Execution ---
if __name__ == "__main__":
    if not DISCORD_BOT_TOKEN:
        print("Fatal: DISCORD_BOT_TOKEN not found in .env file.")
    else:
        db_utils.setup_database()
        bot.run(DISCORD_BOT_TOKEN)