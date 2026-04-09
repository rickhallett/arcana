import json
import logging
import sys
from datetime import UTC, datetime


class JSONFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        log_entry = {
            "ts": datetime.now(UTC).isoformat(),
            "level": record.levelname.lower(),
            "source": record.name,
            "event": record.getMessage(),
        }
        if hasattr(record, "data"):
            log_entry["data"] = record.data
        if hasattr(record, "correlation_id"):
            log_entry["correlation_id"] = record.correlation_id
        if record.exc_info and record.exc_info[0] is not None:
            log_entry["error"] = self.formatException(record.exc_info)
        return json.dumps(log_entry)


def get_logger(name: str) -> logging.Logger:
    logger = logging.getLogger(f"arcana.{name}")
    if not logger.handlers:
        handler = logging.StreamHandler(sys.stderr)
        handler.setFormatter(JSONFormatter())
        logger.addHandler(handler)
        logger.setLevel(logging.INFO)
    return logger


def log(
    source: str,
    level: str,
    event: str,
    data: dict | None = None,
    correlation_id: str | None = None,
) -> None:
    logger = get_logger(source)
    extra = {}
    if data is not None:
        extra["data"] = data
    if correlation_id is not None:
        extra["correlation_id"] = correlation_id
    record = logger.makeRecord(
        logger.name, getattr(logging, level.upper()), "", 0, event, (), None
    )
    for k, v in extra.items():
        setattr(record, k, v)
    logger.handle(record)
