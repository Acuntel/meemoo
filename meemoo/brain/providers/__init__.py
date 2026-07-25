"""Provider factory: name → adapter, credentials resolved, never crashing.

Convention over registration: provider ``"x"`` lives in
``meemoo/brain/providers/x.py`` and exports ``PROVIDER`` (the class). Adding a
fifth provider is exactly one new file — proved by ``fake.py`` and the tests,
which also inject a synthetic module to show no other edits are needed.

Credential resolution order (Art. IX §3 — missing creds never crash):
1. explicit argument
2. process settings (env / .env)
3. encrypted ``provider_keys`` row for the device (Fernet at rest)
If nothing is found and the provider requires a credential, the factory
returns ``None`` and the caller degrades (scripted fallback).
"""

from __future__ import annotations

import importlib
import logging

from sqlalchemy.orm import Session as DbSession
from sqlalchemy.orm import sessionmaker

from meemoo.brain.types import Provider
from meemoo.core.config import get_settings
from meemoo.core.models import ProviderKey
from meemoo.core.secrets import SecretDecryptError, decrypt_secret

logger = logging.getLogger(__name__)

#: Providers shipped in-tree (any module in this package works — this list is
#: only used for "pick the first configured provider" conveniences).
KNOWN_PROVIDERS = ("anthropic", "openai", "google", "ollama", "fake")


def load_provider_class(name: str) -> type[Provider] | None:
    """Import ``meemoo.brain.providers.<name>`` and return its ``PROVIDER``."""
    if not name.replace("_", "").isalnum():
        logger.warning("invalid provider name", extra={"fields": {"provider": name}})
        return None
    try:
        module = importlib.import_module(f"{__name__}.{name}")
    except ImportError:
        logger.warning("unknown provider module", extra={"fields": {"provider": name}})
        return None
    cls = getattr(module, "PROVIDER", None)
    if cls is None or not (isinstance(cls, type) and issubclass(cls, Provider)):
        logger.warning("provider module has no PROVIDER class",
                       extra={"fields": {"provider": name}})
        return None
    return cls


def _settings_key(name: str) -> str | None:
    settings = get_settings()
    return {
        "anthropic": settings.anthropic_api_key,
        "openai": settings.openai_api_key,
        "google": settings.google_api_key,
    }.get(name)


def _db_key(name: str, device_id: int, db_factory: sessionmaker[DbSession]) -> str | None:
    with db_factory() as db:
        row = (
            db.query(ProviderKey)
            .filter(ProviderKey.device_id == device_id, ProviderKey.provider == name)
            .one_or_none()
        )
        if row is None:
            return None
        try:
            return decrypt_secret(row.encrypted_key)
        except SecretDecryptError:
            return None  # already logged (without key material) by secrets.py


def create_provider(
    name: str,
    *,
    api_key: str | None = None,
    base_url: str | None = None,
    device_id: int = 1,
    db_factory: sessionmaker[DbSession] | None = None,
) -> Provider | None:
    """Build a ready-to-call provider, or ``None`` if it can't be configured."""
    cls = load_provider_class(name)
    if cls is None:
        return None
    if cls.requires_key and api_key is None:
        api_key = _settings_key(name)
        if api_key is None and db_factory is not None:
            api_key = _db_key(name, device_id, db_factory)
    if cls.requires_url and base_url is None:
        base_url = get_settings().ollama_url if name == "ollama" else None
    if (cls.requires_key and not api_key) or (cls.requires_url and not base_url):
        logger.info(
            "provider not configured (no credential) — degrading",
            extra={"fields": {"provider": name}},
        )
        return None
    return cls(api_key=api_key, base_url=base_url)


def first_available(
    *, device_id: int = 1, db_factory: sessionmaker[DbSession] | None = None
) -> Provider | None:
    """First hosted/local provider that is actually configured, else None."""
    for name in KNOWN_PROVIDERS[:-1]:  # "fake" is never auto-selected
        provider = create_provider(name, device_id=device_id, db_factory=db_factory)
        if provider is not None:
            return provider
    return None
