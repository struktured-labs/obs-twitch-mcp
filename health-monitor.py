#!/usr/bin/env python3
"""
Health bar monitor for Trinea.
Monitors the green health bar and triggers panic animation when below 50%.
"""

import asyncio
import base64
import io
import os
import sys
from pathlib import Path

# Add src to path for imports
sys.path.insert(0, str(Path(__file__).parent / "src"))

from PIL import Image
import obsws_python as obs

# Config - adjust these based on game capture position
# Health bar region in the game (relative to blackmagic source)
# Full res (1920x1080): X=430-479, Y=75-113
# Scaled to 320x240 (div by 6 for X, 4.5 for Y)
HEALTH_BAR_X = 72   # 430/6
HEALTH_BAR_Y = 17   # 75/4.5
HEALTH_BAR_WIDTH = 9   # 50/6
HEALTH_BAR_HEIGHT = 9  # 39/4.5

# OBS connection
OBS_HOST = os.getenv("OBS_WEBSOCKET_HOST", "localhost")
OBS_PORT = int(os.getenv("OBS_WEBSOCKET_PORT", "4455"))
OBS_PASSWORD = os.getenv("OBS_WEBSOCKET_PASSWORD", "")

# State
panic_overlay_visible = False
death_overlay_visible = False
death_overlay_time = 0
low_health_count = 0  # Consecutive low readings before triggering
client = None
DEATH_OVERLAY_DURATION = 20  # seconds
LOW_HEALTH_THRESHOLD = 3  # Require 3 consecutive low readings to trigger


def get_obs_client():
    global client
    if client is None:
        client = obs.ReqClient(host=OBS_HOST, port=OBS_PORT, password=OBS_PASSWORD)
    return client


def get_health_percentage(screenshot_data: bytes) -> float:
    """Analyze screenshot to determine health percentage from green bar."""
    img = Image.open(io.BytesIO(screenshot_data))

    # Crop to health bar region
    # The blackmagic source is in the upper-left of the scene
    # Health bar is in upper-left of game
    health_region = img.crop((
        HEALTH_BAR_X,
        HEALTH_BAR_Y,
        HEALTH_BAR_X + HEALTH_BAR_WIDTH,
        HEALTH_BAR_Y + HEALTH_BAR_HEIGHT
    ))

    # Count green pixels
    pixels = list(health_region.getdata())
    green_count = 0
    total_pixels = len(pixels)

    for pixel in pixels:
        if len(pixel) >= 3:
            r, g, b = pixel[:3]
            # Green health bar detection
            # Looking for bright green pixels
            if g > 100 and g > r * 1.5 and g > b * 1.5:
                green_count += 1

    # Calculate percentage based on green pixels
    if total_pixels == 0:
        return 100.0

    # The health bar fills from left to right
    # We estimate health by how much of the bar is green
    health_pct = (green_count / total_pixels) * 100

    # Normalize - full health bar should be ~100%
    # Adjust multiplier if needed
    return min(100.0, health_pct * 2)


def show_panic_overlay(obs_client):
    """Show the panic overlay."""
    global panic_overlay_visible
    if panic_overlay_visible:
        return

    try:
        scene = obs_client.get_current_program_scene().scene_name

        # Create browser source for panic overlay
        obs_client.create_input(
            scene,
            "mcp-panic-overlay",
            "browser_source",
            {
                "url": f"file://{Path(__file__).parent}/assets/oh-crap-panic.html",
                "width": 1920,
                "height": 1080,
            },
            True,
        )
        panic_overlay_visible = True
        print("PANIC! Health critical - showing overlay")
    except Exception as e:
        # Source may already exist
        try:
            item_id = obs_client.get_scene_item_id(scene, "mcp-panic-overlay").scene_item_id
            obs_client.set_scene_item_enabled(scene, item_id, True)
            panic_overlay_visible = True
        except Exception:
            print(f"Error showing panic overlay: {e}")


def hide_panic_overlay(obs_client):
    """Hide the panic overlay."""
    global panic_overlay_visible
    if not panic_overlay_visible:
        return

    try:
        scene = obs_client.get_current_program_scene().scene_name
        item_id = obs_client.get_scene_item_id(scene, "mcp-panic-overlay").scene_item_id
        obs_client.set_scene_item_enabled(scene, item_id, False)
        panic_overlay_visible = False
        print("Health recovered - hiding overlay")
    except Exception as e:
        print(f"Error hiding panic overlay: {e}")


