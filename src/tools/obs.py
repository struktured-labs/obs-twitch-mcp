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
def obs_edit_source(source_name: str, settings: dict) -> str:
    """
    Edit settings on an existing source.

    This updates settings without needing to remove and recreate the source.
    Settings are merged with existing ones (overlay mode).

    Args:
        source_name: Name of the source to edit
        settings: Dict of settings to update. Common settings:
            - browser_source: {"url": "...", "width": 1920, "height": 1080}
            - ffmpeg_source: {"local_file": "...", "looping": true}
            - text_ft2_source_v2: {"text": "..."}
            - image_source: {"file": "..."}

    Example:
        obs_edit_source("my-browser", {"url": "https://newurl.com"})
    """
    client = get_obs_client()
    client.set_input_settings(source_name, settings)
    return f"Updated settings on '{source_name}': {settings}"


@mcp.tool()
def obs_get_source_settings(source_name: str) -> dict:
    """
    Get current settings for a source.

    Useful for seeing what settings are available to edit.

    Args:
        source_name: Name of the source to inspect
    """
    client = get_obs_client()
    return client.get_input_settings(source_name)


@mcp.tool()
def obs_remove_source(source_name: str) -> str:
    """Remove a source completely from OBS (from all scenes and input list)."""
    client = get_obs_client()
    client.remove_source(source_name)
    return f"Removed source: {source_name}"


@mcp.tool()
def obs_show_source(source_name: str, scene_name: str = "") -> str:
    """
    Show (enable) a source in a scene.

    Args:
        source_name: Name of the source to show
        scene_name: Scene containing the source (uses current scene if not specified)
    """
    client = get_obs_client()
    if not scene_name:
        scene_name = client.get_current_scene()
    item_id = client.client.get_scene_item_id(scene_name, source_name).scene_item_id
    client.set_scene_item_enabled(scene_name, item_id, True)
    return f"Showing '{source_name}' in scene '{scene_name}'"


@mcp.tool()
def obs_hide_source(source_name: str, scene_name: str = "") -> str:
    """
    Hide (disable) a source in a scene.

    Args:
        source_name: Name of the source to hide
        scene_name: Scene containing the source (uses current scene if not specified)
    """
    client = get_obs_client()
    if not scene_name:
        scene_name = client.get_current_scene()
    item_id = client.client.get_scene_item_id(scene_name, source_name).scene_item_id
    client.set_scene_item_enabled(scene_name, item_id, False)
    return f"Hiding '{source_name}' in scene '{scene_name}'"


@mcp.tool()
def obs_list_inputs() -> list[dict]:
    """List all inputs/sources registered in OBS (even orphaned ones not in any scene)."""
    client = get_obs_client()
    return client.list_inputs()


@mcp.tool()
def obs_cleanup_inputs(prefix: str = "mcp-") -> str:
    """
    Remove all inputs matching a prefix. Useful for cleaning up MCP-created sources.

    Args:
        prefix: Only remove inputs whose names start with this prefix (default: "mcp-")
    """
    client = get_obs_client()
    inputs = client.list_inputs()
    removed = []
    for inp in inputs:
        if inp["name"].startswith(prefix):
            try:
                client.remove_source(inp["name"])
                removed.append(inp["name"])
            except Exception:
                pass
    return f"Removed {len(removed)} sources: {removed}"


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


@mcp.tool()
def obs_add_existing_source(
    source_name: str,
    scene_name: str = "",
    enabled: bool = True,
) -> str:
    """
    Add an existing source/input to a scene.

    This allows you to add a source that already exists in OBS (from another scene
    or in the input list) to the specified scene without creating a new source.

    Args:
        source_name: Name of the existing source to add
        scene_name: Scene to add it to (uses current scene if not specified)
        enabled: Whether the source should be visible (default: True)

    Example:
        obs_add_existing_source("castlevania music", "vibe-coding-main")
    """
    client = get_obs_client()
    if not scene_name:
        scene_name = client.get_current_scene()

    # Check if source already exists in this scene
    try:
        client.client.get_scene_item_id(scene_name, source_name)
        return f"Source '{source_name}' already exists in scene '{scene_name}'"
    except Exception:
        pass  # Source not in scene, continue to add it

    item_id = client.add_source_to_scene(scene_name, source_name, enabled)
    state = "visible" if enabled else "hidden"
    return f"Added '{source_name}' to scene '{scene_name}' (item ID: {item_id}, {state})"


