#!/usr/bin/env python3
"""
Real-time chat server that connects directly to Twitch IRC.
Serves messages via Server-Sent Events for the overlay.
"""

import asyncio
import json
import os
import re
import ssl
import sys
import traceback
from aiohttp import web
from collections import deque
from dataclasses import dataclass, asdict
from datetime import datetime
from pathlib import Path

# Config
CHANNEL = os.getenv("TWITCH_CHANNEL", "struktured")
TOKEN_FILE = Path(__file__).parent / ".twitch_token.json"
PORT = 8765


def get_oauth_token() -> str:
    """Get OAuth token from file (preferred) or environment."""
    if TOKEN_FILE.exists():
        try:
            with open(TOKEN_FILE) as f:
                data = json.load(f)
                token = data.get("access_token", "")
                if token:
                    print(f"Using token from file: {token[:10]}...")
                    return token
        except Exception as e:
            print(f"Error reading token file: {e}")
    env_token = os.getenv("TWITCH_OAUTH_TOKEN", "")
    if env_token:
        print(f"Using token from env: {env_token[:10]}...")
    return env_token


# Message queue for connected clients
message_queue: deque = deque(maxlen=50)
connected_clients: list[asyncio.Queue] = []


@dataclass
class ChatMessage:
    id: str
    username: str
    message: str
    is_mod: bool = False
    is_subscriber: bool = False
    is_broadcaster: bool = False
    timestamp: str = ""


def parse_irc_message(raw: str) -> ChatMessage | None:
    """Parse Twitch IRC message."""
    privmsg_match = re.match(
        r"(?:@(\S+)\s+)?:(\w+)!\w+@\w+\.tmi\.twitch\.tv\s+PRIVMSG\s+#(\w+)\s+:(.+)",
        raw.strip()
    )
    if not privmsg_match:
        return None

    tags_str, username, channel, message = privmsg_match.groups()

    is_mod = False
    is_sub = False
    msg_id = datetime.now().isoformat()

    if tags_str:
        tags = dict(t.split("=", 1) for t in tags_str.split(";") if "=" in t)
        is_mod = tags.get("mod") == "1" or "broadcaster" in tags.get("badges", "")
        is_sub = tags.get("subscriber") == "1"
        msg_id = tags.get("id", msg_id)

    return ChatMessage(
        id=msg_id,
        username=username,
        message=message,
        is_mod=is_mod,
        is_subscriber=is_sub,
        is_broadcaster=username.lower() == CHANNEL.lower(),
        timestamp=datetime.now().isoformat(),
    )


async def irc_listener():
    """Connect to Twitch IRC and broadcast messages."""
    token = get_oauth_token()
    if not token:
        print("ERROR: No OAuth token available!")
        return

    if not token.startswith("oauth:"):
        token = f"oauth:{token}"

    reconnect_delay = 1

    while True:
        writer = None
        try:
            print(f"Connecting to Twitch IRC...")
            ssl_ctx = ssl.create_default_context()
            reader, writer = await asyncio.open_connection(
                "irc.chat.twitch.tv", 6697, ssl=ssl_ctx
            )

            # Authenticate
            writer.write(f"PASS {token}\r\n".encode())
            writer.write(f"NICK {CHANNEL}\r\n".encode())
            writer.write(b"CAP REQ :twitch.tv/tags twitch.tv/commands\r\n")
            writer.write(f"JOIN #{CHANNEL}\r\n".encode())
            await writer.drain()

            print(f"Sent auth commands, waiting for response...")

            buffer = ""
            authenticated = False

            while True:
                try:
                    data = await asyncio.wait_for(reader.read(4096), timeout=330)
                    if not data:
                        print("Connection closed by server (no data)")
                        break

                    buffer += data.decode("utf-8", errors="ignore")

                    while "\r\n" in buffer:
                        line, buffer = buffer.split("\r\n", 1)

                        # Debug: print all IRC messages
                        if not authenticated:
                            print(f"IRC: {line[:100]}")

                        # Check for auth success
                        if "Welcome, GLHF!" in line:
                            authenticated = True
                            reconnect_delay = 1
                            print(f"✓ Connected to #{CHANNEL}!")

                        # Respond to PING
                        if line.startswith("PING"):
                            writer.write(b"PONG :tmi.twitch.tv\r\n")
                            await writer.drain()
                            continue

                        # Check for auth failure
                        if "Login authentication failed" in line:
                            print("ERROR: Authentication failed! Token may be expired.")
                            print("Run: uv run python auth.py")
                            await asyncio.sleep(60)  # Wait before retry
                            break

                        # Parse chat messages
                        msg = parse_irc_message(line)
                        if msg:
                            msg_dict = asdict(msg)
                            message_queue.append(msg_dict)
                            print(f"💬 {msg.username}: {msg.message[:50]}")

                            # Broadcast to SSE clients
                            for client_queue in connected_clients:
                                try:
                                    client_queue.put_nowait(msg_dict)
                                except asyncio.QueueFull:
                                    pass

                except asyncio.TimeoutError:
                    # Send ping to keep connection alive
                    print("Sending keepalive ping...")
                    writer.write(b"PING :keepalive\r\n")
                    await writer.drain()

        except asyncio.CancelledError:
            print("IRC listener cancelled")
            raise
        except Exception as e:
            print(f"IRC error: {e}")
            traceback.print_exc()

        finally:
            if writer:
                try:
                    writer.close()
                    await writer.wait_closed()
                except Exception:
                    pass

        # Reconnect with exponential backoff
        print(f"Reconnecting in {reconnect_delay}s...")
        await asyncio.sleep(reconnect_delay)
        reconnect_delay = min(reconnect_delay * 2, 30)


