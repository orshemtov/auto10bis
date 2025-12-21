import re
import sys
from pathlib import Path

from loguru import logger


def setup_logger(debug: bool = False) -> None:
    logger.remove()
    custom_format = "<green>{time:YYYY-MM-DD HH:mm:ss.SSS}</green> | <level>{level: <8}</level> | <level>{message}</level>"
    level = "DEBUG" if debug else "INFO"
    logger.add(sys.stderr, format=custom_format, level=level)


def find_project_root() -> Path:
    current = Path(__file__).resolve()
    for parent in current.parents:
        if (parent / "pyproject.toml").exists():
            return parent
    return current.parent


def parse_amount(text: str) -> float:
    pattern_1 = r"₪\s*([0-9]+)"  # ₪400, ₪ 400
    pattern_2 = r"([0-9]+)\s*₪"  # 400₪
    matches = re.search(pattern_1, text) or re.search(pattern_2, text)
    if not matches:
        raise ValueError(f"Could not parse amount from text: {text}")
    return float(matches.group(1))
