---
layout: default
title: Tool Reference
---

# Complete Tool Reference

All 118 tools available in OBS + Twitch MCP Server, organized by category.

---

## OBS Control (31 tools)

### Scene Management

| Tool | Parameters | Description |
|------|------------|-------------|
| `obs_list_scenes` | - | List all available scenes |
| `obs_get_current_scene` | - | Get the currently active scene |
| `obs_switch_scene` | `scene_name` | Switch to a specific scene |

### Source & Item Management

| Tool | Parameters | Description |
|------|------------|-------------|
| `obs_get_scene_items` | `scene_name` | List all items in a scene |
| `obs_list_inputs` | - | List all registered input sources |
| `obs_cleanup_inputs` | `prefix` | Remove sources matching name prefix |
| `obs_show_source` | `source_name`, `scene_name?` | Show/enable a source |
| `obs_hide_source` | `source_name`, `scene_name?` | Hide/disable a source |
| `obs_add_existing_source` | `source_name`, `scene_name`, `enabled?` | Add existing source to scene |
| `obs_edit_source` | `source_name`, `settings` | Update source settings |
| `obs_get_source_settings` | `source_name` | Get source configuration |
| `obs_remove_source` | `source_name` | Remove a source completely |

### Text Overlays

| Tool | Parameters | Description |
|------|------------|-------------|
| `obs_add_text_overlay` | `text`, `source_name?`, `font_size?`, `color?`, `position_x?`, `position_y?` | Add text to scene |
| `obs_update_text` | `source_name`, `text` | Update existing text content |

### Media Sources

| Tool | Parameters | Description |
|------|------------|-------------|
| `obs_add_browser_source` | `url`, `source_name?`, `width?`, `height?` | Add web content (HTML, iframe) |
| `obs_add_media_source` | `file_path`, `source_name?`, `loop?` | Add video, audio, or image |

### Audio Control

| Tool | Parameters | Description |
|------|------------|-------------|
| `obs_set_volume` | `source_name`, `volume_db` | Set volume (-100 to 0 dB) |
| `obs_mute` | `source_name`, `muted` | Mute or unmute audio source |

### Audio Filters (Real-time, no restart needed)

| Tool | Parameters | Description |
|------|------------|-------------|
| `obs_list_filters` | `source_name` | List all filters on a source |
| `obs_get_filter` | `source_name`, `filter_name` | Get filter settings |
| `obs_update_filter` | `source_name`, `filter_name`, `settings` | Update filter settings live |
| `obs_enable_filter` | `source_name`, `filter_name`, `enabled` | Toggle filter on/off |
| `obs_apply_audio_preset` | `source_name`, `preset` | Apply preset: `noisy`, `normal`, or `quiet` |

### Monitoring & Capture

| Tool | Parameters | Description |
|------|------------|-------------|
| `obs_screenshot` | `source_name?` | Capture screenshot as base64 PNG |
| `obs_get_stats` | - | Get OBS performance stats (CPU, FPS, dropped frames) |

### Recording

| Tool | Parameters | Description |
|------|------------|-------------|
| `obs_record_status` | - | Get recording status |
| `obs_start_recording` | - | Start recording |
| `obs_stop_recording` | - | Stop recording (returns file path) |
| `obs_pause_recording` | - | Pause recording |
| `obs_resume_recording` | - | Resume recording |

### Replay Buffer (Local Clips)

| Tool | Parameters | Description |
|------|------------|-------------|
| `obs_replay_buffer_status` | - | Check if replay buffer is active |
| `obs_start_replay_buffer` | - | Start replay buffer |
| `obs_stop_replay_buffer` | - | Stop replay buffer |
| `obs_save_replay` | - | Save replay buffer to file |
| `obs_clip` | - | One-command clip (starts buffer if needed, saves) |

### Process Management

| Tool | Parameters | Description |
|------|------------|-------------|
| `start_obs` | `custom_command?`, `env_vars?`, `wait?` | Launch OBS |
| `stop_obs` | `force?`, `graceful_timeout?` | Close OBS |
| `restart_obs` | `custom_command?`, `env_vars?`, `force?` | Restart OBS |
| `get_obs_process_status` | - | Check if OBS is running |

---

## Twitch Chat (9 tools)

| Tool | Parameters | Description |
|------|------------|-------------|
| `twitch_send_message` | `message` | Send message to chat |
| `twitch_reply_to_user` | `username`, `message` | Reply with @mention |
| `twitch_get_recent_messages` | `count?` | Get cached recent messages |
| `twitch_get_chat_history` | `date?`, `limit?` | Get logged messages by date |
| `twitch_list_chat_log_dates` | - | List available chat log dates |
| `twitch_refresh_token` | - | Refresh Twitch client token |
| `twitch_reconnect` | - | Full reconnect (token + chat listener) |
| `twitch_reauth` | - | Start OAuth device flow |
| `twitch_reauth_status` | - | Check auth status |

---

## Twitch Stream Management (8 tools)

