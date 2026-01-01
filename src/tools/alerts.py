"""
Stream alert tools.
"""

import asyncio

from ..app import mcp, get_obs_client


@mcp.tool()
def show_follow_alert(
    username: str,
    message: str = "Thanks for the follow!",
    duration_seconds: int = 5,
) -> str:
    """
    Display a follow alert overlay.

    Args:
        username: The new follower's username
        message: Custom message (default: "Thanks for the follow!")
        duration_seconds: How long to show the alert
    """
    client = get_obs_client()
    scene = client.get_current_scene()

    alert_text = f"🎉 {username} 🎉\n{message}"

    # Remove old alert if present
    try:
        client.remove_source("follow-alert")
    except Exception:
        pass

    # Create alert
    item_id = client.create_text_source(
        scene,
        "follow-alert",
        alert_text,
        font_size=72,
        color=0xFF00FF00,  # Green
    )

    # Center it
    client.set_scene_item_transform(scene, item_id, 960, 400, alignment=4)

    # Schedule removal
    async def remove_after_delay():
        await asyncio.sleep(duration_seconds)
        try:
            client.remove_source("follow-alert")
        except Exception:
            pass

    asyncio.create_task(remove_after_delay())

    return f"Showing follow alert for {username}"


@mcp.tool()
def show_custom_alert(
    title: str,
    subtitle: str = "",
    color: str = "white",
    duration_seconds: int = 5,
    position: str = "center",
) -> str:
    """
    Display a custom alert overlay.

    Args:
        title: Main alert text
        subtitle: Secondary text (optional)
        color: Text color (white, red, green, blue, yellow)
        duration_seconds: How long to show
        position: Where to show (center, top, bottom)
    """
    client = get_obs_client()
    scene = client.get_current_scene()

    alert_text = title
    if subtitle:
        alert_text = f"{title}\n{subtitle}"

    # Color mapping
    colors = {
        "white": 0xFFFFFFFF,
        "red": 0xFFFF0000,
        "green": 0xFF00FF00,
        "blue": 0xFF0000FF,
        "yellow": 0xFFFFFF00,
    }
    color_int = colors.get(color.lower(), 0xFFFFFFFF)

    # Position mapping
    positions = {
        "center": (960, 540),
        "top": (960, 200),
        "bottom": (960, 800),
    }
    x, y = positions.get(position, (960, 540))

    # Remove old alert if present
    try:
        client.remove_source("custom-alert")
    except Exception:
        pass

    # Create alert
    item_id = client.create_text_source(
        scene,
        "custom-alert",
        alert_text,
        font_size=64,
        color=color_int,
    )

    client.set_scene_item_transform(scene, item_id, x, y, alignment=4)

    # Schedule removal
    async def remove_after_delay():
        await asyncio.sleep(duration_seconds)
        try:
            client.remove_source("custom-alert")
        except Exception:
            pass

    asyncio.create_task(remove_after_delay())

    return f"Showing custom alert: {title}"


@mcp.tool()
def clear_all_alerts() -> str:
    """Remove all alert overlays from the scene."""
    client = get_obs_client()

    alerts = ["follow-alert", "custom-alert", "raid-alert", "sub-alert"]
    removed = []

    for alert in alerts:
        try:
            client.remove_source(alert)
            removed.append(alert)
        except Exception:
            pass

    if removed:
        return f"Removed alerts: {', '.join(removed)}"
    return "No alerts to remove"
