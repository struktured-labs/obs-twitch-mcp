"""
Real-time game translation tools.

Uses Claude Vision API for OCR and translation of Japanese game text.
"""

import base64
import asyncio
from typing import Any

from ..app import mcp, get_obs_client


# Cache for last translation to avoid duplicates
_last_japanese_text: str = ""
_auto_translate_task: asyncio.Task | None = None


@mcp.tool()
def translate_screenshot() -> dict:
    """
    Capture OBS screenshot and return it for translation.

    The screenshot is returned as base64 PNG for Claude to analyze.
    Claude should OCR any Japanese text and provide English translation.

    Returns:
        dict with 'image_base64' key containing the screenshot
    """
    client = get_obs_client()
    image_bytes = client.get_screenshot()
    return {
        "image_base64": base64.b64encode(image_bytes).decode("utf-8"),
        "instruction": "Please OCR any Japanese text visible in this game screenshot and provide an English translation. Return format: {japanese: '...', english: '...'}"
    }


@mcp.tool()
def translate_and_overlay(
    japanese_text: str,
    english_text: str,
    position: str = "bottom-center",
    font_size: int = 60,
    duration_seconds: int = 0,
) -> str:
    """
    Display a translation overlay on the OBS scene.

    This should be called after translating text from a screenshot.

    Args:
        japanese_text: The original Japanese text (for logging)
        english_text: The English translation to display
        position: Where to show overlay (bottom-center, top-left, etc.)
        font_size: Size of the overlay text
        duration_seconds: How long to show (0 = until manually removed)
    """
    global _last_japanese_text

    client = get_obs_client()
    scene = client.get_current_scene()

    # Skip if same text
    if japanese_text == _last_japanese_text:
        return "Same text as before, skipping overlay update"

    _last_japanese_text = japanese_text

    # Position mapping
    positions = {
        "bottom-center": (960, 950),
        "bottom-left": (100, 950),
        "bottom-right": (1820, 950),
        "top-center": (960, 50),
        "top-left": (100, 50),
        "top-right": (1820, 50),
        "center": (960, 540),
    }
    x, y = positions.get(position, (960, 950))

    # Remove old overlay
    try:
        client.remove_source("tl-overlay")
    except Exception:
        pass

    # Create new overlay
    item_id = client.create_text_source(
        scene,
        "tl-overlay",
        english_text,
        font_size,
        0xFFFFFFFF,  # White
    )

    # Position it
    client.set_scene_item_transform(scene, item_id, x, y, alignment=4)

    # Schedule removal if duration specified
    if duration_seconds > 0:
        async def remove_after_delay():
            await asyncio.sleep(duration_seconds)
            try:
                client.remove_source("tl-overlay")
            except Exception:
                pass

        asyncio.create_task(remove_after_delay())

    return f"Showing translation: {english_text}"


@mcp.tool()
def clear_translation_overlay(
    duration_seconds: float = 0,
    style: str = "instant",
) -> str:
    """
    Remove the translation overlay from the scene.

    Args:
        duration_seconds: How long the exit animation takes (0 = instant)
        style: Animation style - "instant", "slide-left", "slide-right",
               "slide-up", "slide-down", "fade"
    """
    global _last_japanese_text

    client = get_obs_client()
    scene = client.get_current_scene()

    # Get the item ID for animation
    try:
        item_id = client.client.get_scene_item_id(scene, "tl-overlay").scene_item_id
    except Exception:
        _last_japanese_text = ""
        return "No translation overlay to remove"

    # If instant or no duration, just remove
    if style == "instant" or duration_seconds <= 0:
        try:
            client.remove_source("tl-overlay")
            _last_japanese_text = ""
            return "Translation overlay removed"
        except Exception:
            return "No translation overlay to remove"

    # Animate the removal
    async def animate_removal():
        global _last_japanese_text
        try:
            # Get current transform
            transform = client.get_scene_item_transform(scene, item_id)
            start_x = transform.get("positionX", 960)
            start_y = transform.get("positionY", 950)

            # Calculate end position based on style
            if style == "slide-left":
                end_x, end_y = -500, start_y
            elif style == "slide-right":
                end_x, end_y = 2420, start_y
            elif style == "slide-up":
                end_x, end_y = start_x, -200
            elif style == "slide-down":
                end_x, end_y = start_x, 1280
            elif style == "fade":
                # For fade, we'll just do a quick slide-down as fallback
                # (true opacity fade would require OBS filters)
                end_x, end_y = start_x, 1280
            else:
                end_x, end_y = start_x, start_y

            # Animate over duration
            steps = int(duration_seconds * 30)  # 30 fps animation
            if steps < 1:
                steps = 1

            for i in range(steps):
                t = (i + 1) / steps  # Progress from 0 to 1
                # Ease-out curve for smooth deceleration
                t = 1 - (1 - t) ** 2

                current_x = start_x + (end_x - start_x) * t
                current_y = start_y + (end_y - start_y) * t

                try:
                    client.set_scene_item_transform(scene, item_id, current_x, current_y, alignment=4)
                except Exception:
                    break

                await asyncio.sleep(duration_seconds / steps)

            # Remove the source after animation
            client.remove_source("tl-overlay")
            _last_japanese_text = ""
        except Exception:
            # Fallback: just remove it
            try:
                client.remove_source("tl-overlay")
            except Exception:
                pass
            _last_japanese_text = ""

    asyncio.create_task(animate_removal())
    return f"Translation overlay animating out ({style}, {duration_seconds}s)"


@mcp.tool()
def get_last_translation() -> dict:
    """Get the last translated text."""
    global _last_japanese_text
    return {
        "last_japanese": _last_japanese_text,
    }
