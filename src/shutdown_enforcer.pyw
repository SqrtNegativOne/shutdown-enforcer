import subprocess
import ctypes
from datetime import datetime, timedelta
from tzlocal import get_localzone
import sys
from loguru import logger
from typing import Final
from pathlib import Path
import argparse
import psutil

_LOCAL_TZ = get_localzone()

NOTIFY_WINDOW_TITLE: Final[str] = "Shutdown Enforcer"

INITIAL_NOTIF: Final[str] = "23:00"
APP_CLOSURE: Final[str] = "23:35"
SHUTDOWN: Final[str] = "23:50"

GIVE_UP_BEFORE: Final[str] = "05:00"
GIVE_UP_AFTER: Final[str] = "23:30"

CLOSURE_REACTION_SECONDS: Final[int] = 30
SHUTDOWN_REACTION_SECONDS: Final[int] = 30
POST_SHUTDOWN_REMINDER_WAIT_SECONDS: Final[int] = 60

TASK_PREFIX: Final[str] = "ShutdownEnforcer_"

BASE_DIR: Final[Path] = Path(__file__).parent.parent
LOG_PATH: Final[Path] = BASE_DIR / 'log' / 'shutdown_enforcer.log'

logger.add(LOG_PATH)


def is_admin() -> bool:
    try:
        return ctypes.windll.shell32.IsUserAnAdmin()
    except Exception:
        return False


def parse_time(t: str):
    ti = datetime.strptime(t, "%H:%M").time()
    now = datetime.now(_LOCAL_TZ)
    return now.replace(hour=ti.hour, minute=ti.minute, second=0, microsecond=0)


def run_cmd(args):
    """Run a command safely, log output, and raise on failure."""
    logger.info(f"Running command: {' '.join(args)}")
    try:
        result = subprocess.run(args, check=True, capture_output=True, text=True)
        if result.stdout.strip():
            logger.info(result.stdout.strip())
    except subprocess.CalledProcessError as e:
        logger.error(f"Command failed: {' '.join(args)}\nstdout:\n{e.stdout}\nstderr:\n{e.stderr}")
        raise


def delete_existing_tasks():
    """Delete previously created ShutdownEnforcer tasks."""
    result = subprocess.run(
        ["schtasks", "/query", "/fo", "CSV", "/v"],
        capture_output=True,
        text=True,
        encoding="utf-8"
    )
    for line in result.stdout.splitlines():
        if TASK_PREFIX in line:
            task_name = line.split(",")[0].strip('"')
            logger.info(f"Deleting old task {task_name}")
            subprocess.run(
                ["schtasks", "/delete", "/tn", task_name, "/f"],
                stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL
            )


def create_task(name: str, command: str, run_time):
    if isinstance(run_time, str):
        run_time = parse_time(run_time)

    date_str = run_time.strftime("%d/%m/%Y")
    time_str = run_time.strftime("%H:%M:%S")
    full_name = f"{TASK_PREFIX}{name}_{run_time.strftime('%Y%m%d_%H%M')}"

    cmd = [
        "schtasks", "/create",
        "/tn", full_name,
        "/tr", command,
        "/sc", "once",
        "/sd", date_str,
        "/st", time_str,
        "/ru", f"{psutil.Process().username()}"
    ]

    logger.info(f"Creating task: {full_name} at {run_time.isoformat()}")
    run_cmd(cmd)


def notify(message: str, ms: int = 1500):
    """Delegated notification using your utils.notif() if available."""
    try:
        from utils import notif
        notif(title=NOTIFY_WINDOW_TITLE, message=message, logger=logger, ms=ms)
    except ImportError:
        logger.info(f"[NOTIFY] {message}")


def close_foreground_windows_safe():
    import win32gui
    import win32process

    def enum_window_callback(hwnd, _):
        if not win32gui.IsWindowVisible(hwnd) or not win32gui.IsWindowEnabled(hwnd):
            return
        if win32gui.GetParent(hwnd):
            return

        try:
            _, pid = win32process.GetWindowThreadProcessId(hwnd)
            proc = psutil.Process(pid)
            if proc.name().lower() in {"explorer.exe", "taskmgr.exe"}:
                return
            window_title = win32gui.GetWindowText(hwnd)
            if not window_title.strip():
                return
        except (psutil.NoSuchProcess, psutil.AccessDenied):
            return
        except Exception as e:
            logger.warning(f"Error checking process info: {e}")
            return

        logger.info(f"Closing window '{window_title}' from '{proc.name()}' (PID {pid})")
        try:
            win32gui.PostMessage(hwnd, 0x0010, 0, 0)
        except Exception as e:
            logger.error(f"Failed to close '{window_title}': {e}")

    win32gui.EnumWindows(enum_window_callback, None)


