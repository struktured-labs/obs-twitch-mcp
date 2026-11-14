"""
Scheduled actions for stream management.

Provides tools for:
- Reminders (e.g., "remind me to take a break in 2 hours")
- Recurring chat messages (e.g., post socials every 30 min)
- Timed actions (e.g., change scene at specific time)
"""

import threading
import time
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import Callable
from uuid import uuid4

from ..app import mcp, get_twitch_client
from ..utils.logger import get_logger

logger = get_logger("scheduler")


@dataclass
class ScheduledAction:
    """A scheduled action to perform."""
    id: str
    name: str
    action_type: str  # "reminder", "message", "custom"
    next_run: datetime
    interval_seconds: int | None  # None = one-time, otherwise recurring
    data: dict = field(default_factory=dict)
    enabled: bool = True
    run_count: int = 0
    max_runs: int | None = None  # None = unlimited


# Global scheduler state
_actions: dict[str, ScheduledAction] = {}
_scheduler_thread: threading.Thread | None = None
_scheduler_running = False


def _run_action(action: ScheduledAction) -> None:
    """Execute a scheduled action."""
    logger.info(f"Running scheduled action: {action.name}")

    try:
        if action.action_type == "reminder":
            # Send reminder to chat
            message = action.data.get("message", "Reminder!")
            twitch = get_twitch_client()
            twitch.send_chat_message(f"⏰ Reminder: {message}")

        elif action.action_type == "message":
            # Send a message to chat (static, or LLM-written when dynamic)
            twitch = get_twitch_client()
            message = _compose_message_post(action, twitch)
            if message is None:
                return  # skipped (e.g. stream offline); not counted as a run
            if message:
                twitch.send_chat_message(message)

        elif action.action_type == "scene_change":
            # Change OBS scene
            from ..app import get_obs_client
            scene_name = action.data.get("scene_name")
            if scene_name:
                obs = get_obs_client()
                obs.set_current_scene(scene_name)
                logger.info(f"Changed scene to: {scene_name}")

        elif action.action_type == "custom":
            # Custom callback
            callback = action.data.get("callback")
            if callback:
                callback()

        action.run_count += 1

    except Exception as e:
        logger.error(f"Scheduled action failed: {action.name} - {e}")


HISTORY_KEEP = 5
CHAT_CONTEXT_COUNT = 15


def _compose_message_post(action: ScheduledAction, twitch) -> str | None:
    """Return the text to post for a recurring message, or None to skip this run.

    - only_when_live: skip (and don't count) while the channel is offline, so a
      forgotten recurring message doesn't post for hours after the stream ends.
      If the live check itself errors, post anyway rather than go silent.
    - dynamic: have a small LLM write the post from the base message, stream
      info, recent chat and the last few posts; falls back to the static text.
    """
    data = action.data
    base = data.get("message", "")
    stream_info = None
    if data.get("only_when_live") or data.get("dynamic"):
        try:
            stream_info = twitch.get_stream_info()
            if stream_info is None and data.get("only_when_live"):
                data["skipped_offline"] = data.get("skipped_offline", 0) + 1
                logger.info(f"Skipping '{action.name}': stream offline")
                return None
        except Exception as e:
            logger.warning(f"Live check failed for '{action.name}', posting anyway: {e}")

    if not data.get("dynamic"):
        return base

    from ..utils.recurring_ai import generate_recurring_message

    recent = []
    try:
        for m in twitch.get_recent_messages(CHAT_CONTEXT_COUNT):
            if m.message.startswith("«claude»"):
                continue
            recent.append((m.username, m.message))
    except Exception as e:
        logger.warning(f"Could not read recent chat for dynamic message: {e}")

    history = data.setdefault("history", [])
    text, generated = generate_recurring_message(
        base_message=base,
        context=data.get("context", ""),
        stream_info=stream_info,
        recent_chat=recent,
        previous_posts=history,
    )
    history.append(text)
    del history[:-HISTORY_KEEP]
    data["last_generated"] = generated
    return text


def _scheduler_loop() -> None:
    """Main scheduler loop."""
    global _scheduler_running

    while _scheduler_running:
        now = datetime.now()

        for action_id, action in list(_actions.items()):
            if not action.enabled:
                continue

            if action.next_run <= now:
                # Run the action
                _run_action(action)

                # Check if max runs reached
                if action.max_runs and action.run_count >= action.max_runs:
                    logger.info(f"Action completed all runs: {action.name}")
                    action.enabled = False
                    continue

                # Schedule next run if recurring
                if action.interval_seconds:
                    action.next_run = now + timedelta(seconds=action.interval_seconds)
                else:
                    # One-time action, disable
                    action.enabled = False

        time.sleep(1)  # Check every second


def _start_scheduler() -> None:
    """Start the scheduler thread."""
    global _scheduler_thread, _scheduler_running

    if _scheduler_running:
        return

    _scheduler_running = True
    _scheduler_thread = threading.Thread(target=_scheduler_loop, daemon=True)
    _scheduler_thread.start()
    logger.info("Scheduler started")


def _stop_scheduler() -> None:
    """Stop the scheduler thread."""
    global _scheduler_running
    _scheduler_running = False
    logger.info("Scheduler stopped")


# =============================================================================
# MCP Tools
# =============================================================================