# Filter manipulation tools
@mcp.tool()
def obs_list_filters(source_name: str) -> list[dict]:
    """
    List all filters on an audio or video source.

    Args:
        source_name: Name of the source (e.g., "Mic/Aux", "Desktop Audio")

    Returns:
        List of filters with name, kind, index, and enabled status
    """
    client = get_obs_client()
    return client.get_source_filter_list(source_name)


@mcp.tool()
def obs_get_filter(source_name: str, filter_name: str) -> dict:
    """
    Get detailed settings for a specific filter.

    Args:
        source_name: Name of the source
        filter_name: Name of the filter (e.g., "Noise Gate", "Compressor")

    Returns:
        Dict with filter configuration including all settings
    """
    client = get_obs_client()
    return client.get_source_filter(source_name, filter_name)


@mcp.tool()
def obs_update_filter(
    source_name: str,
    filter_name: str,
    settings: dict
) -> str:
    """
    Update filter settings in real-time (while stream is live).

    This allows dynamic adjustment of audio processing without restarting OBS.

    Args:
        source_name: Name of the source
        filter_name: Name of the filter
        settings: Dict of settings to update (merges with existing)

    Example:
        obs_update_filter("Mic/Aux", "Noise Gate", {
            "close_threshold": -40.0,
            "open_threshold": -35.0
        })
    """
    client = get_obs_client()
    client.set_source_filter_settings(source_name, filter_name, settings, overlay=True)
    return f"Updated filter '{filter_name}' on '{source_name}'"


@mcp.tool()
def obs_enable_filter(source_name: str, filter_name: str, enabled: bool = True) -> str:
    """
    Enable or disable a filter.

    Args:
        source_name: Name of the source
        filter_name: Name of the filter
        enabled: True to enable, False to disable
    """
    client = get_obs_client()
    client.set_source_filter_enabled(source_name, filter_name, enabled)
    state = "enabled" if enabled else "disabled"
    return f"Filter '{filter_name}' on '{source_name}' {state}"


@mcp.tool()
def obs_apply_audio_preset(
    source_name: str,
    preset: str = "noisy"
) -> dict:
    """
    Apply pre-configured audio filter chains for different environments.

    Presets:
    - "noisy": Optimized for loud road/traffic noise (aggressive noise reduction)
    - "normal": Balanced settings for typical streaming (moderate noise reduction)
    - "quiet": Minimal processing for quiet studio environments

    Args:
        source_name: Name of the audio source (e.g., "Mic/Aux")
        preset: Environment preset to apply

    Returns:
        Dict with applied settings and enabled filters
    """
    client = get_obs_client()
    applied = []

    if preset == "noisy":
        # Noise Suppression - keep enabled
        applied.append("Noise Suppression (already enabled)")

        # Noise Gate - gentle settings for noisy environment
        client.set_source_filter_enabled(source_name, "Noise Gate", True)
        client.set_source_filter_settings(source_name, "Noise Gate", {
            "close_threshold": -40.0,
            "open_threshold": -35.0,
            "attack_time": 25,
            "hold_time": 200,
            "release_time": 150,
        })
        applied.append("Noise Gate enabled (gentle)")

        # Compressor - re-enable with existing settings
        client.set_source_filter_enabled(source_name, "Compressor", True)
        applied.append("Compressor enabled (3.5:1 ratio)")

        # Limiter - adjust threshold
        client.set_source_filter_settings(source_name, "Limiter", {
            "threshold": -6.0,
            "release_time": 50,
        })
        applied.append("Limiter adjusted (-6 dB)")

    elif preset == "normal":
        # Moderate noise reduction
        client.set_source_filter_enabled(source_name, "Noise Gate", True)
        client.set_source_filter_settings(source_name, "Noise Gate", {
            "close_threshold": -45.0,
            "open_threshold": -40.0,
            "attack_time": 15,
            "hold_time": 150,
            "release_time": 100,
        })
        applied.append("Noise Gate enabled (moderate)")

        client.set_source_filter_enabled(source_name, "Compressor", True)
        applied.append("Compressor enabled")

    elif preset == "quiet":
        # Minimal processing
        client.set_source_filter_enabled(source_name, "Noise Gate", False)
        applied.append("Noise Gate disabled")

        client.set_source_filter_enabled(source_name, "Compressor", False)
        applied.append("Compressor disabled")

    return {
        "preset": preset,
        "source": source_name,
        "applied": applied,
    }
