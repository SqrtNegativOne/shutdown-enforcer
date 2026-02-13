import subprocess
import ctypes
from datetime import datetime, timedelta
from tzlocal import get_localzone
from typing import Final
from pathlib import Path
import psutil
from utils import logger


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

ROOT_DIR = Path(__file__).parent.parent.resolve()
VENV_PY_EXE = ROOT_DIR / ".venv" / "Scripts" / "pythonw.exe"

SCRIPT_DIR = ROOT_DIR / "src"
NOTIFY_PY_FILE = SCRIPT_DIR / "notify.py" # ⚠️ .py instead of .pyw
CLOSE_PY_FILE = SCRIPT_DIR / "close.pyw"
SHUTDOWN_PY_FILE = SCRIPT_DIR / "shutdown.pyw"

FILES = [
    VENV_PY_EXE,
    NOTIFY_PY_FILE,
    CLOSE_PY_FILE,
    SHUTDOWN_PY_FILE,
]


def is_admin() -> bool:
    try:
        return ctypes.windll.shell32.IsUserAnAdmin()
    except Exception:
        return False


def parse_time(t: str):
    ti = datetime.strptime(t, "%H:%M").time()
    now = datetime.now(_LOCAL_TZ)
    return now.replace(hour=ti.hour, minute=ti.minute, second=0, microsecond=0)


def _hidden_startupinfo():
    si = subprocess.STARTUPINFO()
    si.dwFlags |= subprocess.STARTF_USESHOWWINDOW
    si.wShowWindow = subprocess.SW_HIDE
    return si


def run_cmd(args):
    """Run a command safely, log output, and raise on failure."""
    logger.info(f"Running command: {' '.join(args)}")
    try:
        result = subprocess.run(
            args,
            check=True,
            capture_output=True,
            text=True,
            startupinfo=_hidden_startupinfo(),
            creationflags=subprocess.CREATE_NO_WINDOW,
        )
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
        encoding="utf-8",
        startupinfo=_hidden_startupinfo(),
        creationflags=subprocess.CREATE_NO_WINDOW,
    )
    for line in result.stdout.splitlines():
        if TASK_PREFIX in line:
            task_name = line.split(",")[0].strip('"')
            logger.info(f"Deleting old task {task_name}")
            subprocess.run(
                ["schtasks", "/delete", "/tn", task_name, "/f"],
                stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                startupinfo=_hidden_startupinfo(),
                creationflags=subprocess.CREATE_NO_WINDOW,
            )


def create_task(name: str, command: str, run_time):
    if isinstance(run_time, str):
        run_time = parse_time(run_time)
    
    now = datetime.now(_LOCAL_TZ)
    if run_time < now:
        logger.info(f"Requested run_time {run_time} is in the past. Giving up on this task.")
        return

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
        "/ru", psutil.Process().username(),
        "/rl", "HIGHEST",
        "/f",
    ]

    logger.info(f"Creating task: {full_name} at {run_time.isoformat()}")
    run_cmd(cmd)


def get_py_file_cmd(py_file_path: Path, args: str = "") -> str:
    return f'"{VENV_PY_EXE}" "{py_file_path}" {args}'


def setup_tasks():
    for file in FILES:
        if not file.exists():
            raise FileNotFoundError(f"Required file {file} not found. Ensure all necessary files are present before running setup.")

    if not is_admin():
        raise PermissionError("This script must be run with administrative privileges.")

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

    create_task(
        "InitialNotif",
        get_py_file_cmd(NOTIFY_PY_FILE, f'"Closure in {closure_diff} minutes (at {APP_CLOSURE})"'),
        initial_notif
    )

    create_task(
        "PreClosure",
        get_py_file_cmd(NOTIFY_PY_FILE, f'"Closure in {CLOSURE_REACTION_SECONDS} seconds"'),
        app_closure - timedelta(seconds=CLOSURE_REACTION_SECONDS)
    )

    create_task(
        "Closure",
        get_py_file_cmd(CLOSE_PY_FILE),
        app_closure
    )

    create_task(
        "PostClosureNotif",
        get_py_file_cmd(NOTIFY_PY_FILE, f'"Closed. Shutdown in {shutdown_diff} minutes (at {SHUTDOWN})"'),
        app_closure + timedelta(seconds=CLOSURE_REACTION_SECONDS + 5)
    )

    create_task(
        "PreShutdown",
        get_py_file_cmd(NOTIFY_PY_FILE, f'"Shutdown in {SHUTDOWN_REACTION_SECONDS} seconds (at {SHUTDOWN})"'),
        shutdown - timedelta(seconds=SHUTDOWN_REACTION_SECONDS)
    )

    create_task(
        "Shutdown",
        get_py_file_cmd(SHUTDOWN_PY_FILE),
        shutdown
    )

    logger.info("All tasks created successfully.")


if __name__ == "__main__":
    logger.info("Starting setup.pyw")
    try:
        setup_tasks()
    except Exception as e:
        logger.error(f"Error in setup.pyw: {e}")