def show_death_overlay(obs_client):
    """Show the F death overlay."""
    global death_overlay_visible, death_overlay_time
    import time

    if death_overlay_visible:
        return

    # Hide panic overlay first
    hide_panic_overlay(obs_client)

    try:
        scene = obs_client.get_current_program_scene().scene_name

        obs_client.create_input(
            scene,
            "mcp-death-overlay",
            "browser_source",
            {
                "url": f"file://{Path(__file__).parent}/assets/f-to-pay-respects.html",
                "width": 1920,
                "height": 1080,
            },
            True,
        )
        death_overlay_visible = True
        death_overlay_time = time.time()
        print("☠️ DEATH! F to pay respects...")
    except Exception as e:
        try:
            item_id = obs_client.get_scene_item_id(scene, "mcp-death-overlay").scene_item_id
            obs_client.set_scene_item_enabled(scene, item_id, True)
            death_overlay_visible = True
            death_overlay_time = time.time()
        except Exception:
            print(f"Error showing death overlay: {e}")


def hide_death_overlay(obs_client):
    """Hide the death overlay."""
    global death_overlay_visible
    if not death_overlay_visible:
        return

    try:
        scene = obs_client.get_current_program_scene().scene_name
        item_id = obs_client.get_scene_item_id(scene, "mcp-death-overlay").scene_item_id
        obs_client.set_scene_item_enabled(scene, item_id, False)
        death_overlay_visible = False
        print("Death overlay hidden - back to life!")
    except Exception as e:
        print(f"Error hiding death overlay: {e}")


def check_death_overlay_timeout(obs_client):
    """Check if death overlay should be hidden after timeout."""
    global death_overlay_visible, death_overlay_time
    import time

    if death_overlay_visible and time.time() - death_overlay_time > DEATH_OVERLAY_DURATION:
        hide_death_overlay(obs_client)


async def monitor_health():
    """Main monitoring loop."""
    print("Starting Trinea health monitor...")
    print(f"Health bar region: ({HEALTH_BAR_X}, {HEALTH_BAR_Y}) - {HEALTH_BAR_WIDTH}x{HEALTH_BAR_HEIGHT}")
    print("Monitoring for health below 50%...")

    obs_client = get_obs_client()

    while True:
        try:
            # Take screenshot of blackmagic source (game capture)
            result = obs_client.get_source_screenshot(
                name="blackmagic",
                img_format="png",
                width=320,  # Lower res for faster processing
                height=240,
                quality=70,
            )

            # Decode base64 image
            data = result.image_data
            if "," in data:
                data = data.split(",")[1]
            screenshot = base64.b64decode(data)

            # Analyze health
            health_pct = get_health_percentage(screenshot)

            # Check death overlay timeout first
            check_death_overlay_timeout(obs_client)

            # Track consecutive low health readings
            global low_health_count
            if health_pct < 5:
                low_health_count += 1
            elif health_pct < 50:
                low_health_count = max(0, low_health_count - 1)  # Slowly reset
            else:
                low_health_count = 0  # Reset on good health

            # Check thresholds with hysteresis
            if low_health_count >= LOW_HEALTH_THRESHOLD:  # Death confirmed!
                show_death_overlay(obs_client)
            elif health_pct < 50 and low_health_count < LOW_HEALTH_THRESHOLD:
                if not death_overlay_visible:  # Don't show panic during death
                    show_panic_overlay(obs_client)
            else:
                hide_panic_overlay(obs_client)

            # Debug output every 5 seconds or on state change
            import time
            current_time = int(time.time())
            if current_time % 5 == 0 or panic_overlay_visible or death_overlay_visible:
                status = "☠️ DEAD" if death_overlay_visible else ("⚠️ PANIC" if panic_overlay_visible else "✓ OK")
                print(f"Health: {health_pct:.1f}% (low_count: {low_health_count}) {status}", flush=True)

        except Exception as e:
            print(f"Monitor error: {e}")

        # Check every 500ms
        await asyncio.sleep(0.5)


def main():
    print("=" * 50)
    print("Trinea Health Monitor")
    print("=" * 50)
    asyncio.run(monitor_health())


if __name__ == "__main__":
    main()
