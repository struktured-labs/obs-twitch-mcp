"""
VOD (Video on Demand) tools for managing OBS recordings.

Provides tools for:
- Listing OBS recordings
- Trimming videos with ffmpeg
- Uploading recordings to YouTube
"""

import os
import subprocess
from datetime import datetime
from pathlib import Path

from ..app import mcp
from ..utils.logger import get_logger
from ..utils.youtube_client import get_youtube_client

logger = get_logger("vod")

# Default OBS recording directory (can be overridden by env var)
DEFAULT_RECORDING_DIR = Path.home() / "Videos"


def _get_recording_dir() -> Path:
    """Get the OBS recording directory from OBS config or env var."""
    # Check env var first
    custom_dir = os.getenv("OBS_RECORDING_DIR")
    if custom_dir:
        return Path(custom_dir)

    # Try to read from OBS config
    obs_config_paths = list(Path.home().glob(".config/obs-studio/basic/profiles/*/basic.ini"))
    for config_path in obs_config_paths:
        try:
            with open(config_path) as f:
                for line in f:
                    if line.startswith("FilePath="):
                        path = line.strip().split("=", 1)[1]
                        if path and Path(path).exists():
                            logger.debug(f"Using OBS recording path from config: {path}")
                            return Path(path)
        except Exception:
            pass

    return DEFAULT_RECORDING_DIR


def _get_video_duration(file_path: str) -> float:
    """Get video duration in seconds using ffprobe."""
    try:
        result = subprocess.run(
            [
                "ffprobe",
                "-v", "error",
                "-show_entries", "format=duration",
                "-of", "default=noprint_wrappers=1:nokey=1",
                file_path,
            ],
            capture_output=True,
            text=True,
        )
        return float(result.stdout.strip())
    except Exception:
        return 0.0


