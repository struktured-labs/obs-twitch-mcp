#!/usr/bin/env python3
"""Monitor chat for obs-twitch-mcp mentions and auto-respond with repo link."""

import json
import os
import time
import re
from pathlib import Path

# Add src to path for imports
import sys
sys.path.insert(0, str(Path(__file__).parent / "src"))

from utils.twitch_client import TwitchClient

TRIGGER_PATTERNS = [
    r'obs-twitch-mcp',
    r'obs twitch mcp',
    r'what.*(repo|github|code|project)',
    r'where.*(repo|github|code|source)',
    r'link.*(repo|github|project)',
]

RESPONSE = "This stream uses obs-twitch-mcp - AI-controlled streaming with Claude Code! Repo: github.com/struktured-labs/obs-twitch-mcp"

# Auto-ban patterns for spam bots
BAN_PATTERNS = [
    r'streamboo',
    r'best\s*(viewers|follows|primes)',
    r'buy\s*(viewers|follows|primes)',
    r'cheap\s*(viewers|follows|primes)',
    r'viewerbot',
    r'wanna become famous',
]

CHAT_LOG_DIR = Path(__file__).parent / "chat_logs"
RESPONDED_FILE = Path(__file__).parent / "tmp" / "responded_messages.json"

def load_responded():
    if RESPONDED_FILE.exists():
        return set(json.loads(RESPONDED_FILE.read_text()))
    return set()

def save_responded(responded):
    RESPONDED_FILE.parent.mkdir(exist_ok=True)
    RESPONDED_FILE.write_text(json.dumps(list(responded)))

def get_latest_messages(limit=20):
    if not CHAT_LOG_DIR.exists():
        return []
    log_files = sorted(CHAT_LOG_DIR.glob("*.jsonl"), reverse=True)
    if not log_files:
        return []
    messages = []
    for log_file in log_files[:1]:
        lines = log_file.read_text().strip().split('\n')
        for line in lines[-limit:]:
            try:
                messages.append(json.loads(line))
            except:
                pass
    return messages

def should_respond(message_text, username):
    if username.lower() == "struktured":
        if "github.com/struktured-labs/obs-twitch-mcp" in message_text:
            return False
    text_lower = message_text.lower()
    for pattern in TRIGGER_PATTERNS:
        if re.search(pattern, text_lower):
            return True
    return False

def should_ban(message_text, username):
    """Check if message matches spam bot patterns."""
    # Don't ban mods/broadcaster
    if username.lower() in ["struktured", "nightbot", "streamelements"]:
        return False
    text_lower = message_text.lower()
    for pattern in BAN_PATTERNS:
        if re.search(pattern, text_lower):
            return True
    return False

def main():
    print("Chat Monitor Started - watching for obs-twitch-mcp mentions...", flush=True)
    print(f"Triggers: {TRIGGER_PATTERNS}", flush=True)

    token_file = Path(__file__).parent / ".twitch_token.json"
    if token_file.exists():
        token_data = json.loads(token_file.read_text())
        token = token_data.get("access_token")
    else:
        token = os.environ.get("TWITCH_OAUTH_TOKEN")

    client_id = os.environ.get("TWITCH_CLIENT_ID")
    client_secret = os.environ.get("TWITCH_CLIENT_SECRET")

    if not token or not client_id:
        print("No token or client_id found!", flush=True)
        return

    channel = os.environ.get("TWITCH_CHANNEL", "struktured")
    print(f"Token loaded, client_id: {client_id[:10]}..., channel: {channel}", flush=True)

    client = TwitchClient(
        channel=channel,
        oauth_token=token,
        client_id=client_id,
        client_secret=client_secret or ""
    )
    print("TwitchClient created, starting monitor loop...", flush=True)
    responded = load_responded()

    while True:
        try:
            messages = get_latest_messages(20)
            for msg in messages:
                msg_id = msg.get("message_id", "")
                if msg_id in responded:
                    continue
                username = msg.get("username", "")
                text = msg.get("message", "")

                # Check for spam bots first
                if should_ban(text, username):
                    print(f"SPAM DETECTED from {username}: {text}", flush=True)
                    try:
                        client.ban_user(username, "Spam bot detected")
                        print(f"BANNED: {username}", flush=True)
                    except Exception as e:
                        print(f"Failed to ban {username}: {e}", flush=True)
                    responded.add(msg_id)
                    save_responded(responded)
                    continue

                # Check for repo questions
                if should_respond(text, username):
                    print(f"Trigger detected from {username}: {text}", flush=True)
                    reply = f"@{username} {RESPONSE}"
                    client.send_chat_message(reply)
                    print(f"Responded: {reply}", flush=True)
                    responded.add(msg_id)
                    save_responded(responded)
            time.sleep(3)
        except KeyboardInterrupt:
            print("\nStopping chat monitor...", flush=True)
            break
        except Exception as e:
            print(f"Error: {e}", flush=True)
            time.sleep(5)

if __name__ == "__main__":
    main()
