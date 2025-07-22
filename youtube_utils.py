import re
import isodate
import math
from datetime import datetime
import google.generativeai as genai
from youtube_transcript_api import YouTubeTranscriptApi, TranscriptsDisabled, NoTranscriptFound
from googleapiclient.discovery import build
from google.api_core.exceptions import ResourceExhausted

class QuotaExceededError(Exception):
    """Custom exception for when the API quota is exceeded."""
    pass

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

def get_playlist_id(url: str) -> str | None:
    """Extracts the YouTube playlist ID from various URL formats."""
    # This regex will find the playlist ID in URLs like:
    # - https://www.youtube.com/playlist?list=PL...
    # - https://www.youtube.com/watch?v=...&list=PL...
    # - https://youtube.com/playlist/PL...
    match = re.search(r'list=([0-9A-Za-z_-]+)', url)
    if match:
        return match.group(1)
    return None

def parse_iso8601_duration(duration: str) -> str:
    """Parses an ISO 8601 duration string into a human-readable format (HH:MM:SS)."""
    delta = isodate.parse_duration(duration)
    total_seconds = int(delta.total_seconds())
    hours, remainder = divmod(total_seconds, 3600)
    minutes, seconds = divmod(remainder, 60)
    if hours > 0:
        return f"{hours:02}:{minutes:02}:{seconds:02}"
    else:
        return f"{minutes:02}:{seconds:02}"

def estimate_reading_time(text: str) -> str:
    """Estimates the reading time for a given text."""
    word_count = len(text.split())
    # Average reading speed is ~200 words per minute
    minutes = math.ceil(word_count / 200)
    if minutes == 0:
        return "~1 min read"
    return f"~{minutes} min{'s' if minutes > 1 else ''} read"

def get_video_details(video_id: str, youtube) -> dict | None:
    """Fetches video title, duration, and channel title from the YouTube API."""
    if not youtube:
        raise ValueError("YouTube API client is not initialized.")
    
    request = youtube.videos().list(
        part="snippet,contentDetails",
        id=video_id
    )
    response = request.execute()
    
    if not response.get('items'):
        return None
        
    item = response['items'][0]
    title = item['snippet']['title']
    channel_title = item['snippet']['channelTitle']
    duration_iso = item['contentDetails']['duration']
    duration_str = parse_iso8601_duration(duration_iso)
    published_at_iso = item['snippet']['publishedAt']
    published_at_dt = datetime.fromisoformat(published_at_iso.replace('Z', '+00:00'))
    published_at_str = published_at_dt.strftime("%B %d, %Y")
    
    return {
        "title": title, 
        "duration": duration_str, 
        "published_at": published_at_str,
        "channel_title": channel_title
    }

def get_transcript(video_id: str) -> tuple[str, str]:
    """
    Fetches and formats the transcript for a video, including timestamps,
    and returns the language code. This is a blocking I/O call.
    Returns a tuple of (transcript_text, language_code).
    """
    try:
        transcript_list = YouTubeTranscriptApi.list_transcripts(video_id)
        
        # Robust transcript finding logic
        try:
            # Prefer English (manual or generated)
            transcript = transcript_list.find_transcript(['en'])
        except NoTranscriptFound:
            # If no English transcript, fall back to the first available one
            transcript = transcript_list[0]

        transcript_data = transcript.fetch()
        
        formatted_transcript = []
        for item in transcript_data:
            # CORRECTED: Use dot notation (item.start, item.text) to access attributes
            seconds = int(item.start)
            hours, remainder = divmod(seconds, 3600)
            minutes, seconds = divmod(remainder, 60)
            timestamp = f"[{hours:02}:{minutes:02}:{seconds:02}]"
            formatted_transcript.append(f"{timestamp} {item.text}")
            
        full_transcript = "\n".join(formatted_transcript)
        language_code = transcript.language_code
        
        return full_transcript, language_code

    except (TranscriptsDisabled, NoTranscriptFound):
        raise
    except Exception as e:
        # Log the specific error for debugging
        print(f"An unexpected error occurred in get_transcript for video {video_id}: {e}")
        raise

