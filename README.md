# OBS + Twitch MCP Server

**Let AI control your stream.** This MCP (Model Context Protocol) server gives Claude direct control over OBS Studio and Twitch, enabling voice-commanded scene switches, automatic Japanese game translation, smart shoutouts, and 100+ streaming tools.

Built for streamers who play retro Japanese games, do romhacking, or want AI-assisted stream management.

---

## What Can It Do?

### Talk to Your Stream
Tell Claude what you want, and it happens:
- *"Switch to my BRB scene"* → Scene changes, mic mutes, camera hides
- *"Shoutout to nahnegnal"* → Personalized message + their clip plays on screen
- *"I'm back"* → Unmutes, shows camera, welcomes you back in chat
- *"Clip that!"* → Saves last 30 seconds locally

### Real-Time Game Translation
Playing a Japan-only game? Claude watches your screen and translates dialogue automatically:
- Detects dialogue boxes in retro games (Penta Dragon, Trinea, etc.)
- OCRs Japanese text using Claude Vision
- Shows English translation overlay on stream
- Smart change detection = 60-80% fewer API calls

### Stream Automation
- **Auto-welcome** returning viewers by name
- **Hype detection** auto-clips when chat explodes
- **Scheduled messages** for socials, hydration reminders
- **Raid finder** suggests channels in your category

### 118 Tools Total
Scene control, audio filters, chat moderation, polls, clips, YouTube uploads, viewer analytics, and more.

---

## Quick Start

### Prerequisites

