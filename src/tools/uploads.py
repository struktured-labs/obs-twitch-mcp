"""
Video upload tools.

Provides tools for uploading videos to various platforms.
Currently supports:
- YouTube (via Data API v3)

Limited support:
- Twitch (no API upload - manual only)

Future platforms:
- Rumble
- PeerTube
- Instagram
- TikTok
"""

from ..app import mcp, get_twitch_client
from ..utils.youtube_client import get_youtube_client


# =============================================================================
# Twitch Video Upload Tools
# =============================================================================


@mcp.tool()
def upload_video_to_twitch(
    file_path: str,
    title: str,
    description: str = "",
) -> dict:
    """
    Upload a video file to Twitch.

    NOTE: Twitch Helix API does not support video uploads. The old v5 API
    had this feature but it was deprecated. Videos must be uploaded manually
    via the Twitch Video Producer web interface.

    For creating clips from live streams, use twitch_create_clip instead.

    Args:
        file_path: Path to the video file to upload
        title: Title for the video on Twitch
        description: Optional description for the video

    Returns:
        Error explaining the limitation.
    """
    return {
        "status": "error",
        "platform": "twitch",
        "message": "Twitch API does not support video uploads. Use the Video Producer at https://dashboard.twitch.tv/content/video-producer to upload manually, or use twitch_create_clip to clip from live streams.",
        "file_path": file_path,
        "suggested_title": title,
    }


@mcp.tool()
def get_my_twitch_videos(count: int = 10) -> list[dict]:
    """
    Get videos from your Twitch channel.

    Args:
        count: Number of videos to return (default 10)

    Returns:
        List of video details including title, URL, duration, view count.
    """
    client = get_twitch_client()
    return client.get_videos(count=count)


@mcp.tool()
def get_twitch_video_info(video_id: str) -> dict:
    """
    Get details about a specific Twitch video.

    Args:
        video_id: The Twitch video ID

    Returns:
        Video details or error if not found.
    """
    client = get_twitch_client()
    video = client.get_video(video_id)
    if video:
        return video
    return {"status": "error", "message": f"Video {video_id} not found"}


# =============================================================================
# YouTube Video Upload Tools
# =============================================================================


@mcp.tool()
def upload_video_to_youtube(
    file_path: str,
    title: str,
    description: str = "",
    tags: str = "",
    privacy: str = "unlisted",
) -> dict:
    """
    Upload a video file to YouTube.

    Requires OAuth2 setup:
    1. Create project in Google Cloud Console
    2. Enable YouTube Data API v3
    3. Create OAuth2 credentials (Desktop app)
    4. Download client secrets JSON as .youtube_client_secrets.json
    5. First upload will open browser for authorization

    Args:
        file_path: Path to the video file to upload
        title: Video title
        description: Video description
        tags: Comma-separated tags (e.g., "gaming,stream,clip")
        privacy: "public", "private", or "unlisted" (default: unlisted)

    Returns:
        Dict with video ID and URL on success.
    """
    try:
        client = get_youtube_client()
        tag_list = [t.strip() for t in tags.split(",") if t.strip()] if tags else []

        result = client.upload_video(
            file_path=file_path,
            title=title,
            description=description,
            tags=tag_list,
            privacy_status=privacy,
        )
        return {
            "status": "success",
            "platform": "youtube",
            "video_id": result["video_id"],
            "url": result["url"],
            "message": f"Video uploaded to YouTube: {result['url']}",
        }
    except FileNotFoundError as e:
        return {
            "status": "error",
            "platform": "youtube",
            "message": str(e),
        }
    except Exception as e:
        return {
            "status": "error",
            "platform": "youtube",
            "message": f"Upload failed: {e}",
        }


@mcp.tool()
def get_my_youtube_videos(count: int = 10) -> list[dict]:
    """
    Get videos from your YouTube channel.

    Args:
        count: Number of videos to return (default 10)

    Returns:
        List of video details including title, URL, published date.
    """
    try:
        client = get_youtube_client()
        return client.get_my_videos(count=count)
    except Exception as e:
        return [{"status": "error", "message": str(e)}]


@mcp.tool()
def get_youtube_video_info(video_id: str) -> dict:
    """
    Get details about a specific YouTube video.

    Args:
        video_id: The YouTube video ID

    Returns:
        Video details or error if not found.
    """
    try:
        client = get_youtube_client()
        video = client.get_video(video_id)
        if video:
            return video
        return {"status": "error", "message": f"Video {video_id} not found"}
    except Exception as e:
        return {"status": "error", "message": str(e)}


@mcp.tool()
def delete_youtube_video(video_id: str) -> dict:
    """
    Delete a video from YouTube.

    Args:
        video_id: The YouTube video ID to delete

    Returns:
        Success or error status.
    """
    try:
        client = get_youtube_client()
        client.delete_video(video_id)
        return {
            "status": "success",
            "message": f"Video {video_id} deleted from YouTube",
        }
    except Exception as e:
        return {"status": "error", "message": str(e)}


# =============================================================================
# Generic Upload Tool (Platform Router)
# =============================================================================


@mcp.tool()
def upload_video(
    file_path: str,
    platform: str,
    title: str,
    description: str = "",
) -> dict:
    """
    Upload a video to a specified platform.

    This is a generic upload tool that routes to the appropriate platform.
    Currently supports: youtube

    Limited: twitch (no API upload)
    Future platforms: rumble, peertube, instagram, tiktok

    Args:
        file_path: Path to the video file to upload
        platform: Target platform (twitch, youtube, etc.)
        title: Title for the video
        description: Optional description

    Returns:
        Dict with upload status and details.
    """
    platform = platform.lower().strip()

    if platform == "twitch":
        return upload_video_to_twitch(file_path, title, description)
    elif platform in ("youtube", "yt"):
        return upload_video_to_youtube(file_path, title, description)
    elif platform == "rumble":
        return {
            "status": "error",
            "platform": platform,
            "message": "Rumble upload not yet implemented. Coming soon!",
        }
    elif platform == "peertube":
        return {
            "status": "error",
            "platform": platform,
            "message": "PeerTube upload not yet implemented. Coming soon!",
        }
    elif platform in ("instagram", "ig"):
        return {
            "status": "error",
            "platform": platform,
            "message": "Instagram upload not yet implemented. Coming soon!",
        }
    elif platform == "tiktok":
        return {
            "status": "error",
            "platform": platform,
            "message": "TikTok upload not yet implemented. Coming soon!",
        }
    else:
        return {
            "status": "error",
            "platform": platform,
            "message": f"Unknown platform: {platform}. Supported: youtube, twitch (limited)",
        }