@mcp.tool()
def set_reminder(message: str, minutes: int) -> dict:
    """
    Set a reminder that will be posted to chat.

    Args:
        message: The reminder message
        minutes: Minutes from now to trigger the reminder

    Returns:
        Dict with reminder ID and scheduled time.
    """
    _start_scheduler()

    action_id = str(uuid4())[:8]
    trigger_time = datetime.now() + timedelta(minutes=minutes)

    action = ScheduledAction(
        id=action_id,
        name=f"Reminder: {message[:30]}",
        action_type="reminder",
        next_run=trigger_time,
        interval_seconds=None,
        data={"message": message},
    )
    _actions[action_id] = action

    logger.info(f"Reminder set for {trigger_time}: {message}")
    return {
        "status": "created",
        "id": action_id,
        "message": message,
        "triggers_at": trigger_time.isoformat(),
        "in_minutes": minutes,
    }


@mcp.tool()
def set_recurring_message(
    message: str,
    interval_minutes: int,
    max_times: int = 0,
    dynamic: bool = False,
    context: str = "",
    only_when_live: bool = True,
) -> dict:
    """
    Set a recurring message to post to chat.

    Useful for periodic reminders like "Follow the channel!" or social links.

    Args:
        message: The message to post. When dynamic, this is the base: its facts
            and call-to-action (e.g. "try !ask") are kept, wording is varied.
        interval_minutes: Minutes between each post
        max_times: Maximum times to post (0 = unlimited)
        dynamic: If True, a small LLM writes each post fresh from the base
            message, `context`, stream title/game, recent chat and the last few
            posts (no repeats). Falls back to the static message on any error.
        context: Extra background for dynamic posts (game, mods, project notes).
        only_when_live: Skip posts while the channel is offline (default True),
            so a forgotten recurring message doesn't spam after the stream ends.

    Returns:
        Dict with action ID.
    """
    _start_scheduler()

    action_id = str(uuid4())[:8]
    first_run = datetime.now() + timedelta(minutes=interval_minutes)

    action = ScheduledAction(
        id=action_id,
        name=f"Recurring: {message[:30]}",
        action_type="message",
        next_run=first_run,
        interval_seconds=interval_minutes * 60,
        data={
            "message": message,
            "dynamic": dynamic,
            "context": context,
            "only_when_live": only_when_live,
        },
        max_runs=max_times if max_times > 0 else None,
    )
    _actions[action_id] = action

    logger.info(
        f"Recurring message set every {interval_minutes}m "
        f"(dynamic={dynamic}, only_when_live={only_when_live}): {message}"
    )
    return {
        "status": "created",
        "id": action_id,
        "message": message,
        "dynamic": dynamic,
        "only_when_live": only_when_live,
        "interval_minutes": interval_minutes,
        "first_run": first_run.isoformat(),
        "max_times": max_times if max_times > 0 else "unlimited",
    }


@mcp.tool()
def schedule_scene_change(scene_name: str, minutes: int) -> dict:
    """
    Schedule an OBS scene change.

    Args:
        scene_name: Name of the scene to switch to
        minutes: Minutes from now to trigger

    Returns:
        Dict with action ID.
    """
    _start_scheduler()

    action_id = str(uuid4())[:8]
    trigger_time = datetime.now() + timedelta(minutes=minutes)

    action = ScheduledAction(
        id=action_id,
        name=f"Scene: {scene_name}",
        action_type="scene_change",
        next_run=trigger_time,
        interval_seconds=None,
        data={"scene_name": scene_name},
    )
    _actions[action_id] = action

    logger.info(f"Scene change scheduled to '{scene_name}' at {trigger_time}")
    return {
        "status": "created",
        "id": action_id,
        "scene_name": scene_name,
        "triggers_at": trigger_time.isoformat(),
    }


@mcp.tool()
def list_scheduled_actions() -> list[dict]:
    """
    List all scheduled actions.

    Returns:
        List of action details.
    """
    return [
        {
            "id": action.id,
            "name": action.name,
            "type": action.action_type,
            "enabled": action.enabled,
            "next_run": action.next_run.isoformat(),
            "interval_minutes": action.interval_seconds // 60 if action.interval_seconds else None,
            "run_count": action.run_count,
            "max_runs": action.max_runs,
            "dynamic": action.data.get("dynamic", False),
            "only_when_live": action.data.get("only_when_live", False),
            "skipped_offline": action.data.get("skipped_offline", 0),
            "last_post": (action.data.get("history") or [None])[-1],
        }
        for action in _actions.values()
    ]


@mcp.tool()
def cancel_scheduled_action(action_id: str) -> dict:
    """
    Cancel a scheduled action.

    Args:
        action_id: The ID of the action to cancel

    Returns:
        Status dict.
    """
    if action_id in _actions:
        action = _actions.pop(action_id)
        logger.info(f"Cancelled action: {action.name}")
        return {"status": "cancelled", "id": action_id, "name": action.name}
    return {"status": "not_found", "id": action_id}


@mcp.tool()
def pause_scheduled_action(action_id: str) -> dict:
    """
    Pause a scheduled action without cancelling it.

    Args:
        action_id: The ID of the action to pause

    Returns:
        Status dict.
    """
    if action_id in _actions:
        _actions[action_id].enabled = False
        return {"status": "paused", "id": action_id}
    return {"status": "not_found", "id": action_id}


@mcp.tool()
def resume_scheduled_action(action_id: str) -> dict:
    """
    Resume a paused scheduled action.

    Args:
        action_id: The ID of the action to resume

    Returns:
        Status dict.
    """
    if action_id in _actions:
        _actions[action_id].enabled = True
        return {"status": "resumed", "id": action_id}
    return {"status": "not_found", "id": action_id}


@mcp.tool()
def clear_all_scheduled_actions() -> dict:
    """
    Cancel all scheduled actions.

    Returns:
        Status dict.
    """
    count = len(_actions)
    _actions.clear()
    logger.info(f"Cleared {count} scheduled actions")
    return {"status": "cleared", "count": count}
