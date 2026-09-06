import subprocess
import ctypes
from datetime import datetime, timedelta
from tzlocal import get_localzone
from pathlib import Path
import psutil
import yaml
from utils import logger


_LOCAL_TZ = get_localzone()

ROOT_DIR = Path(__file__).parent.parent.resolve()
SCRIPT_DIR = ROOT_DIR / "src"

CONFIG_CANDIDATES = [
    ROOT_DIR / "config.yaml",
    SCRIPT_DIR / "config.yaml",
]
EXAMPLE_CANDIDATES = [
    ROOT_DIR / "config.yaml.example",
    SCRIPT_DIR / "config.yaml.example",
]

DEFAULT_CONFIG = {
    "task_prefix": "ShutdownEnforcer_",
    "notify_window_title": "Shutdown Enforcer",
    "app_closure": "23:50",
    "shutdown": "23:55",
    "reminder_minutes_before": [55, 10, 5, 4, 3, 2, 1],
    "closure_reaction_seconds": 30,
    "shutdown_reaction_seconds": 30,
    "post_shutdown_reminder_wait_seconds": 60,
}


def _normalize_time(val, default: str) -> str:
    if val is None:
        return default
    if isinstance(val, int):
        return f"{val // 60:02d}:{val % 60:02d}"
    if hasattr(val, "strftime"):
        return val.strftime("%H:%M")
    return str(val).strip()


def find_config_file() -> Path | None:
    for path in CONFIG_CANDIDATES:
        if path.is_file():
            return path
    for path in EXAMPLE_CANDIDATES:
        if path.is_file():
            logger.warning(
                f"Config file not found. Falling back to example config: {path}"
            )
            return path
    return None


def load_config() -> dict:
    cfg_file = find_config_file()
    if cfg_file is None:
        logger.warning("No configuration file found. Using default values.")
        return DEFAULT_CONFIG.copy()

    logger.info(f"Loading configuration from {cfg_file}")
    try:
        with open(cfg_file, "r", encoding="utf-8") as f:
            raw = yaml.safe_load(f) or {}
    except Exception as e:
        logger.error(
            f"Error reading configuration from {cfg_file}: {e}. Using defaults."
        )
        return DEFAULT_CONFIG.copy()

    reminders_raw = raw.get(
        "reminder_minutes_before", DEFAULT_CONFIG["reminder_minutes_before"]
    )
    if isinstance(reminders_raw, (list, tuple)):
        reminders = [int(m) for m in reminders_raw]
    else:
        reminders = DEFAULT_CONFIG["reminder_minutes_before"]

    return {
        "task_prefix": str(raw.get("task_prefix", DEFAULT_CONFIG["task_prefix"])),
        "notify_window_title": str(
            raw.get("notify_window_title", DEFAULT_CONFIG["notify_window_title"])
        ),
        "app_closure": _normalize_time(
            raw.get("app_closure"), DEFAULT_CONFIG["app_closure"]
        ),
        "shutdown": _normalize_time(
            raw.get("shutdown"), DEFAULT_CONFIG["shutdown"]
        ),
        "reminder_minutes_before": reminders,
        "closure_reaction_seconds": int(
            raw.get(
                "closure_reaction_seconds", DEFAULT_CONFIG["closure_reaction_seconds"]
            )
        ),
        "shutdown_reaction_seconds": int(
            raw.get(
                "shutdown_reaction_seconds",
                DEFAULT_CONFIG["shutdown_reaction_seconds"],
            )
        ),
        "post_shutdown_reminder_wait_seconds": int(
            raw.get(
                "post_shutdown_reminder_wait_seconds",
                DEFAULT_CONFIG["post_shutdown_reminder_wait_seconds"],
            )
        ),
    }


config = load_config()

TASK_PREFIX: str = config["task_prefix"]
NOTIFY_WINDOW_TITLE: str = config["notify_window_title"]
APP_CLOSURE: str = config["app_closure"]
SHUTDOWN: str = config["shutdown"]
REMINDER_MINUTES_BEFORE: list[int] = config["reminder_minutes_before"]
CLOSURE_REACTION_SECONDS: int = config["closure_reaction_seconds"]
SHUTDOWN_REACTION_SECONDS: int = config["shutdown_reaction_seconds"]
POST_SHUTDOWN_REMINDER_WAIT_SECONDS: int = config["post_shutdown_reminder_wait_seconds"]

VENV_PY_EXE = ROOT_DIR / ".venv" / "Scripts" / "pythonw.exe"

NOTIFY_PY_FILE = SCRIPT_DIR / "notify.py"  # ⚠️ .py instead of .pyw
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


def parse_time(t: str | int):
    if isinstance(t, int):
        t = f"{t // 60:02d}:{t % 60:02d}"
    elif hasattr(t, "strftime"):
        t = t.strftime("%H:%M")
    ti = datetime.strptime(str(t).strip(), "%H:%M").time()
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
        logger.error(
            f"Command failed: {' '.join(args)}\nstdout:\n{e.stdout}\nstderr:\n{e.stderr}"
        )
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
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                startupinfo=_hidden_startupinfo(),
                creationflags=subprocess.CREATE_NO_WINDOW,
            )


