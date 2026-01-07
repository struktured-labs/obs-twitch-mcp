"""
Chat message filtering for overlay display.

Filters out:
- Spam (rate limiting, duplicates, caps abuse)
- Bad words (configurable blocklist)
- Sensitive data (emails, phone numbers, URLs)
- Bot messages (Nightbot, StreamElements, etc.)
"""

import re
import time
from dataclasses import dataclass, field
from typing import Any

from .logger import get_logger

logger = get_logger("chat_filter")


# Default blocked patterns (spam, sensitive data)
DEFAULT_BLOCKED_PATTERNS = [
    # Spam patterns
    r"(?i)follow me at",
    r"(?i)check out my",
    r"(?i)free (vbucks|robux|gift|nitro)",
    r"(?i)want to become famous",
    r"(?i)best viewer",
    r"(?i)I just mass reported",

    # URL shorteners (often spam)
    r"bit\.ly/",
    r"tinyurl\.com/",
    r"t\.co/",
    r"goo\.gl/",

    # Sensitive data patterns
    r"\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b",  # Emails
    r"\b\d{3}[-.\s]?\d{3}[-.\s]?\d{4}\b",  # Phone numbers (US format)
    r"\b(?:oauth|token|api[_-]?key|password|secret)[:\s=]+\S+",  # Tokens/keys
]

# Known bot accounts
DEFAULT_BOTS = [
    "nightbot",
    "streamelements",
    "streamlabs",
    "moobot",
    "fossabot",
    "wizebot",
    "deepbot",
    "coebot",
    "ankhbot",
    "phantombot",
    "stay_hydrated_bot",
    "commanderroot",
    "soundalerts",
]

# Common bad words (basic list - users should extend)
DEFAULT_BAD_WORDS = [
    # Slurs and hate speech patterns would go here
    # Keeping minimal for base install, users add their own
]