### Stream Info

| Tool | Parameters | Description |
|------|------------|-------------|
| `twitch_get_stream_info` | - | Get title, game, viewers, start time |
| `twitch_set_stream_title` | `title` | Update stream title |
| `twitch_set_stream_game` | `game_name` | Change game/category |
| `twitch_search_game` | `query` | Search for game by name |

### Polls

| Tool | Parameters | Description |
|------|------------|-------------|
| `twitch_create_poll` | `title`, `choices`, `duration?` | Create live poll |
| `twitch_end_poll` | `poll_id`, `show_results?` | End poll early |
| `twitch_get_polls` | - | Get active/recent polls |

### Raids

| Tool | Parameters | Description |
|------|------------|-------------|
| `twitch_raid` | `username` | Start raid to channel |
| `twitch_cancel_raid` | - | Cancel ongoing raid |
| `twitch_find_raid_targets` | `category?`, `count?` | Find raid targets in same category |

---

## Moderation (7 tools)

| Tool | Parameters | Description |
|------|------------|-------------|
| `twitch_ban_user` | `username`, `reason?` | Permanently ban user |
| `twitch_timeout_user` | `username`, `duration_seconds?`, `reason?` | Timeout user (default 10 min) |
| `twitch_unban_user` | `username` | Unban user |
| `twitch_slow_mode` | `seconds` | Enable slow mode (0 = disable) |
| `twitch_emote_only` | `enabled` | Toggle emote-only mode |
| `twitch_subscriber_only` | `enabled` | Toggle sub-only mode |
| `twitch_clear_chat` | - | Clear all chat messages |

---

## Clips & Recording (18 tools)

### Twitch Clips

| Tool | Parameters | Description |
|------|------------|-------------|
| `twitch_create_clip` | `has_delay?` | Create ~30s clip from live stream |
| `twitch_get_clip_info` | `clip_id` | Get clip details |
| `twitch_get_my_clips` | `count?` | Get recent clips from channel |

### Clip Playback

| Tool | Parameters | Description |
|------|------------|-------------|
| `play_clip_on_stream` | `clip_url`, `source_name?`, `duration_seconds?` | Display clip on stream |
| `stop_clip_playback` | `source_name?` | Stop clip playback |
| `capture_clip_frame` | `source_name?` | Capture frame for analysis |
| `analyze_and_comment_clip` | `description` | Send clip analysis to chat |

---

## Video & Upload (13 tools)

### Local Recordings

| Tool | Parameters | Description |
|------|------------|-------------|
| `list_recordings` | `count?`, `pattern?` | Scan for video files with metadata |
| `get_recording_info` | `file_path` | Get video duration, codec, size |
| `trim_video` | `input_path`, `output_path?`, `start_time?`, `end_time?`, `duration?` | Trim with ffmpeg |
| `censor_video_segment` | `input_path`, `start_time`, `end_time`, `output_path?`, `mode?` | Mute audio, blur, or blackout |

### YouTube

| Tool | Parameters | Description |
|------|------------|-------------|
| `upload_video_to_youtube` | `file_path`, `title`, `description?`, `tags?`, `privacy?` | Upload to YouTube |
| `get_my_youtube_videos` | `count?` | Get your YouTube channel videos |
| `get_youtube_video_info` | `video_id` | Get video details |
| `delete_youtube_video` | `video_id` | Delete from YouTube |
| `upload_recording` | `file_path`, `title`, `description?`, `tags?`, `privacy?`, `trim_start?`, `trim_end?` | Upload with optional trim |

### Twitch VODs

| Tool | Parameters | Description |
|------|------------|-------------|
| `get_my_twitch_videos` | `count?` | Get VODs from channel |
| `get_twitch_video_info` | `video_id` | Get VOD details |

### Generic

| Tool | Parameters | Description |
|------|------------|-------------|
| `upload_video` | `file_path`, `platform`, `title`, `description?` | Route to platform-specific upload |

---

## Translation (10 tools)

### Manual Translation

| Tool | Parameters | Description |
|------|------------|-------------|
| `translate_screenshot` | - | Capture OBS screenshot for translation |
| `translate_and_overlay` | `japanese_text`, `english_text`, `position?`, `font_size?`, `duration_seconds?` | Display translation overlay |
| `clear_translation_overlay` | `duration_seconds?`, `style?` | Remove overlay with animation |
| `get_last_translation` | - | Get last translated text |

### Automatic Service

| Tool | Parameters | Description |
|------|------------|-------------|
| `translation_service_start` | `poll_interval?`, `change_threshold?`, `auto_detect?` | Start auto-translation |
| `translation_service_stop` | `clear_overlay?` | Stop service |
| `translation_service_status` | - | Get stats (API calls, efficiency %) |
| `translation_service_configure` | `poll_interval?`, `change_threshold?`, ... | Update settings while running |
| `translation_service_reset` | - | Reset service instance |
| `translation_service_force_translate` | - | Force immediate translation |

