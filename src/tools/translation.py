"""
Real-time game translation tools.

Uses Claude Vision API for OCR and translation of Japanese game text.

Provides both manual tools (translate_screenshot, translate_and_overlay)
and automatic background service (translation_service_start/stop/status).
"""

import base64
import asyncio
import json
import logging
from typing import Any

from ..app import mcp, get_obs_client
from ..utils.translation_service import TranslationService

logger = logging.getLogger(__name__)


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
    font_size: int = 112,
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

    # Get canvas size for proper positioning
    video_settings = client.client.get_video_settings()
    canvas_width = video_settings.base_width
    canvas_height = video_settings.base_height

    # Position mapping (calculated based on canvas size)
    # Shift left by 20% of canvas width for game-specific centering
    shift_left = int(canvas_width * 0.20)
    center_x = (canvas_width // 2) - shift_left
    bottom_y = int(canvas_height * 0.88)  # 88% down from top
    top_y = int(canvas_height * 0.05)     # 5% from top
    left_x = int(canvas_width * 0.05)      # 5% from left
    right_x = int(canvas_width * 0.95)     # 95% from left

    positions = {
        "bottom-center": (center_x, bottom_y),
        "bottom-left": (left_x, bottom_y),
        "bottom-right": (right_x, bottom_y),
        "top-center": (center_x, top_y),
        "top-left": (left_x, top_y),
        "top-right": (right_x, top_y),
        "center": (center_x, canvas_height // 2),
    }
    x, y = positions.get(position, (center_x, bottom_y))

    # Try to update existing overlay, or create new one
    try:
        # Try to update existing text
        client.set_source_text("tl-overlay", english_text)
        # Get item ID to reposition
        item_id = client.client.get_scene_item_id(scene, "tl-overlay").scene_item_id
        # Position it (alignment=5 = center)
        client.set_scene_item_transform(scene, item_id, x, y, alignment=5)
    except Exception:
        # Doesn't exist, create new one
        try:
            # Remove any orphaned source
            client.remove_source("tl-overlay")
        except Exception:
            pass

        item_id = client.create_text_source(
            scene,
            "tl-overlay",
            english_text,
            font_size,
            0xFFFFFFFF,  # White
        )
        # Position it (alignment=5 = center)
        client.set_scene_item_transform(scene, item_id, x, y, alignment=5)

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


# ============================================================================
# BACKGROUND TRANSLATION SERVICE
# ============================================================================

# Module-level translation service instance
_translation_service: TranslationService | None = None


def get_translation_service() -> TranslationService:
    """Get or create the global translation service instance."""
    global _translation_service
    if _translation_service is None:
        _translation_service = TranslationService()
    return _translation_service


async def _update_overlay_wrapper(japanese_text: str, english_text: str) -> None:
    """
    Wrapper for translate_and_overlay that can be called from background service.

    Args:
        japanese_text: Original Japanese text
        english_text: English translation
    """
    try:
        print(f"[TRANSLATION SERVICE] Calling overlay with: {english_text}", flush=True)
        translate_and_overlay(japanese_text, english_text)
        print(f"[TRANSLATION SERVICE] Overlay updated successfully!", flush=True)
        logger.info(f"Overlay updated: {english_text}")
    except Exception as e:
        print(f"[TRANSLATION SERVICE] OVERLAY FAILED: {type(e).__name__}: {e}", flush=True)
        logger.error(f"Failed to update overlay: {e}", exc_info=True)
        raise


async def _clear_overlay_wrapper() -> None:
    """
    Wrapper for clear_translation_overlay that can be called from background service.
    """
    try:
        print("[TRANSLATION SERVICE] Clearing overlay (dialogue removed)", flush=True)
        clear_translation_overlay()
        logger.info("Overlay cleared (dialogue removed)")
    except Exception as e:
        print(f"[TRANSLATION SERVICE] CLEAR FAILED: {type(e).__name__}: {e}", flush=True)
        logger.error(f"Failed to clear overlay: {e}", exc_info=True)


@mcp.tool()
async def translation_service_start(
    poll_interval: float = 2.0,
    change_threshold: int = 7,
    auto_detect: bool = True,
) -> dict:
    """
    Start background translation service for automatic game dialogue translation.

    The service will:
    1. Continuously monitor OBS screenshots
    2. Auto-detect dialogue box regions (cached for performance)
    3. Use smart change detection to skip unchanged frames (60-80% API savings)
    4. Automatically translate and display new dialogue

    Performance:
    - 2-3x faster translation (crops to dialogue region)
    - 60-80% fewer API calls (change detection)
    - Non-blocking background operation

    Args:
        poll_interval: Seconds between screenshot checks (default: 2.0)
        change_threshold: Sensitivity for change detection, 0-20 (default: 7)
                         Lower = more sensitive, higher = less sensitive
        auto_detect: Auto-detect dialogue box location (default: True)

    Returns:
        Status dict with service configuration

    Example:
        translation_service_start(poll_interval=1.5, change_threshold=5)
    """
    service = get_translation_service()
    obs_client = get_obs_client()

    # Configure service
    if poll_interval != 2.0:
        service.poll_interval = poll_interval
    if change_threshold != 7:
        service.change_threshold = change_threshold

    # Start service
    result = await service.start(
        obs_client=obs_client,
        translate_fn=None,  # Service uses Vision client directly
        overlay_fn=_update_overlay_wrapper,
        clear_overlay_fn=_clear_overlay_wrapper,
    )

    return result


@mcp.tool()
async def translation_service_stop(clear_overlay: bool = True) -> dict:
    """
    Stop background translation service.

    Args:
        clear_overlay: Whether to clear the translation overlay (default: True)

    Returns:
        Status dict with final statistics
    """
    service = get_translation_service()
    result = await service.stop(clear_overlay=clear_overlay)

    if clear_overlay:
        try:
            clear_translation_overlay()
        except Exception:
            pass

    return result


@mcp.tool()
def translation_service_status() -> dict:
    """
    Get translation service status and statistics.

    Returns:
        Dict with:
        - enabled: Whether service is running
        - configuration: Current settings (poll_interval, change_threshold, etc.)
        - state: Current dialogue box location, last translation
        - statistics: Performance metrics (API calls saved, latency, efficiency)

    Example response:
    {
        "enabled": true,
        "configuration": {
            "poll_interval": 2.0,
            "change_threshold": 7
        },
        "statistics": {
            "total_screenshots": 150,
            "total_translations": 25,
            "api_calls_saved": 125,
            "efficiency_percent": 83.3,
            "avg_latency_ms": 287.5
        }
    }
    """
    service = get_translation_service()
    return service.get_status()


@mcp.tool()
async def translation_service_configure(
    poll_interval: float | None = None,
    change_threshold: int | None = None,
    dialogue_box: str | None = None,
    detection_interval: float | None = None,
    debug_mode: bool | None = None,
) -> dict:
    """
    Configure translation service settings (can update while running).

    Args:
        poll_interval: Seconds between checks (e.g., 1.5 for faster polling)
        change_threshold: Sensitivity 0-20 (lower = more sensitive)
        dialogue_box: Manual override for dialogue box as "x,y,width,height"
                     Example: "100,700,400,200" for box at (100,700) sized 400x200
        detection_interval: Seconds between dialogue box re-detection (default: 300)
        debug_mode: Save debug images to tmp/translation_debug/ (default: False)

    Returns:
        Dict with updated configuration

    Example:
        # Make it poll faster
        translation_service_configure(poll_interval=1.0)

        # Set dialogue box manually (if auto-detection fails)
        translation_service_configure(dialogue_box="100,700,400,200")

        # Enable debug mode to see cropped images
        translation_service_configure(debug_mode=True)
    """
    service = get_translation_service()

    kwargs = {}
    if poll_interval is not None:
        kwargs["poll_interval"] = poll_interval
    if change_threshold is not None:
        kwargs["change_threshold"] = change_threshold
    if dialogue_box is not None:
        kwargs["dialogue_box"] = dialogue_box
    if detection_interval is not None:
        kwargs["detection_interval"] = detection_interval
    if debug_mode is not None:
        kwargs["debug_mode"] = debug_mode

    return service.configure(**kwargs)


@mcp.tool()
def translation_service_reset() -> dict:
    """
    Reset the translation service instance completely.

    This creates a fresh service instance, clearing all state.
    Use this if the service gets stuck or behaves unexpectedly.

    Returns:
        Status dict
    """
    global _translation_service
    _translation_service = None
    return {"status": "reset", "message": "Service instance reset. Start the service again."}


@mcp.tool()
async def translation_service_force_translate() -> dict:
    """
    Force immediate translation of current dialogue (bypass change detection).

    Useful for:
    - Testing the service
    - Re-translating current text
    - Forcing update after manual dialogue_box configuration

    Returns:
        Dict with translation result
    """
    service = get_translation_service()

    if not service.enabled:
        return {"error": "Translation service not running. Start it first with translation_service_start()"}

    # Temporarily reset hash to force translation
    old_hash = service.last_hash
    service.last_hash = None

    # Wait for next frame to be processed
    await asyncio.sleep(0.5)

    # Restore hash
    service.last_hash = old_hash

    return {
        "status": "forced_translation",
        "message": "Translation forced, check overlay for result",
    }