def _format_duration(seconds: float) -> str:
    """Format seconds as HH:MM:SS."""
    hours = int(seconds // 3600)
    minutes = int((seconds % 3600) // 60)
    secs = int(seconds % 60)
    if hours > 0:
        return f"{hours}:{minutes:02d}:{secs:02d}"
    return f"{minutes}:{secs:02d}"


@mcp.tool()
def list_recordings(count: int = 10, pattern: str = "*.mkv,*.mp4,*.flv") -> list[dict]:
    """
    List recent OBS recordings.

    Scans the OBS recording directory for video files and returns
    metadata about each one.

    Args:
        count: Number of recordings to return (default 10)
        pattern: Comma-separated file patterns to match (default: *.mkv,*.mp4,*.flv)

    Returns:
        List of recording info dicts with path, size, duration, date.
    """
    recording_dir = _get_recording_dir()
    logger.info(f"Scanning recordings in {recording_dir}")

    if not recording_dir.exists():
        return [{"status": "error", "message": f"Recording directory not found: {recording_dir}"}]

    # Find all matching files
    files = []
    for ext_pattern in pattern.split(","):
        files.extend(recording_dir.glob(ext_pattern.strip()))

    # Sort by modification time (newest first)
    files.sort(key=lambda f: f.stat().st_mtime, reverse=True)

    recordings = []
    for f in files[:count]:
        stat = f.stat()
        duration = _get_video_duration(str(f))
        recordings.append({
            "path": str(f),
            "filename": f.name,
            "size_mb": round(stat.st_size / (1024 * 1024), 2),
            "duration": _format_duration(duration),
            "duration_seconds": round(duration, 2),
            "modified": datetime.fromtimestamp(stat.st_mtime).isoformat(),
        })

    logger.info(f"Found {len(recordings)} recordings")
    return recordings


@mcp.tool()
def trim_video(
    input_path: str,
    output_path: str = "",
    start_time: str = "",
    end_time: str = "",
    duration: str = "",
) -> dict:
    """
    Trim a video file using ffmpeg.

    Can specify either end_time OR duration (not both).
    Times can be in formats: "MM:SS", "HH:MM:SS", or seconds.

    Args:
        input_path: Path to the input video file
        output_path: Path for output file (default: input_trimmed.ext)
        start_time: Start time to trim from (default: beginning)
        end_time: End time to trim to (mutually exclusive with duration)
        duration: Duration to keep (mutually exclusive with end_time)

    Returns:
        Dict with status and output file path.

    Examples:
        trim_video("/path/to/video.mkv", start_time="5:00", end_time="10:00")
        trim_video("/path/to/video.mkv", start_time="0:30", duration="2:00")
    """
    if not os.path.exists(input_path):
        return {"status": "error", "message": f"Input file not found: {input_path}"}

    # Generate output path if not specified
    if not output_path:
        input_file = Path(input_path)
        output_path = str(input_file.parent / f"{input_file.stem}_trimmed{input_file.suffix}")

    # Build ffmpeg command
    cmd = ["ffmpeg", "-y"]  # -y to overwrite

    if start_time:
        cmd.extend(["-ss", start_time])

    cmd.extend(["-i", input_path])

    if end_time:
        cmd.extend(["-to", end_time])
    elif duration:
        cmd.extend(["-t", duration])

    # Copy codecs for fast trimming (no re-encoding)
    cmd.extend(["-c", "copy", output_path])

    logger.info(f"Trimming video: {' '.join(cmd)}")

    try:
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=300)
        if result.returncode != 0:
            logger.error(f"ffmpeg error: {result.stderr}")
            return {"status": "error", "message": f"ffmpeg failed: {result.stderr[:500]}"}

        # Get output file info
        output_duration = _get_video_duration(output_path)
        output_size = os.path.getsize(output_path) / (1024 * 1024)

        return {
            "status": "success",
            "output_path": output_path,
            "duration": _format_duration(output_duration),
            "size_mb": round(output_size, 2),
        }
    except subprocess.TimeoutExpired:
        return {"status": "error", "message": "Trim operation timed out (5 min limit)"}
    except Exception as e:
        logger.error(f"Trim failed: {e}")
        return {"status": "error", "message": str(e)}


@mcp.tool()
def censor_video_segment(
    input_path: str,
    start_time: str,
    end_time: str,
    output_path: str = "",
    mode: str = "mute",
) -> dict:
    """
    Censor a segment of a video (mute audio or blur video).

    Useful for removing copyrighted music or sensitive content.

    Args:
        input_path: Path to the input video file
        start_time: Start of segment to censor
        end_time: End of segment to censor
        output_path: Path for output file (default: input_censored.ext)
        mode: Censoring mode - "mute" (audio only), "blur", or "black"

    Returns:
        Dict with status and output file path.
    """
    if not os.path.exists(input_path):
        return {"status": "error", "message": f"Input file not found: {input_path}"}

    if not output_path:
        input_file = Path(input_path)
        output_path = str(input_file.parent / f"{input_file.stem}_censored{input_file.suffix}")

    # Parse times to seconds for filter
    def parse_time(t: str) -> float:
        parts = t.split(":")
        if len(parts) == 3:
            return int(parts[0]) * 3600 + int(parts[1]) * 60 + float(parts[2])
        elif len(parts) == 2:
            return int(parts[0]) * 60 + float(parts[1])
        return float(t)

    start_sec = parse_time(start_time)
    end_sec = parse_time(end_time)

    if mode == "mute":
        # Mute audio during the segment
        audio_filter = f"volume=enable='between(t,{start_sec},{end_sec})':volume=0"
        cmd = [
            "ffmpeg", "-y", "-i", input_path,
            "-af", audio_filter,
            "-c:v", "copy",
            output_path,
        ]
    elif mode == "blur":
        # Blur video during segment (requires re-encoding)
        video_filter = f"boxblur=enable='between(t,{start_sec},{end_sec})':luma_radius=20:chroma_radius=20"
        cmd = [
            "ffmpeg", "-y", "-i", input_path,
            "-vf", video_filter,
            "-c:a", "copy",
            output_path,
        ]
    elif mode == "black":
        # Black out video during segment
        video_filter = f"drawbox=enable='between(t,{start_sec},{end_sec})':w=iw:h=ih:color=black:t=fill"
        audio_filter = f"volume=enable='between(t,{start_sec},{end_sec})':volume=0"
        cmd = [
            "ffmpeg", "-y", "-i", input_path,
            "-vf", video_filter,
            "-af", audio_filter,
            output_path,
        ]
    else:
        return {"status": "error", "message": f"Unknown mode: {mode}. Use 'mute', 'blur', or 'black'"}

    logger.info(f"Censoring video: {' '.join(cmd)}")

    try:
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=600)
        if result.returncode != 0:
            logger.error(f"ffmpeg error: {result.stderr}")
            return {"status": "error", "message": f"ffmpeg failed: {result.stderr[:500]}"}

        return {
            "status": "success",
            "output_path": output_path,
            "censored_segment": f"{start_time} to {end_time}",
            "mode": mode,
        }
    except subprocess.TimeoutExpired:
        return {"status": "error", "message": "Censor operation timed out (10 min limit)"}
    except Exception as e:
        logger.error(f"Censor failed: {e}")
        return {"status": "error", "message": str(e)}


