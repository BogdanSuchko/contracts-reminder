from __future__ import annotations

import logging
from logging import Logger


def setup_logging(level: str = "INFO") -> Logger:
    logging.basicConfig(
        level=level,
        format="%(asctime)s | %(levelname)s | %(name)s | %(message)s",
    )
    return logging.getLogger("contract_bot")
