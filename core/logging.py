import logging
import sys
from pathlib import Path

from rich.console import Console
from rich.logging import RichHandler

console = Console()

_LOG_DIR = Path.home() / ".bobby" / "logs"
_LOG_DIR.mkdir(parents=True, exist_ok=True)


def get_logger(name: str) -> logging.Logger:
    logger = logging.getLogger(name)
    if logger.handlers:
        return logger

    logger.setLevel(logging.DEBUG)

    # Rich console handler (pretty output)
    rich_handler = RichHandler(console=console, show_path=False, markup=True)
    rich_handler.setLevel(logging.INFO)
    logger.addHandler(rich_handler)

    # File handler (full debug logs)
    file_handler = logging.FileHandler(_LOG_DIR / "bobby.log")
    file_handler.setLevel(logging.DEBUG)
    file_handler.setFormatter(
        logging.Formatter("%(asctime)s %(levelname)s %(name)s — %(message)s")
    )
    logger.addHandler(file_handler)

    return logger
