# Close all foreground windows.
import win32gui
import win32process
import psutil
from utils import logger
from notify import notif

app_closure_prompt = """All possible foreground windows have been closed.
Now perform shutdown ritual.
"""

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

if __name__ == "__main__":
    try:
        notif("Shutdown Enforcer", "Shutting down in 30 minutes.", ms=3000)
        win32gui.EnumWindows(enum_window_callback, None)
    except Exception as e:
        logger.error(f"Error in app_closure.pyw: {e}")
        notif("Shutdown Enforcer Error", f"An error occurred: {e}", ms=5000)