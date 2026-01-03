#!/usr/bin/env python3
"""
Lurk command monitor.
Watches Twitch chat for !lurk commands and triggers the lurk animation.
"""

import asyncio
import json
import os
import sys
from pathlib import Path

import aiohttp
import obsws_python as obs

# OBS connection
OBS_HOST = os.getenv("OBS_WEBSOCKET_HOST", "localhost")
OBS_PORT = int(os.getenv("OBS_WEBSOCKET_PORT", "4455"))
OBS_PASSWORD = os.getenv("OBS_WEBSOCKET_PASSWORD", "")

# Chat server
CHAT_SERVER = "http://localhost:8765"

# State
obs_client = None
lurk_hide_task = None


def get_obs_client():
    global obs_client
    if obs_client is None:
        obs_client = obs.ReqClient(host=OBS_HOST, port=OBS_PORT, password=OBS_PASSWORD)
    return obs_client


async def show_lurk_animation(username: str, duration: int = 10):
    """Show the lurk animation for a user."""
    global lurk_hide_task

    client = get_obs_client()
    scene = client.get_current_program_scene().scene_name

    # Build URL with username
    html_path = Path(__file__).parent / "assets" / "lurk-animation.html"
    url = f"file://{html_path}?user={username}"

    # Try to update existing source
    try:
        client.set_input_settings("mcp-lurk-overlay", {"url": url}, True)
        # Show the source
        try:
            item_id = client.get_scene_item_id(scene, "mcp-lurk-overlay").scene_item_id
            client.set_scene_item_enabled(scene, item_id, True)
        except Exception:
            pass
        print(f"🥷 Updated lurk animation for {username}")
    except Exception:
        # Create new source
        try:
            client.create_input(
                scene,
                "mcp-lurk-overlay",
                "browser_source",
                {"url": url, "width": 1920, "height": 1080},
                True
            )
            print(f"🥷 Created lurk animation for {username}")
        except Exception as e:
            print(f"Error creating lurk overlay: {e}")
            return

    # Cancel any existing hide task
    if lurk_hide_task and not lurk_hide_task.done():
        lurk_hide_task.cancel()

    # Schedule hiding
    async def hide_after_delay():
        await asyncio.sleep(duration)
        try:
            item_id = client.get_scene_item_id(scene, "mcp-lurk-overlay").scene_item_id
            client.set_scene_item_enabled(scene, item_id, False)
            print(f"🥷 Lurk animation hidden")
        except Exception:
            pass

    lurk_hide_task = asyncio.create_task(hide_after_delay())


async def watch_chat():
    """Watch chat server SSE for !lurk commands."""
    print("Connecting to chat server SSE...")

    while True:
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(f"{CHAT_SERVER}/events") as response:
                    print("Connected to chat SSE!")

                    async for line in response.content:
                        line = line.decode("utf-8").strip()
                        if line.startswith("data:"):
                            try:
                                data = json.loads(line[5:].strip())
                                message = data.get("message", "").lower().strip()
                                username = data.get("username", "Someone")

                                if message == "!lurk" or message.startswith("!lurk "):
                                    print(f"🥷 {username} is lurking!")
                                    await show_lurk_animation(username, 10)

                            except json.JSONDecodeError:
                                pass

        except aiohttp.ClientError as e:
            print(f"Chat connection error: {e}")
            await asyncio.sleep(5)
        except asyncio.CancelledError:
            print("Lurk monitor cancelled")
            raise
        except Exception as e:
            print(f"Error: {e}")
            await asyncio.sleep(5)


async def main():
    print("=" * 50)
    print("Lurk Command Monitor")
    print("=" * 50)
    print("Watching for !lurk commands...")

    # Test OBS connection
    try:
        client = get_obs_client()
        scene = client.get_current_program_scene().scene_name
        print(f"Connected to OBS (scene: {scene})")
    except Exception as e:
        print(f"Warning: Could not connect to OBS: {e}")

    await watch_chat()


if __name__ == "__main__":
    asyncio.run(main())
