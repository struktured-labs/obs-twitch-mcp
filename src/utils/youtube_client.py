"""
YouTube API client for video uploads.

Uses the YouTube Data API v3 for uploading videos.
Requires OAuth2 credentials from Google Cloud Console.
"""

import json
import os
from pathlib import Path

from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from google.auth.transport.requests import Request
from googleapiclient.discovery import build
from googleapiclient.http import MediaFileUpload

from .logger import get_logger

logger = get_logger("youtube_client")


# Scopes required for uploading, reading, and deleting videos
YOUTUBE_UPLOAD_SCOPE = [
    "https://www.googleapis.com/auth/youtube.upload",
    "https://www.googleapis.com/auth/youtube.readonly",
    "https://www.googleapis.com/auth/youtube",  # Full access for delete
]

# Token storage path (same pattern as Twitch)
TOKEN_FILE = Path(__file__).parent.parent.parent / ".youtube_token.json"
CLIENT_SECRETS_FILE = Path(__file__).parent.parent.parent / ".youtube_client_secrets.json"


class YouTubeClient:
    """YouTube API client for video operations."""

    def __init__(self):
        self._youtube = None
        self._credentials = None

    def _get_credentials(self) -> Credentials:
        """Get or refresh OAuth2 credentials."""
        creds = None

        # Load existing token
        if TOKEN_FILE.exists():
            try:
                with open(TOKEN_FILE) as f:
                    token_data = json.load(f)
                creds = Credentials.from_authorized_user_info(token_data, YOUTUBE_UPLOAD_SCOPE)
                logger.debug("Loaded YouTube token from file")
            except Exception as e:
                logger.warning(f"Failed to load YouTube token file: {e}")

        # Refresh or get new credentials
        if not creds or not creds.valid:
            if creds and creds.expired and creds.refresh_token:
                logger.info("YouTube token expired, refreshing...")
                try:
                    creds.refresh(Request())
                    logger.info("YouTube token refreshed successfully")
                except Exception as e:
                    logger.error(f"YouTube token refresh failed: {e}")
                    creds = None  # Force re-auth

            if not creds or not creds.valid:
                # Try env vars first, then JSON file
                client_id = os.environ.get("YOUTUBE_CLIENT_ID")
                client_secret = os.environ.get("YOUTUBE_CLIENT_SECRET")

                if client_id and client_secret:
                    logger.info("Using YouTube credentials from env vars")
                    # Build client config from env vars
                    client_config = {
                        "installed": {
                            "client_id": client_id,
                            "client_secret": client_secret,
                            "auth_uri": "https://accounts.google.com/o/oauth2/auth",
                            "token_uri": "https://oauth2.googleapis.com/token",
                            "redirect_uris": ["http://localhost"],
                        }
                    }
                    flow = InstalledAppFlow.from_client_config(client_config, YOUTUBE_UPLOAD_SCOPE)
                elif CLIENT_SECRETS_FILE.exists():
                    logger.info("Using YouTube credentials from secrets file")
                    flow = InstalledAppFlow.from_client_secrets_file(
                        str(CLIENT_SECRETS_FILE), YOUTUBE_UPLOAD_SCOPE
                    )
                else:
                    logger.error("No YouTube credentials found")
                    raise FileNotFoundError(
                        "YouTube credentials not found. Either set YOUTUBE_CLIENT_ID and "
                        "YOUTUBE_CLIENT_SECRET env vars, or download client secrets JSON from "
                        "Google Cloud Console and save as .youtube_client_secrets.json"
                    )

                logger.info("Starting YouTube OAuth flow (will open browser)")
                creds = flow.run_local_server(port=8090)
                logger.info("YouTube OAuth completed successfully")

            # Save credentials
            with open(TOKEN_FILE, "w") as f:
                f.write(creds.to_json())
            logger.debug(f"YouTube token saved to {TOKEN_FILE}")

        return creds

    def _ensure_credentials_valid(self) -> None:
        """Ensure credentials are valid, refreshing if needed."""
        if self._credentials and self._credentials.expired and self._credentials.refresh_token:
            logger.info("YouTube credentials expired, refreshing proactively")
            try:
                self._credentials.refresh(Request())
                logger.info("YouTube credentials refreshed")
            except Exception as e:
                logger.error(f"Proactive refresh failed: {e}")
                # Force re-init on next use
                self._youtube = None
                self._credentials = None

    @property
    def youtube(self):
        """Get authenticated YouTube API service."""
        if self._youtube is None:
            self._credentials = self._get_credentials()
            self._youtube = build("youtube", "v3", credentials=self._credentials)
        else:
            # Proactively refresh before use
            self._ensure_credentials_valid()
        return self._youtube

    def upload_video(
        self,
        file_path: str,
        title: str,
        description: str = "",
        tags: list[str] | None = None,
        category_id: str = "20",  # Gaming category
        privacy_status: str = "unlisted",
    ) -> dict:
        """
        Upload a video to YouTube.

        Args:
            file_path: Path to the video file
            title: Video title
            description: Video description
            tags: List of tags
            category_id: YouTube category ID (20 = Gaming)
            privacy_status: "public", "private", or "unlisted"

        Returns:
            Dict with video ID and URL
        """
        if not os.path.exists(file_path):
            raise FileNotFoundError(f"Video file not found: {file_path}")

        body = {
            "snippet": {
                "title": title,
                "description": description,
                "tags": tags or [],
                "categoryId": category_id,
            },
            "status": {
                "privacyStatus": privacy_status,
                "selfDeclaredMadeForKids": False,
            },
        }

        # Create media upload object
        media = MediaFileUpload(
            file_path,
            mimetype="video/*",
            resumable=True,
            chunksize=1024 * 1024 * 10,  # 10MB chunks
        )

        # Execute upload
        request = self.youtube.videos().insert(
            part=",".join(body.keys()),
            body=body,
            media_body=media,
        )

        response = None
        while response is None:
            status, response = request.next_chunk()
            if status:
                # Progress callback could go here
                pass

        video_id = response["id"]
        return {
            "video_id": video_id,
            "url": f"https://www.youtube.com/watch?v={video_id}",
            "title": response["snippet"]["title"],
            "status": "uploaded",
        }

    def get_my_videos(self, count: int = 10) -> list[dict]:
        """
        Get videos from own channel.

        Args:
            count: Number of videos to return

        Returns:
            List of video details
        """
        # First get the channel's uploads playlist
        channels_response = self.youtube.channels().list(
            part="contentDetails",
            mine=True,
        ).execute()

        if not channels_response.get("items"):
            return []

        uploads_playlist_id = channels_response["items"][0]["contentDetails"][
            "relatedPlaylists"
        ]["uploads"]

        # Get videos from uploads playlist
        playlist_response = self.youtube.playlistItems().list(
            part="snippet",
            playlistId=uploads_playlist_id,
            maxResults=count,
        ).execute()

        return [
            {
                "id": item["snippet"]["resourceId"]["videoId"],
                "title": item["snippet"]["title"],
                "description": item["snippet"]["description"],
                "url": f"https://www.youtube.com/watch?v={item['snippet']['resourceId']['videoId']}",
                "published_at": item["snippet"]["publishedAt"],
                "thumbnail_url": item["snippet"]["thumbnails"].get("default", {}).get("url", ""),
            }
            for item in playlist_response.get("items", [])
        ]

    def get_video(self, video_id: str) -> dict | None:
        """
        Get details for a specific video.

        Args:
            video_id: The YouTube video ID

        Returns:
            Video details or None if not found
        """
        response = self.youtube.videos().list(
            part="snippet,status,statistics",
            id=video_id,
        ).execute()

        if not response.get("items"):
            return None

        item = response["items"][0]
        return {
            "id": item["id"],
            "title": item["snippet"]["title"],
            "description": item["snippet"]["description"],
            "url": f"https://www.youtube.com/watch?v={item['id']}",
            "published_at": item["snippet"]["publishedAt"],
            "view_count": item["statistics"].get("viewCount", 0),
            "like_count": item["statistics"].get("likeCount", 0),
            "privacy_status": item["status"]["privacyStatus"],
            "thumbnail_url": item["snippet"]["thumbnails"].get("default", {}).get("url", ""),
        }

    def delete_video(self, video_id: str) -> bool:
        """
        Delete a video from YouTube.

        Args:
            video_id: The YouTube video ID to delete

        Returns:
            True if deleted successfully
        """
        self.youtube.videos().delete(id=video_id).execute()
        return True


# Singleton instance
_youtube_client = None


def get_youtube_client() -> YouTubeClient:
    """Get or create YouTube client singleton."""
    global _youtube_client
    if _youtube_client is None:
        _youtube_client = YouTubeClient()
    return _youtube_client
