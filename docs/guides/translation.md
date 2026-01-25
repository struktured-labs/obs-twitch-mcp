---
layout: default
title: Translation Guide
---

# Real-Time Game Translation

This is the killer feature for retro game streamers. Claude watches your screen and translates Japanese text automatically, displaying English subtitles on your stream.

**Perfect for:**
- Japan-only Game Boy/NES/SNES RPGs
- Visual novels
- Any game with untranslated text

---

## How It Works

```
┌─────────────────┐     ┌──────────────┐     ┌─────────────────┐
│   OBS Screen    │────▶│ Claude Vision│────▶│ Translation     │
│   (screenshot)  │     │ (OCR + AI)   │     │ Overlay on OBS  │
└─────────────────┘     └──────────────┘     └─────────────────┘
```

1. **Screenshot** - Captures your game from OBS
2. **OCR** - Claude Vision reads the Japanese text
3. **Translation** - Converts to natural English
4. **Overlay** - Shows translation on your stream

The automatic service does this every 2 seconds, but only calls the API when the text actually changes.

---

## Setup

### 1. Get an Anthropic API Key

1. Go to [console.anthropic.com](https://console.anthropic.com)
2. Create an account or log in
3. Go to API Keys
4. Create a new key
5. Copy it

### 2. Add to Your Credentials

Edit your `setenv.sh`:

```bash
export ANTHROPIC_API_KEY="sk-ant-api03-your-key-here"
```

Restart Claude Code after saving.

### 3. Test It

With a Japanese game on screen in OBS, try:

```
"Translate what's on screen"
```

You should see the Japanese text and English translation appear.

---

## Manual vs Automatic Translation

### Manual Mode

Best for: Testing, occasional translations, non-dialogue text

```
"Translate what's on screen"
"Translate the menu"
"What does that item description say?"
```

Each command takes one screenshot and translates it.

### Automatic Mode

Best for: Streaming story-heavy games, continuous dialogue

```
"Start the translation service"
```

This:
- Monitors every 2 seconds (configurable)
- Auto-detects dialogue boxes
- Only translates when text changes (saves 60-80% of API calls)
- Shows overlay automatically
- Runs in background

To stop:
```
"Stop the translation service"
```

---

## Automatic Service Configuration

### Basic Start

```
"Start translating"
```

### With Custom Settings

```
"Start translating with 3 second intervals"
"Start the translation service, check every 1.5 seconds"
```

### Check Status

```
"How's the translation service doing?"
"Translation status"
```

Shows:
- Running status
- API calls made vs skipped (efficiency)
- Average latency
- Last translation

### Configure While Running

```
"Make translation check faster - every 1 second"
"Set translation threshold to 15%"  (how different text must be to re-translate)
```

---

## Translation Overlay

The English text appears at the bottom of your screen by default.

### Customize Position

```
"Move translation to the top"
"Put translation overlay at 100, 800"  (x, y coordinates)
```

### Customize Appearance

```
"Make translation text bigger"
"Set translation font size to 100"
```

### Clear Manually

```
"Clear the translation"
"Hide translation overlay"
```

---

## How Smart Detection Works

The service doesn't call the API for every frame. Here's how it saves your API budget:

### 1. Dialogue Box Detection

On first run, it detects where dialogue typically appears in your game. This region is cached.

```
Game Screen:
┌────────────────────────────┐
│                            │
│         (game area)        │
│                            │
├────────────────────────────┤
│   [Dialogue text here]     │  ← Only this region is analyzed
└────────────────────────────┘
```

### 2. Change Detection

Uses perceptual hashing to compare frames:

- Same dialogue? Skip API call
- New dialogue? Translate it
- Menu/battle screen? Different region, may skip

### 3. Efficiency Stats

```
"Translation status"

Service: Running
API calls: 45
Skipped (no change): 180
Efficiency: 80%
Avg latency: 320ms
```

That means 80% of checks didn't need an API call!

---

## Game-Specific Tips

### RPGs with Text Boxes (Penta Dragon, Dragon Quest, etc.)

Automatic mode works great. The dialogue box is usually detected automatically.

```
"Start translating"
```

### Visual Novels

May need larger poll interval due to lots of text:

```
"Start translating with 3 second intervals"
```

### Action Games with Sparse Text

Use manual mode for menus and item descriptions:

```
"Translate that"
"What does the shop say?"
```

### Games with Multiple Text Areas

If auto-detection picks the wrong area:

```
"Stop translation"
"Start translation with auto-detect disabled"
```

Then manually translate key moments.

---

## Troubleshooting

### Translation is wrong or garbled

- Check your game isn't using unusual fonts
- Try manual mode to see the raw OCR output
- Some heavily stylized text is hard to OCR

### Overlay not appearing

- Make sure you have a text source in OBS
- Check OBS scene for "translation_overlay" source
- Try: "Add a text overlay that says test"

### API errors

- Check your ANTHROPIC_API_KEY is set
- Verify you have API credits
- Check [status.anthropic.com](https://status.anthropic.com)

### Service stops randomly

- Token may have expired
- Run: "Translation status" to check
- Restart: "Stop translation" then "Start translation"

### Detecting wrong region

```
"Reset translation service"
"Start translation"
```

This clears the cached dialogue box region.

---

## Cost Considerations

Claude Vision API calls cost money. The smart detection helps a lot:

| Mode | Calls per Hour | Approximate Cost |
|------|----------------|------------------|
| Manual (occasional) | 10-20 | ~$0.02-0.04 |
| Auto (2s, with smart detect) | 50-200 | ~$0.10-0.40 |
| Auto (without smart detect) | 1800 | ~$3.60 |

Smart detection typically saves 60-80% of calls.

### Tips to Reduce Costs

1. **Use automatic mode** - smart detection saves money
2. **Increase poll interval** for slow-paced games
3. **Stop service** during battles/exploration
4. **Manual mode** for menus and occasional text

---

## Example Session

```
You: "I'm about to play Penta Dragon, start translating"

Claude: Starting translation service with smart dialogue detection.
        Monitoring every 2 seconds. I'll show translations as
        new dialogue appears.

        [Translation service started]

--- 30 minutes later ---

You: "How many API calls have we made?"

Claude: Translation service status:
        - Running: Yes
        - API calls: 89
        - Skipped (unchanged): 412
        - Efficiency: 82%
        - Average latency: 285ms

        We've saved about 82% of potential API calls through
        change detection!

You: "Great, stop translating - I'm going to grind for a bit"

Claude: [Stops translation service]
        Translation service stopped. Made 89 API calls total.
        Overlay cleared.
```

---

## Next Steps

- **[Automation Guide](automation.md)** - Auto-welcome viewers while you play
- **[Getting Started](getting-started.md)** - Initial setup if you haven't done it
