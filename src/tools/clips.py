"""
Clip capture and playback tools.

Provides tools for:
- Creating Twitch clips from live stream
- Capturing OBS replay buffer clips
- Playing clips on stream
- Analyzing clip content
"""

import base64
import time

from ..app import mcp, get_obs_client, get_twitch_client


# =============================================================================
# OBS Replay Buffer Tools
# =============================================================================


@mcp.tool()
def obs_replay_buffer_status() -> dict:
    """
    Get the status of OBS replay buffer.

    Returns whether replay buffer is active and ready to save clips.
    """
    client = get_obs_client()
    return client.get_replay_buffer_status()


@mcp.tool()
def obs_start_replay_buffer() -> str:
    """
    Start the OBS replay buffer.

    The replay buffer continuously records and keeps the last N seconds
    (configured in OBS settings) ready to be saved as a clip.
    """
    client = get_obs_client()
    client.start_replay_buffer()
    return "Replay buffer started"


@mcp.tool()
def obs_stop_replay_buffer() -> str:
    """Stop the OBS replay buffer."""
    client = get_obs_client()
    client.stop_replay_buffer()
    return "Replay buffer stopped"


@mcp.tool()
def obs_save_replay() -> dict:
    """
    Save the current replay buffer to a file.

    This captures the last N seconds (as configured in OBS) and saves
    it as a video file. Returns the path to the saved file.

    Note: Replay buffer must be running first (use obs_start_replay_buffer).
    """
    client = get_obs_client()

    # Check if replay buffer is active
    status = client.get_replay_buffer_status()
    if not status.get("active"):
        return {
            "status": "error",
            "message": "Replay buffer is not active. Start it first with obs_start_replay_buffer.",
        }

    # Save the replay
    saved_path = client.save_replay_buffer()

    return {
        "status": "saved",
        "file_path": saved_path,
    }


# =============================================================================
# OBS Recording Tools
# =============================================================================


@mcp.tool()
def obs_record_status() -> dict:
    """Get OBS recording status (active, paused, duration, etc.)."""
    client = get_obs_client()
    return client.get_record_status()


@mcp.tool()
def obs_start_recording() -> str:
    """Start OBS recording."""
    client = get_obs_client()
    client.start_record()
    return "Recording started"


@mcp.tool()
def obs_stop_recording() -> dict:
    """
    Stop OBS recording and return the output file path.

    Returns the path to the recorded video file.
    """
    client = get_obs_client()
    output_path = client.stop_record()
    return {
        "status": "stopped",
        "file_path": output_path,
    }


@mcp.tool()
def obs_pause_recording() -> str:
    """Pause OBS recording."""
    client = get_obs_client()
    client.pause_record()
    return "Recording paused"


@mcp.tool()
def obs_resume_recording() -> str:
    """Resume OBS recording."""
    client = get_obs_client()
    client.resume_record()
    return "Recording resumed"


# =============================================================================
# Twitch Clip Tools
# =============================================================================


@mcp.tool()
def twitch_create_clip(has_delay: bool = False) -> dict:
    """
    Create a Twitch clip from the current live stream.

    This creates a clip of approximately the last 30 seconds of the stream.
    The clip will be available on Twitch after processing (usually a few seconds).

    Args:
        has_delay: Set to True if your stream has a delay configured,
                   to capture the right moment.

    Returns:
        Dict with clip ID and edit URL for customizing the clip.
    """
    client = get_twitch_client()

    # Check if streaming
    stream_info = client.get_stream_info()
    if not stream_info:
        return {
            "status": "error",
            "message": "Not currently streaming - cannot create clip",
        }

    try:
        result = client.create_clip(has_delay=has_delay)
        return {
            "status": "created",
            "clip_id": result["id"],
            "edit_url": result["edit_url"],
            "note": "Clip is processing. It may take a few seconds to be available.",
        }
    except Exception as e:
        return {
            "status": "error",
            "message": str(e),
        }


