from flask import Flask, Response, redirect, url_for, abort, request
from dotenv import load_dotenv

# Third Party
from googleapiclient.discovery import build
from pymongo import MongoClient, ASCENDING

# Util
from datetime import datetime, timedelta, timezone
from collections import defaultdict
import os
import re

# Setup
load_dotenv()
MONGO_CLIENT = MongoClient(os.getenv('MONGO_CONNECTION'))
DATABASE = MONGO_CLIENT[os.getenv('MONGO_DB_NAME')]
YOUTUBE_CLIENT = build('youtube', 'v3', developerKey=os.getenv('YOUTUBE_API_KEY'))
app = Flask(__name__)

# Config
CRON_SECRET = os.getenv('CRON_SECRET')
TSR_YOUTUBE = os.getenv('TSR_YOUTUBE_CHANNEL')


@app.route('/')
def root() -> Response:
    """
    This endpoint redirects users to the /status endpoint, where documentation can be found.

    Methods:
        GET: Redirects to the /status endpoint.

    Returns:
        Response: A redirect response to the /status URL.
    """
    return redirect(url_for('status'))


# --- APIs ---
@app.route('/status', methods=['GET'])
def status() -> Response:
    """
    This endpoint can be used to check the health of the server. 
    It responds with a message indicating that the server is running.

    Methods:
        GET: Retrieves the current status of the server.

    Returns:
        Response: A JSON object containing a message and an HTTP status code 200
    """
    return {"msg": 'Status OK, server is running'}, 200


@app.route('/youtube', methods=['POST'])
def youtube() -> Response:
    """
    This endpoint is triggered by a scheduled task (e.g. cron) to check for new YouTube videos
    uploaded to the TSR channel. It requires a valid bearer token for authentication.

    The endpoint queries the YouTube Data API for videos published within the last ~6 hours,
    logs their titles and links, and returns a summary response.

    Methods:
        POST: Authenticates the request and fetches recently uploaded videos from YouTube.

    Headers:
        Authorization: A bearer token matching the CRON_SECRET environment variable.

    Returns:
        Response: A JSON object containing a message and the number of videos found.
    """
    # Validate auth
    auth_header = request.headers.get('Authorization')
    if not auth_header or not auth_header.startswith('Bearer '):
        abort(401, description='Missing or invalid Authorization header')

    token = auth_header.split(' ')[1]
    if token != CRON_SECRET:
        abort(403, description='Invalid bearer token')

    # Get videos from past 6 hours
    pst = timezone(timedelta(hours=-7))
    now_pst = datetime.now(pst)
    published_after_utc = (now_pst - timedelta(hours=6)).astimezone(timezone.utc)
    published_after = published_after_utc.isoformat(timespec='seconds').replace('+00:00', 'Z')

    yt_request = YOUTUBE_CLIENT.search().list(
        part='snippet',
        channelId=TSR_YOUTUBE,
        order='date',
        type='video',
        publishedAfter=published_after,
        maxResults=50
    )
    response = yt_request.execute()

    # Categorize videos
    categories_mapping = defaultdict(list)
    for item in response.get('items', []):
        category = item['snippet']['title'].split(' - ')[0]
        categories_mapping[category].append(item)

    # Process Videos
    if categories_mapping["Time Attack"]: process_ta(categories_mapping["Time Attack"])
    if categories_mapping["Raw Footage"]: process_raw(categories_mapping["Raw Footage"])

    return {
        "msg": f"Job processed succesfully with {len(response['items'])} item(s)."
    }


# --- Util ---
def process_ta(videos: list) -> None:
    """
    Processes Time Attack YouTube videos by fetching full descriptions, extracting metadata,
    converting and normalizing fields, and saving the result to MongoDB.

    If an existing record with the same proof URL exists, it is updated.

    Methods:
        None (helper function)

    Args:
        videos (list): A list of YouTube search result items containing basic video metadata.

    Returns:
        None
    """
    video_ids = [video["id"]["videoId"] for video in videos]
    if not video_ids:
        return

    details_response = YOUTUBE_CLIENT.videos().list(
        part='snippet',
        id=','.join(video_ids)
    ).execute()

    for full_video in details_response.get("items", []):
        video_id = full_video["id"]
        snippet = full_video["snippet"]
        description = snippet["description"]
        metadata = extract_metadata(description)

        if not metadata:
            print(f"Skipped video {video_id}: no metadata block found", flush=True)
            continue

        try:
            track = metadata["track"].strip().lower().replace(" ", "-")
            configuration = metadata.get("configuration", "").strip()
            date = datetime.strptime(metadata["date"], "%m/%d/%Y")
            car = metadata["car"].strip()
            tag = metadata.get("tag", "").strip()
            time_seconds = parse_lap_time_to_seconds(metadata["time"])
            proof = f"https://www.youtube.com/watch?v={video_id}"
            driver_email = metadata["driver"].strip().lower()

            user = DATABASE["User"].find_one({"email": driver_email})
            if not user:
                print(f"Skipped video {video_id}: user not found for email {driver_email}", flush=True)
                continue

            track_time_doc = {
                "track": track,
                "configuration": configuration,
                "date": date,
                "car": car,
                "tag": tag,
                "time": time_seconds,
                "proof": proof,
                "userId": user["_id"],
            }

            DATABASE["TrackTime"].update_one(
                {"proof": proof},
                {"$set": track_time_doc},
                upsert=True
            )

            print(f"Upserted track time for {track} | {proof}", flush=True)

        except Exception as e:
            print(f"Error processing video {video_id}: {e}", flush=True)
    

def process_raw(videos: list) -> None:
    pass


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