def create_task(name: str, command: str, run_time):
    if isinstance(run_time, str):
        run_time = parse_time(run_time)

    now = datetime.now(_LOCAL_TZ)
    if run_time < now:
        logger.info(
            f"Requested run_time {run_time} is in the past. Giving up on this task."
        )
        return

    date_str = run_time.strftime("%d/%m/%Y")
    time_str = run_time.strftime("%H:%M:%S")
    full_name = f"{TASK_PREFIX}{name}_{run_time.strftime('%Y%m%d_%H%M')}"

    cmd = [
        "schtasks",
        "/create",
        "/tn",
        full_name,
        "/tr",
        command,
        "/sc",
        "once",
        "/sd",
        date_str,
        "/st",
        time_str,
        "/ru",
        psutil.Process().username(),
        "/rl",
        "HIGHEST",
        "/f",
    ]

    logger.info(f"Creating task: {full_name} at {run_time.isoformat()}")
    run_cmd(cmd)


def get_py_file_cmd(py_file_path: Path, args: str = "") -> str:
    return f'"{VENV_PY_EXE}" "{py_file_path}" {args}'


def setup_tasks():
    global TASK_PREFIX, NOTIFY_WINDOW_TITLE, APP_CLOSURE, SHUTDOWN, REMINDER_MINUTES_BEFORE
    global CLOSURE_REACTION_SECONDS, SHUTDOWN_REACTION_SECONDS, POST_SHUTDOWN_REMINDER_WAIT_SECONDS

    cfg = load_config()
    TASK_PREFIX = cfg["task_prefix"]
    NOTIFY_WINDOW_TITLE = cfg["notify_window_title"]
    APP_CLOSURE = cfg["app_closure"]
    SHUTDOWN = cfg["shutdown"]
    REMINDER_MINUTES_BEFORE = cfg["reminder_minutes_before"]
    CLOSURE_REACTION_SECONDS = cfg["closure_reaction_seconds"]
    SHUTDOWN_REACTION_SECONDS = cfg["shutdown_reaction_seconds"]
    POST_SHUTDOWN_REMINDER_WAIT_SECONDS = cfg["post_shutdown_reminder_wait_seconds"]

    for file in FILES:
        if not file.exists():
            raise FileNotFoundError(
                f"Required file {file} not found. Ensure all necessary files are present before running setup."
            )

    if not is_admin():
        raise PermissionError("This script must be run with administrative privileges.")

    now = datetime.now(_LOCAL_TZ)

    delete_existing_tasks()

    app_closure_time = parse_time(APP_CLOSURE)
    shutdown_time = parse_time(SHUTDOWN)

    if REMINDER_MINUTES_BEFORE:
        max_reminder = max(REMINDER_MINUTES_BEFORE)
        initial_notif_time = app_closure_time - timedelta(minutes=max_reminder)
    else:
        initial_notif_time = app_closure_time - timedelta(minutes=30)

    shutdown_diff_mins = int((shutdown_time - app_closure_time).total_seconds() // 60)

    if now < initial_notif_time:
        create_task(
            "InitShutdown",
            get_py_file_cmd(
                SHUTDOWN_PY_FILE,
                f'"{int((shutdown_time - initial_notif_time).total_seconds() // 60)}"',
            ),
            initial_notif_time,
        )
    elif now < shutdown_time:
        init_run_time = now + timedelta(seconds=15)
        create_task(
            "InitShutdown",
            get_py_file_cmd(
                SHUTDOWN_PY_FILE,
                f'"{int((shutdown_time - init_run_time).total_seconds() // 60)}"',
            ),
            init_run_time,
        )

    create_task(
        "PreClosure",
        get_py_file_cmd(
            NOTIFY_PY_FILE,
            f'"{NOTIFY_WINDOW_TITLE}" "Closure in {CLOSURE_REACTION_SECONDS} seconds"',
        ),
        app_closure_time - timedelta(seconds=CLOSURE_REACTION_SECONDS),
    )

    create_task("Closure", get_py_file_cmd(CLOSE_PY_FILE), app_closure_time)

    create_task(
        "PostClosureNotif",
        get_py_file_cmd(
            NOTIFY_PY_FILE,
            f'"{NOTIFY_WINDOW_TITLE}" "Closed. Shutdown in {shutdown_diff_mins} minutes (at {SHUTDOWN})"',
        ),
        app_closure_time + timedelta(seconds=CLOSURE_REACTION_SECONDS + 5),
    )

    for mins in REMINDER_MINUTES_BEFORE:
        unit = "minute" if mins == 1 else "minutes"
        create_task(
            f"ClosureReminder{mins}min",
            get_py_file_cmd(
                NOTIFY_PY_FILE,
                f'"{NOTIFY_WINDOW_TITLE}" "Closure in {mins} {unit} (at {APP_CLOSURE})"',
            ),
            app_closure_time - timedelta(minutes=mins),
        )

    for mins in REMINDER_MINUTES_BEFORE:
        unit = "minute" if mins == 1 else "minutes"
        create_task(
            f"ShutdownReminder{mins}min",
            get_py_file_cmd(
                NOTIFY_PY_FILE,
                f'"{NOTIFY_WINDOW_TITLE}" "Shutdown in {mins} {unit} (at {SHUTDOWN})"',
            ),
            shutdown_time - timedelta(minutes=mins),
        )

    create_task(
        "PreShutdown",
        get_py_file_cmd(
            NOTIFY_PY_FILE,
            f'"{NOTIFY_WINDOW_TITLE}" "Shutdown in {SHUTDOWN_REACTION_SECONDS} seconds (at {SHUTDOWN})"',
        ),
        shutdown_time - timedelta(seconds=SHUTDOWN_REACTION_SECONDS),
    )

    logger.info("All tasks created successfully.")


if __name__ == "__main__":
    logger.info("Starting setup.pyw")
    try:
        setup_tasks()
    except Exception as e:
        logger.error(f"Error in setup.pyw: {e}")

