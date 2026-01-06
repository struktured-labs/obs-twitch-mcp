"""
Stream health monitoring tools.

Provides tools for monitoring stream quality metrics:
- Dropped frames
- Bitrate
- FPS
- CPU usage
- Memory usage
- Disk space
"""

import os
import shutil
from datetime import datetime

from ..app import mcp, get_obs_client
from ..utils.logger import get_logger

logger = get_logger("health")

# Thresholds for health status
DROPPED_FRAMES_WARN = 0.1  # 0.1% dropped frames = warning
DROPPED_FRAMES_BAD = 1.0   # 1% dropped frames = bad
FPS_WARN_THRESHOLD = 0.95  # < 95% of target FPS = warning
CPU_WARN_THRESHOLD = 80    # > 80% CPU = warning
DISK_WARN_GB = 10          # < 10GB free = warning


@mcp.tool()
def get_stream_health() -> dict:
    """
    Get comprehensive stream health status.

    Returns metrics about OBS performance, encoding quality,
    and system resources.

    Returns:
        Dict with health status and detailed metrics.
    """
    obs = get_obs_client()

    try:
        stats = obs.get_stats()
    except Exception as e:
        logger.error(f"Failed to get OBS stats: {e}")
        return {"status": "error", "message": str(e)}

    # Calculate health indicators
    issues = []
    warnings = []

    # Check dropped frames
    render_dropped = stats.get("output_skipped_frames", 0)
    render_total = stats.get("output_total_frames", 1)
    render_dropped_pct = (render_dropped / render_total) * 100 if render_total > 0 else 0

    encode_dropped = stats.get("render_skipped_frames", 0)
    encode_total = stats.get("render_total_frames", 1)
    encode_dropped_pct = (encode_dropped / encode_total) * 100 if encode_total > 0 else 0

    if render_dropped_pct > DROPPED_FRAMES_BAD:
        issues.append(f"High render dropped frames: {render_dropped_pct:.2f}%")
    elif render_dropped_pct > DROPPED_FRAMES_WARN:
        warnings.append(f"Moderate render dropped frames: {render_dropped_pct:.2f}%")

    if encode_dropped_pct > DROPPED_FRAMES_BAD:
        issues.append(f"High encoding lag: {encode_dropped_pct:.2f}%")
    elif encode_dropped_pct > DROPPED_FRAMES_WARN:
        warnings.append(f"Moderate encoding lag: {encode_dropped_pct:.2f}%")

    # Check CPU usage
    cpu_usage = stats.get("cpu_usage", 0)
    if cpu_usage > CPU_WARN_THRESHOLD:
        warnings.append(f"High CPU usage: {cpu_usage:.1f}%")

    # Check FPS
    active_fps = stats.get("active_fps", 0)
    # Assume 60 FPS target - could make this configurable
    if active_fps > 0 and active_fps < 60 * FPS_WARN_THRESHOLD:
        warnings.append(f"Low FPS: {active_fps:.1f}")

    # Check disk space
    try:
        disk = shutil.disk_usage("/")
        free_gb = disk.free / (1024 ** 3)
        if free_gb < DISK_WARN_GB:
            warnings.append(f"Low disk space: {free_gb:.1f}GB free")
    except Exception:
        pass

    # Determine overall status
    if issues:
        status = "bad"
    elif warnings:
        status = "warning"
    else:
        status = "good"

    return {
        "status": status,
        "issues": issues,
        "warnings": warnings,
        "metrics": {
            "fps": round(stats.get("active_fps", 0), 1),
            "cpu_usage": round(cpu_usage, 1),
            "memory_usage_mb": round(stats.get("memory_usage", 0), 1),
            "render_dropped_frames": render_dropped,
            "render_total_frames": render_total,
            "render_dropped_pct": round(render_dropped_pct, 3),
            "encode_dropped_frames": encode_dropped,
            "encode_total_frames": encode_total,
            "encode_dropped_pct": round(encode_dropped_pct, 3),
            "average_frame_time_ms": round(stats.get("average_frame_render_time", 0), 2),
        },
        "timestamp": datetime.now().isoformat(),
    }


