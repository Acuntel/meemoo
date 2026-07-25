"""Version registry: model/prompt/threshold stamps for escalation records.

Every escalation-relevant record (audit rows, alerts, escalation log lines)
must say WHICH model, prompt, and detection thresholds were in force at the
time (TODO Phase 1). Modules register their versions at startup; the audit
helpers and logging helpers read them here.
"""

from __future__ import annotations

_VERSIONS: dict[str, str] = {}

VERSION_KINDS = ("model", "prompt", "threshold")


def set_version(kind: str, value: str) -> None:
    """Register the active version for ``kind`` ('model'|'prompt'|'threshold')."""
    if kind not in VERSION_KINDS:
        raise ValueError(f"unknown version kind {kind!r}; expected one of {VERSION_KINDS}")
    _VERSIONS[kind] = value


def get_versions() -> dict[str, str]:
    """Snapshot of currently registered versions (may be empty in early boot)."""
    return dict(_VERSIONS)


def version_fields() -> dict[str, object]:
    """Versions shaped as log/DB field names: model_version, prompt_version, ..."""
    return {f"{kind}_version": value for kind, value in _VERSIONS.items()}


def reset_versions() -> None:
    """Clear the registry (tests only)."""
    _VERSIONS.clear()
