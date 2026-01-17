# Mic/Aux Baseline Settings (Human-Tuned)

**Hardware:**
- Microphone: Shure SM7dB (with +28dB built-in preamp)
- Interface: MOTU M4
- Gain: ~3 o'clock position
- Environment: Very loud area by busy road

**Date:** 2026-01-17

## Current Filter Chain (Order from OBS)

### 1. Noise Suppression
- **Type:** RNNoise v2
- **Status:** ENABLED
- **Settings:** Default

### 2. Noise Gate
- **Status:** DISABLED (was too aggressive, clipped speech)
- **Settings:**
  - Open Threshold: -27.0 dB
  - Close Threshold: -57.0 dB
  - Attack Time: 5 ms
  - Hold Time: 100 ms

### 3. Compressor
- **Status:** DISABLED (user wants to re-enable with better settings)
- **Settings:**
  - Ratio: 3.5:1
  - Threshold: -30.5 dB
  - Release Time: 100 ms
  - Output Gain: +9.9 dB

### 4. Limiter
- **Status:** ENABLED
- **Settings:**
  - Threshold: -9.2 dB
  - Release Time: 50 ms

## Notes

- Noise Gate disabled because it was clipping speech
- Compressor disabled but user wants it back on with better settings
- Need aggressive noise reduction for road noise
- Temporary setup - moving to quieter location in 3-4 months
