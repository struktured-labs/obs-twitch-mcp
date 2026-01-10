"""
Twitch API and IRC client wrapper.
"""

import socket
import ssl
import time
from dataclasses import dataclass, field
from typing import Callable

import httpx

from . import chat_logger
from .logger import get_logger
from .twitch_auth import refresh_token, save_token, load_token

logger = get_logger("twitch_client")


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

    def _refresh_token(self) -> bool:
        """Refresh the OAuth token. Returns True if successful."""
        token_data = load_token()
        if not token_data or not token_data.get("refresh_token"):
            logger.warning("Cannot refresh token: no refresh_token available")
            return False
        if not self.client_secret:
            logger.warning("Cannot refresh token: client_secret not provided")
            return False
        try:
            new_token = refresh_token(
                self.client_id, self.client_secret, token_data["refresh_token"]
            )
            save_token(new_token)
            self.oauth_token = new_token["access_token"]
            self._user_id = None  # Reset cached user ID
            logger.info("Token auto-refreshed successfully")
            return True
        except Exception as e:
            logger.error(f"Token refresh failed: {e}")
            return False

    def _api_call(self, method: str, url: str, **kwargs) -> httpx.Response:
        """Make an API call with auto-retry on 401 and exponential backoff."""
        # Extract extra headers once (don't pop on each iteration)
        extra_headers = kwargs.pop("headers", {})
        # Don't allow timeout to be overridden via kwargs
        kwargs.pop("timeout", None)
        backoff = 1  # Start with 1 second backoff

        for attempt in range(3):
            headers = {
                "Client-ID": self.client_id,
                "Authorization": f"Bearer {self.oauth_token.replace('oauth:', '')}",
                **extra_headers,
            }

            resp = getattr(httpx, method)(url, headers=headers, timeout=10.0, **kwargs)

            if resp.status_code == 401:
                logger.warning(f"API call to {url} failed with 401 (attempt {attempt + 1}/3)")
                if self._refresh_token():
                    time.sleep(backoff)
                    backoff *= 2  # Exponential backoff
                    continue  # Retry with new token
                else:
                    logger.error("Token refresh failed, giving up")
                    break  # Refresh failed, give up
            elif resp.status_code >= 400:
                logger.warning(f"API call to {url} failed: {resp.status_code} - {resp.text[:200]}")
            return resp
        return resp  # Return last response even if failed

    @property
    def user_id(self) -> str:
        """Get the authenticated user's ID."""
        if self._user_id is None:
            resp = self._api_call("get", "https://api.twitch.tv/helix/users")
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
        sock.settimeout(8.0)  # Set timeout BEFORE SSL wrap and connect
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
            except Exception as e:
                logger.warning(f"Message handler error: {e}")  # Log but don't break chain

    def add_message_handler(self, handler: Callable[[ChatMessage], None]) -> None:
        """Add a handler for incoming chat messages."""
        self._message_handlers.append(handler)

    def get_stream_info(self) -> dict | None:
        """Get current stream information."""
        resp = self._api_call(
            "get", f"https://api.twitch.tv/helix/streams?user_login={self.channel}"
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
        data = {}
        if title:
            data["title"] = title
        if game_id:
            data["game_id"] = game_id

        if data:
            self._api_call(
                "patch",
                f"https://api.twitch.tv/helix/channels?broadcaster_id={self.user_id}",
                json=data,
            )

    def search_game(self, query: str) -> list[dict]:
        """Search for a game by name."""
        resp = self._api_call(
            "get", f"https://api.twitch.tv/helix/search/categories?query={query}"
        )
        data = resp.json()
        return [
            {"id": g["id"], "name": g["name"], "box_art_url": g.get("box_art_url")}
            for g in data.get("data", [])
        ]

    def ban_user(self, username: str, reason: str = "") -> None:
        """Ban a user from chat."""
        # First get user ID
        resp = self._api_call("get", f"https://api.twitch.tv/helix/users?login={username}")
        user_data = resp.json()
        if not user_data.get("data"):
            raise ValueError(f"User {username} not found")

        target_user_id = user_data["data"][0]["id"]

        # Ban the user
        ban_resp = self._api_call(
            "post",
            f"https://api.twitch.tv/helix/moderation/bans?broadcaster_id={self.user_id}&moderator_id={self.user_id}",
            json={"data": {"user_id": target_user_id, "reason": reason}},
        )
        if ban_resp.status_code >= 400:
            raise ValueError(f"Ban failed: {ban_resp.status_code} - {ban_resp.text}")

    def timeout_user(self, username: str, duration: int = 600, reason: str = "") -> None:
        """Timeout a user from chat."""
        resp = self._api_call("get", f"https://api.twitch.tv/helix/users?login={username}")
        user_data = resp.json()
        if not user_data.get("data"):
            raise ValueError(f"User {username} not found")

        target_user_id = user_data["data"][0]["id"]

        self._api_call(
            "post",
            f"https://api.twitch.tv/helix/moderation/bans?broadcaster_id={self.user_id}&moderator_id={self.user_id}",
            json={"data": {"user_id": target_user_id, "duration": duration, "reason": reason}},
        )

    def unban_user(self, username: str) -> None:
        """Unban a user from chat."""
        resp = self._api_call("get", f"https://api.twitch.tv/helix/users?login={username}")
        user_data = resp.json()
        if not user_data.get("data"):
            raise ValueError(f"User {username} not found")

        target_user_id = user_data["data"][0]["id"]

        self._api_call(
            "delete",
            f"https://api.twitch.tv/helix/moderation/bans?broadcaster_id={self.user_id}&moderator_id={self.user_id}&user_id={target_user_id}",
        )

    def get_user_clips(self, username: str, count: int = 1) -> list[dict]:
        """Get clips from a user's channel."""
        # Get user ID
        resp = self._api_call("get", f"https://api.twitch.tv/helix/users?login={username}")
        user_data = resp.json()
        if not user_data.get("data"):
            return []

        user_id = user_data["data"][0]["id"]

        # Get clips
        resp = self._api_call(
            "get", f"https://api.twitch.tv/helix/clips?broadcaster_id={user_id}&first={count}"
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
        # Get user ID
        resp = self._api_call("get", f"https://api.twitch.tv/helix/users?login={username}")
        user_data = resp.json()
        if not user_data.get("data"):
            raise ValueError(f"User {username} not found")

        target_user_id = user_data["data"][0]["id"]

        self._api_call(
            "post",
            f"https://api.twitch.tv/helix/chat/shoutouts?from_broadcaster_id={self.user_id}&to_broadcaster_id={target_user_id}&moderator_id={self.user_id}",
        )

    def get_user_id(self, username: str) -> str | None:
        """Get a user's ID from their username."""
        resp = self._api_call("get", f"https://api.twitch.tv/helix/users?login={username}")
        user_data = resp.json()
        if user_data.get("data"):
            return user_data["data"][0]["id"]
        return None

    def get_streams_by_game(self, game_id: str, count: int = 20) -> list[dict]:
        """Get live streams for a specific game/category."""
        resp = self._api_call(
            "get", f"https://api.twitch.tv/helix/streams?game_id={game_id}&first={count}"
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
        # Get target user ID
        target_user_id = self.get_user_id(target_username)
        if not target_user_id:
            raise ValueError(f"User {target_username} not found")

        # Start the raid
        resp = self._api_call(
            "post",
            f"https://api.twitch.tv/helix/raids?from_broadcaster_id={self.user_id}&to_broadcaster_id={target_user_id}",
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
        resp = self._api_call(
            "delete", f"https://api.twitch.tv/helix/raids?broadcaster_id={self.user_id}"
        )

        if resp.status_code >= 400:
            return f"Cancel raid failed: {resp.status_code}"
        return "Raid cancelled"

    def create_clip(self, has_delay: bool = False) -> dict:
        """
        Create a clip from the current live stream.

        Args:
            has_delay: If True, adds a delay before capturing (for stream delay compensation)

        Returns:
            Dict with clip ID and edit URL
        """
        resp = self._api_call(
            "post",
            f"https://api.twitch.tv/helix/clips?broadcaster_id={self.user_id}&has_delay={str(has_delay).lower()}",
        )

        if resp.status_code >= 400:
            raise ValueError(f"Clip creation failed: {resp.status_code} - {resp.text}")

        data = resp.json()
        if data.get("data"):
            return {
                "id": data["data"][0]["id"],
                "edit_url": data["data"][0]["edit_url"],
            }
        raise ValueError("Clip creation failed: no data returned")

    def get_clip(self, clip_id: str) -> dict | None:
        """
        Get details for a specific clip by ID.

        Args:
            clip_id: The clip ID to look up

        Returns:
            Clip details or None if not found
        """
        resp = self._api_call(
            "get", f"https://api.twitch.tv/helix/clips?id={clip_id}"
        )
        data = resp.json()
        if data.get("data"):
            c = data["data"][0]
            return {
                "id": c["id"],
                "url": c["url"],
                "embed_url": c["embed_url"],
                "broadcaster_name": c["broadcaster_name"],
                "creator_name": c["creator_name"],
                "title": c["title"],
                "view_count": c["view_count"],
                "created_at": c["created_at"],
                "thumbnail_url": c["thumbnail_url"],
                "duration": c["duration"],
                "video_url": c.get("video_id", ""),
            }
        return None

    def get_my_clips(self, count: int = 10) -> list[dict]:
        """
        Get clips from own channel.

        Args:
            count: Number of clips to return

        Returns:
            List of clip details
        """
        resp = self._api_call(
            "get", f"https://api.twitch.tv/helix/clips?broadcaster_id={self.user_id}&first={count}"
        )
        data = resp.json()
        return [
            {
                "id": c["id"],
                "url": c["url"],
                "embed_url": c["embed_url"],
                "title": c["title"],
                "view_count": c["view_count"],
                "created_at": c["created_at"],
                "thumbnail_url": c["thumbnail_url"],
                "duration": c["duration"],
                "creator_name": c["creator_name"],
            }
            for c in data.get("data", [])
        ]

    # Video Methods (read-only - Twitch Helix API doesn't support video upload)

    def get_videos(self, count: int = 10) -> list[dict]:
        """
        Get videos from own channel.

        Args:
            count: Number of videos to return

        Returns:
            List of video details
        """
        resp = self._api_call(
            "get",
            f"https://api.twitch.tv/helix/videos?user_id={self.user_id}&first={count}",
        )
        data = resp.json()
        return [
            {
                "id": v["id"],
                "title": v["title"],
                "description": v["description"],
                "url": v["url"],
                "duration": v["duration"],
                "view_count": v["view_count"],
                "created_at": v["created_at"],
                "published_at": v["published_at"],
                "thumbnail_url": v["thumbnail_url"],
                "type": v["type"],
            }
            for v in data.get("data", [])
        ]

    def get_video(self, video_id: str) -> dict | None:
        """
        Get details for a specific video.

        Args:
            video_id: The video ID

        Returns:
            Video details or None if not found
        """
        resp = self._api_call(
            "get",
            f"https://api.twitch.tv/helix/videos?id={video_id}",
        )
        data = resp.json()
        if data.get("data"):
            v = data["data"][0]
            return {
                "id": v["id"],
                "title": v["title"],
                "description": v["description"],
                "url": v["url"],
                "duration": v["duration"],
                "view_count": v["view_count"],
                "created_at": v["created_at"],
                "published_at": v["published_at"],
                "thumbnail_url": v["thumbnail_url"],
                "type": v["type"],
            }
        return None
