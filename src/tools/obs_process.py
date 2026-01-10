"""
OBS process management tools.

Cross-platform tools for starting and stopping OBS Studio.
"""

import os
import platform
import shutil
import signal
import subprocess
from pathlib import Path

from ..app import mcp
from ..utils.logger import get_logger

logger = get_logger("obs_process")


def _get_obs_command() -> list[str] | None:
    """
    Find the OBS executable for the current platform.

    Returns:
        Command list to launch OBS, or None if not found.
    """
    system = platform.system()

    if system == "Linux":
        # Try common Linux locations
        candidates = [
            "obs",  # In PATH
            "obs-studio",  # Alternative name
            "/usr/bin/obs",
            "/usr/local/bin/obs",
            # Flatpak
            "flatpak run com.obsproject.Studio",
            # Snap
            "/snap/bin/obs-studio",
        ]
        for cmd in candidates:
            if " " in cmd:
                # Flatpak command
                parts = cmd.split()
                if shutil.which(parts[0]):
                    return parts
            elif shutil.which(cmd):
                return [cmd]

    elif system == "Darwin":  # macOS
        candidates = [
            "/Applications/OBS.app/Contents/MacOS/OBS",
            os.path.expanduser("~/Applications/OBS.app/Contents/MacOS/OBS"),
        ]
        for path in candidates:
            if os.path.exists(path):
                return [path]
        # Fallback: use 'open' command
        if os.path.exists("/Applications/OBS.app"):
            return ["open", "-a", "OBS"]

    elif system == "Windows":
        # Common Windows install locations
        program_files = os.environ.get("ProgramFiles", r"C:\Program Files")
        program_files_x86 = os.environ.get("ProgramFiles(x86)", r"C:\Program Files (x86)")

        candidates = [
            os.path.join(program_files, "obs-studio", "bin", "64bit", "obs64.exe"),
            os.path.join(program_files_x86, "obs-studio", "bin", "64bit", "obs64.exe"),
            os.path.join(program_files, "obs-studio", "bin", "32bit", "obs32.exe"),
            # Steam install
            os.path.join(program_files_x86, "Steam", "steamapps", "common", "OBS Studio", "bin", "64bit", "obs64.exe"),
        ]
        for path in candidates:
            if os.path.exists(path):
                return [path]

        # Try PATH
        if shutil.which("obs64.exe"):
            return ["obs64.exe"]
        if shutil.which("obs.exe"):
            return ["obs.exe"]

    return None


def _get_obs_pids() -> list[int]:
    """Get PIDs of running OBS processes."""
    system = platform.system()
    pids = []

    try:
        if system == "Windows":
            # Use tasklist on Windows
            for exe_name in ["obs64.exe", "obs32.exe", "obs.exe"]:
                result = subprocess.run(
                    ["tasklist", "/FI", f"IMAGENAME eq {exe_name}", "/FO", "CSV", "/NH"],
                    capture_output=True,
                    text=True,
                )
                for line in result.stdout.strip().split("\n"):
                    if line and exe_name.lower() in line.lower():
                        parts = line.strip('"').split('","')
                        if len(parts) >= 2:
                            try:
                                pids.append(int(parts[1]))
                            except ValueError:
                                pass
        else:
            # Linux/macOS: Use pgrep -x for exact process name match
            # This avoids matching "obsws-python", "claude obs-studio", etc.
            for name in ["obs", "obs-studio"]:
                result = subprocess.run(
                    ["pgrep", "-x", name],
                    capture_output=True,
                    text=True,
                )
                for line in result.stdout.strip().split("\n"):
                    if line:
                        try:
                            pid = int(line)
                            if pid not in pids:
                                pids.append(pid)
                        except ValueError:
                            pass

            # Also check for flatpak OBS
            result = subprocess.run(
                ["pgrep", "-f", "^/app/bin/obs$"],
                capture_output=True,
                text=True,
            )
            for line in result.stdout.strip().split("\n"):
                if line:
                    try:
                        pid = int(line)
                        if pid not in pids:
                            pids.append(pid)
                    except ValueError:
                        pass

            # Verify each PID is actually OBS by checking /proc/{pid}/exe on Linux
            if system == "Linux" and pids:
                verified_pids = []
                for pid in pids:
                    try:
                        exe_path = os.readlink(f"/proc/{pid}/exe")
                        # Check if it's actually OBS binary
                        if "obs" in os.path.basename(exe_path).lower():
                            verified_pids.append(pid)
                    except (OSError, FileNotFoundError):
                        # Process may have exited or we don't have permission
                        pass
                pids = verified_pids

    except Exception as e:
        logger.warning(f"Could not get OBS PIDs: {e}")

    return pids


