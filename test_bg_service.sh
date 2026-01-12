#!/bin/bash
# Test what the background service does
source ../../setenv.sh
uv run python3 << 'EOF'
import asyncio
import os
from pathlib import Path
from src.utils.obs_client import OBSClient
from src.utils.vision_client import get_vision_client
from src.utils.image_utils import crop_image, bytes_to_image, image_to_bytes
from src.tools.translation import translate_and_overlay

async def test():
    # Get OBS client
    obs = OBSClient(
        host=os.getenv('OBS_WEBSOCKET_HOST', 'localhost'),
        port=int(os.getenv('OBS_WEBSOCKET_PORT', '4455')),
        password=os.getenv('OBS_WEBSOCKET_PASSWORD', '')
    )

    # Capture and crop (mimicking service)
    print("1. Capturing screenshot...")
    screenshot = obs.get_screenshot()
    print(f"   Screenshot: {len(screenshot)} bytes")

    print("2. Cropping to dialogue region...")
    image = bytes_to_image(screenshot)
    cropped = crop_image(image, (0, 700, 1920, 380))
    cropped_bytes = image_to_bytes(cropped)
    print(f"   Cropped: {len(cropped_bytes)} bytes")

    print("3. Translating with Vision API...")
    vision = get_vision_client()
    translation = await vision.translate_image(cropped_bytes)
    print(f"   Japanese: {translation.get('japanese_text', 'N/A')}")
    print(f"   English: {translation.get('english_text', 'N/A')}")

    print("4. Updating overlay...")
    result = translate_and_overlay(
        translation.get('japanese_text', ''),
        translation['english_text']
    )
    print(f"   Result: {result}")

    print("\n✓ All steps completed successfully!")

asyncio.run(test())
EOF
