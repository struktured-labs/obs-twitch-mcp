"""
LLM-written recurring chat messages.

A recurring message can be "dynamic": instead of posting the same static text
every N minutes, each post is written fresh by a small model from:
- the base message (the facts/CTA that must survive, e.g. "try !ask")
- optional extra context from the streamer (what the game/mods are)
- current stream info (title, game, uptime)
- recent chat (so it can riff on what people are talking about)
- the last few posts (so it doesn't repeat itself)

Any failure falls back to the static base message, so a dynamic message never
goes silent because the API hiccuped.
"""

import os
import re

import anthropic

from .logger import get_logger

logger = get_logger("recurring_ai")

MODEL = os.getenv("RECURRING_AI_MODEL", "claude-haiku-5-5")
MAX_TOKENS = 200
MAX_CHAT_CHARS = 480  # Twitch limit is 500; leave room for the prefix
PREFIX = "«claude» "

SYSTEM_PROMPT = """You write one periodic chat message for struktured's Twitch stream, posted by the channel's AI helper.

Rules:
- ONE message, at most 2 short sentences, under 300 characters. Plain text, no quotes around it, no hashtags.
- Keep every concrete fact and call-to-action from the BASE MESSAGE (e.g. a !command); everything else you may rephrase freely.
- Vary it: talk about what's happening in the game, the mods/project, or riff lightly on recent chat. Don't repeat the angle or wording of the PREVIOUS POSTS.
- You may mention a chatter by name only if they said something worth a friendly nod; never mock anyone, never mention bots/spam.
- Never invent facts about the game or the streamer beyond what you're given.
- No URLs, no @everyone, no claims about follower/viewer counts.
- Do NOT include the «claude» prefix; it is added automatically.
- Output only the message text."""


def _build_prompt(
    base_message: str,
    context: str,
    stream_info: dict | None,
    recent_chat: list[tuple[str, str]],
    previous_posts: list[str],
) -> str:
    parts = [f"BASE MESSAGE:\n{base_message}"]
    if context:
        parts.append(f"STREAMER CONTEXT:\n{context}")
    if stream_info:
        info = ", ".join(
            f"{k}: {stream_info[k]}"
            for k in ("title", "game_name", "started_at")
            if stream_info.get(k)
        )
        if info:
            parts.append(f"STREAM INFO:\n{info}")
    if recent_chat:
        chat = "\n".join(f"{u}: {m[:200]}" for u, m in recent_chat)
        parts.append(f"RECENT CHAT (oldest first):\n{chat}")
    else:
        parts.append("RECENT CHAT: (quiet)")
    if previous_posts:
        parts.append("PREVIOUS POSTS (don't repeat these):\n" + "\n".join(f"- {p}" for p in previous_posts))
    return "\n\n".join(parts)


def _clean(text: str) -> str:
    text = text.strip().strip('"').strip()
    text = re.sub(r"^«claude»\s*", "", text)
    text = re.sub(r"https?://\S+", "", text)
    text = " ".join(text.split())
    return text


def with_prefix(text: str) -> str:
    text = text.strip()
    if not text.startswith("«claude»"):
        text = PREFIX + text
    return text[:MAX_CHAT_CHARS]


def generate_recurring_message(
    base_message: str,
    context: str = "",
    stream_info: dict | None = None,
    recent_chat: list[tuple[str, str]] | None = None,
    previous_posts: list[str] | None = None,
    client: anthropic.Anthropic | None = None,
) -> tuple[str, bool]:
    """Write one recurring post. Returns (message_with_prefix, was_generated).

    Falls back to the static base message (was_generated=False) on any error.
    """
    fallback = with_prefix(base_message)
    try:
        if client is None:
            api_key = os.getenv("ANTHROPIC_API_KEY")
            if not api_key:
                raise ValueError("ANTHROPIC_API_KEY not set")
            client = anthropic.Anthropic(api_key=api_key)
        prompt = _build_prompt(
            base_message, context, stream_info, recent_chat or [], previous_posts or []
        )
        resp = client.messages.create(
            model=MODEL,
            max_tokens=MAX_TOKENS,
            system=SYSTEM_PROMPT,
            messages=[{"role": "user", "content": prompt}],
        )
        text = "".join(b.text for b in resp.content if getattr(b, "type", "") == "text")
        text = _clean(text)
        if not text:
            raise ValueError("empty generation")
        return with_prefix(text), True
    except Exception as e:
        logger.warning(f"Dynamic recurring message failed, using static text: {e}")
        return fallback, False