async def handle_sse(request):
    """Server-Sent Events endpoint for real-time messages."""
    response = web.StreamResponse()
    response.headers["Content-Type"] = "text/event-stream"
    response.headers["Cache-Control"] = "no-cache"
    response.headers["Connection"] = "keep-alive"
    response.headers["Access-Control-Allow-Origin"] = "*"
    await response.prepare(request)

    client_queue = asyncio.Queue(maxsize=100)
    connected_clients.append(client_queue)
    print(f"SSE client connected (total: {len(connected_clients)})")

    # Send recent messages first
    for msg in list(message_queue)[-20:]:
        await response.write(f"data: {json.dumps(msg)}\n\n".encode())

    try:
        while True:
            msg = await client_queue.get()
            await response.write(f"data: {json.dumps(msg)}\n\n".encode())
    except (asyncio.CancelledError, ConnectionResetError):
        pass
    finally:
        connected_clients.remove(client_queue)
        print(f"SSE client disconnected (total: {len(connected_clients)})")

    return response


async def handle_chat(request):
    """REST endpoint for polling."""
    messages = list(message_queue)[-20:]
    return web.json_response(
        {"messages": messages},
        headers={"Access-Control-Allow-Origin": "*"}
    )


async def handle_health(request):
    """Health check."""
    return web.json_response(
        {"status": "ok", "clients": len(connected_clients), "messages": len(message_queue)},
        headers={"Access-Control-Allow-Origin": "*"}
    )


async def handle_overlay(request):
    """Serve the chat overlay HTML."""
    html_path = Path(__file__).parent / "assets" / "retro-chat.html"
    if html_path.exists():
        return web.FileResponse(html_path)
    return web.Response(text="Overlay not found", status=404)


async def handle_countdown(request):
    """Serve the countdown timer HTML."""
    html_path = Path(__file__).parent / "assets" / "countdown-timer.html"
    if html_path.exists():
        return web.FileResponse(html_path)
    return web.Response(text="Countdown not found", status=404)


async def handle_claude_badge(request):
    """Serve the Claude AI badge HTML."""
    html_path = Path(__file__).parent / "assets" / "claude-badge.html"
    if html_path.exists():
        return web.FileResponse(html_path)
    return web.Response(text="Badge not found", status=404)


async def handle_nahnegnal_qte(request):
    """Serve the nahnegnal QTE animation HTML."""
    html_path = Path(__file__).parent / "assets" / "nahnegnal-qte.html"
    if html_path.exists():
        return web.FileResponse(html_path)
    return web.Response(text="Animation not found", status=404)


async def start_background_tasks(app):
    print(f"Starting IRC listener for #{CHANNEL}...")
    app["irc_task"] = asyncio.create_task(irc_listener())


async def cleanup_background_tasks(app):
    app["irc_task"].cancel()
    try:
        await app["irc_task"]
    except asyncio.CancelledError:
        pass


def main():
    print("=" * 50)
    print("Chat Overlay Server")
    print("=" * 50)

    app = web.Application()
    app.router.add_get("/", handle_overlay)
    app.router.add_get("/overlay", handle_overlay)
    app.router.add_get("/events", handle_sse)
    app.router.add_get("/chat", handle_chat)
    app.router.add_get("/health", handle_health)
    app.router.add_get("/countdown", handle_countdown)
    app.router.add_get("/claude-badge", handle_claude_badge)
    app.router.add_get("/nahnegnal-qte", handle_nahnegnal_qte)
    app.on_startup.append(start_background_tasks)
    app.on_cleanup.append(cleanup_background_tasks)

    print(f"Channel: #{CHANNEL}")
    print(f"Port: {PORT}")
    print(f"Overlay: http://localhost:{PORT}/overlay")
    print("=" * 50)

    web.run_app(app, host="localhost", port=PORT, print=None)


if __name__ == "__main__":
    main()
