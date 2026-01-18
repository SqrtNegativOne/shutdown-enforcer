# Close all foreground windows.
import win32gui
import win32process
import psutil
from utils import logger

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