import discord
import io
import re

def sanitize_filename(title: str) -> str:
    """Removes invalid characters from a string to make it a valid filename."""
    # Remove invalid characters
    sanitized = re.sub(r'[\\/*?:"<>|]', "", title)
    # Replace spaces with underscores
    sanitized = sanitized.replace(" ", "_")
    # Truncate to a reasonable length
    return (sanitized[:100] + '..') if len(sanitized) > 100 else sanitized

def sanitize_title_for_markdown(title: str) -> str:
    """
    Sanitizes a title for use in markdown links by escaping or removing 
    problematic characters that could break Discord's markdown parsing.
    """
    # Remove or escape characters that break markdown links
    # Remove brackets entirely
    sanitized = title.replace('[', '').replace(']', '')
    
    # Escape other problematic markdown characters
    sanitized = sanitized.replace('*', '\\*')  # Escape asterisks
    sanitized = sanitized.replace('_', '\\_')  # Escape underscores
    sanitized = sanitized.replace('`', '\\`')  # Escape backticks
    
    # Remove or replace other potentially problematic characters
    sanitized = sanitized.replace('\n', ' ')   # Replace newlines with spaces
    sanitized = sanitized.replace('\r', ' ')   # Replace carriage returns
    
    # Trim whitespace
    sanitized = sanitized.strip()
    
    return sanitized


def smart_truncate(text: str, max_length: int = 1024) -> str:
    """Truncates text to a maximum length, respecting word/sentence boundaries."""
    if len(text) <= max_length:
        return text

    # Find the last period before the limit
    cut_off_point = text.rfind('.', 0, max_length - 3)
    # If no period, find the last space
    if cut_off_point == -1:
        cut_off_point = text.rfind(' ', 0, max_length - 3)
    
    if cut_off_point != -1:
        # Cut at the found point and add ellipsis
        return text[:cut_off_point] + "..."
    else:
        # If no space or period is found, do a hard truncate
        return text[:max_length - 3] + "..."

def create_summary_embed(
    summary_text: str, 
    video_title: str, 
    url: str, 
    video_id: str, 
    duration: str, 
    reading_time: str, 
    published_at: str, 
    channel_title: str,
    summary_created_at: str = None, 
    cached=False
) -> discord.Embed:
    """
    Creates a definitive embed with a permanent metadata block at the top 
    and dynamically adds fields based on the summary's structure, with smart truncation.
    """
    
    # --- Step 1: Build the permanent metadata block ---
    metadata_lines = [
        f"**Channel:** {channel_title}",
        f"**Uploaded On:** {published_at}",
        f"**Video Length:** {duration}",
        f"**Est. Reading Time:** {reading_time}"
    ]
    if cached and summary_created_at:
        metadata_lines.append(f"**Summary Generated:** {summary_created_at}")
    
    metadata_string = "\n".join(metadata_lines)

    # --- Step 2: Create the embed with metadata in the description ---
    embed = discord.Embed(
        title=f"📄 Summary of: {video_title}",
        description=metadata_string,
        color=discord.Color.green() if cached else discord.Color.blue(),
        url=url
    )
    embed.set_thumbnail(url=f"https://img.youtube.com/vi/{video_id}/hqdefault.jpg")

    # --- Step 3: Dynamically parse and add fields from the summary text ---
    lines = summary_text.strip().split('\n')
    
    current_field_title = ""
    current_field_value = ""

    for line in lines:
        match = re.match(r'\*\*(.*?):\*\*', line)
        if match:
            if current_field_title and current_field_value.strip():
                # Use smart_truncate before adding the field
                truncated_value = smart_truncate(current_field_value.strip())
                embed.add_field(name=current_field_title, value=truncated_value, inline=False)
            
            current_field_title = match.group(1).strip()
            current_field_value = line.replace(f"**{current_field_title}:**", "").strip()
        else:
            current_field_value += f"\n{line}"

    # Add the last field if it exists, using smart_truncate
    if current_field_title and current_field_value.strip():
        truncated_value = smart_truncate(current_field_value.strip())
        embed.add_field(name=current_field_title, value=truncated_value, inline=False)

    # --- Step 4: Add the footer ---
    footer_text = "This summary was retrieved from the cache." if cached else "Full summary attached as a text file."
    embed.set_footer(text=footer_text)
    return embed







def format_summary_for_file(summary_text: str) -> str:
    """Removes markdown for a clean text file output."""
    # Replace "**HEADING**" with "HEADING"
    return re.sub(r'\*\*(.*?)\*\*', r'\1', summary_text)

async def send_summary(
    interaction: discord.Interaction, 
    summary_text: str, 
    video_title: str, 
    url: str, 
    video_id: str, 
    duration: str, 
    reading_time: str, 
    published_at: str, 
    channel_title: str,  # Added
    summary_created_at: str = None, 
    cached=False
):
    """Sends a summary message with an embed and a file."""
    embed = create_summary_embed(
        summary_text, 
        video_title, 
        url, 
        video_id, 
        duration, 
        reading_time, 
        published_at, 
        channel_title,  # Pass to embed creator
        summary_created_at, 
        cached
    )
    
    # Create the formatted text file
    file_content = format_summary_for_file(summary_text)
    summary_file = io.BytesIO(file_content.encode('utf-8'))
    
    # Sanitize title for filename
    filename = f"{sanitize_filename(video_title)}.txt"
    
    message_content = "✅ Here is the summary for you!" if not cached else "Found an existing summary for this video! Here it is:"

    # Use followup.send for subsequent messages after the initial response
    if interaction.response.is_done():
         await interaction.followup.send(
            content=message_content,
            embed=embed,
            files=[discord.File(summary_file, filename=filename)]
        )
    else:
        # This path is for single video summaries where we can edit the original "thinking..." message
        await interaction.edit_original_response(
            content=message_content,
            embed=embed,
            attachments=[discord.File(summary_file, filename=filename)]
        )
