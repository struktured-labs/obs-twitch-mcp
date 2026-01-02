#!/usr/bin/env python3
"""Auto-switch OBS scene after countdown timer ends."""

import time
import obsws_python as obs

DELAY_SECONDS = 10 * 60  # 10 minutes
TARGET_SCENE = "vibe-coding-main"

def main():
    print(f"Waiting {DELAY_SECONDS} seconds ({DELAY_SECONDS // 60} minutes) before switching to '{TARGET_SCENE}'...")

    # Countdown display
    remaining = DELAY_SECONDS
    while remaining > 0:
        mins, secs = divmod(remaining, 60)
        print(f"\r  {mins:02d}:{secs:02d} remaining...", end="", flush=True)
        time.sleep(1)
        remaining -= 1

    print(f"\n\nTimer complete! Switching to '{TARGET_SCENE}'...")

    try:
        cl = obs.ReqClient(host='localhost', port=4455, password='')
        cl.set_current_program_scene(TARGET_SCENE)
        print(f"Successfully switched to '{TARGET_SCENE}'!")
    except Exception as e:
        print(f"Error switching scene: {e}")

if __name__ == "__main__":
    main()
