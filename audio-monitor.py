#!/usr/bin/env python3
"""
Audio level monitor - writes mic levels to a JSON file for the PNGtuber.

Usage:
    pip install sounddevice
    python audio-monitor.py

The PNGtuber HTML polls audio-levels.json to animate based on volume.
"""

import json
import time
from pathlib import Path

try:
    import sounddevice as sd
    import numpy as np
except ImportError:
    print("Installing required packages...")
    import subprocess
    subprocess.run(["pip", "install", "sounddevice", "numpy"])
    import sounddevice as sd
    import numpy as np

OUTPUT_FILE = Path(__file__).parent / "assets" / "audio-levels.json"
SAMPLE_RATE = 44100
BLOCK_SIZE = 1024


def get_volume(indata, frames, time_info, status):
    """Callback to process audio and calculate volume."""
    volume = float(np.linalg.norm(indata) * 10)
    volume = min(100.0, volume)  # Cap at 100

    # Write to file
    with open(OUTPUT_FILE, 'w') as f:
        json.dump({"volume": round(volume, 2), "timestamp": time.time()}, f)


def main():
    print(f"Audio Monitor for PNGtuber")
    print(f"Writing levels to: {OUTPUT_FILE}")
    print(f"Press Ctrl+C to stop\n")

    # List available devices
    print("Available audio devices:")
    print(sd.query_devices())
    print()

    # Use pulse for better compatibility
    device_id = 7  # pulse
    device_info = sd.query_devices(device_id)
    print(f"Using: {device_info['name']}")
    print()

    try:
        with sd.InputStream(callback=get_volume,
                          device=device_id,
                          channels=1,
                          samplerate=SAMPLE_RATE,
                          blocksize=BLOCK_SIZE):
            print("Monitoring audio... Speak to test!")
            while True:
                time.sleep(0.1)
    except KeyboardInterrupt:
        print("\nStopped.")


if __name__ == "__main__":
    main()
