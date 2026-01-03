#!/usr/bin/env python3
"""Auto-translate game text every N seconds."""

import asyncio
import base64
import json
import os
import sys
import time
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent / "src"))

import obsws_python as obs

# OBS connection settings
OBS_HOST = os.environ.get("OBS_HOST", "localhost")
OBS_PORT = int(os.environ.get("OBS_PORT", "4455"))
OBS_PASSWORD = os.environ.get("OBS_PASSWORD", "")

SCAN_INTERVAL = 3  # seconds
FONT_SIZE = 48
OVERLAY_SOURCE = "mcp-translation-overlay"

last_translation = ""

def get_screenshot():
    """Capture OBS screenshot and return base64 PNG."""
    client = obs.ReqClient(host=OBS_HOST, port=OBS_PORT, password=OBS_PASSWORD)
    try:
        resp = client.get_source_screenshot(
            name="",  # Empty = current scene
            img_format="png",
            width=1920,
            height=1080,
            quality=85
        )
        return resp.image_data.split(",", 1)[-1]  # Remove data:image/png;base64, prefix
    finally:
        client.disconnect()

def save_screenshot(b64_data, path="tmp/auto_screenshot.png"):
    """Save base64 screenshot to file."""
    Path(path).parent.mkdir(exist_ok=True)
    Path(path).write_bytes(base64.b64decode(b64_data))
    return path

def update_overlay(text):
    """Update the translation overlay text in OBS."""
    global last_translation
    if text == last_translation:
        return False

    client = obs.ReqClient(host=OBS_HOST, port=OBS_PORT, password=OBS_PASSWORD)
    try:
        # Try to update existing source
        try:
            client.set_input_settings(
                name=OVERLAY_SOURCE,
                settings={"text": text},
                overlay=True
            )
        except:
            # Source doesn't exist, create it
            current_scene = client.get_current_program_scene().scene_name

            # Calculate position for bottom-center
            pos_x = 960  # Center for 1920 width
            pos_y = 980  # Near bottom for 1080 height

            settings = {
                "text": text,
                "font": {"face": "Sans Serif", "size": FONT_SIZE, "style": "Bold"},
                "color1": 0xFFFFFFFF,
                "color2": 0xFFFFFFFF,
                "outline": True,
                "outline_size": 3,
                "outline_color": 0xFF000000,
            }

            client.create_input(
                scene_name=current_scene,
                input_name=OVERLAY_SOURCE,
                input_kind="text_ft2_source_v2",
                input_settings=settings,
                scene_item_enabled=True
            )

        last_translation = text
        return True
    finally:
        client.disconnect()

def main():
    print(f"Auto-translate started - scanning every {SCAN_INTERVAL} seconds", flush=True)
    print("Press Ctrl+C to stop", flush=True)
    print("-" * 50, flush=True)

    screenshot_path = "tmp/auto_screenshot.png"

    while True:
        try:
            # Capture screenshot
            b64_data = get_screenshot()
            save_screenshot(b64_data, screenshot_path)
            print(f"[{time.strftime('%H:%M:%S')}] Screenshot captured, saved to {screenshot_path}", flush=True)
            print("  -> Send to Claude for OCR/translation via MCP tool", flush=True)

            time.sleep(SCAN_INTERVAL)

        except KeyboardInterrupt:
            print("\nStopping auto-translate...", flush=True)
            break
        except Exception as e:
            print(f"Error: {e}", flush=True)
            time.sleep(SCAN_INTERVAL)

if __name__ == "__main__":
    main()
