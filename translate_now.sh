#!/bin/bash
# Quick manual translation script
source ../../setenv.sh
uv run python3 << 'EOF'
import asyncio
import os
from src.utils.obs_client import OBSClient
from src.utils.vision_client import get_vision_client
from src.utils.image_utils import crop_image, bytes_to_image, image_to_bytes
from src.tools.translation import translate_and_overlay

async def main():
    obs = OBSClient(
        host=os.getenv('OBS_WEBSOCKET_HOST', 'localhost'),
        port=int(os.getenv('OBS_WEBSOCKET_PORT', '4455')),
        password=os.getenv('OBS_WEBSOCKET_PASSWORD', '')
    )

    screenshot = obs.get_screenshot()
    image = bytes_to_image(screenshot)
    cropped = crop_image(image, (0, 700, 1920, 380))
    cropped_bytes = image_to_bytes(cropped)

    vision = get_vision_client()
    result = await vision.translate_image(cropped_bytes)

    print(f"Japanese: {result['japanese_text']}")
    print(f"English: {result['english_text']}")

    translate_and_overlay(
        result.get('japanese_text', ''),
        result['english_text']
    )

asyncio.run(main())
EOF
