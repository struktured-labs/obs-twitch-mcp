"""Tests for dynamic / live-only recurring chat messages (no network)."""

from datetime import datetime
from types import SimpleNamespace

from src.tools import scheduler
from src.utils import recurring_ai
from src.utils.twitch_client import ChatMessage


class FakeTwitch:
    def __init__(self, live=True, chat=None, live_raises=False):
        self.live = live
        self.chat = chat or []
        self.live_raises = live_raises
        self.sent = []

    def get_stream_info(self):
        if self.live_raises:
            raise RuntimeError("helix down")
        return {"title": "F13 on SNES", "game_name": "Friday the 13th"} if self.live else None

    def get_recent_messages(self, count=10):
        return self.chat[-count:]

    def send_chat_message(self, msg):
        self.sent.append(msg)


class FakeClient:
    def __init__(self, reply="Jason's lurking near cabin 3. Ask me anything with !ask", raises=False):
        self.reply = reply
        self.raises = raises
        self.prompts = []
        self.messages = self

    def create(self, **kw):
        if self.raises:
            raise RuntimeError("api down")
        self.prompts.append(kw["messages"][0]["content"])
        return SimpleNamespace(content=[SimpleNamespace(type="text", text=self.reply)])


def _action(**data):
    base = {"message": "Ask me anything with !ask"}
    base.update(data)
    return scheduler.ScheduledAction(
        id="t", name="Recurring: t", action_type="message",
        next_run=datetime.now(), interval_seconds=600, data=base,
    )


def test_static_message_posts_unchanged():
    tw = FakeTwitch()
    assert scheduler._compose_message_post(_action(), tw) == "Ask me anything with !ask"


def test_offline_skips_and_counts_skip(monkeypatch):
    tw = FakeTwitch(live=False)
    monkeypatch.setattr(scheduler, "get_twitch_client", lambda: tw)
    a = _action(only_when_live=True)
    scheduler._run_action(a)
    assert tw.sent == [] and a.run_count == 0 and a.data["skipped_offline"] == 1


def test_offline_control_posts_when_not_live_only(monkeypatch):
    tw = FakeTwitch(live=False)
    monkeypatch.setattr(scheduler, "get_twitch_client", lambda: tw)
    a = _action(only_when_live=False)
    scheduler._run_action(a)
    assert tw.sent == ["Ask me anything with !ask"] and a.run_count == 1


def test_live_check_error_posts_anyway():
    tw = FakeTwitch(live_raises=True)
    assert scheduler._compose_message_post(_action(only_when_live=True), tw) is not None


def test_dynamic_uses_llm_with_chat_and_history(monkeypatch):
    fake = FakeClient()
    real = recurring_ai.generate_recurring_message
    monkeypatch.setattr(
        recurring_ai, "generate_recurring_message",
        lambda **kw: real(client=fake, **kw),
    )
    chat = [
        ChatMessage(username="viewer1", message="where is jason"),
        ChatMessage(username="struktured", message="«claude» old post"),
    ]
    tw = FakeTwitch(chat=chat)
    a = _action(dynamic=True, only_when_live=True, context="MnG MSU-1 port, rumble mod")
    out = scheduler._compose_message_post(a, tw)
    assert out.startswith("«claude» ") and "!ask" in out
    assert a.data["last_generated"] is True and a.data["history"] == [out]
    p = fake.prompts[0]
    assert "viewer1: where is jason" in p and "old post" not in p
    assert "rumble mod" in p and "Friday the 13th" in p
    scheduler._compose_message_post(a, tw)
    assert out in fake.prompts[1]  # previous post fed back to avoid repeats


def test_dynamic_falls_back_to_static_on_error(monkeypatch):
    fake = FakeClient(raises=True)
    real = recurring_ai.generate_recurring_message
    monkeypatch.setattr(
        recurring_ai, "generate_recurring_message",
        lambda **kw: real(client=fake, **kw),
    )
    a = _action(dynamic=True)
    out = scheduler._compose_message_post(a, FakeTwitch())
    assert out == "«claude» Ask me anything with !ask" and a.data["last_generated"] is False


def test_clean_strips_prefix_quotes_urls_and_caps_length():
    assert recurring_ai._clean('"«claude» hi https://x.y there"') == "hi there"
    assert len(recurring_ai.with_prefix("x" * 900)) == recurring_ai.MAX_CHAT_CHARS
