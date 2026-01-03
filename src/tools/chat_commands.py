"""
Chat command handlers for Twitch chat.
"""

import asyncio
from pathlib import Path

from ..app import mcp, get_obs_client, get_twitch_client


# Track active lurk overlay
_lurk_hide_task = None


@mcp.tool()
def show_lurk_animation(username: str, duration_seconds: int = 10) -> str:
    """
    Show a lurk animation for a user.

    Args:
        username: The username of the lurker
        duration_seconds: How long to show the animation (default: 10)
    """
    global _lurk_hide_task

    obs = get_obs_client()
    scene = obs.get_current_scene()

    # Build URL with username parameter
    html_path = Path(__file__).parent.parent.parent / "assets" / "lurk-animation.html"
    url = f"file://{html_path}?user={username}"

    # Try to edit existing source, create if doesn't exist
    try:
        obs.set_input_settings("mcp-lurk-overlay", {"url": url})
        # Make sure it's visible
        try:
            item_id = obs.client.get_scene_item_id(scene, "mcp-lurk-overlay").scene_item_id
            obs.set_scene_item_enabled(scene, item_id, True)
        except Exception:
            pass
    except Exception:
        # Source doesn't exist, create it
        obs.create_browser_source(scene, "mcp-lurk-overlay", url, 1920, 1080)

    # Cancel any existing hide task
    if _lurk_hide_task and not _lurk_hide_task.done():
        _lurk_hide_task.cancel()

    # Schedule hiding
    async def hide_after_delay():
        await asyncio.sleep(duration_seconds)
        try:
            item_id = obs.client.get_scene_item_id(scene, "mcp-lurk-overlay").scene_item_id
            obs.set_scene_item_enabled(scene, item_id, False)
        except Exception:
            pass

    _lurk_hide_task = asyncio.create_task(hide_after_delay())

    return f"Showing lurk animation for {username} for {duration_seconds}s"


@mcp.tool()
def hide_lurk_animation() -> str:
    """Hide the lurk animation immediately."""
    global _lurk_hide_task

    obs = get_obs_client()
    scene = obs.get_current_scene()

    # Cancel any pending hide task
    if _lurk_hide_task and not _lurk_hide_task.done():
        _lurk_hide_task.cancel()

    try:
        item_id = obs.client.get_scene_item_id(scene, "mcp-lurk-overlay").scene_item_id
        obs.set_scene_item_enabled(scene, item_id, False)
        return "Lurk animation hidden"
    except Exception:
        return "No lurk animation to hide"


@mcp.tool()
def handle_chat_command(username: str, message: str) -> str:
    """
    Handle a chat command from a user.

    Supported commands:
        !lurk - Show lurk animation for 10 seconds

    Args:
        username: The username who sent the command
        message: The full message text
    """
    message_lower = message.lower().strip()

    if message_lower == "!lurk" or message_lower.startswith("!lurk "):
        return show_lurk_animation(username, 10)

    return f"Unknown command: {message}"
