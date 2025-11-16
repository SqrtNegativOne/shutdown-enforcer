import tkinter

BG_COLOR = 'black'
TEXT_COLOR = 'white'

SHOW_MILLISECONDS = 800

def notif(title, message, logger, ms=SHOW_MILLISECONDS):
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
