from utils import logger
from notify import notif
import subprocess

logger.info(f"Shutting down the system now.")
notif(title="Shutdown Enforcer", message="Shutting down now.", ms=2000)
subprocess.run(["shutdown", "/s", "/t", "0"])