def setup_tasks():
    if not is_admin():
        raise PermissionError("This script must be run as administrator.")

    now = datetime.now(_LOCAL_TZ)
    if now > parse_time(GIVE_UP_AFTER) or now < parse_time(GIVE_UP_BEFORE):
        logger.info("Outside scheduling hours. Exiting.")
        return

    delete_existing_tasks()

    initial_notif = parse_time(INITIAL_NOTIF)
    app_closure = parse_time(APP_CLOSURE)
    shutdown = parse_time(SHUTDOWN)

    closure_diff = int((app_closure - initial_notif).total_seconds() // 60)
    shutdown_diff = int((shutdown - app_closure).total_seconds() // 60)

    py = sys.executable
    script = Path(__file__).resolve()

    def run(action, msg=None):
        base = f'"{py}" "{script}" --action {action}'
        if msg:
            base += f' --msg "{msg}"'
        return base

    create_task(
        "InitialNotif",
        run("notify", f"Closure in {closure_diff} minutes (at {APP_CLOSURE})"),
        initial_notif
    )

    create_task(
        "PreClosure",
        run("notify", f"Closure in {CLOSURE_REACTION_SECONDS} seconds"),
        app_closure - timedelta(seconds=CLOSURE_REACTION_SECONDS)
    )

    create_task(
        "Closure",
        run("close"),
        app_closure
    )

    create_task(
        "PostClosureNotif",
        run("notify", f"Closed. Shutdown in {shutdown_diff} minutes (at {SHUTDOWN})"),
        app_closure + timedelta(seconds=CLOSURE_REACTION_SECONDS + 5)
    )

    create_task(
        "PreShutdown",
        run("notify", f"Shutdown in {SHUTDOWN_REACTION_SECONDS} seconds (at {SHUTDOWN})"),
        shutdown - timedelta(seconds=SHUTDOWN_REACTION_SECONDS)
    )

    create_task(
        "Shutdown",
        run("shutdown_now"),
        shutdown
    )

    create_task(
        "PostShutdownReminder",
        run("notify", "Shutdown may have failed. Please shut down manually."),
        shutdown + timedelta(seconds=POST_SHUTDOWN_REMINDER_WAIT_SECONDS)
    )

    logger.info("All tasks created successfully.")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--action",
        choices=["setup", "notify", "close", "shutdown_now"],
        help="Action to perform. Defaults to 'setup' if omitted."
    )
    parser.add_argument("--msg", help="Optional message for notify")
    args = parser.parse_args()

    # Default to setup if --action missing
    action = args.action or "setup"
    logger.info(f"Script run with {action} action.")

    try:
        if action == "setup":
            logger.info(f"Setting up tasks.")
            setup_tasks()
        elif action == "notify":
            logger.info(f"Notifying.")
            notify(args.msg or "Notification")
        elif action == "close":
            logger.info(f"Closing all foreground windows.")
            close_foreground_windows_safe()
        elif action == "shutdown_now":
            logger.info(f"Shutting down the system now.")
            notify("Shutting down now.", ms=2000)
            # Sanity check before shutdown
            now = datetime.now(_LOCAL_TZ)
            if now < parse_time(SHUTDOWN) - timedelta(minutes=5):
                logger.warning("Shutdown invoked too early. Aborting shutdown.")
                sys.exit(1)
            subprocess.run(["shutdown", "/s", "/t", "0"])
    except subprocess.CalledProcessError as e:
        logger.error(f"Subprocess command failed: {e}")
        logger.error(f"Subprocess command failed with exit code {e.returncode}")
        logger.error(f"Command: {' '.join(e.cmd)}")
        logger.error(f"STDOUT: {e.stdout}")
        logger.error(f"STDERR: {e.stderr}") # This will likely contain the *real* error message
    except Exception as e:
        logger.exception(f"Fatal error in action '{action}': {e}")
        sys.exit(1)