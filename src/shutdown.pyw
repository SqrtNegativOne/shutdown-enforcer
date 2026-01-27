from notify import notif
import subprocess

notif(title="Shutdown Enforcer", message="Shutting down now.", ms=2000)
subprocess.run(["shutdown", "/s", "/t", "0"])
notif("Shutdown Enforcer", "Shutdown command executed.", ms=2000)