async def generate_summary(transcript: str, video_title: str, language_code: str) -> str:
    """Generates a summary using the Gemini API, dynamically choosing a format and language."""
    try:
        model = genai.GenerativeModel('gemini-1.5-flash')
        prompt = f"""
        You are an expert video summarizer. Your primary goal is to analyze the video transcript, which includes timestamps, and generate a structured, time-stamped summary.

        **Video Title:** {video_title}
        **Video Language:** {language_code}

        **Instructions:**

        **Step 1: Classify the Video Content**
        First, analyze the transcript to determine if the video is primarily:
        A) **News & Informational:** Discussing events, products, announcements, etc.
        B) **Tutorial & How-To:** Providing step-by-step instructions.

        **Step 2: Generate Summary with Timestamps**
        Based on the classification, use ONE of the following formats.
        **CRITICAL: For each bullet point or step you generate, you MUST append the corresponding timestamp from the transcript (e.g., `[HH:MM:SS]`). This timestamp should mark the beginning of where that specific point is discussed in the video.**
        The entire summary, including all headings and content, MUST be in the specified video language ({language_code}).

        ---
        **FORMAT A: News & Informational**

        **Type:** News / Informational
        **Overview:** [Brief, one-paragraph summary of the main topic and purpose.]
        **Key Information:**
        - [Bulleted list of the most important facts, findings, or announcements, each with a timestamp.]
        **Entities Mentioned:**
        - **Organization:** [Name of company or organization] [HH:MM:SS]
        - **Product:** [Name of product or service] [HH:MM:SS]
        - [Add other relevant entities, each with a timestamp.]
        **Additional Resources:**
        - [List any links mentioned. If none, state 'N/A'.]

        ---
        **FORMAT B: Tutorial & How-To**

        **Type:** Tutorial / How-To
        **Objective:** [Brief, one-sentence description of what the viewer will learn to do.]
        **Prerequisites:**
        - [Bulleted list of tools, software, or knowledge needed, each with a timestamp if applicable.]
        **Actionable Steps:**
        1. [First step in the process.] [HH:MM:SS]
        2. [Second step in the process.] [HH:MM:SS]
        3. [Continue with all necessary steps, each with a timestamp.]
        **Resources Mentioned:**
        - [List any links mentioned. If none, state 'N/A'.]
        ---

        **IMPORTANT REMINDERS:**
        - Only use the format that best fits the video.
        - **Every key point, entity, or step must end with its corresponding `[HH:MM:SS]` timestamp.**
        - The entire response must be in the language: **{language_code}**.
        - If a heading is not applicable (e.g., no 'Product' is mentioned), omit that line.

        **Transcript with Timestamps:**
        ```
        {transcript}
        ```
        """
        summary_response = await model.generate_content_async(prompt)
        return summary_response.text
    except ResourceExhausted as e:
        if "exceeded your current quota" in str(e):
            raise QuotaExceededError from e
        else:
            raise e

def get_playlist_video_urls(playlist_url: str, youtube) -> list[str]:
    """Fetches all video URLs from a YouTube playlist. This is a blocking I/O call."""
    if not youtube:
        raise ValueError("YouTube API client is not initialized.")

    playlist_id = get_playlist_id(playlist_url)
    if not playlist_id:
        raise ValueError("Invalid YouTube playlist URL.")

    video_urls = []
    next_page_token = None

    while True:
        request = youtube.playlistItems().list(
            part="contentDetails",
            playlistId=playlist_id,
            maxResults=50,  # Max allowed by API
            pageToken=next_page_token
        )
        response = request.execute()

        for item in response.get('items', []):
            video_id = item['contentDetails']['videoId']
            video_urls.append(f"https://www.youtube.com/watch?v={video_id}")

        next_page_token = response.get('nextPageToken')
        if not next_page_token:
            break
            
    return video_urls
