"""
Background IRC listener for Twitch chat.

Connects to IRC and logs all incoming messages.
"""

import re
import socket
import ssl
import threading
import time
from dataclasses import dataclass
from typing import Callable

from . import chat_logger
from .twitch_client import ChatMessage


@dataclass
class ChatListener:
    """Background listener for Twitch IRC chat."""

    channel: str
    oauth_token: str
    nick: str = ""
    _socket: ssl.SSLSocket | None = None
    _thread: threading.Thread | None = None
    _running: bool = False
    _handlers: list[Callable[[ChatMessage], None]] = None

    def __post_init__(self):
        if not self.nick:
            self.nick = self.channel
        if self._handlers is None:
            self._handlers = []

    def add_handler(self, handler: Callable[[ChatMessage], None]) -> None:
        """Add a message handler."""
        if self._handlers is None:
            self._handlers = []
        self._handlers.append(handler)

    def _connect(self) -> None:
        """Connect to Twitch IRC."""
        token = self.oauth_token
        if not token.startswith("oauth:"):
            token = f"oauth:{token}"

        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        ctx = ssl.create_default_context()
        self._socket = ctx.wrap_socket(sock, server_hostname="irc.chat.twitch.tv")
        self._socket.connect(("irc.chat.twitch.tv", 6697))
        self._socket.settimeout(1.0)  # Short timeout for responsive shutdown

        # Authenticate
        self._socket.send(f"PASS {token}\r\n".encode())
        self._socket.send(f"NICK {self.nick}\r\n".encode())

        # Request tags for more message info
        self._socket.send(b"CAP REQ :twitch.tv/tags twitch.tv/commands\r\n")

        # Join channel
        self._socket.send(f"JOIN #{self.channel}\r\n".encode())

    def _parse_message(self, raw: str) -> ChatMessage | None:
        """Parse an IRC message into a ChatMessage."""
        # PRIVMSG format: @tags :user!user@user.tmi.twitch.tv PRIVMSG #channel :message
        privmsg_match = re.match(
            r"(?:@(\S+)\s+)?:(\w+)!\w+@\w+\.tmi\.twitch\.tv\s+PRIVMSG\s+#(\w+)\s+:(.+)",
            raw.strip()
        )

        if not privmsg_match:
            return None

        tags_str, username, channel, message = privmsg_match.groups()

        # Parse tags
        is_mod = False
        is_sub = False
        msg_id = ""

        if tags_str:
            tags = dict(t.split("=", 1) for t in tags_str.split(";") if "=" in t)
            is_mod = tags.get("mod") == "1" or tags.get("badges", "").find("broadcaster") >= 0
            is_sub = tags.get("subscriber") == "1"
            msg_id = tags.get("id", "")

        return ChatMessage(
            username=username,
            message=message,
            message_id=msg_id,
            is_mod=is_mod,
            is_subscriber=is_sub,
        )

    def _listen_loop(self) -> None:
        """Main listening loop."""
        buffer = ""

        while self._running:
            try:
                data = self._socket.recv(4096).decode("utf-8", errors="ignore")
                if not data:
                    # Connection closed
                    break

                buffer += data

                while "\r\n" in buffer:
                    line, buffer = buffer.split("\r\n", 1)

                    # Respond to PING to stay connected
                    if line.startswith("PING"):
                        self._socket.send(b"PONG :tmi.twitch.tv\r\n")
                        continue

                    # Parse chat messages
                    msg = self._parse_message(line)
                    if msg:
                        # Log the message
                        chat_logger.log_message(msg)

                        # Notify handlers
                        for handler in (self._handlers or []):
                            try:
                                handler(msg)
                            except Exception:
                                pass

            except socket.timeout:
                # Normal timeout, just continue
                continue
            except Exception as e:
                if self._running:
                    print(f"Chat listener error: {e}")
                    time.sleep(5)  # Brief pause before reconnecting
                    try:
                        self._connect()
                    except Exception:
                        pass

    def start(self) -> None:
        """Start the listener in a background thread."""
        if self._running:
            return

        self._running = True
        self._connect()
        self._thread = threading.Thread(target=self._listen_loop, daemon=True)
        self._thread.start()
        print(f"Chat listener started for #{self.channel}")

    def stop(self) -> None:
        """Stop the listener."""
        self._running = False
        if self._socket:
            try:
                self._socket.close()
            except Exception:
                pass
        if self._thread:
            self._thread.join(timeout=2.0)
        print("Chat listener stopped")

    @property
    def is_running(self) -> bool:
        return self._running
