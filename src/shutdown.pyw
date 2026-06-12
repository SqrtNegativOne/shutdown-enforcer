from notify import notif
import subprocess
import sys

DEFAULT_MINS = 45

def shutdown_and_notify(mins: int):
    subprocess.run(["shutdown", "/s", "/t", str(mins * 60)])
    notif("Shutdown Enforcer", f"Shutdown scheduled in {mins} minutes.", ms=3000)

def main():
    if len(sys.argv) < 2:
        notif("Shutdown Enforcer Error", f"No arguments provided. Shutting down in {DEFAULT_MINS} minutes.", ms=3000)
        shutdown_and_notify(DEFAULT_MINS)
        return

    try:
        mins = int(sys.argv[1])
    except ValueError as ve:
        notif("Shutdown Enforcer Error", f"Invalid input for minutes: {ve}. Must be a positive integer. Shutting down in {DEFAULT_MINS} minutes.", ms=4000)
        shutdown_and_notify(DEFAULT_MINS)
        return

    if mins <= 0:
        notif("Shutdown Enforcer Error", f"Invalid input for minutes: {mins}. Must be a positive integer. Shutting down in {DEFAULT_MINS} minutes.", ms=4000)
        shutdown_and_notify(DEFAULT_MINS)
        return

    shutdown_and_notify(mins)

if __name__ == "__main__":
    try:
        main()
    except Exception as e:
        notif("Shutdown Enforcer Error", f"An error occurred: {e}", ms=4000)