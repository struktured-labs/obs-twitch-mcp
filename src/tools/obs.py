"""
OBS Studio control tools.
"""

import base64

from ..app import mcp, get_obs_client


@mcp.tool()
def obs_list_scenes() -> list[str]:
    """List all available OBS scenes."""
    client = get_obs_client()
    return client.list_scenes()


@mcp.tool()
def obs_get_current_scene() -> str:
    """Get the current program scene name."""
    client = get_obs_client()
    return client.get_current_scene()


@mcp.tool()
def obs_switch_scene(scene_name: str) -> str:
    """Switch to a specific OBS scene."""
    client = get_obs_client()
    client.switch_scene(scene_name)
    return f"Switched to scene: {scene_name}"


@mcp.tool()
def obs_get_scene_items(scene_name: str = "") -> list[dict]:
    """Get all items/sources in a scene. Uses current scene if not specified."""
    client = get_obs_client()
    if not scene_name:
        scene_name = client.get_current_scene()
    return client.get_scene_items(scene_name)


@mcp.tool()
def obs_add_text_overlay(
    text: str,
    source_name: str = "mcp-text-overlay",
    font_size: int = 60,
    color: str = "white",
    position_x: float = 960,
    position_y: float = 900,
) -> str:
    """
    Add a text overlay to the current scene.

    Args:
        text: The text to display
        source_name: Name for the text source (default: mcp-text-overlay)
        font_size: Font size in pixels (default: 60)
        color: Color name or hex (white, red, green, blue, yellow, #RRGGBB)
        position_x: X position in pixels (default: 960 = center for 1920)
        position_y: Y position in pixels (default: 900 = near bottom for 1080)
    """
    client = get_obs_client()
    scene = client.get_current_scene()

    # Parse color
    color_map = {
        "white": 0xFFFFFFFF,
        "red": 0xFFFF0000,
        "green": 0xFF00FF00,
        "blue": 0xFF0000FF,
        "yellow": 0xFFFFFF00,
        "cyan": 0xFF00FFFF,
        "magenta": 0xFFFF00FF,
    }
    if color.startswith("#"):
        color_int = int(f"FF{color[1:]}", 16)
    else:
        color_int = color_map.get(color.lower(), 0xFFFFFFFF)

    # Remove existing source with same name
    try:
        client.remove_source(source_name)
    except Exception:
        pass

    # Create new text source
    item_id = client.create_text_source(scene, source_name, text, font_size, color_int)

    # Position it (alignment 4 = center)
    client.set_scene_item_transform(scene, item_id, position_x, position_y, alignment=4)

    return f"Created text overlay '{source_name}' with text: {text}"


@mcp.tool()
def obs_update_text(source_name: str, text: str) -> str:
    """Update the text on an existing text source."""
    client = get_obs_client()
    client.set_source_text(source_name, text)
    return f"Updated text on '{source_name}'"


@mcp.tool()
def obs_remove_source(source_name: str) -> str:
    """Remove a source from OBS."""
    client = get_obs_client()
    client.remove_source(source_name)
    return f"Removed source: {source_name}"


@mcp.tool()
def obs_set_volume(source_name: str, volume_db: float) -> str:
    """
    Set volume for an audio source.

    Args:
        source_name: Name of the audio source
        volume_db: Volume in decibels (-100 to 0, where 0 is max)
    """
    client = get_obs_client()
    client.set_volume(source_name, volume_db)
    return f"Set volume of '{source_name}' to {volume_db} dB"


@mcp.tool()
def obs_mute(source_name: str, muted: bool = True) -> str:
    """Mute or unmute an audio source."""
    client = get_obs_client()
    client.set_mute(source_name, muted)
    state = "muted" if muted else "unmuted"
    return f"Source '{source_name}' {state}"


@mcp.tool()
def obs_get_stats() -> dict:
    """Get OBS performance statistics (CPU, FPS, etc.)."""
    client = get_obs_client()
    return client.get_stats()


@mcp.tool()
def obs_screenshot(source_name: str = "") -> str:
    """
    Capture a screenshot of a source or current scene.

    Returns base64-encoded PNG image data.
    """
    client = get_obs_client()
    if not source_name:
        source_name = None
    image_bytes = client.get_screenshot(source_name)
    return base64.b64encode(image_bytes).decode("utf-8")


@mcp.tool()
def obs_add_browser_source(
    url: str,
    source_name: str = "mcp-browser",
    width: int = 1920,
    height: int = 1080,
) -> str:
    """
    Add a browser source to the current scene.

    Useful for displaying web content, Twitch clip embeds, etc.
    """
    client = get_obs_client()
    scene = client.get_current_scene()

    # Remove existing if present
    try:
        client.remove_source(source_name)
    except Exception:
        pass

    client.create_browser_source(scene, source_name, url, width, height)
    return f"Created browser source '{source_name}' with URL: {url}"


@mcp.tool()
def obs_add_media_source(
    file_path: str,
    source_name: str = "mcp-media",
    loop: bool = False,
) -> str:
    """
    Add a media source (video, audio, image) to the current scene.

    Args:
        file_path: Path to the media file
        source_name: Name for the source
        loop: Whether to loop the media
    """
    client = get_obs_client()
    scene = client.get_current_scene()

    # Remove existing if present
    try:
        client.remove_source(source_name)
    except Exception:
        pass

    client.create_media_source(scene, source_name, file_path, loop)
    return f"Created media source '{source_name}' from: {file_path}"
