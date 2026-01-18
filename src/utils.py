from loguru import logger
from typing import Final
from pathlib import Path
BASE_DIR: Final[Path] = Path(__file__).parent.parent
LOG_PATH: Final[Path] = BASE_DIR / 'log' / 'shutdown_enforcer.log'
logger.add(LOG_PATH)