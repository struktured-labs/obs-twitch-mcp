"""
Video upload tools.

Provides tools for uploading videos to various platforms.
Currently supports:
- Twitch (via Helix API)

Future platforms:
- YouTube
- Rumble
- PeerTube
- Instagram
- TikTok
"""

from ..app import mcp, get_twitch_client


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
    Currently supports: twitch

    Future platforms: youtube, rumble, peertube, instagram, tiktok

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
        return {
            "status": "error",
            "platform": platform,
            "message": "YouTube upload not yet implemented. Coming soon!",
        }
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
            "message": f"Unknown platform: {platform}. Supported: twitch",
        }
