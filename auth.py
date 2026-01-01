#!/usr/bin/env python3
"""
Twitch authentication helper.

Usage:
    source ../setenv.sh  # or wherever your setenv.sh is
    python auth.py

This will guide you through the device code flow and save the token.
"""

import os
import sys

# Add src to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "src"))

from utils.twitch_auth import authenticate, get_valid_token


def main():
    client_id = os.environ.get("TWITCH_CLIENT_ID")
    client_secret = os.environ.get("TWITCH_CLIENT_SECRET", "")

    if not client_id:
        print("Error: TWITCH_CLIENT_ID not set")
        print("\nRun this first:")
        print("  source /home/struktured/projects/obs-studio/setenv.sh")
        return 1

    print("Twitch Authentication Helper")
    print("-" * 40)

    token = get_valid_token(client_id, client_secret)

    print("\n" + "=" * 50)
    print("SUCCESS!")
    print("=" * 50)
    print(f"\nAccess Token: {token}")
    print("\nUpdate your setenv.sh with:")
    print(f"export TWITCH_OAUTH_TOKEN={token}")
    print("\nOr the token is auto-saved and will be used on next MCP restart.")

    return 0


if __name__ == "__main__":
    sys.exit(main())
