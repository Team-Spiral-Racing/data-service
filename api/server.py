from flask import Flask, Response, redirect, url_for, abort, request
from dotenv import load_dotenv

# Third Party
from googleapiclient.discovery import build
from pymongo import MongoClient, ASCENDING

# Util
from datetime import datetime, timedelta, timezone
from collections import defaultdict
from git_utils import GitUtils
from util import *
import os

# Setup
load_dotenv()
MONGO_CLIENT = MongoClient(os.getenv('MONGO_CONNECTION'))
DATABASE = MONGO_CLIENT[os.getenv('MONGO_DB_NAME')]
YOUTUBE_CLIENT = build('youtube', 'v3', developerKey=os.getenv('YOUTUBE_API_KEY'))
COMMITTER = GitUtils(
    token=os.getenv("GITHUB_TOKEN"),
    owner="Team-Spiral-Racing",
    repo="blog",
    branch="main"
)
app = Flask(__name__)

# Config
CRON_SECRET = os.getenv('CRON_SECRET')
API_KEY = os.getenv('API_KEY')
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


@app.route('/blog', methods=['POST'])
def blog() -> Response:
    blog_post = None

    # Parse request
    data = request.get_json() or {}
    blog_id = data.get("blog")
    auth_header = request.headers.get("Authorization")

    # Parse auth
    if not auth_header or not auth_header.startswith("Bearer "):
        abort(401, description="Missing or invalid Authorization header")
    token = auth_header.split(" ", 1)[1]

    if blog_id:
        # Case 1: Specific blog post - verify with API_KEY
        if token != API_KEY:
            abort(403, description="Invalid bearer token for blog update")

        blog_post = DATABASE["BlogPost"].find_one({"_id": blog_id})
        if not blog_post:
            abort(404, description=f"BlogPost with ID {blog_id} not found")

        process_single_blog(blog_post)
    else:
        # Case 2: Full sync or cron-based update - verify with CRON_SECRET
        if token != CRON_SECRET:
            abort(403, description="Invalid bearer token for cron job")

        blog_cron_sync()
   
    return {
        "msg": f"Job processed succesfully."
    }


# --- Detailed ---
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


def process_single_blog(blog_post):
    """
    Processes and commits a single blog post to the GitHub repository.

    This function formats the blog post into markdown, downloads its associated 
    background image, and commits both the markdown and image to the GitHub repo 
    under the path: `content/posts/<slug>`.

    Args:
        blog_post (dict): A dictionary representing the blog post. It must contain:
            - '_id': The slug used for the post directory.
            - 'imageRef': A URL to the background image.
            - other fields required by `format_markdown_to_blowfish`.

    Side Effects:
        - Writes/updates files on disk.
        - Commits and pushes changes to the configured GitHub repository.
    """
    # Gather post context
    blog_markdown = format_markdown_to_blowfish(DATABASE, blog_post)
    image_background = blog_post["imageRef"]
    article_path = blog_post["_id"]

    # Commit to repo
    COMMITTER.commit_blog_post(
        slug=article_path,
        markdown=blog_markdown,
        image_url=image_background
    )


def blog_cron_sync():
    """
    Fetches all blog posts from the database and compares them with the GitHub
    repository. Commits only the ones that have changed or are new.
    """
    changed_files = []
    blog_posts = DATABASE["BlogPost"].find()

    for blog_post in blog_posts:
        slug = blog_post["_id"]
        image_url = blog_post["imageRef"]
        markdown = format_markdown_to_blowfish(DATABASE, blog_post)

        post_dir = f"content/posts/{slug}"
        markdown_path = f"{post_dir}/index.md"
        markdown_bytes = markdown.encode("utf-8")
        if COMMITTER.file_changed(markdown_path, markdown_bytes):
            COMMITTER.write_file(markdown_path, markdown_bytes)
            changed_files.append(markdown_path)

        image_bytes, ext = COMMITTER.download_image(image_url)
        image_path = f"{post_dir}/featured{ext}"
        if COMMITTER.file_changed(image_path, image_bytes):
            COMMITTER.write_file(image_path, image_bytes)
            changed_files.append(image_path)

    if COMMITTER.commit_files(
        changed_files,
        "ci(ops): sync all blog posts",
        author_email="bot@teamspiralracing.com",
        author_name="TSR Service Account [Bot]"
    ):
        return {"msg": f"Committed {len(changed_files)} changed files."}
    else:
        return {"msg": "No changes detected. Nothing to commit."}