---

## Shoutouts & Profiles (6 tools)

| Tool | Parameters | Description |
|------|------------|-------------|
| `shoutout_streamer` | `username`, `show_clip?`, `duration_seconds?`, `custom_message?`, `use_profile_data?` | Smart shoutout with clip |
| `clear_shoutout_clip` | - | Remove clip overlay |
| `get_streamer_profile` | `username` | Full profile (bio, type, views, panels) |
| `get_streamer_channel_info` | `username` | Current game, title, language |
| `get_streamer_clips` | `username`, `count?` | Streamer's recent clips |
| `get_streamer_panels` | `username` | Channel panels (Playwright-scraped) |

---

## Viewer Engagement (11 tools)

### Auto-Welcome

| Tool | Parameters | Description |
|------|------------|-------------|
| `enable_welcome_messages` | - | Enable auto-welcome |
| `disable_welcome_messages` | - | Disable auto-welcome |
| `set_welcome_threshold` | `minutes` | Set "welcome back" threshold |

### Analytics

| Tool | Parameters | Description |
|------|------------|-------------|
| `get_viewer_stats` | `username` | Individual viewer stats |
| `get_top_chatters` | `count?` | Most active chatters |
| `get_loyal_viewers` | `count?` | Most sessions across streams |
| `get_session_summary` | - | Current stream session stats |
| `reset_session` | - | Reset per-session tracking |
| `export_engagement_data` | - | Export all viewer data |

### Lurk

| Tool | Parameters | Description |
|------|------------|-------------|
| `show_lurk_animation` | `username`, `duration_seconds?` | Display lurk animation |
| `hide_lurk_animation` | - | Hide immediately |

---

## Automation & Scheduling (8 tools)

| Tool | Parameters | Description |
|------|------------|-------------|
| `set_reminder` | `message`, `minutes` | One-time reminder to chat |
| `set_recurring_message` | `message`, `interval_minutes`, `max_times?` | Recurring chat messages |
| `schedule_scene_change` | `scene_name`, `minutes` | Timed scene switch |
| `list_scheduled_actions` | - | View all scheduled tasks |
| `cancel_scheduled_action` | `action_id` | Cancel specific action |
| `pause_scheduled_action` | `action_id` | Pause without canceling |
| `resume_scheduled_action` | `action_id` | Resume paused action |
| `clear_all_scheduled_actions` | - | Cancel all |

---

## Alerts (3 tools)

| Tool | Parameters | Description |
|------|------------|-------------|
| `show_follow_alert` | `username`, `message?`, `duration_seconds?` | Display follower alert |
| `show_custom_alert` | `title`, `subtitle?`, `color?`, `duration_seconds?`, `position?` | Custom alert overlay |
| `clear_all_alerts` | - | Remove all active alerts |

---

## Chat Overlay (6 tools)

| Tool | Parameters | Description |
|------|------------|-------------|
| `show_chat_overlay` | `theme?`, `position?`, `width?`, `height?`, `fade_seconds?`, ... | Display live chat on stream |
| `hide_chat_overlay` | - | Hide overlay |
| `remove_chat_overlay` | - | Remove source completely |
| `configure_chat_filter` | `block_spam?`, `block_bots?`, `block_links?`, ... | Message filtering |
| `get_chat_overlay_status` | - | Check overlay status |
| `list_chat_themes` | - | Available themes: retro, jrpg, minimal |

---

## Auto-Clip Detection (7 tools)

| Tool | Parameters | Description |
|------|------------|-------------|
| `enable_autoclip` | - | Start hype moment detection |
| `disable_autoclip` | - | Stop detection |
| `get_autoclip_stats` | - | View detection stats |
| `set_autoclip_threshold` | `messages_per_second` | Adjust sensitivity |
| `set_autoclip_cooldown` | `seconds` | Set minimum clip spacing |
| `add_hype_keyword` | `keyword` | Add custom trigger |
| `list_hype_keywords` | - | View active keywords |

---

## Health Monitoring (4 tools)

| Tool | Parameters | Description |
|------|------------|-------------|
| `get_stream_health` | - | Comprehensive health status |
| `get_stream_bitrate` | - | Current bitrate info |
| `get_disk_space` | - | Disk usage breakdown |
| `alert_if_unhealthy` | `auto_fix?` | Health check with optional auto-fix |

---

## Chat Commands (3 tools)

| Tool | Parameters | Description |
|------|------------|-------------|
| `handle_chat_command` | `username`, `message` | Process chat commands |
| `list_commands` | - | View available commands |
| `toggle_command` | `command_name`, `enabled` | Enable/disable command |
| `set_command_cooldown` | `command_name`, `cooldown_seconds` | Set cooldown |

---

## Built-in Chat Commands

| Command | Description |
|---------|-------------|
| `!clip` | Create local clip |
| `!uptime` | Stream uptime |
| `!lurk` | Lurk animation |
| `!song` | Current song (if configured) |
