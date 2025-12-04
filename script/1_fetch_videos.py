import googleapiclient.discovery
from youtube_transcript_api import YouTubeTranscriptApi
from youtube_transcript_api._errors import TranscriptsDisabled, NoTranscriptFound
import json
import time
import os
import ssl
import certifi
from dotenv import load_dotenv
import urllib.request
from typing import Any

# SSL Fix - patch urllib to use certifi
cert_path = certifi.where()
original_urlopen = urllib.request.urlopen


def patched_urlopen(url, *args, **kwargs):
    if "context" not in kwargs:
        kwargs["context"] = ssl.create_default_context(cafile=cert_path)
    return original_urlopen(url, *args, **kwargs)


urllib.request.urlopen = patched_urlopen

load_dotenv()

API_KEY = os.getenv("YOUTUBE_API_KEY")
CHANNEL_ID = os.getenv("CHANNEL_ID")


def get_transcript(video_id):
    """Get transcript with error handling"""
    try:
        transcript_list = YouTubeTranscriptApi.get_transcript(video_id)
        full_text = " ".join([t["text"] for t in transcript_list])
        return full_text
    except (TranscriptsDisabled, NoTranscriptFound):
        return None
    except Exception:
        return None


def get_channel_content(api_key, channel_id, max_videos=20):
    """Fetch videos from YouTube channel"""
    # construct the client once and keep the Any annotation so static type checkers
    # don't complain about missing Resource members like playlistItems
    youtube: Any = googleapiclient.discovery.build(  # type: ignore
        "youtube", "v3", developerKey=api_key
    )

    res = (
        youtube.channels()  # type: ignore
        .list(id=channel_id, part="contentDetails,snippet")
        .execute()
    )

    if not res.get("items"):
        print(f"❌ Channel {channel_id} not found!")
        return []

    channel_name = res["items"][0]["snippet"]["title"]
    uploads_playlist = res["items"][0]["contentDetails"]["relatedPlaylists"]["uploads"]

    print(f"📺 Channel: {channel_name}")
    print(f"📍 Fetching videos...\n")

    videos = []
    next_page_token = None

    while len(videos) < max_videos:
        playlist_res = (
            youtube.playlistItems()  # type: ignore
            .list(
                playlistId=uploads_playlist,
                part="snippet",
                maxResults=50,
                pageToken=next_page_token,
            )
            .execute()
        )

        for item in playlist_res["items"]:
            if len(videos) >= max_videos:
                break

            video_id = item["snippet"]["resourceId"]["videoId"]
            title = item["snippet"]["title"]

            print(f"[{len(videos) + 1}] {title[:60]}...", end=" ")

            transcript = get_transcript(video_id)

            if transcript:
                videos.append(
                    {
                        "video_id": video_id,
                        "title": title,
                        "url": f"https://www.youtube.com/watch?v={video_id}",
                        "transcript": transcript,
                        "word_count": len(transcript.split()),
                        "published_at": item["snippet"]["publishedAt"],
                    }
                )
                print(f"✅ ({len(transcript.split())} words)")
            else:
                print("❌ No transcript")

            time.sleep(0.3)

        next_page_token = playlist_res.get("nextPageToken")
        if not next_page_token:
            break

    return videos


if __name__ == "__main__":
    if not API_KEY or not CHANNEL_ID:
        print("❌ Error: Check your .env file")
        exit(1)

    print("🚀 Starting YouTube data fetch...\n")

    data = get_channel_content(API_KEY, CHANNEL_ID, max_videos=20)

    if not data:
        print("\n❌ No videos found. Try a different channel.")
        exit(1)

    os.makedirs("data", exist_ok=True)

    with open("data/youtuber_context.json", "w", encoding="utf-8") as f:
        json.dump(data, f, indent=4, ensure_ascii=False)

    print(f"\n✅ Done! Fetched {len(data)} videos")
    print(f"💾 Saved to data/youtuber_context.json")
    print(f"📊 Total words: {sum(v['word_count'] for v in data):,}")
    print("\n🚀 Next: python 2_process_and_embed.py")
