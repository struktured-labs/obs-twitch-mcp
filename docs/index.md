---
layout: default
title: Home
---

# OBS + Twitch MCP Server

**Let AI control your stream.** Give Claude direct control over OBS Studio and Twitch for voice-commanded scene switches, automatic Japanese game translation, smart shoutouts, and 100+ streaming tools.

## Quick Links

- [Getting Started Guide](guides/getting-started.md) - Install and configure in 15 minutes
- [Translation Guide](guides/translation.md) - Set up real-time Japanese game translation
- [Automation Guide](guides/automation.md) - Auto-welcome, scheduled messages, hype detection
- [Full Tool Reference](guides/tool-reference.md) - All 118 tools documented

---

## What Makes This Different?

### Natural Language Control
Don't memorize commands. Just tell Claude what you want:

| You say... | What happens |
|------------|--------------|
| "I'll be right back" | Scene switches, mic mutes, chat gets notified |
| "Shoutout to that person who just raided" | Profile lookup → personalized message → their clip plays |
| "Translate this" | Screenshot → OCR → English overlay appears |
| "Clip that!" | Last 30 seconds saved locally |

### Built for Retro Game Streamers
Playing untranslated Japanese games? This tool was made for you:

- **Real-time translation** with Claude Vision OCR
- **Smart dialogue detection** - only translates when text changes
- **60-80% fewer API calls** through change detection
- **~300ms latency** - fast enough for streaming

### 118 Tools, One Interface
Everything you need:

| Category | Tools | Examples |
|----------|-------|----------|
| OBS Control | 31 | Scenes, sources, audio, recording, filters |
| Twitch Chat | 9 | Send, read, reply, history |
| Stream Management | 8 | Title, game, polls, raids |
| Translation | 10 | Manual, automatic, overlays |
| Clips & Video | 18 | Local clips, Twitch clips, YouTube upload |
| Viewer Engagement | 11 | Auto-welcome, analytics, lurk tracking |
| Automation | 8 | Reminders, scheduled messages, scene changes |
| Moderation | 7 | Ban, timeout, slow mode |
| And more... | 16 | Alerts, health monitoring, chat overlay |

---

## Who Is This For?

**Streamers who:**
- Play Japanese-only retro games and want live translation
- Want AI assistance without giving up control
- Like automation but not complex setups
- Have technical background (romhacking, coding) but aren't necessarily programmers

**You'll need:**
- Basic comfort with command line (copy-paste level is fine)
- OBS Studio installed
- Twitch account with API access
- Claude Code (free tier works)

---

## See It In Action

```
You: "Start the translation service and switch to my gaming scene"

Claude: I'll start the automatic translation and switch scenes.
        [Starts translation_service_start]
        [Calls obs_switch_scene("Gaming")]

        Translation service is now running - monitoring every 2 seconds.
        Switched to Gaming scene. Ready to stream!
```

```
You: "Shoutout to nahnegnal"

Claude: Let me look up their profile and give them a shoutout.
        [Calls get_streamer_profile("nahnegnal")]
        [Calls shoutout_streamer("nahnegnal")]

        Sent shoutout to nahnegnal! They're an affiliate who streams
        retro games. Playing their latest clip on stream now.
```

---

## Getting Started

Ready to set up? Head to the [Getting Started Guide](guides/getting-started.md).

Or check out the [README](https://github.com/struktured-labs/obs-twitch-mcp#readme) for the quick version.

---

## Support

- **Issues:** [GitHub Issues](https://github.com/struktured-labs/obs-twitch-mcp/issues)
- **Watch it live:** [twitch.tv/struktured](https://twitch.tv/struktured)

Built by [struktured](https://github.com/struktured) for streaming retro Japanese games with real-time translation.