@mcp.tool()
def upload_recording(
    file_path: str,
    title: str,
    description: str = "",
    tags: str = "",
    privacy: str = "unlisted",
    trim_start: str = "",
    trim_end: str = "",
) -> dict:
    """
    Upload an OBS recording to YouTube.

    Can optionally trim the video before uploading.

    Args:
        file_path: Path to the video file
        title: YouTube video title
        description: Video description
        tags: Comma-separated tags
        privacy: "public", "private", or "unlisted" (default: unlisted)
        trim_start: Optional start time to trim from
        trim_end: Optional end time to trim to

    Returns:
        Dict with upload status and YouTube URL.
    """
    if not os.path.exists(file_path):
        return {"status": "error", "message": f"File not found: {file_path}"}

    upload_path = file_path

    # Trim if requested
    if trim_start or trim_end:
        logger.info("Trimming video before upload...")
        input_file = Path(file_path)
        trimmed_path = str(input_file.parent / f"{input_file.stem}_upload{input_file.suffix}")

        trim_result = trim_video(
            input_path=file_path,
            output_path=trimmed_path,
            start_time=trim_start,
            end_time=trim_end,
        )
        if trim_result.get("status") != "success":
            return trim_result
        upload_path = trimmed_path

    # Upload to YouTube
    logger.info(f"Uploading {upload_path} to YouTube...")
    try:
        client = get_youtube_client()
        tag_list = [t.strip() for t in tags.split(",") if t.strip()] if tags else []

        result = client.upload_video(
            file_path=upload_path,
            title=title,
            description=description,
            tags=tag_list,
            privacy_status=privacy,
        )

        logger.info(f"Upload complete: {result['url']}")
        return {
            "status": "success",
            "video_id": result["video_id"],
            "url": result["url"],
            "title": title,
            "trimmed": bool(trim_start or trim_end),
        }
    except Exception as e:
        logger.error(f"Upload failed: {e}")
        return {"status": "error", "message": str(e)}


@mcp.tool()
def get_recording_info(file_path: str) -> dict:
    """
    Get detailed info about a recording file.

    Args:
        file_path: Path to the video file

    Returns:
        Dict with duration, size, codec info, etc.
    """
    if not os.path.exists(file_path):
        return {"status": "error", "message": f"File not found: {file_path}"}

    try:
        # Get detailed info using ffprobe
        result = subprocess.run(
            [
                "ffprobe",
                "-v", "error",
                "-show_format",
                "-show_streams",
                "-of", "json",
                file_path,
            ],
            capture_output=True,
            text=True,
        )

        import json
        info = json.loads(result.stdout)

        # Extract useful info
        format_info = info.get("format", {})
        streams = info.get("streams", [])

        video_stream = next((s for s in streams if s.get("codec_type") == "video"), {})
        audio_stream = next((s for s in streams if s.get("codec_type") == "audio"), {})

        duration = float(format_info.get("duration", 0))

        return {
            "path": file_path,
            "duration": _format_duration(duration),
            "duration_seconds": round(duration, 2),
            "size_mb": round(int(format_info.get("size", 0)) / (1024 * 1024), 2),
            "format": format_info.get("format_name", "unknown"),
            "video_codec": video_stream.get("codec_name", "none"),
            "video_resolution": f"{video_stream.get('width', 0)}x{video_stream.get('height', 0)}",
            "video_fps": video_stream.get("r_frame_rate", "unknown"),
            "audio_codec": audio_stream.get("codec_name", "none"),
            "audio_channels": audio_stream.get("channels", 0),
        }
    except Exception as e:
        logger.error(f"Failed to get recording info: {e}")
        return {"status": "error", "message": str(e)}