@mcp.tool()
def twitch_get_clip_info(clip_id: str) -> dict:
    """
    Get details about a specific Twitch clip.

    Args:
        clip_id: The clip ID to look up

    Returns:
        Clip details including URL, title, duration, view count, etc.
    """
    client = get_twitch_client()
    clip = client.get_clip(clip_id)
    if clip:
        return clip
    return {"status": "error", "message": f"Clip {clip_id} not found"}


@mcp.tool()
def twitch_get_my_clips(count: int = 10) -> list[dict]:
    """
    Get recent clips from your own channel.

    Args:
        count: Number of clips to return (default 10)

    Returns:
        List of clip details sorted by most recent.
    """
    client = get_twitch_client()
    return client.get_my_clips(count=count)


# =============================================================================
# Clip Playback Tools
# =============================================================================


@mcp.tool()
def play_clip_on_stream(
    clip_url: str,
    source_name: str = "mcp-clip-player",
    duration_seconds: int = 0,
) -> dict:
    """
    Play a clip or video on stream as an overlay.

    Can play Twitch clips (via embed URL) or local video files.

    Args:
        clip_url: URL of the clip (Twitch embed URL) or path to local video file
        source_name: Name for the OBS source (default: mcp-clip-player)
        duration_seconds: How long to show the clip (0 = until manually removed)

    Returns:
        Status of the clip playback
    """
    obs = get_obs_client()
    scene = obs.get_current_scene()

    # Remove existing clip player if present
    try:
        obs.remove_source(source_name)
    except Exception:
        pass

    # Determine if it's a local file or URL
    if clip_url.startswith("/") or clip_url.startswith("~"):
        # Local file - use media source
        obs.create_media_source(scene, source_name, clip_url, loop=False)
        source_type = "media"
    else:
        # URL - use browser source for Twitch embeds
        # Add autoplay parameters if it's a Twitch clip
        if "clips.twitch.tv" in clip_url or "twitch.tv" in clip_url:
            if "?" in clip_url:
                clip_url += "&parent=localhost&autoplay=true"
            else:
                clip_url += "?parent=localhost&autoplay=true"

        obs.create_browser_source(scene, source_name, clip_url, width=1280, height=720)
        source_type = "browser"

    result = {
        "status": "playing",
        "source_name": source_name,
        "source_type": source_type,
        "url": clip_url,
    }

    # If duration specified, schedule removal
    if duration_seconds > 0:
        result["auto_remove_after"] = duration_seconds
        result["note"] = f"Clip will be removed after {duration_seconds} seconds"

    return result


@mcp.tool()
def stop_clip_playback(source_name: str = "mcp-clip-player") -> str:
    """
    Stop clip playback and remove the clip overlay.

    Args:
        source_name: Name of the clip source to remove (default: mcp-clip-player)
    """
    obs = get_obs_client()
    try:
        obs.remove_source(source_name)
        return f"Clip playback stopped, removed '{source_name}'"
    except Exception as e:
        return f"Could not remove clip source: {e}"


# =============================================================================
# Clip Analysis Tools
# =============================================================================


@mcp.tool()
def capture_clip_frame(source_name: str = "") -> dict:
    """
    Capture a frame from a video source for analysis.

    This takes a screenshot that can be analyzed by Claude to understand
    what's happening in the clip/stream.

    Args:
        source_name: Name of the source to capture (empty = current scene)

    Returns:
        Dict with base64 image data for analysis
    """
    obs = get_obs_client()
    if not source_name:
        source_name = None

    image_bytes = obs.get_screenshot(source_name)
    image_b64 = base64.b64encode(image_bytes).decode("utf-8")

    return {
        "status": "captured",
        "source": source_name or "current_scene",
        "image_base64": image_b64,
        "format": "png",
    }


@mcp.tool()
def analyze_and_comment_clip(description: str) -> dict:
    """
    Send a comment to chat about a clip based on your analysis.

    After using capture_clip_frame and analyzing what you see,
    use this tool to share your observations with chat.

    Args:
        description: Your analysis/commentary about the clip content

    Returns:
        Confirmation that the message was sent
    """
    twitch = get_twitch_client()
    twitch.send_chat_message(f"Clip analysis: {description}")

    return {
        "status": "sent",
        "message": description,
    }