You'll need:
- **OBS Studio** with WebSocket enabled (Tools → WebSocket Server Settings)
- **Python 3.11+**
- **uv** (Python package manager) - [Install uv](https://docs.astral.sh/uv/getting-started/installation/)
- **Claude Code** or another MCP-compatible client
- **Twitch Developer App** (for API access)

### 1. Clone and Install

```bash
# Clone the repo (or download ZIP)
git clone https://github.com/struktured-labs/obs-twitch-mcp.git
cd obs-twitch-mcp

# Install dependencies
uv sync

# Install browser automation (needed for Twitch panel scraping)
uv run playwright install chromium
```

### 2. Set Up Credentials

```bash
# Copy the example config
cp setenv.example.sh setenv.sh

# Edit with your credentials
nano setenv.sh  # or use any text editor
```

<details>
<summary><strong>What credentials do I need?</strong></summary>

| Variable | Where to get it |
|----------|-----------------|
| `TWITCH_CLIENT_ID` | [Twitch Developer Console](https://dev.twitch.tv/console/apps) → Create App |
| `TWITCH_CLIENT_SECRET` | Same place, click "New Secret" |
| `TWITCH_OAUTH_TOKEN` | Run `uv run python auth.py` (opens browser) |
| `TWITCH_CHANNEL` | Your Twitch username |
| `OBS_WEBSOCKET_PASSWORD` | OBS → Tools → WebSocket Server Settings |
| `OBS_WEBSOCKET_PORT` | Usually `4455` (default) |
| `ANTHROPIC_API_KEY` | [Anthropic Console](https://console.anthropic.com/) (for translation) |
| `YOUTUBE_CLIENT_ID` | [Google Cloud Console](https://console.cloud.google.com/) (optional, for uploads) |
| `YOUTUBE_CLIENT_SECRET` | Same place |

</details>

### 3. Configure Claude Code

Add to your `~/.claude/settings.json`:

```json
{
  "mcpServers": {
    "obs-twitch": {
      "command": "bash",
      "args": ["-c", "source /path/to/obs-twitch-mcp/setenv.sh && uv run --directory /path/to/obs-twitch-mcp python -m src.server"]
    }
  }
}
```

Replace `/path/to/obs-twitch-mcp` with your actual path.

<details>
<summary><strong>Windows Setup</strong></summary>

Create a `setenv.bat` file:
```batch
@echo off
set TWITCH_CLIENT_ID=your_client_id
set TWITCH_CLIENT_SECRET=your_secret
set TWITCH_OAUTH_TOKEN=oauth:your_token
set TWITCH_CHANNEL=your_channel
set OBS_WEBSOCKET_PASSWORD=your_password
set OBS_WEBSOCKET_PORT=4455
```

Then in `settings.json`:
```json
{
  "mcpServers": {
    "obs-twitch": {
      "command": "cmd",
      "args": ["/c", "setenv.bat && uv run python -m src.server"],
      "cwd": "C:\\path\\to\\obs-twitch-mcp"
    }
  }
}
```

</details>

### 4. Start Streaming!

1. Launch OBS Studio
2. Start Claude Code: `claude`
3. Try: *"What scene am I on?"* or *"List my OBS scenes"*

---

## Features In-Depth

### OBS Control

**Scenes & Sources**
```
"Switch to my gaming scene"
"Hide the webcam"
"Show the chat overlay"
"Add a text overlay that says 'BRB 5 min'"
```

**Audio**
```
"Mute my mic"
"Set desktop audio to -10 dB"
"Apply the noisy room preset to my mic"  (adjusts noise gate, compressor, etc.)
```

**Recording & Clips**
```
"Start recording"
"Save a clip"  (uses replay buffer - last 30 sec)
"Stop recording and upload to YouTube"
```

### Twitch Integration

**Chat**
```
"Send a message: Thanks for the raid!"
"What are people saying in chat?"
"Reply to nahnegnal and thank them"
```

**Moderation**
```
"Timeout spammer123 for 10 minutes"
"Enable slow mode"
"Ban that bot"
```

**Stream Info**
```
"Change my title to 'Translating Penta Dragon!'"
"Switch game to Retro"
"Create a poll: Should we grind or progress?"
```

**Shoutouts**
```
"Shoutout to cozystreamer"
→ Claude looks up their profile, sees they're a Twitch Partner who streams Castlevania
→ Sends: "Go check out @cozystreamer! They're a verified partner streaming Castlevania - 500K channel views!"
→ Plays their most recent clip on your stream
```

### Game Translation

Perfect for streaming Japan-only games like:
- Penta Dragon (1992 GB RPG)
- Trinea
- Any untranslated retro game

**Manual Mode**
```
"Translate what's on screen"
→ Claude screenshots OBS, OCRs the Japanese, shows English overlay
```

**Automatic Mode** (recommended)
```
"Start the translation service"
→ Monitors every 2 seconds
→ Only translates when dialogue changes (saves API calls)
→ ~300ms latency
→ Auto-detects dialogue box region

"Stop translating"
→ Stops service, clears overlay
```

### Viewer Engagement

**Auto-Welcome**
```
"Enable welcome messages"
→ "Welcome back, nahnegnal!" (if they've been here before)
→ "Welcome to the stream, newviewer!" (first time)
```

**Analytics**
```
"Who are my top chatters today?"
"Show me loyal viewers"  (most sessions across streams)
"Get stats for nahnegnal"
```

**Lurk Support**
```
When viewer types !lurk:
→ Shows custom lurk animation
→ Tracks their lurk in engagement data
```

### Automation

**Scheduled Messages**
```
"Remind chat about my Discord every 30 minutes"
"Set a reminder in 5 minutes to check the chat"
```

**Auto-Clipping**
```
"Enable auto-clip"
→ Monitors chat speed
→ When chat explodes (5+ msg/sec), automatically saves a clip
→ Triggers on hype words: POG, CLIP, OMEGALUL, etc.
```

**Scheduled Scene Changes**
```
"Switch to the ending scene in 2 minutes"
```

### Video Management

**Local Recordings**
```
"List my recordings"
"Trim the last recording - cut the first 30 seconds"
"Censor from 1:30 to 1:45"  (mutes audio, optional blur)
```

**YouTube Uploads**
```
"Upload my last recording to YouTube"
"Title: Penta Dragon Part 3, tags: retro, jrpg, translation"
→ Uploads with metadata, defaults to public
```

---

## Tool Reference

<details>
<summary><strong>OBS Tools (31)</strong></summary>

| Tool | Description |
|------|-------------|
| `obs_list_scenes` | List all scenes |
| `obs_get_current_scene` | Get active scene |
| `obs_switch_scene` | Change scene |
| `obs_get_scene_items` | List items in scene |
| `obs_show_source` | Show/enable source |
| `obs_hide_source` | Hide/disable source |
| `obs_add_text_overlay` | Add text to scene |
| `obs_update_text` | Update text content |
| `obs_remove_source` | Remove source |
| `obs_add_browser_source` | Add web content |
| `obs_add_media_source` | Add video/image |
| `obs_set_volume` | Set volume (dB) |
| `obs_mute` | Mute/unmute |
| `obs_screenshot` | Capture screenshot |
| `obs_get_stats` | Performance stats |
| `obs_list_filters` | List audio/video filters |
| `obs_get_filter` | Get filter settings |
| `obs_update_filter` | Update filter live |
| `obs_enable_filter` | Toggle filter |
| `obs_apply_audio_preset` | Apply preset (noisy/normal/quiet) |
| `obs_replay_buffer_status` | Check replay buffer |
| `obs_start_replay_buffer` | Start buffer |
| `obs_stop_replay_buffer` | Stop buffer |
| `obs_save_replay` | Save buffer to file |
| `obs_clip` | One-command clip |
| `obs_record_status` | Recording status |
| `obs_start_recording` | Start recording |
| `obs_stop_recording` | Stop recording |
| `obs_pause_recording` | Pause |
| `obs_resume_recording` | Resume |
| `start_obs` | Launch OBS |
| `stop_obs` | Close OBS |

</details>

<details>
<summary><strong>Twitch Tools (24)</strong></summary>

| Tool | Description |
|------|-------------|
| `twitch_send_message` | Send chat message |
| `twitch_reply_to_user` | Reply with @mention |
| `twitch_get_recent_messages` | Recent chat messages |
| `twitch_get_chat_history` | Historical logs |
| `twitch_get_stream_info` | Title, game, viewers |
| `twitch_set_stream_title` | Update title |
| `twitch_set_stream_game` | Change category |
| `twitch_search_game` | Search games |
| `twitch_create_poll` | Create poll |
| `twitch_end_poll` | End poll |
| `twitch_get_polls` | Get polls |
| `twitch_raid` | Start raid |
| `twitch_cancel_raid` | Cancel raid |
| `twitch_find_raid_targets` | Suggest raid targets |
| `twitch_ban_user` | Ban user |
| `twitch_timeout_user` | Timeout user |
| `twitch_unban_user` | Unban |
| `twitch_slow_mode` | Toggle slow mode |
| `twitch_emote_only` | Toggle emote-only |
| `twitch_subscriber_only` | Toggle sub-only |
| `twitch_clear_chat` | Clear chat |
| `twitch_create_clip` | Create Twitch clip |
| `twitch_get_clip_info` | Get clip details |
| `twitch_get_my_clips` | List channel clips |

</details>

<details>
<summary><strong>Translation Tools (10)</strong></summary>

| Tool | Description |
|------|-------------|
| `translate_screenshot` | Manual translate |
| `translate_and_overlay` | Show translation |
| `clear_translation_overlay` | Remove overlay |
| `get_last_translation` | Last translated text |
| `translation_service_start` | Start auto-translate |
| `translation_service_stop` | Stop service |
| `translation_service_status` | Service stats |
| `translation_service_configure` | Update settings |
| `translation_service_reset` | Reset service |
| `translation_service_force_translate` | Force immediate |

</details>

<details>
<summary><strong>Shoutout & Profile Tools (6)</strong></summary>

| Tool | Description |
|------|-------------|
| `shoutout_streamer` | Smart shoutout + clip |
| `clear_shoutout_clip` | Remove clip |
| `get_streamer_profile` | Full profile data |
| `get_streamer_channel_info` | Current game/title |
| `get_streamer_clips` | Streamer's clips |
| `get_streamer_panels` | Channel panels |

</details>

<details>
<summary><strong>Engagement & Analytics (11)</strong></summary>

| Tool | Description |
|------|-------------|
| `enable_welcome_messages` | Auto-welcome on |
| `disable_welcome_messages` | Auto-welcome off |
| `set_welcome_threshold` | Welcome-back timing |
| `get_viewer_stats` | Individual stats |
| `get_top_chatters` | Most active |
| `get_loyal_viewers` | Most sessions |
| `get_session_summary` | Current session |
| `reset_session` | Reset tracking |
| `export_engagement_data` | Export all data |
| `show_lurk_animation` | Lurk overlay |
| `hide_lurk_animation` | Hide lurk |

</details>

<details>
<summary><strong>Automation & Scheduling (8)</strong></summary>

| Tool | Description |
|------|-------------|
| `set_reminder` | One-time reminder |
| `set_recurring_message` | Repeating message |
| `schedule_scene_change` | Timed scene switch |
| `list_scheduled_actions` | View scheduled |
| `cancel_scheduled_action` | Cancel action |
| `pause_scheduled_action` | Pause action |
| `resume_scheduled_action` | Resume action |
| `clear_all_scheduled_actions` | Cancel all |

</details>

<details>
<summary><strong>Video & Upload Tools (13)</strong></summary>

| Tool | Description |
|------|-------------|
| `list_recordings` | Find video files |
| `get_recording_info` | Video metadata |
| `trim_video` | Trim with ffmpeg |
| `censor_video_segment` | Mute/blur segment |
| `upload_video` | Generic upload |
| `upload_video_to_youtube` | YouTube upload |
| `upload_recording` | Upload with trim |
| `get_my_youtube_videos` | Your YT videos |
| `get_youtube_video_info` | YT video details |
| `delete_youtube_video` | Delete from YT |
| `get_my_twitch_videos` | Your VODs |
| `get_twitch_video_info` | VOD details |
| `play_clip_on_stream` | Show clip on stream |

</details>

<details>
<summary><strong>Other Tools</strong></summary>

**Alerts (3)**
- `show_follow_alert`, `show_custom_alert`, `clear_all_alerts`

**Chat Overlay (6)**
- `show_chat_overlay`, `hide_chat_overlay`, `remove_chat_overlay`
- `configure_chat_filter`, `get_chat_overlay_status`, `list_chat_themes`

**Auto-Clip (7)**
- `enable_autoclip`, `disable_autoclip`, `get_autoclip_stats`
- `set_autoclip_threshold`, `set_autoclip_cooldown`
- `add_hype_keyword`, `list_hype_keywords`

**Health Monitoring (4)**
- `get_stream_health`, `get_stream_bitrate`, `get_disk_space`, `alert_if_unhealthy`

**Chat Commands (3)**
- `handle_chat_command`, `list_commands`, `toggle_command`

</details>

---

## Chat Overlay Themes

Three built-in themes for displaying live chat on stream:

| Theme | Style | Best For |
|-------|-------|----------|
| `retro` | CRT scanlines, neon glow, pixel font | Retro game streams |
| `jrpg` | RPG dialogue box style, pixel art | JRPG playthroughs |
| `minimal` | Clean, modern, semi-transparent | Any stream |

```
"Show the chat overlay with retro theme"
"Put chat in the bottom left"
```

---

## Troubleshooting

### "Tool not found" or MCP won't connect

1. Make sure OBS is running with WebSocket enabled
2. Check your `setenv.sh` has correct credentials
3. Restart Claude Code after config changes
4. Try: `uv run python -m src.server` directly to see errors

### Twitch token expired

```bash
cd obs-twitch-mcp
uv run python auth.py
# Opens browser for re-authorization
```

### Translation not working

- Need `ANTHROPIC_API_KEY` in setenv.sh
- Check OBS screenshot source is correct
- Try manual: "Translate what's on screen" first

### Panel scraping fails

```bash
# Reinstall Playwright
uv run playwright install chromium
```

Panel scraping is non-fatal - profiles still work, just without panel data.

---

## Project Structure

```
obs-twitch-mcp/
├── src/
│   ├── tools/           # MCP tool implementations
│   │   ├── obs.py       # OBS control (31 tools)
│   │   ├── chat.py      # Twitch chat (9 tools)
│   │   ├── twitch.py    # Stream management (8 tools)
│   │   ├── clips.py     # Clips & recording (18 tools)
│   │   ├── translation.py   # Game translation (10 tools)
│   │   ├── shoutout.py  # Shoutouts & profiles (6 tools)
│   │   ├── engagement.py    # Viewer analytics (8 tools)
│   │   ├── scheduler.py # Automation (8 tools)
│   │   └── ...more
│   ├── utils/           # Client implementations
│   │   ├── obs_client.py
│   │   ├── twitch_client.py
│   │   ├── youtube_client.py
│   │   ├── vision_client.py      # Claude Vision OCR
│   │   ├── translation_service.py
│   │   └── ...more
│   └── server.py        # MCP server entry point
├── assets/              # HTML overlays & animations
│   ├── chat-overlay/    # Chat themes (retro, jrpg, minimal)
│   ├── lurk-animation.html
│   └── ...40+ custom overlays
├── data/                # Persistent data (viewer stats)
├── setenv.example.sh    # Credential template
└── pyproject.toml       # Dependencies
```

---

## Platform Support

| Platform | Status | Notes |
|----------|--------|-------|
| Linux | ✅ Full | Primary development platform |
| macOS | ✅ Full | Tested |
| Windows | ⚠️ 90% | Need `setenv.bat` instead of `.sh` |

---

## Contributing

This is primarily a personal streaming tool, but issues and PRs are welcome!

**Repository:** [github.com/struktured-labs/obs-twitch-mcp](https://github.com/struktured-labs/obs-twitch-mcp)

---

## Security Notes

- **Never commit `setenv.sh`** - it contains your API keys
- Token files (`.twitch_token.json`, `.youtube_token.json`) are gitignored
- Chat messages from Claude are prefixed with `«claude»` so viewers know it's AI

---

## License

MIT

---

## Credits

Built by [struktured](https://twitch.tv/struktured) for streaming retro Japanese games with real-time translation.

Uses:
- [obsws-python](https://github.com/aatikturk/obsws-python) - OBS WebSocket
- [twitchAPI](https://github.com/Teekeks/pyTwitchAPI) - Twitch integration
- [Claude Vision](https://anthropic.com) - OCR and translation
- [Playwright](https://playwright.dev) - Browser automation