@mcp.tool()
def get_stream_bitrate() -> dict:
    """
    Get current streaming/recording bitrate info.

    Returns:
        Dict with bitrate information.
    """
    obs = get_obs_client()

    try:
        # Get output status for stream/record
        stream_status = obs.get_stream_status()
        record_status = obs.get_record_status()

        result = {
            "streaming": {
                "active": stream_status.get("active", False),
                "duration": stream_status.get("duration", 0),
                "bytes_sent": stream_status.get("bytes_sent", 0),
            },
            "recording": {
                "active": record_status.get("active", False),
                "paused": record_status.get("paused", False),
                "duration": record_status.get("duration", 0),
                "bytes": record_status.get("bytes", 0),
            },
        }

        # Calculate approximate bitrate if streaming
        if stream_status.get("active") and stream_status.get("duration", 0) > 0:
            duration_sec = stream_status["duration"] / 1000  # Convert ms to sec
            bytes_sent = stream_status.get("bytes_sent", 0)
            if duration_sec > 0:
                bitrate_kbps = (bytes_sent * 8) / (duration_sec * 1000)
                result["streaming"]["bitrate_kbps"] = round(bitrate_kbps, 0)

        return result
    except Exception as e:
        logger.error(f"Failed to get bitrate info: {e}")
        return {"status": "error", "message": str(e)}


@mcp.tool()
def get_disk_space() -> dict:
    """
    Get disk space information for recording drives.

    Returns:
        Dict with disk usage info for relevant paths.
    """
    paths_to_check = [
        ("/", "System"),
        (os.path.expanduser("~/Videos"), "Videos"),
    ]

    # Add custom recording dir if set
    custom_dir = os.getenv("OBS_RECORDING_DIR")
    if custom_dir:
        paths_to_check.append((custom_dir, "Recordings"))

    results = []
    for path, label in paths_to_check:
        try:
            if os.path.exists(path):
                usage = shutil.disk_usage(path)
                results.append({
                    "label": label,
                    "path": path,
                    "total_gb": round(usage.total / (1024 ** 3), 1),
                    "used_gb": round(usage.used / (1024 ** 3), 1),
                    "free_gb": round(usage.free / (1024 ** 3), 1),
                    "percent_used": round((usage.used / usage.total) * 100, 1),
                })
        except Exception as e:
            logger.warning(f"Could not check disk {path}: {e}")

    # Estimate recording time remaining (assuming ~5 Mbps bitrate)
    video_disk = next((d for d in results if d["label"] == "Videos"), results[0] if results else None)
    if video_disk:
        free_bytes = video_disk["free_gb"] * (1024 ** 3)
        # 5 Mbps = 0.625 MB/s = 2.25 GB/hour
        hours_remaining = free_bytes / (2.25 * 1024 ** 3)
        video_disk["estimated_recording_hours"] = round(hours_remaining, 1)

    return {"disks": results}


@mcp.tool()
def alert_if_unhealthy(auto_fix: bool = False) -> dict:
    """
    Check stream health and alert if there are issues.

    Can optionally attempt automatic fixes for some issues.

    Args:
        auto_fix: If True, attempt to fix issues automatically

    Returns:
        Dict with health status and any actions taken.
    """
    health = get_stream_health()
    actions_taken = []

    if health["status"] == "bad" and auto_fix:
        # Potential auto-fixes:
        # - If disk is nearly full, could delete old recordings
        # - If CPU is high, could lower encoding preset
        # These would require more OBS API access

        # For now, just log the issue
        logger.warning(f"Stream health issues: {health['issues']}")

    if health["status"] != "good":
        # Send alert to chat
        twitch = None
        try:
            from ..app import get_twitch_client
            twitch = get_twitch_client()
        except Exception:
            pass

        if twitch and health["issues"]:
            # Only alert on actual issues, not warnings
            pass  # Don't spam chat with health alerts for now

    return {
        "health": health,
        "actions_taken": actions_taken,
    }
