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

# in discord_utils.py

def create_summary_embed(
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
) -> discord.Embed:
    """Creates the definitive embed with the two-line block metadata at the top."""
    
    parts = re.split(r'(\*\*.*?\*\*)', summary_text)
    overview = parts[0].strip() if parts else "No overview provided."

    # --- Step 1: Build the metadata in the exact two-line block format you want ---
    metadata_blocks = [
        f"**Channel:**\n{channel_title}",
        f"**Uploaded On:**\n{published_at}",
        f"**Video Length:**\n{duration}",
        f"**Est. Reading Time:**\n{reading_time}"
    ]
    if cached and summary_created_at:
        metadata_blocks.append(f"**Summary Generated:**\n{summary_created_at}")
    
    # Join with double newlines to create the space BETWEEN each block item.
    metadata_string = "\n\n".join(metadata_blocks)

    # --- Step 2: Combine metadata and overview with a clean space in between ---
    # This places the metadata block FIRST, then the overview.
    final_description = f"{metadata_string}\n\n{overview}"

    # --- Step 3: Create the embed with our perfectly ordered description ---
    embed = discord.Embed(
        title=f"📄 Summary of: {video_title}",
        description=final_description,
        color=discord.Color.green() if cached else discord.Color.blue(),
        url=url
    )
    embed.set_thumbnail(url=f"https://img.youtube.com/vi/{video_id}/hqdefault.jpg")

    # --- Step 4: Add the WHAT, WHY, etc. sections as distinct fields ---
    # These will appear neatly below the description block.
    if len(parts) > 1:
        for i in range(1, len(parts), 2):
            section_title = parts[i].strip()
            if i + 1 < len(parts):
                section_content = parts[i+1].strip()
                if section_content and len(section_content) < 1024:
                    embed.add_field(name=section_title, value=section_content, inline=False)

    # --- Step 5: Add the footer ---
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
