from notify import notif
import subprocess

def main():
    notif(title="Shutdown Enforcer", message="Shutting down now.", ms=2000)
    subprocess.run(["shutdown", "/s", "/t", "0"])
    notif("Shutdown Enforcer", "Shutdown command executed.", ms=2000)

if __name__ == "__main__":
    try:
        main()
    except Exception as e:
        notif("Shutdown Enforcer Error", f"An error occurred: {e}", ms=4000)