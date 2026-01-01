# OBS + Twitch MCP Server

A unified MCP (Model Context Protocol) server for controlling OBS Studio and Twitch, with real-time Japanese game translation support.

## Features

### OBS Control
- Switch scenes, list scenes
- Add/remove text overlays
- Add media sources (video, images, animations)
- Control audio (volume, mute/unmute)
- Capture screenshots

### Twitch Integration
- Send/read chat messages
- Moderation (ban, timeout, unban, slow mode, emote-only)
- Update stream title and game
- Shoutout other streamers with clip overlay

### Real-time Translation
- Capture game screenshots
- OCR Japanese text (via Claude Vision)
- Display English translation overlay

### Alerts
- Follow alerts
- Custom alerts
- Shoutout with clip embed

## Installation

```bash
# Clone and enter directory
cd obs-twitch-mcp

# Install with uv
uv sync
```

## Configuration

Copy `setenv.example.sh` to `setenv.sh` and fill in your credentials:

```bash
cp setenv.example.sh setenv.sh
# Edit setenv.sh with your values
```

Required environment variables:
- `TWITCH_CLIENT_ID` - Twitch app client ID
- `TWITCH_CLIENT_SECRET` - Twitch app client secret
- `TWITCH_OAUTH_TOKEN` - User OAuth token with required scopes
- `TWITCH_CHANNEL` - Your Twitch channel name
- `OBS_WEBSOCKET_PASSWORD` - OBS WebSocket password
- `OBS_WEBSOCKET_PORT` - OBS WebSocket port (default: 4455)

## Usage with Claude Code

Add to `~/.claude/settings.json`:

```json
{
  "mcpServers": {
    "obs-twitch": {
      "command": "uv",
      "args": ["run", "--directory", "/path/to/obs-twitch-mcp", "python", "-m", "src.server"],
      "env": {
        "TWITCH_CLIENT_ID": "your_client_id",
        "TWITCH_CLIENT_SECRET": "your_secret",
        "TWITCH_OAUTH_TOKEN": "oauth:your_token",
        "TWITCH_CHANNEL": "your_channel",
        "OBS_WEBSOCKET_PASSWORD": "your_password"
      }
    }
  }
}
```

## Available Tools

### OBS Tools
- `obs_list_scenes` - List all scenes
- `obs_switch_scene` - Switch to a scene
- `obs_add_text_overlay` - Add text to scene
- `obs_remove_source` - Remove a source
- `obs_set_volume` - Set audio volume
- `obs_mute` - Mute/unmute audio
- `obs_screenshot` - Capture screenshot
- `obs_add_browser_source` - Add web content
- `obs_add_media_source` - Add video/audio

### Twitch Tools
- `twitch_send_message` - Send chat message
- `twitch_get_stream_info` - Get stream status
- `twitch_set_stream_title` - Update title
- `twitch_set_stream_game` - Update game/category

### Moderation Tools
- `twitch_ban_user` - Ban a user
- `twitch_timeout_user` - Timeout a user
- `twitch_unban_user` - Unban a user
- `twitch_slow_mode` - Enable/disable slow mode
- `twitch_emote_only` - Toggle emote-only
- `twitch_subscriber_only` - Toggle sub-only

### Translation Tools
- `translate_screenshot` - Capture for translation
- `translate_and_overlay` - Show translation on OBS
- `clear_translation_overlay` - Remove translation

### Alert Tools
- `show_follow_alert` - Display follow alert
- `show_custom_alert` - Display custom alert
- `shoutout_streamer` - Shoutout with clip

## License

MIT
