from googleapiclient.discovery import build
from datetime import datetime, timedelta, timezone

API_KEY = ''
CHANNEL_ID = 'UCta0SQtijD99YME39hHCrag'  # replace with your channel ID

youtube = build('youtube', 'v3', developerKey=API_KEY)

# Look at past 6 hours
pst = timezone(timedelta(hours=-7))
now_pst = datetime.now(pst)
published_after_utc = (now_pst - timedelta(hours=1000)).astimezone(timezone.utc)
published_after = published_after_utc.isoformat(timespec='seconds').replace('+00:00', 'Z')

request = youtube.search().list(
    part='snippet',
    channelId=CHANNEL_ID,
    order='date',
    type='video',
    publishedAfter=published_after,
    maxResults=50
)

response = request.execute()

for item in response.get('items', []):
    title = item['snippet']['title']
    video_id = item['id']['videoId']
    print(f"{title}: (https://www.youtube.com/watch?v={video_id})")
