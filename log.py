from loguru import logger
import sys


def setup_logger(debug: bool = False) -> None:
    logger.remove()
    custom_format = "<green>{time:YYYY-MM-DD HH:mm:ss.SSS}</green> | <level>{level: <8}</level> | <level>{message}</level>"
    level = "DEBUG" if debug else "INFO"
    logger.add(sys.stderr, format=custom_format, level=level)
