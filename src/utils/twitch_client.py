"""
Twitch API and IRC client wrapper.
"""

import asyncio
import socket
import ssl
from dataclasses import dataclass, field
from typing import Callable

from . import chat_logger


@dataclass
class ChatMessage:
    """Represents a Twitch chat message."""

    username: str
    message: str
    message_id: str = ""
    is_mod: bool = False
    is_subscriber: bool = False


@dataclass
class TwitchClient:
    """Wrapper for Twitch API and IRC chat."""

    client_id: str
    client_secret: str
    oauth_token: str
    channel: str
    _user_id: str | None = None
    _chat_messages: list[ChatMessage] = field(default_factory=list)
    _message_handlers: list[Callable[[ChatMessage], None]] = field(default_factory=list)

    @property
    def user_id(self) -> str:
        """Get the authenticated user's ID."""
        if self._user_id is None:
            # Fetch user ID from API
            import httpx

            headers = {
                "Client-ID": self.client_id,
                "Authorization": f"Bearer {self.oauth_token.replace('oauth:', '')}",
            }
            resp = httpx.get("https://api.twitch.tv/helix/users", headers=headers)
            data = resp.json()
            if data.get("data"):
                self._user_id = data["data"][0]["id"]
            else:
                raise ValueError("Could not fetch user ID from Twitch API")
        return self._user_id

    def send_chat_message(self, message: str) -> None:
        """Send a message to the channel chat via IRC."""
        token = self.oauth_token
        if not token.startswith("oauth:"):
            token = f"oauth:{token}"

        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        ctx = ssl.create_default_context()
        ssock = ctx.wrap_socket(sock, server_hostname="irc.chat.twitch.tv")
        ssock.connect(("irc.chat.twitch.tv", 6697))
        ssock.send(f"PASS {token}\r\n".encode())
        ssock.send(f"NICK {self.channel}\r\n".encode())
        ssock.send(f"JOIN #{self.channel}\r\n".encode())
        import time
        time.sleep(0.5)
        ssock.send(f"PRIVMSG #{self.channel} :{message}\r\n".encode())
        time.sleep(0.3)
        ssock.close()

    def get_recent_messages(self, count: int = 10) -> list[ChatMessage]:
        """Get recent chat messages (from cache)."""
        return self._chat_messages[-count:]

    def receive_message(self, msg: ChatMessage) -> None:
        """Receive a chat message: cache it, log it, and notify handlers."""
        # Add to in-memory cache (keep last 500)
        self._chat_messages.append(msg)
        if len(self._chat_messages) > 500:
            self._chat_messages = self._chat_messages[-500:]

        # Persist to log file
        chat_logger.log_message(msg)

        # Notify handlers
        for handler in self._message_handlers:
            try:
                handler(msg)
            except Exception:
                pass  # Don't let handler errors break the chain

    def add_message_handler(self, handler: Callable[[ChatMessage], None]) -> None:
        """Add a handler for incoming chat messages."""
        self._message_handlers.append(handler)

    def get_stream_info(self) -> dict | None:
        """Get current stream information."""
        import httpx

        headers = {
            "Client-ID": self.client_id,
            "Authorization": f"Bearer {self.oauth_token.replace('oauth:', '')}",
        }
        resp = httpx.get(
            f"https://api.twitch.tv/helix/streams?user_login={self.channel}",
            headers=headers,
        )
        data = resp.json()
        if data.get("data"):
            stream = data["data"][0]
            return {
                "title": stream.get("title"),
                "game_name": stream.get("game_name"),
                "game_id": stream.get("game_id"),
                "viewer_count": stream.get("viewer_count"),
                "started_at": stream.get("started_at"),
            }
        return None

    def set_stream_info(self, title: str | None = None, game_id: str | None = None) -> None:
        """Update stream title and/or game."""
        import httpx

        headers = {
            "Client-ID": self.client_id,
            "Authorization": f"Bearer {self.oauth_token.replace('oauth:', '')}",
            "Content-Type": "application/json",
        }
        data = {}
        if title:
            data["title"] = title
        if game_id:
            data["game_id"] = game_id

        if data:
            httpx.patch(
                f"https://api.twitch.tv/helix/channels?broadcaster_id={self.user_id}",
                headers=headers,
                json=data,
            )

    def search_game(self, query: str) -> list[dict]:
        """Search for a game by name."""
        import httpx

        headers = {
            "Client-ID": self.client_id,
            "Authorization": f"Bearer {self.oauth_token.replace('oauth:', '')}",
        }
        resp = httpx.get(
            f"https://api.twitch.tv/helix/search/categories?query={query}",
            headers=headers,
        )
        data = resp.json()
        return [
            {"id": g["id"], "name": g["name"], "box_art_url": g.get("box_art_url")}
            for g in data.get("data", [])
        ]

    def ban_user(self, username: str, reason: str = "") -> None:
        """Ban a user from chat."""
        import httpx

        # First get user ID
        headers = {
            "Client-ID": self.client_id,
            "Authorization": f"Bearer {self.oauth_token.replace('oauth:', '')}",
        }
        resp = httpx.get(
            f"https://api.twitch.tv/helix/users?login={username}",
            headers=headers,
        )
        user_data = resp.json()
        if not user_data.get("data"):
            raise ValueError(f"User {username} not found")

        target_user_id = user_data["data"][0]["id"]

        # Ban the user
        headers["Content-Type"] = "application/json"
        ban_resp = httpx.post(
            f"https://api.twitch.tv/helix/moderation/bans?broadcaster_id={self.user_id}&moderator_id={self.user_id}",
            headers=headers,
            json={"data": {"user_id": target_user_id, "reason": reason}},
        )
        if ban_resp.status_code >= 400:
            raise ValueError(f"Ban failed: {ban_resp.status_code} - {ban_resp.text}")

    def timeout_user(self, username: str, duration: int = 600, reason: str = "") -> None:
        """Timeout a user from chat."""
        import httpx

        headers = {
            "Client-ID": self.client_id,
            "Authorization": f"Bearer {self.oauth_token.replace('oauth:', '')}",
        }
        resp = httpx.get(
            f"https://api.twitch.tv/helix/users?login={username}",
            headers=headers,
        )
        user_data = resp.json()
        if not user_data.get("data"):
            raise ValueError(f"User {username} not found")

        target_user_id = user_data["data"][0]["id"]

        headers["Content-Type"] = "application/json"
        httpx.post(
            f"https://api.twitch.tv/helix/moderation/bans?broadcaster_id={self.user_id}&moderator_id={self.user_id}",
            headers=headers,
            json={"data": {"user_id": target_user_id, "duration": duration, "reason": reason}},
        )

    def unban_user(self, username: str) -> None:
        """Unban a user from chat."""
        import httpx

        headers = {
            "Client-ID": self.client_id,
            "Authorization": f"Bearer {self.oauth_token.replace('oauth:', '')}",
        }
        resp = httpx.get(
            f"https://api.twitch.tv/helix/users?login={username}",
            headers=headers,
        )
        user_data = resp.json()
        if not user_data.get("data"):
            raise ValueError(f"User {username} not found")

        target_user_id = user_data["data"][0]["id"]

        httpx.delete(
            f"https://api.twitch.tv/helix/moderation/bans?broadcaster_id={self.user_id}&moderator_id={self.user_id}&user_id={target_user_id}",
            headers=headers,
        )

    def get_user_clips(self, username: str, count: int = 1) -> list[dict]:
        """Get clips from a user's channel."""
        import httpx

        headers = {
            "Client-ID": self.client_id,
            "Authorization": f"Bearer {self.oauth_token.replace('oauth:', '')}",
        }

        # Get user ID
        resp = httpx.get(
            f"https://api.twitch.tv/helix/users?login={username}",
            headers=headers,
        )
        user_data = resp.json()
        if not user_data.get("data"):
            return []

        user_id = user_data["data"][0]["id"]

        # Get clips
        resp = httpx.get(
            f"https://api.twitch.tv/helix/clips?broadcaster_id={user_id}&first={count}",
            headers=headers,
        )
        clips_data = resp.json()
        return [
            {
                "id": c["id"],
                "url": c["url"],
                "embed_url": c["embed_url"],
                "title": c["title"],
                "view_count": c["view_count"],
                "thumbnail_url": c["thumbnail_url"],
            }
            for c in clips_data.get("data", [])
        ]

    def shoutout(self, username: str) -> None:
        """Send a shoutout to another streamer."""
        import httpx

        headers = {
            "Client-ID": self.client_id,
            "Authorization": f"Bearer {self.oauth_token.replace('oauth:', '')}",
        }

        # Get user ID
        resp = httpx.get(
            f"https://api.twitch.tv/helix/users?login={username}",
            headers=headers,
        )
        user_data = resp.json()
        if not user_data.get("data"):
            raise ValueError(f"User {username} not found")

        target_user_id = user_data["data"][0]["id"]

        httpx.post(
            f"https://api.twitch.tv/helix/chat/shoutouts?from_broadcaster_id={self.user_id}&to_broadcaster_id={target_user_id}&moderator_id={self.user_id}",
            headers=headers,
        )

    def get_user_id(self, username: str) -> str | None:
        """Get a user's ID from their username."""
        import httpx

        headers = {
            "Client-ID": self.client_id,
            "Authorization": f"Bearer {self.oauth_token.replace('oauth:', '')}",
        }
        resp = httpx.get(
            f"https://api.twitch.tv/helix/users?login={username}",
            headers=headers,
        )
        user_data = resp.json()
        if user_data.get("data"):
            return user_data["data"][0]["id"]
        return None

    def get_streams_by_game(self, game_id: str, count: int = 20) -> list[dict]:
        """Get live streams for a specific game/category."""
        import httpx

        headers = {
            "Client-ID": self.client_id,
            "Authorization": f"Bearer {self.oauth_token.replace('oauth:', '')}",
        }
        resp = httpx.get(
            f"https://api.twitch.tv/helix/streams?game_id={game_id}&first={count}",
            headers=headers,
        )
        data = resp.json()
        return [
            {
                "user_id": s["user_id"],
                "user_login": s["user_login"],
                "user_name": s["user_name"],
                "game_name": s["game_name"],
                "title": s["title"],
                "viewer_count": s["viewer_count"],
            }
            for s in data.get("data", [])
        ]

    def start_raid(self, target_username: str) -> dict:
        """Start a raid to another channel."""
        import httpx

        headers = {
            "Client-ID": self.client_id,
            "Authorization": f"Bearer {self.oauth_token.replace('oauth:', '')}",
        }

        # Get target user ID
        target_user_id = self.get_user_id(target_username)
        if not target_user_id:
            raise ValueError(f"User {target_username} not found")

        # Start the raid
        resp = httpx.post(
            f"https://api.twitch.tv/helix/raids?from_broadcaster_id={self.user_id}&to_broadcaster_id={target_user_id}",
            headers=headers,
        )

        if resp.status_code >= 400:
            raise ValueError(f"Raid failed: {resp.status_code} - {resp.text}")

        data = resp.json()
        if data.get("data"):
            return {
                "target": target_username,
                "created_at": data["data"][0].get("created_at"),
                "is_mature": data["data"][0].get("is_mature", False),
            }
        return {"target": target_username, "status": "initiated"}

    def cancel_raid(self) -> str:
        """Cancel an ongoing raid."""
        import httpx

        headers = {
            "Client-ID": self.client_id,
            "Authorization": f"Bearer {self.oauth_token.replace('oauth:', '')}",
        }

        resp = httpx.delete(
            f"https://api.twitch.tv/helix/raids?broadcaster_id={self.user_id}",
            headers=headers,
        )

        if resp.status_code >= 400:
            return f"Cancel raid failed: {resp.status_code}"
        return "Raid cancelled"
