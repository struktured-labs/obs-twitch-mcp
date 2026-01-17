# Mic/Aux Current Settings (Noisy Environment Preset)

**Hardware:**
- Microphone: Shure SM7dB (with +28dB built-in preamp)
- Interface: MOTU M4
- Gain: ~3 o'clock position
- Environment: Very loud area by busy road

**Date Applied:** 2026-01-17
**Preset:** Noisy Environment (optimized for road noise)

## Active Filter Chain (Order from OBS)

### 1. Noise Suppression
- **Type:** RNNoise v2
- **Status:** ENABLED
- **Settings:** Default (aggressive for road noise)

### 2. Noise Gate
- **Status:** ENABLED (gentle settings)
- **Settings:**
  - Open Threshold: -32 dB (gentler than baseline -27 dB)
  - Close Threshold: -42 dB (less aggressive than baseline -57 dB)
  - Attack Time: 25 ms (slower to avoid clipping speech)
  - Hold Time: 200 ms (holds longer to avoid choppy audio)

### 3. Compressor
- **Status:** ENABLED
- **Settings:**
  - Ratio: 3.5:1 (moderate compression)
  - Threshold: -18 dB (catches more peaks than baseline -30.5 dB)
  - Attack Time: 6 ms (fast attack)
  - Release Time: 60 ms (faster than baseline 100 ms)
  - Output Gain: 0 dB (no boost, rely on limiter)

### 4. Limiter
- **Status:** ENABLED
- **Settings:**
  - Threshold: -6 dB (more headroom than baseline -9.2 dB)
  - Release Time: 60 ms (faster recovery)

## Key Improvements Over Baseline

- **Noise Gate:** Gentler thresholds prevent speech clipping
- **Compressor:** Re-enabled with optimized settings for consistent levels
- **Attack/Hold times:** Tuned to avoid choppy audio in noisy environment
- **Overall:** Better balance between cutting road noise and preserving speech clarity

## Notes

- User confirmed: "sounds better, keep the settings"
- Optimized for temporary loud environment (3-4 months until move)
- Can revert to baseline if needed (saved in audio-settings-baseline.md)
