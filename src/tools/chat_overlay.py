"""
Chat overlay MCP tools.

Provides tools for displaying live Twitch chat on stream via browser source.
"""

from pathlib import Path
from urllib.parse import urlencode

from ..app import mcp, get_obs_client
from ..utils.chat_filter import get_chat_filter
from ..utils.sse_server import get_sse_server
from ..utils.logger import get_logger

logger = get_logger("chat_overlay")

# Source name for the chat overlay
CHAT_OVERLAY_SOURCE = "mcp-chat-overlay"

# Available themes
THEMES = {
    "retro": "retro.html",
    "jrpg": "jrpg.html",
    "minimal": "minimal.html",
}


def _get_theme_path(theme: str) -> Path:
    """Get the path to a theme HTML file."""
    assets_dir = Path(__file__).parent.parent.parent / "assets" / "chat-overlay"
    filename = THEMES.get(theme, THEMES["retro"])
    return assets_dir / filename


def _build_overlay_url(
    theme: str = "retro",
    fade_seconds: int = 60,
    show_avatars: bool = True,
    font_size: str = "medium",
    direction: str = "up",
    background: str = "default",
    max_messages: int = 15,
    scanlines: bool = True,
    sse_port: int = 8765,
) -> str:
    """Build the overlay URL with all configuration parameters."""
    theme_path = _get_theme_path(theme)

    params = {
        "fade": fade_seconds,
        "avatars": "true" if show_avatars else "false",
        "size": font_size,
        "dir": direction,
        "bg": background,
        "maxmsgs": max_messages,
        "scanlines": "true" if scanlines else "false",
        "sse": f"http://localhost:{sse_port}/events",
    }

    return f"file://{theme_path}?{urlencode(params)}"


@mcp.tool()
def show_chat_overlay(
    theme: str = "retro",
    position: str = "bottom-left",
    width: int = 600,
    height: int = 800,
    fade_seconds: int = 60,
    show_avatars: bool = True,
    font_size: str = "medium",
    direction: str = "up",
    background: str = "default",
    max_messages: int = 15,
    scanlines: bool = True,
) -> dict:
    """
    Show a live chat overlay on the current OBS scene.

    Args:
        theme: Visual theme - "retro" (neon/CRT), "jrpg" (pixel art), "minimal" (clean)
        position: Where to place - "bottom-left", "bottom-right", "left", "right"
        width: Overlay width in pixels
        height: Overlay height in pixels
        fade_seconds: Seconds before messages fade out (0 = never fade)
        show_avatars: Whether to show user profile pictures
        font_size: Text size - "small", "medium", "large"
        direction: Message flow - "up" (new at bottom) or "down" (new at top)
        background: Message background - "default", "dark", "transparent", "subtle"
        max_messages: Maximum visible messages
        scanlines: Whether to show retro CRT scanline effect

    Returns:
        Dict with status and overlay info.
    """
    client = get_obs_client()
    scene = client.get_current_scene()

    # Build the overlay URL
    url = _build_overlay_url(
        theme=theme,
        fade_seconds=fade_seconds,
        show_avatars=show_avatars,
        font_size=font_size,
        direction=direction,
        background=background,
        max_messages=max_messages,
        scanlines=scanlines,
    )

    logger.info(f"Creating chat overlay with theme '{theme}' at {position}")
    logger.debug(f"Overlay URL: {url}")

    # Calculate position
    positions = {
        "bottom-left": (20, None, None, 20),   # left, top, right, bottom
        "bottom-right": (None, None, 20, 20),
        "left": (20, 100, None, 100),
        "right": (None, 100, 20, 100),
        "top-left": (20, 20, None, None),
        "top-right": (None, 20, 20, None),
    }
    pos = positions.get(position, positions["bottom-left"])

    try:
        # Try to update existing source
        client.set_input_settings(CHAT_OVERLAY_SOURCE, {
            "url": url,
            "width": width,
            "height": height,
        })
        # Make sure it's visible
        try:
            item_id = client.client.get_scene_item_id(scene, CHAT_OVERLAY_SOURCE).scene_item_id
            client.set_scene_item_enabled(scene, item_id, True)
        except Exception:
            pass
        logger.info("Updated existing chat overlay")
    except Exception:
        # Create new browser source
        client.create_browser_source(scene, CHAT_OVERLAY_SOURCE, url, width, height)
        logger.info("Created new chat overlay source")

    # Update SSE server config if available
    sse = get_sse_server()
    if sse:
        sse.update_config(
            theme=theme,
            fade_seconds=fade_seconds,
            max_messages=max_messages,
            show_avatars=show_avatars,
            font_size=font_size,
            direction=direction,
        )

    return {
        "status": "success",
        "source_name": CHAT_OVERLAY_SOURCE,
        "theme": theme,
        "position": position,
        "size": f"{width}x{height}",
        "config": {
            "fade_seconds": fade_seconds,
            "show_avatars": show_avatars,
            "font_size": font_size,
            "direction": direction,
            "max_messages": max_messages,
        },
    }