@mcp.tool()
def start_obs(
    custom_command: str = "",
    env_vars: dict = None,
    wait: bool = False,
) -> dict:
    """
    Start OBS Studio.

    Args:
        custom_command: Custom command to launch OBS (overrides auto-detection)
        env_vars: Additional environment variables to set (e.g., {"LD_LIBRARY_PATH": "/path"})
        wait: If True, wait for OBS to exit (blocks until closed)

    Returns:
        Dict with status and process info.

    Examples:
        start_obs()  # Auto-detect OBS location
        start_obs(custom_command="flatpak run com.obsproject.Studio")
        start_obs(env_vars={"LD_LIBRARY_PATH": "/custom/path"})
    """
    # Check if already running
    existing_pids = _get_obs_pids()
    if existing_pids:
        return {
            "status": "already_running",
            "pids": existing_pids,
            "message": f"OBS is already running (PID: {existing_pids[0]})",
        }

    # Determine command
    if custom_command:
        cmd = custom_command.split()
    else:
        cmd = _get_obs_command()

    if not cmd:
        return {
            "status": "error",
            "message": "Could not find OBS installation. Install OBS or provide custom_command.",
            "platform": platform.system(),
            "searched": [
                "obs (PATH)",
                "/usr/bin/obs",
                "/Applications/OBS.app",
                "C:\\Program Files\\obs-studio\\bin\\64bit\\obs64.exe",
            ],
        }

    # Prepare environment
    env = os.environ.copy()
    if env_vars:
        env.update(env_vars)

    # Check for OBS_LAUNCH_LD_LIBRARY_PATH from MCP config (preferred)
    if platform.system() == "Linux" and "LD_LIBRARY_PATH" not in (env_vars or {}):
        obs_ld_path = os.environ.get("OBS_LAUNCH_LD_LIBRARY_PATH")
        if obs_ld_path:
            current = env.get("LD_LIBRARY_PATH", "")
            env["LD_LIBRARY_PATH"] = f"{obs_ld_path}:{current}" if current else obs_ld_path
            logger.info(f"Using OBS_LAUNCH_LD_LIBRARY_PATH: {obs_ld_path}")

    logger.info(f"Starting OBS with command: {' '.join(cmd)}")

    try:
        if wait:
            result = subprocess.run(cmd, env=env)
            return {
                "status": "exited",
                "exit_code": result.returncode,
                "command": " ".join(cmd),
            }
        else:
            process = subprocess.Popen(
                cmd,
                env=env,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                start_new_session=True,
            )
            return {
                "status": "started",
                "pid": process.pid,
                "command": " ".join(cmd),
                "platform": platform.system(),
            }
    except FileNotFoundError:
        return {
            "status": "error",
            "message": f"Command not found: {cmd[0]}",
            "command": " ".join(cmd),
        }
    except Exception as e:
        logger.error(f"Failed to start OBS: {e}")
        return {
            "status": "error",
            "message": str(e),
            "command": " ".join(cmd),
        }


def _wait_for_pid_exit(pid: int, timeout: float = 10.0) -> bool:
    """Wait for a process to exit, return True if exited within timeout."""
    import time
    start = time.time()
    while time.time() - start < timeout:
        try:
            os.kill(pid, 0)  # Check if process exists
            time.sleep(0.2)
        except ProcessLookupError:
            return True  # Process exited
    return False  # Timeout


