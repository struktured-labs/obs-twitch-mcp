"""
Persistent chat logging utility.
Saves Twitch chat messages to daily log files in JSON format.
"""

import json
import os
from datetime import datetime
from pathlib import Path
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from .twitch_client import ChatMessage

# Log directory inside the project (git-ignored)
LOG_DIR = Path(__file__).parent.parent.parent / "logs" / "chat"


def get_log_path(date: datetime | None = None) -> Path:
    """Get the log file path for a given date."""
    if date is None:
        date = datetime.now()
    return LOG_DIR / f"{date.strftime('%Y-%m-%d')}.jsonl"


def ensure_log_dir() -> None:
    """Ensure the log directory exists."""
    LOG_DIR.mkdir(parents=True, exist_ok=True)


def log_message(msg: "ChatMessage") -> None:
    """Log a chat message to the daily log file."""
    ensure_log_dir()
    log_path = get_log_path()

    entry = {
        "timestamp": datetime.now().isoformat(),
        "username": msg.username,
        "message": msg.message,
        "message_id": msg.message_id,
        "is_mod": msg.is_mod,
        "is_subscriber": msg.is_subscriber,
    }

    with open(log_path, "a", encoding="utf-8") as f:
        f.write(json.dumps(entry) + "\n")


def read_logs(date: datetime | None = None, limit: int = 100) -> list[dict]:
    """Read chat logs for a given date."""
    log_path = get_log_path(date)

    if not log_path.exists():
        return []

    messages = []
    with open(log_path, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line:
                messages.append(json.loads(line))

    return messages[-limit:] if limit else messages


def get_available_dates() -> list[str]:
    """Get list of dates that have chat logs."""
    if not LOG_DIR.exists():
        return []

    dates = []
    for f in LOG_DIR.glob("*.jsonl"):
        dates.append(f.stem)

    return sorted(dates, reverse=True)
