import os
from loguru import logger

LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO")

logger.add(
    "logs/code_editor.log",
    rotation="50 MB",
    level=LOG_LEVEL,
    format="{time:YYYY-MM-DD at HH:mm:ss} | {level} | {message}",
)
