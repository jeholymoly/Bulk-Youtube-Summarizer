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

def get_transcript(video_id: str) -> str:
    """Fetches and formats the transcript for a video. This is a blocking I/O call."""
    try:
        transcript_list = YouTubeTranscriptApi.get_transcript(video_id)
        return " ".join([item['text'] for item in transcript_list])
    except (TranscriptsDisabled, NoTranscriptFound):
        raise
    except Exception as e:
        print(f"An unexpected error occurred in get_transcript: {e}")
        raise

async def generate_summary(transcript: str, video_title: str) -> str:
    """Generates a summary using the Gemini API."""
    try:
        model = genai.GenerativeModel('gemini-1.5-flash')
        prompt = f"""
        You are an expert video summarizer. Your goal is to provide a clear, concise, and well-structured summary of a YouTube video based on its transcript.

        **Video Title:** {video_title}

        **Instructions:**
        1.  **Overview:** Start with a brief, one-paragraph overview that captures the main topic and purpose of the video.
        2.  **Structured Breakdown:** After the overview, create distinct sections using the following markdown headings:
            - `**WHAT**`: What is the main subject or event discussed?
            - `**WHY**`: Why is this topic important or relevant? What is the motivation behind the content?
            - `**WHO**`: Who are the key people, speakers, or groups involved?
            - `**WHEN**`: When did the events take place, or when is the information relevant?
            - `**WHERE**`: Where is the geographical or contextual setting of the video?
            - `**HOW**`: How are the main points demonstrated or achieved? What are the key steps or processes described?
        3.  **Omit If Not Applicable:** If a specific section (e.g., 'WHEN') is not relevant to the video's content, simply omit it from the summary. Do not include headings for empty sections.
        4.  **Clarity and Conciseness:** Ensure the language is clear and easy to understand. Focus on the most important information and avoid unnecessary jargon.

        **Transcript:**
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
