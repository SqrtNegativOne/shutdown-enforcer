import tkinter
from utils import logger

BG_COLOR = 'black'
TEXT_COLOR = 'white'

SHOW_MILLISECONDS = 800

def notif(title, message, ms=SHOW_MILLISECONDS):
    logger.info(f"Notification: {title} - {message}")

    root = tkinter.Tk()
    root.title(title)
    root.geometry("350x100")
    root.config(bg=BG_COLOR)
    root.attributes("-topmost", True)
    root.resizable(False, False)
    label = tkinter.Label(
        root,
        text=message,
        font=("Segoe UI", 16),
        wraplength=320,
        justify="center",
        bg=BG_COLOR,
        foreground=TEXT_COLOR
    )
    label.pack(
        expand=True,
        fill="both",
        padx=10,
        pady=10
    )
    root.after(ms, root.destroy)
    root.mainloop()

if __name__ == "__main__":
    import sys
    if len(sys.argv) < 2:
        logger.error(f"Insufficient arguments for notification given. Arguments received: {sys.argv}. Providing test response.")
        title = "Test Notification"
        message = "This is a test notification. Please provide title and message as arguments for actual notifications."
    elif len(sys.argv) == 2:
        title = "Shutdown Enforcer"
        message = sys.argv[1]
    else:
        title = sys.argv[1]
        message = sys.argv[2]
    try:
        notif(title, message)
    except Exception as e:
        logger.error(f"Failed to show notification: {e}")
        sys.exit(1)