@dataclass
class ChatFilter:
    """Filter chain for chat messages."""

    # Rate limiting
    rate_limit_messages: int = 5  # Max messages per window
    rate_limit_window: float = 10.0  # Window in seconds

    # Feature toggles
    block_spam: bool = True
    block_bots: bool = True
    block_links: bool = False  # Some channels want links
    block_caps: bool = True
    caps_threshold: float = 0.7  # 70% caps = too much

    # Blocklists
    blocked_patterns: list[str] = field(default_factory=list)
    blocked_words: list[str] = field(default_factory=list)
    blocked_bots: list[str] = field(default_factory=list)

    # State tracking
    _user_message_times: dict = field(default_factory=dict)
    _recent_messages: list = field(default_factory=list)
    _max_recent: int = 100

    def __post_init__(self):
        # Initialize with defaults
        if not self.blocked_patterns:
            self.blocked_patterns = list(DEFAULT_BLOCKED_PATTERNS)
        if not self.blocked_bots:
            self.blocked_bots = list(DEFAULT_BOTS)
        if not self.blocked_words:
            self.blocked_words = list(DEFAULT_BAD_WORDS)

        # Compile regex patterns for performance
        self._compiled_patterns = []
        for pattern in self.blocked_patterns:
            try:
                self._compiled_patterns.append(re.compile(pattern, re.IGNORECASE))
            except re.error as e:
                logger.warning(f"Invalid regex pattern '{pattern}': {e}")

    def process(self, message: dict) -> dict | None:
        """
        Process a chat message through all filters.

        Args:
            message: Dict with keys: username, message, is_mod, is_subscriber, etc.

        Returns:
            The message dict if it passes all filters, None if blocked.
        """
        username = message.get("username", "").lower()
        text = message.get("message", "")
        is_mod = message.get("is_mod", False)

        # Mods bypass most filters (but not sensitive data)
        bypass_filters = is_mod

        # 1. Bot filter
        if self.block_bots and not bypass_filters:
            if self._is_bot(username):
                logger.debug(f"Blocked bot message from {username}")
                return None

        # 2. Rate limit filter
        if self.block_spam and not bypass_filters:
            if self._is_rate_limited(username):
                logger.debug(f"Rate limited {username}")
                return None

        # 3. Duplicate filter
        if self.block_spam and not bypass_filters:
            if self._is_duplicate(username, text):
                logger.debug(f"Blocked duplicate from {username}")
                return None

        # 4. Caps abuse filter
        if self.block_caps and not bypass_filters:
            if self._is_caps_abuse(text):
                logger.debug(f"Blocked caps abuse from {username}")
                return None

        # 5. Pattern filter (spam, sensitive data - applies to everyone)
        if self._matches_blocked_pattern(text):
            logger.debug(f"Blocked pattern match from {username}")
            return None

        # 6. Bad words filter
        if self._contains_bad_word(text):
            logger.debug(f"Blocked bad word from {username}")
            return None

        # 7. Link filter (optional)
        if self.block_links and not bypass_filters:
            if self._contains_link(text):
                logger.debug(f"Blocked link from {username}")
                return None

        # Message passed all filters
        return message

    def _is_bot(self, username: str) -> bool:
        """Check if username is a known bot."""
        return username.lower() in self.blocked_bots

    def _is_rate_limited(self, username: str) -> bool:
        """Check if user has exceeded rate limit."""
        now = time.time()
        username = username.lower()

        # Clean old entries
        if username in self._user_message_times:
            self._user_message_times[username] = [
                t for t in self._user_message_times[username]
                if now - t < self.rate_limit_window
            ]

        # Check rate
        times = self._user_message_times.get(username, [])
        if len(times) >= self.rate_limit_messages:
            return True

        # Record this message
        if username not in self._user_message_times:
            self._user_message_times[username] = []
        self._user_message_times[username].append(now)

        return False

    def _is_duplicate(self, username: str, text: str) -> bool:
        """Check for duplicate messages."""
        # Normalize: lowercase, strip whitespace
        normalized = text.lower().strip()
        key = f"{username.lower()}:{normalized}"

        # Check recent messages
        if key in self._recent_messages:
            return True

        # Add to recent
        self._recent_messages.append(key)
        if len(self._recent_messages) > self._max_recent:
            self._recent_messages.pop(0)

        return False

    def _is_caps_abuse(self, text: str) -> bool:
        """Check if message has too many capital letters."""
        # Only check messages with enough letters
        letters = [c for c in text if c.isalpha()]
        if len(letters) < 10:
            return False

        caps = sum(1 for c in letters if c.isupper())
        return (caps / len(letters)) > self.caps_threshold

    def _matches_blocked_pattern(self, text: str) -> bool:
        """Check if message matches any blocked regex pattern."""
        for pattern in self._compiled_patterns:
            if pattern.search(text):
                return True
        return False

    def _contains_bad_word(self, text: str) -> bool:
        """Check if message contains blocked words."""
        text_lower = text.lower()
        for word in self.blocked_words:
            # Word boundary check
            pattern = rf"\b{re.escape(word)}\b"
            if re.search(pattern, text_lower, re.IGNORECASE):
                return True
        return False

    def _contains_link(self, text: str) -> bool:
        """Check if message contains a URL."""
        url_pattern = r"https?://|www\.|[a-zA-Z0-9-]+\.(com|org|net|io|gg|tv|co|me)"
        return bool(re.search(url_pattern, text, re.IGNORECASE))

    # Configuration methods

    def add_blocked_word(self, word: str) -> None:
        """Add a word to the blocklist."""
        if word.lower() not in [w.lower() for w in self.blocked_words]:
            self.blocked_words.append(word)
            logger.info(f"Added blocked word: {word}")

    def remove_blocked_word(self, word: str) -> bool:
        """Remove a word from the blocklist."""
        for i, w in enumerate(self.blocked_words):
            if w.lower() == word.lower():
                self.blocked_words.pop(i)
                logger.info(f"Removed blocked word: {word}")
                return True
        return False

    def add_blocked_pattern(self, pattern: str) -> bool:
        """Add a regex pattern to the blocklist."""
        try:
            compiled = re.compile(pattern, re.IGNORECASE)
            self._compiled_patterns.append(compiled)
            self.blocked_patterns.append(pattern)
            logger.info(f"Added blocked pattern: {pattern}")
            return True
        except re.error as e:
            logger.warning(f"Invalid regex pattern '{pattern}': {e}")
            return False

    def add_blocked_bot(self, username: str) -> None:
        """Add a bot username to the blocklist."""
        if username.lower() not in self.blocked_bots:
            self.blocked_bots.append(username.lower())
            logger.info(f"Added blocked bot: {username}")

    def get_config(self) -> dict:
        """Get current filter configuration."""
        return {
            "block_spam": self.block_spam,
            "block_bots": self.block_bots,
            "block_links": self.block_links,
            "block_caps": self.block_caps,
            "rate_limit_messages": self.rate_limit_messages,
            "rate_limit_window": self.rate_limit_window,
            "blocked_words_count": len(self.blocked_words),
            "blocked_patterns_count": len(self.blocked_patterns),
            "blocked_bots_count": len(self.blocked_bots),
        }

    def update_config(self, **kwargs) -> dict:
        """Update filter configuration."""
        for key, value in kwargs.items():
            if hasattr(self, key):
                setattr(self, key, value)
                logger.info(f"Updated filter config: {key}={value}")
        return self.get_config()


# Global filter instance
_filter: ChatFilter | None = None


def get_chat_filter() -> ChatFilter:
    """Get or create the global chat filter."""
    global _filter
    if _filter is None:
        _filter = ChatFilter()
    return _filter


def reset_chat_filter() -> ChatFilter:
    """Reset the global chat filter to defaults."""
    global _filter
    _filter = ChatFilter()
    return _filter
