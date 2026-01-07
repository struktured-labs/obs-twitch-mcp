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
            result = subprocess.run(
                ["tasklist", "/FI", "IMAGENAME eq obs64.exe", "/FO", "CSV", "/NH"],
                capture_output=True,
                text=True,
            )
            for line in result.stdout.strip().split("\n"):
                if line and "obs" in line.lower():
                    parts = line.strip('"').split('","')
                    if len(parts) >= 2:
                        try:
                            pids.append(int(parts[1]))
                        except ValueError:
                            pass
        else:
            # Use pgrep on Linux/macOS
            result = subprocess.run(
                ["pgrep", "-f", "obs"],
                capture_output=True,
                text=True,
            )
            for line in result.stdout.strip().split("\n"):
                if line:
                    try:
                        pids.append(int(line))
                    except ValueError:
                        pass
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

    # Add common Linux library paths if not set
    if platform.system() == "Linux" and "LD_LIBRARY_PATH" not in (env_vars or {}):
        # Check for Python lib path (like in user's run.sh)
        python_lib = Path.home() / ".local/share/uv/python"
        if python_lib.exists():
            # Find the most recent Python install
            python_dirs = sorted(python_lib.glob("cpython-*/lib"), reverse=True)
            if python_dirs:
                current = env.get("LD_LIBRARY_PATH", "")
                env["LD_LIBRARY_PATH"] = f"{python_dirs[0]}:{current}" if current else str(python_dirs[0])

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


@mcp.tool()
def stop_obs(force: bool = False) -> dict:
    """
    Stop OBS Studio.

    Args:
        force: If True, forcefully kill OBS (SIGKILL). Otherwise, graceful shutdown (SIGTERM).

    Returns:
        Dict with status.
    """
    pids = _get_obs_pids()

    if not pids:
        return {
            "status": "not_running",
            "message": "OBS is not running",
        }

    system = platform.system()
    stopped = []
    failed = []

    for pid in pids:
        try:
            if system == "Windows":
                # Use taskkill on Windows
                subprocess.run(
                    ["taskkill", "/F" if force else "", "/PID", str(pid)],
                    capture_output=True,
                )
            else:
                # Use signals on Linux/macOS
                sig = signal.SIGKILL if force else signal.SIGTERM
                os.kill(pid, sig)
            stopped.append(pid)
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
        "message": f"Stopped {len(stopped)} OBS process(es)",
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
    # Stop OBS
    stop_result = stop_obs(force=force)

    if stop_result["status"] not in ["stopped", "not_running", "partial"]:
        return {
            "status": "error",
            "message": "Failed to stop OBS",
            "stop_result": stop_result,
        }

    # Wait a moment for cleanup
    import time
    time.sleep(1)

    # Start OBS
    start_result = start_obs(custom_command=custom_command, env_vars=env_vars)

    return {
        "status": "restarted" if start_result["status"] == "started" else start_result["status"],
        "stop_result": stop_result,
        "start_result": start_result,
    }
