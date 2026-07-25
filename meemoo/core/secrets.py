"""Fernet encryption for provider API keys (Constitution Art. IX; TODO Phase 1).

Key material sources, in order:
1. ``MEEMOO_FERNET_KEY`` env/setting (deployments)
2. a local key file (generated on first use, chmod 0600)

Plaintext secrets are NEVER logged, never stored, and never appear in
``repr()`` of anything in this module. A missing key never crashes startup —
the key is simply generated.
"""

from __future__ import annotations

import logging
from pathlib import Path

from cryptography.fernet import Fernet, InvalidToken

from meemoo.core.config import get_settings

logger = logging.getLogger(__name__)


class SecretDecryptError(Exception):
    """Raised when a stored ciphertext cannot be decrypted with our key."""


def _load_or_create_key(key_file: Path) -> bytes:
    if key_file.exists():
        return key_file.read_bytes().strip()
    key = Fernet.generate_key()
    key_file.parent.mkdir(parents=True, exist_ok=True)
    key_file.write_bytes(key)
    key_file.chmod(0o600)
    logger.info(
        "generated new Fernet key file",
        extra={"fields": {"path": str(key_file)}},  # path only — never the key
    )
    return key


def get_fernet() -> Fernet:
    """The process Fernet, from env or the local key file (created if absent)."""
    settings = get_settings()
    if settings.meemoo_fernet_key:
        return Fernet(settings.meemoo_fernet_key.encode())
    return Fernet(_load_or_create_key(Path(settings.meemoo_fernet_key_file)))


def encrypt_secret(plaintext: str) -> bytes:
    """Encrypt a provider key for at-rest storage. Never log the argument."""
    return get_fernet().encrypt(plaintext.encode())


def decrypt_secret(ciphertext: bytes) -> str:
    """Decrypt a stored provider key. Never log the return value."""
    try:
        return get_fernet().decrypt(ciphertext).decode()
    except InvalidToken as exc:
        # Deliberately no ciphertext/key material in the error or the log.
        logger.error("provider key decrypt failed (wrong or rotated Fernet key)")
        raise SecretDecryptError("cannot decrypt stored key") from exc
