---
layout: default
title: Automation Guide
---

# Stream Automation

Let Claude handle the repetitive stuff while you focus on gaming. This guide covers auto-welcome messages, scheduled reminders, hype detection, and more.

---

## Auto-Welcome Viewers

Greet viewers automatically when they chat for the first time (or return after being away).

### Enable It

```
"Enable welcome messages"
```

Now when someone chats:
- **New viewer:** "Welcome to the stream, username!"
- **Returning viewer:** "Welcome back, username!"

### Customize Threshold

By default, "returning" means they've been gone 30+ minutes. Change it:

```
"Set welcome threshold to 60 minutes"
"Welcome back after 15 minutes away"
```

### Disable

```
"Disable welcome messages"
```

---

## Scheduled Messages

Remind chat about your Discord, socials, or hydration on a schedule.

### One-Time Reminder

```
"Remind chat to follow in 10 minutes"
"Set a reminder: 'Taking a short break!' in 5 minutes"
```

### Recurring Messages

```
"Remind chat about my Discord every 30 minutes"
"Post 'Remember to stay hydrated!' every 45 minutes"
"Send my social links every hour, up to 3 times"
```

### Manage Scheduled Actions

```
"What's scheduled?"
"List scheduled actions"
```

Shows all pending reminders and recurring messages.

```
"Cancel the Discord reminder"
"Pause the hydration reminder"
"Resume the hydration reminder"
"Clear all scheduled actions"
```

---

## Scheduled Scene Changes

Perfect for intros, outros, and breaks.

```
"Switch to the BRB scene in 2 minutes"
"Change to the ending scene in 5 minutes"
```

---

## Hype Detection & Auto-Clipping

Automatically clip when chat goes wild.

### How It Works

1. Monitors chat speed (messages per second)
2. When chat explodes (5+ msg/sec by default), saves a clip
3. Also triggers on hype keywords

### Enable

```
"Enable auto-clip"
```

### Configure Sensitivity

```
"Set auto-clip threshold to 3 messages per second"  (more sensitive)
"Set auto-clip threshold to 8 messages per second"  (less sensitive)
```

### Cooldown (Prevent Spam)

```
"Set auto-clip cooldown to 2 minutes"
```

Prevents clips within 2 minutes of each other.

### Custom Hype Keywords

Default keywords: POG, CLIP, OMEGALUL, LUL, KEKW, etc.

Add your own:

```
"Add hype keyword SHEESH"
"Add hype keyword LETS GO"
```

```
"List hype keywords"
```

### Check Stats

```
"Auto-clip stats"
```

Shows clips made, triggers detected, etc.

### Disable

```
"Disable auto-clip"
```

---

## Viewer Analytics

Track who's chatting and how often.

### Session Stats

```
"Who are my top chatters?"
"Show session summary"
```

### Loyalty Tracking

```
"Who are my most loyal viewers?"  (most sessions across streams)
"Get stats for nahnegnal"
```

Shows:
- Total messages
- Session count
- First/last seen
- Lurk count

### Export Data

```
"Export engagement data"
```

Saves to JSON for external analysis.

### Reset

```
"Reset session stats"  (clears current session, keeps historical)
```

---

## Lurk Support

When viewers type `!lurk`, show them some love.

### Automatic Handling

The `!lurk` command is built-in. When someone types it:
1. Custom animation plays (if configured)
2. Their lurk is tracked in engagement data

### Manual Trigger

```
"Show lurk animation for username"
```

### Hide

```
"Hide the lurk animation"
```

---

## Chat Commands

Built-in viewer commands:

| Command | What it does |
|---------|--------------|
| `!lurk` | Lurk animation + tracking |
| `!clip` | Creates a local clip |
| `!uptime` | Shows stream duration |

### Manage Commands

```
"List commands"
"Disable the clip command"
"Enable the clip command"
"Set clip command cooldown to 30 seconds"
```

---

## Combining Automations

Here's a typical stream setup:

```
You: "Set up for my stream"

Claude: I'll set up your usual automation:

        [Enables welcome messages]
        [Sets recurring Discord reminder every 30 min]
        [Enables auto-clip with 60s cooldown]

        Ready! I'll:
        - Welcome new and returning viewers
        - Remind chat about Discord every 30 minutes
        - Auto-clip hype moments
```

### End of Stream

```
You: "I'm ending the stream"

Claude: [Disables welcome messages]
        [Clears scheduled actions]
        [Disables auto-clip]
        [Gets session summary]

        Stream summary:
        - 45 unique chatters
        - 12 new viewers
        - 3 auto-clips saved
        - Top chatter: nahnegnal (89 messages)
```

---

## Example Automation Flows

### "BRB" Flow

```
You: "BRB 5 minutes"

Claude: [Switches to BRB scene]
        [Mutes mic]
        [Hides camera]
        [Sends chat: "struktured will be back in ~5 minutes!"]
        [Schedules scene change back in 5 minutes]
```

### "I'm Back" Flow

```
You: "I'm back"

Claude: [Switches to main scene]
        [Unmutes mic]
        [Shows camera]
        [Sends chat: "And we're back!"]
```

### Raid Incoming

```
[Chat explodes with raid messages]

Claude: Detected incoming raid! Auto-clip triggered.
        [Saves clip]

You: "Shoutout the raider"

Claude: [Looks up raid leader profile]
        [Sends personalized shoutout]
        [Plays their clip on stream]
```

---

## Tips

### Don't Over-Automate

- Too many scheduled messages = annoying
- 30-45 minute intervals work well
- Quality > quantity for chat engagement

### Test Before Going Live

```
"What's scheduled?"
"Send a test message to chat"
```

### Adjust Based on Stream Size

- Small streams (< 10 viewers): Longer intervals, manual shoutouts
- Larger streams: More automation, shorter intervals

---

## Next Steps

- **[Translation Guide](translation.md)** - Real-time Japanese game translation
- **[Getting Started](getting-started.md)** - Initial setup
