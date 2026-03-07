"""
Local audio transcription using faster-whisper on GPU.

Captures system audio via PipeWire and transcribes with Whisper large-v3
running on the local NVIDIA GPU. Zero API cost.
"""

import os
import signal
import subprocess
import tempfile
import time
from pathlib import Path

from .logger import get_logger

logger = get_logger("audio_transcribe")

# Singleton model reference — loaded lazily, lives for the session
_whisper_model = None
_model_loading = False

# Audio capture settings
CAPTURE_DURATION_SECONDS = 8
SAMPLE_RATE = 16000

# Temp dir for audio files (gitignored)
AUDIO_TMP = Path(__file__).parent.parent.parent / "tmp"


def _get_monitor_source() -> str:
    """Find the best PipeWire monitor source for capturing stream audio."""
    try:
        result = subprocess.run(
            ["pactl", "list", "short", "sources"],
            capture_output=True, text=True, timeout=5,
        )
        for line in result.stdout.strip().split("\n"):
            # Prefer MOTU or primary output monitor
            if ".monitor" in line and "RUNNING" in line:
                parts = line.split("\t")
                if len(parts) >= 2:
                    return parts[1]
            # Fallback: any monitor source
        for line in result.stdout.strip().split("\n"):
            if ".monitor" in line:
                parts = line.split("\t")
                if len(parts) >= 2:
                    return parts[1]
    except Exception as e:
        logger.warning(f"Failed to list PipeWire sources: {e}")

    # Last resort default
    return "@DEFAULT_MONITOR@"


def _get_whisper_model():
    """Get or create the Whisper model singleton (lazy loaded on first use)."""
    global _whisper_model, _model_loading

    if _whisper_model is not None:
        return _whisper_model

    if _model_loading:
        return None  # Prevent concurrent loads

    _model_loading = True
    try:
        from faster_whisper import WhisperModel

        logger.info("Loading Whisper large-v3 on CUDA (first use, takes ~30s)...")
        t0 = time.time()
        _whisper_model = WhisperModel(
            "large-v3",
            device="cuda",
            compute_type="float16",
        )
        logger.info(f"Whisper model loaded in {time.time() - t0:.1f}s")
        return _whisper_model
    except Exception as e:
        logger.error(f"Failed to load Whisper model: {e}")
        _model_loading = False
        return None


def capture_and_transcribe(duration: int = CAPTURE_DURATION_SECONDS) -> str:
    """Capture system audio and transcribe it.

    Returns formatted transcript with language detection.
    """
    AUDIO_TMP.mkdir(parents=True, exist_ok=True)
    audio_path = AUDIO_TMP / "chat_ai_audio.wav"

    # Step 1: Capture audio via PipeWire
    monitor = _get_monitor_source()
    logger.info(f"Capturing {duration}s audio from {monitor}")

    try:
        proc = subprocess.Popen(
            [
                "pw-record",
                f"--target={monitor}",
                "--format=s16",
                f"--rate={SAMPLE_RATE}",
                "--channels=1",
                str(audio_path),
            ],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
        time.sleep(duration)
        proc.send_signal(signal.SIGINT)
        proc.wait(timeout=3)
    except Exception as e:
        try:
            proc.kill()
        except Exception:
            pass
        return f"Audio capture failed: {e}"

    # Check we got real audio data
    if not audio_path.exists() or audio_path.stat().st_size < 1000:
        return "No audio captured — stream might be silent or audio routing issue."

    # Step 2: Transcribe with Whisper
    model = _get_whisper_model()
    if model is None:
        return "Whisper model not available — still loading or GPU unavailable."

    try:
        t0 = time.time()
        segments, info = model.transcribe(
            str(audio_path),
            language=None,  # Auto-detect language
            vad_filter=True,  # Filter out silence
        )
        segments = list(segments)
        elapsed = time.time() - t0

        if not segments:
            return f"No speech detected in the last {duration} seconds (detected language: {info.language})."

        # Format transcript
        lang = info.language
        lang_prob = info.language_probability

        lines = []
        lines.append(f"Language: {lang} (confidence: {lang_prob:.0%})")
        lines.append(f"Transcription ({elapsed:.1f}s to process):")

        for seg in segments:
            lines.append(f"  [{seg.start:.1f}s-{seg.end:.1f}s] {seg.text.strip()}")

        logger.info(
            f"Transcribed {duration}s audio in {elapsed:.1f}s: "
            f"{lang} ({lang_prob:.0%}), {len(segments)} segments"
        )
        return "\n".join(lines)

    except Exception as e:
        logger.error(f"Transcription failed: {e}")
        return f"Transcription failed: {e}"
    finally:
        # Clean up
        try:
            audio_path.unlink(missing_ok=True)
        except Exception:
            pass
