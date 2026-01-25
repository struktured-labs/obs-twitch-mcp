---
layout: default
title: Home
---

# OBS + Twitch MCP Server

**Give Claude full control of your stream.** This MCP server connects Claude directly to OBS Studio, Twitch, and YouTube - letting you manage your entire stream through natural conversation.

No more clicking through menus. Just tell Claude what you want.

## Quick Links

- [Getting Started Guide](guides/getting-started.md) - Install and configure in 15 minutes
- [Automation Guide](guides/automation.md) - Auto-welcome, scheduled messages, hype detection
- [Full Tool Reference](guides/tool-reference.md) - All 118 tools documented
- [Translation Guide](guides/translation.md) - Experimental game translation feature

---

## What Makes This Different?

### Deep Platform Integration

This isn't just a chat bot. Claude gets direct API access to control your entire streaming setup:

**OBS Studio** - Full WebSocket control:
- Scene switching, source visibility, audio levels
- Real-time filter adjustments (no OBS restart needed)
- Recording, replay buffer, screenshots
- Text overlays, browser sources, media playback

**Twitch** - Complete API access:
- Chat: send messages, read history, reply to viewers
- Moderation: ban, timeout, slow mode, emote-only
- Stream info: update title, game, create polls
- Raids: find targets, start raids, shoutouts with clips
- Viewer analytics: track chatters, loyalty, engagement

**YouTube** - Video management:
- Upload recordings with title, description, tags
- List your videos, get video info
- Privacy controls (public, unlisted, private)

### Natural Language Control

Don't memorize commands. Just tell Claude what you want:

| You say... | What happens |
|------------|--------------|
| "I'll be right back" | Scene switches, mic mutes, chat gets notified |
| "Shoutout to that raider" | Profile lookup → personalized message → their clip plays |
| "Clip that!" | Last 30 seconds saved locally |
| "Upload my last recording to YouTube" | Handles the entire upload flow |
| "Set my title to 'Retro Gaming Night'" | Twitch title updates |

### 118 Tools, One Interface

| Category | Tools | Examples |
|----------|-------|----------|
| OBS Control | 31 | Scenes, sources, audio, recording, filters |
| Twitch Chat | 9 | Send, read, reply, history |
| Stream Management | 8 | Title, game, polls, raids |
| Clips & Video | 18 | Local clips, Twitch clips, YouTube upload |
| Viewer Engagement | 11 | Auto-welcome, analytics, lurk tracking |
| Automation | 8 | Reminders, scheduled messages, scene changes |
| Moderation | 7 | Ban, timeout, slow mode |
| Translation | 10 | Manual and automatic (experimental) |
| And more... | 6 | Alerts, health monitoring, chat overlay |

---

## Who Is This For?

**Streamers who:**
- Want AI assistance without giving up control
- Like automation but not complex setups
- Have some technical background (romhacking, tinkering) but aren't necessarily programmers
- Want to control OBS, Twitch, and YouTube from one place

**You'll need:**
- Basic comfort with command line (copy-paste level is fine)
- OBS Studio installed
- Twitch account with API access
- Claude Code (free tier works)

---

## See It In Action

```
You: "Switch to BRB and mute my mic"

Claude: [Calls obs_switch_scene("BRB")]
        [Calls obs_mute("Mic/Aux", true)]

        Done - switched to BRB scene and muted your mic.
```

```
You: "Shoutout to nahnegnal"

Claude: Let me look up their profile and give them a shoutout.
        [Calls get_streamer_profile("nahnegnal")]
        [Calls shoutout_streamer("nahnegnal")]

        Sent shoutout to nahnegnal! They're an affiliate who streams
        retro games. Playing their latest clip on stream now.
```

```
You: "Upload my last recording to YouTube, title it 'Stream Highlights'"

Claude: [Calls list_recordings()]
        [Calls upload_video_to_youtube(...)]

        Uploading stream-2024-01-25.mp4 to YouTube...
        Done! Video is now public: https://youtu.be/...
```

---

## Experimental: Game Translation

For retro game streamers - Claude can OCR Japanese text from your game and show English translations as an overlay. This feature is **experimental** but works reasonably well for dialogue-heavy games. See the [Translation Guide](guides/translation.md) for setup.

---

## Getting Started

Ready to set up? Head to the [Getting Started Guide](guides/getting-started.md).

Or check out the [README](https://github.com/struktured-labs/obs-twitch-mcp#readme) for the quick version.

---

## Support

- **Issues:** [GitHub Issues](https://github.com/struktured-labs/obs-twitch-mcp/issues)
- **Watch it live:** [twitch.tv/struktured](https://twitch.tv/struktured)

Built by [struktured](https://github.com/struktured) for AI-powered stream control.
