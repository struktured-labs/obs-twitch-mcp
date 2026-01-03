"""
Streamer shoutout tools.
"""

import asyncio

from ..app import mcp, get_obs_client, get_twitch_client


@mcp.tool()
def shoutout_streamer(
    username: str,
    show_clip: bool = True,
    duration_seconds: int = 15,
    custom_message: str = "",
) -> str:
    """
    Shoutout another streamer with optional clip overlay.

    1. Sends shoutout in chat
    2. Optionally displays their latest clip on stream
    3. Auto-removes after duration

    Args:
        username: The streamer to shoutout
        show_clip: Whether to show their latest clip (default: True)
        duration_seconds: How long to show the clip overlay
        custom_message: Custom shoutout message (optional)
    """
    twitch = get_twitch_client()
    obs = get_obs_client()

    # Send chat shoutout
    if custom_message:
        message = f"Go check out @{username}! {custom_message} https://twitch.tv/{username}"
    else:
        message = f"🎉 Go check out @{username}! They're awesome! https://twitch.tv/{username}"

    twitch.send_chat_message(message)

    # Try official shoutout command
    try:
        twitch.shoutout(username)
    except Exception:
        pass  # May fail if not affiliate/partner

    result = f"Shouted out {username} in chat"

    # Show clip if requested
    if show_clip:
        clips = twitch.get_user_clips(username, count=1)
        if clips:
            clip = clips[0]
            scene = obs.get_current_scene()
            embed_url = f"{clip['embed_url']}&parent=localhost&autoplay=true&muted=false"

            # Try to edit existing source first, create if doesn't exist
            try:
                obs.set_input_settings("shoutout-clip", {"url": embed_url})
                # Make sure it's visible
                try:
                    item_id = obs.client.get_scene_item_id(scene, "shoutout-clip").scene_item_id
                    obs.set_scene_item_enabled(scene, item_id, True)
                except Exception:
                    pass
            except Exception:
                # Source doesn't exist, create it
                obs.create_browser_source(scene, "shoutout-clip", embed_url, 640, 360)
                # Position in corner
                item_id = obs.client.get_scene_item_id(scene, "shoutout-clip").scene_item_id
                obs.set_scene_item_transform(scene, item_id, 1600, 100, alignment=9)  # Top-right

            result += f" with clip: {clip['title']}"

            # Schedule hiding (not removal)
            async def hide_after_delay():
                await asyncio.sleep(duration_seconds)
                try:
                    item_id = obs.client.get_scene_item_id(scene, "shoutout-clip").scene_item_id
                    obs.set_scene_item_enabled(scene, item_id, False)
                except Exception:
                    pass

            asyncio.create_task(hide_after_delay())
        else:
            result += " (no clips found)"

    return result


@mcp.tool()
def get_streamer_clips(username: str, count: int = 5) -> list[dict]:
    """
    Get recent clips from a streamer.

    Args:
        username: The streamer's username
        count: Number of clips to fetch (max 100)
    """
    twitch = get_twitch_client()
    return twitch.get_user_clips(username, count)


@mcp.tool()
def clear_shoutout_clip() -> str:
    """Remove the shoutout clip overlay."""
    obs = get_obs_client()
    try:
        obs.remove_source("shoutout-clip")
        return "Shoutout clip removed"
    except Exception:
        return "No shoutout clip to remove"
