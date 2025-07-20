import sqlite3
from datetime import datetime, timedelta

def setup_database():
    """
    Initializes the SQLite database and creates tables if they don't exist.
    """
    conn = sqlite3.connect('summaries.db')
    cursor = conn.cursor()

    # --- Create summaries table ---
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS summaries (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            youtube_url TEXT NOT NULL UNIQUE,
            video_title TEXT,
            channel_title TEXT,
            summary_text TEXT,
            status TEXT NOT NULL,
            requested_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')

    # --- Create user_usage table for rate limiting ---
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS user_usage (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            youtube_url TEXT NOT NULL,
            summarized_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')

    # --- Backward compatibility: Add channel_title if missing ---
    try:
        cursor.execute("SELECT channel_title FROM summaries LIMIT 1")
    except sqlite3.OperationalError:
        print("Attempting to add 'channel_title' column to existing table...")
        cursor.execute("ALTER TABLE summaries ADD COLUMN channel_title TEXT")
        print("'channel_title' column added successfully.")

    # Clean up any 'processing' tasks from a previous run
    cursor.execute("UPDATE summaries SET status = 'failed' WHERE status = 'processing'")
    conn.commit()
    conn.close()
    print("Database initialized and cleaned successfully.")

def get_summary_from_db(url: str):
    """Checks for an existing summary in the database."""
    conn = sqlite3.connect('summaries.db')
    cursor = conn.cursor()
    cursor.execute(
        "SELECT video_title, summary_text, status, requested_at, channel_title FROM summaries WHERE youtube_url = ?", 
        (url,)
    )
    result = cursor.fetchone()
    conn.close()
    return result

def add_summary_to_db(url: str, video_title: str, channel_title: str, summary_text: str):
    """Adds a complete summary to the database."""
    conn = sqlite3.connect('summaries.db')
    cursor = conn.cursor()
    cursor.execute(
        """
        INSERT OR REPLACE INTO summaries (youtube_url, video_title, channel_title, summary_text, status) 
        VALUES (?, ?, ?, ?, 'complete')
        """,
        (url, video_title, channel_title, summary_text)
    )
    conn.commit()
    conn.close()

def update_summary_status(url: str, status: str):
    """Updates the status of a summary record."""
    conn = sqlite3.connect('summaries.db')
    cursor = conn.cursor()
    cursor.execute("UPDATE summaries SET status = ? WHERE youtube_url = ?", (status, url))
    conn.commit()
    conn.close()

def insert_processing_record(url: str) -> int | None:
    """Inserts a new record with 'processing' status and returns its ID."""
    conn = sqlite3.connect('summaries.db')
    cursor = conn.cursor()
    try:
        cursor.execute("INSERT INTO summaries (youtube_url, status) VALUES (?, 'processing')", (url,))
        conn.commit()
        record_id = cursor.lastrowid
        return record_id
    except sqlite3.IntegrityError:
        return None # Indicates that the URL already exists
    finally:
        conn.close()

def delete_summary_record(url: str):
    """Deletes a summary record by URL, used for retrying failed jobs."""
    conn = sqlite3.connect('summaries.db')
    cursor = conn.cursor()
    cursor.execute("DELETE FROM summaries WHERE youtube_url = ?", (url,))
    conn.commit()
    conn.close()

# --- User Usage Tracking for Rate Limiting ---

def log_user_usage(user_id: int, url: str):
    """Logs a successful summary generation for a user."""
    conn = sqlite3.connect('summaries.db')
    cursor = conn.cursor()
    cursor.execute(
        "INSERT INTO user_usage (user_id, youtube_url) VALUES (?, ?)",
        (user_id, url)
    )
    conn.commit()
    conn.close()

def get_user_usage_today(user_id: int) -> int:
    """Counts how many summaries a user has generated since midnight UTC."""
    conn = sqlite3.connect('summaries.db')
    cursor = conn.cursor()
    
    # Get the current time in UTC and determine the start of the current day (midnight)
    now_utc = datetime.utcnow()
    start_of_today_utc = now_utc.replace(hour=0, minute=0, second=0, microsecond=0)
    
    cursor.execute(
        "SELECT COUNT(*) FROM user_usage WHERE user_id = ? AND summarized_at >= ?",
        (user_id, start_of_today_utc)
    )
    count = cursor.fetchone()[0]
    conn.close()
    return count