@mcp.tool()
def stop_obs(force: bool = False, graceful_timeout: float = 20.0) -> dict:
    """
    Stop OBS Studio.

    Args:
        force: If True, forcefully kill OBS (SIGKILL). Otherwise, graceful shutdown (SIGTERM).
        graceful_timeout: Seconds to wait for graceful shutdown before forcing (default: 20).

    Returns:
        Dict with status.
    """
    pids = _get_obs_pids()

    if not pids:
        return {
            "status": "not_running",
            "message": "OBS is not running",
        }

    # Note: OBS websocket protocol has no exit/quit request, so we use SIGTERM
    # This may trigger "closed unexpectedly" warning on next startup (cosmetic only)

    system = platform.system()
    stopped = []
    failed = []
    force_killed = []

    for pid in pids:
        try:
            if system == "Windows":
                # Use taskkill on Windows
                subprocess.run(
                    ["taskkill", "/F" if force else "", "/PID", str(pid)],
                    capture_output=True,
                )
                stopped.append(pid)
            else:
                if force:
                    # Immediate SIGKILL
                    os.kill(pid, signal.SIGKILL)
                    stopped.append(pid)
                    force_killed.append(pid)
                else:
                    # Graceful: SIGTERM, wait, then SIGKILL if needed
                    os.kill(pid, signal.SIGTERM)
                    logger.info(f"Sent SIGTERM to OBS process {pid}, waiting for graceful exit...")

                    if _wait_for_pid_exit(pid, graceful_timeout):
                        stopped.append(pid)
                        logger.info(f"OBS process {pid} exited gracefully")
                    else:
                        # Process didn't exit, force kill
                        logger.warning(f"OBS process {pid} didn't exit gracefully, sending SIGKILL")
                        os.kill(pid, signal.SIGKILL)
                        _wait_for_pid_exit(pid, 2.0)  # Brief wait after SIGKILL
                        stopped.append(pid)
                        force_killed.append(pid)

            logger.info(f"Stopped OBS process {pid}")
        except ProcessLookupError:
            # Already dead
            stopped.append(pid)
        except PermissionError:
            failed.append({"pid": pid, "error": "Permission denied"})
        except Exception as e:
            failed.append({"pid": pid, "error": str(e)})

    if failed:
        return {
            "status": "partial",
            "stopped": stopped,
            "failed": failed,
            "message": f"Stopped {len(stopped)} processes, {len(failed)} failed",
        }

    return {
        "status": "stopped",
        "pids": stopped,
        "force": force,
        "force_killed": force_killed,
        "message": f"Stopped {len(stopped)} OBS process(es)" + (f" ({len(force_killed)} force killed)" if force_killed else " (graceful)"),
    }


@mcp.tool()
def get_obs_process_status() -> dict:
    """
    Get the status of OBS Studio process.

    Returns:
        Dict with running status and process info.
    """
    pids = _get_obs_pids()
    obs_cmd = _get_obs_command()

    return {
        "running": len(pids) > 0,
        "pids": pids,
        "platform": platform.system(),
        "obs_found": obs_cmd is not None,
        "obs_command": " ".join(obs_cmd) if obs_cmd else None,
    }


@mcp.tool()
def restart_obs(
    custom_command: str = "",
    env_vars: dict = None,
    force: bool = False,
) -> dict:
    """
    Restart OBS Studio.

    Args:
        custom_command: Custom command to launch OBS
        env_vars: Additional environment variables
        force: Force kill before restart

    Returns:
        Dict with status.
    """
    # Stop OBS (now waits for graceful exit)
    stop_result = stop_obs(force=force)

    if stop_result["status"] not in ["stopped", "not_running", "partial"]:
        return {
            "status": "error",
            "message": "Failed to stop OBS",
            "stop_result": stop_result,
        }

    # Start OBS
    start_result = start_obs(custom_command=custom_command, env_vars=env_vars)

    return {
        "status": "restarted" if start_result["status"] == "started" else start_result["status"],
        "stop_result": stop_result,
        "start_result": start_result,
    }
