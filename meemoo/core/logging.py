"""Structured logging: JSON lines for machines, readable console for humans.

Use ``logging.getLogger(__name__)`` everywhere; call :func:`setup_logging` once
at startup. Pass structured context via ``extra={"fields": {...}}``.
"""

from __future__ import annotations

import json
import logging
import sys
from datetime import UTC, datetime

from meemoo.core.versioning import version_fields

_SETUP_DONE = False


class JsonFormatter(logging.Formatter):
    """One JSON object per line; safe for ingestion and the audit trail."""

    def format(self, record: logging.LogRecord) -> str:
        payload: dict[str, object] = {
            "ts": datetime.now(UTC).isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "msg": record.getMessage(),
        }
        fields = getattr(record, "fields", None)
        if isinstance(fields, dict):
            payload.update(fields)
        if record.exc_info and record.exc_info[0] is not None:
            payload["exc"] = self.formatException(record.exc_info)
        return json.dumps(payload, default=str)


class ConsoleFormatter(logging.Formatter):
    """Human console line, with structured fields appended as key=value."""

    def format(self, record: logging.LogRecord) -> str:
        base = (
            f"{datetime.now(UTC).strftime('%H:%M:%S')} "
            f"{record.levelname:<7} {record.name}: {record.getMessage()}"
        )
        fields = getattr(record, "fields", None)
        if isinstance(fields, dict) and fields:
            kv = " ".join(f"{k}={v}" for k, v in fields.items())
            base = f"{base} [{kv}]"
        if record.exc_info and record.exc_info[0] is not None:
            base = f"{base}\n{self.formatException(record.exc_info)}"
        return base


def escalation_extra(**fields: object) -> dict[str, dict[str, object]]:
    """``extra=`` dict for escalation-relevant log lines, version-stamped.

    Merges the caller's fields with the active model/prompt/threshold versions
    (see :mod:`meemoo.core.versioning`) so every escalation record says which
    brain and thresholds were in force. Usage::

        logger.warning("escalating to L1", extra=escalation_extra(alert_id=7))
    """
    merged: dict[str, object] = dict(version_fields())
    merged.update(fields)
    return {"fields": merged}


def setup_logging(*, json_output: bool = False, level: str = "INFO") -> None:
    """Configure the root logger once; later calls are no-ops."""
    global _SETUP_DONE
    if _SETUP_DONE:
        return
    handler = logging.StreamHandler(sys.stderr)
    handler.setFormatter(JsonFormatter() if json_output else ConsoleFormatter())
    root = logging.getLogger()
    root.handlers.clear()
    root.addHandler(handler)
    root.setLevel(level.upper())
    _SETUP_DONE = True
