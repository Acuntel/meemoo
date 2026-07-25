"""Logging tests: JSON fields pass through; escalation lines carry versions."""

from __future__ import annotations

import json
import logging
from collections.abc import Mapping

from meemoo.core.logging import JsonFormatter, escalation_extra
from meemoo.core.versioning import get_versions, reset_versions, set_version, version_fields


def _record_with_extra(extra: Mapping[str, object]) -> logging.LogRecord:
    record = logging.LogRecord(
        name="test", level=logging.WARNING, pathname=__file__, lineno=1,
        msg="escalating", args=(), exc_info=None,
    )
    for key, value in extra.items():
        setattr(record, key, value)
    return record


def test_json_formatter_includes_structured_fields() -> None:
    record = _record_with_extra({"fields": {"alert_id": 7}})
    payload = json.loads(JsonFormatter().format(record))
    assert payload["msg"] == "escalating"
    assert payload["alert_id"] == 7
    assert payload["level"] == "WARNING"


def test_escalation_extra_stamps_versions() -> None:
    reset_versions()
    try:
        set_version("model", "scripted-fallback-v1")
        set_version("prompt", "checkin-v3")
        set_version("threshold", "fall-v0")
        extra = escalation_extra(alert_id=42, device_id=1)
        assert extra["fields"]["model_version"] == "scripted-fallback-v1"
        assert extra["fields"]["prompt_version"] == "checkin-v3"
        assert extra["fields"]["threshold_version"] == "fall-v0"
        assert extra["fields"]["alert_id"] == 42

        payload = json.loads(JsonFormatter().format(_record_with_extra(extra)))
        assert payload["model_version"] == "scripted-fallback-v1"
    finally:
        reset_versions()


def test_version_registry_helpers() -> None:
    reset_versions()
    try:
        assert get_versions() == {}
        assert version_fields() == {}
        set_version("model", "m1")
        assert get_versions() == {"model": "m1"}
        try:
            set_version("bogus", "x")
            raised = False
        except ValueError:
            raised = True
        assert raised
    finally:
        reset_versions()
