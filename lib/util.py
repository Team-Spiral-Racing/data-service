import re

# --- Time Attack ---

def extract_metadata(description: str) -> dict:
    """
    Extracts metadata enclosed between === delimiters in the video description.

    Example block:
    ===
    track: Buttonwillow
    configuration: CW13
    date: 06/03/2025
    car: hyperion
    tag: v3
    time: 1:12.123
    driver: jonathan.lo@teamspiralracing.com
    ===

    Returns:
        dict: Parsed metadata as key-value pairs.
    """
    matches = re.findall(r'===\s*(.*?)\s*===', description, re.DOTALL)
    if not matches:
        return {}

    block = matches[0]
    metadata = {}

    for line in block.strip().splitlines():
        if ':' in line:
            key, value = line.split(':', 1)
            metadata[key.strip()] = value.strip()

    return metadata


def parse_lap_time_to_seconds(lap_time: str) -> float:
    """
    Converts a lap time string into a float value in seconds.

    Supports both MM:SS.xxx and SS.xxx formats.

    Methods:
        None (helper function)

    Args:
        lap_time (str): Lap time string from the YouTube description (e.g., "1:12.123").

    Returns:
        float: Total lap time in seconds (e.g., 72.123).
    """
    if ':' in lap_time:
        minutes, seconds = lap_time.split(':')
        return int(minutes) * 60 + float(seconds)
    return float(lap_time)


# --- Blog ---

def format_markdown_to_blowfish(mongo_database, blog_post):
    """
    Formats a blog post dictionary into a markdown string with frontmatter metadata.

    Retrieves the author's email from the MongoDB "User" collection using the authorId,
    generates a content summary, and composes markdown with title, date, summary,
    and author metadata.

    Args:
        mongo_database: A MongoDB database object with access to collections.
        blog_post (dict): A dictionary containing keys like 'title', 'createdAt',
                          'authorId', and 'content'.

    Returns:
        str: Markdown-formatted string representing the blog post.
              Includes frontmatter with title, date, summary, and author email.
    """
    # Gather input variables
    user = mongo_database["User"].find_one({"_id": blog_post['authorId']})
    content_length = len(blog_post['content'])
    summary_length = 100 if content_length else content_length
    summary = blog_post['content'][:summary_length].replace('#', '').replace('\n', ' ')

    # Format Text
    return f"""---
title: "{blog_post['title']}"
date: {blog_post['createdAt'].strftime('%Y-%m-%d')}
draft: false
summary: "{summary.strip()}..."
showAuthor: true
authors:
  - "{user['email']}"
---

{blog_post['content']}
"""