@mcp.tool()
def hide_chat_overlay() -> dict:
    """
    Hide the chat overlay from the current scene.

    Returns:
        Dict with status.
    """
    client = get_obs_client()
    scene = client.get_current_scene()

    try:
        item_id = client.client.get_scene_item_id(scene, CHAT_OVERLAY_SOURCE).scene_item_id
        client.set_scene_item_enabled(scene, item_id, False)
        logger.info("Chat overlay hidden")
        return {"status": "hidden", "source_name": CHAT_OVERLAY_SOURCE}
    except Exception as e:
        logger.warning(f"Could not hide chat overlay: {e}")
        return {"status": "not_found", "message": "Chat overlay not found in current scene"}


@mcp.tool()
def remove_chat_overlay() -> dict:
    """
    Completely remove the chat overlay source from OBS.

    Returns:
        Dict with status.
    """
    client = get_obs_client()

    try:
        client.remove_source(CHAT_OVERLAY_SOURCE)
        logger.info("Chat overlay removed")
        return {"status": "removed", "source_name": CHAT_OVERLAY_SOURCE}
    except Exception as e:
        logger.warning(f"Could not remove chat overlay: {e}")
        return {"status": "not_found", "message": str(e)}


@mcp.tool()
def configure_chat_filter(
    block_spam: bool = True,
    block_bots: bool = True,
    block_links: bool = False,
    block_caps: bool = True,
    rate_limit_messages: int = 5,
    rate_limit_window: float = 10.0,
    add_blocked_word: str = "",
    add_blocked_bot: str = "",
) -> dict:
    """
    Configure chat message filtering for the overlay.

    Args:
        block_spam: Enable spam detection (rate limits, duplicates)
        block_bots: Hide messages from known bots
        block_links: Hide messages containing URLs
        block_caps: Hide messages with excessive caps
        rate_limit_messages: Max messages per user in window
        rate_limit_window: Rate limit window in seconds
        add_blocked_word: Add a word to the blocklist
        add_blocked_bot: Add a bot username to the blocklist

    Returns:
        Dict with current filter configuration.
    """
    chat_filter = get_chat_filter()

    # Update settings
    chat_filter.update_config(
        block_spam=block_spam,
        block_bots=block_bots,
        block_links=block_links,
        block_caps=block_caps,
        rate_limit_messages=rate_limit_messages,
        rate_limit_window=rate_limit_window,
    )

    # Add to blocklists if specified
    if add_blocked_word:
        chat_filter.add_blocked_word(add_blocked_word)

    if add_blocked_bot:
        chat_filter.add_blocked_bot(add_blocked_bot)

    logger.info("Chat filter configuration updated")
    return {
        "status": "success",
        "config": chat_filter.get_config(),
    }


@mcp.tool()
def get_chat_overlay_status() -> dict:
    """
    Get the current status of the chat overlay system.

    Returns:
        Dict with overlay status, SSE server status, and filter config.
    """
    client = get_obs_client()
    scene = client.get_current_scene()
    sse = get_sse_server()
    chat_filter = get_chat_filter()

    # Check if overlay exists and is visible
    overlay_status = "not_found"
    try:
        item_id = client.client.get_scene_item_id(scene, CHAT_OVERLAY_SOURCE).scene_item_id
        item_info = client.client.get_scene_item_enabled(scene, item_id)
        overlay_status = "visible" if item_info.scene_item_enabled else "hidden"
    except Exception:
        pass

    # SSE server status
    sse_status = {
        "running": sse is not None and sse._running if sse else False,
        "clients": sse.client_count if sse else 0,
        "config": sse.get_config() if sse else {},
    }

    return {
        "overlay": {
            "status": overlay_status,
            "source_name": CHAT_OVERLAY_SOURCE,
            "scene": scene,
        },
        "sse_server": sse_status,
        "filter": chat_filter.get_config(),
    }


@mcp.tool()
def list_chat_themes() -> list[dict]:
    """
    List available chat overlay themes.

    Returns:
        List of theme info dicts.
    """
    themes = []
    assets_dir = Path(__file__).parent.parent.parent / "assets" / "chat-overlay"

    theme_info = {
        "retro": {
            "name": "Retro",
            "description": "Neon colors with CRT scanline effect. Great for general streaming.",
            "style": "Cyberpunk / 80s arcade",
        },
        "jrpg": {
            "name": "JRPG",
            "description": "Pixel art text boxes inspired by classic Japanese RPGs.",
            "style": "Retro gaming / 16-bit era",
        },
        "minimal": {
            "name": "Minimal",
            "description": "Clean, transparent design that stays out of the way.",
            "style": "Modern / Professional",
        },
    }

    for theme_id, filename in THEMES.items():
        info = theme_info.get(theme_id, {})
        path = assets_dir / filename
        themes.append({
            "id": theme_id,
            "name": info.get("name", theme_id.title()),
            "description": info.get("description", ""),
            "style": info.get("style", ""),
            "available": path.exists(),
        })

    return themes
