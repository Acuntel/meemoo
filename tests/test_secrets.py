"""Secrets tests: Fernet round-trip; key material NEVER in logs or repr."""

from __future__ import annotations

import logging
from collections.abc import Iterator
from pathlib import Path

import pytest
from cryptography.fernet import Fernet

from meemoo.core import secrets
from meemoo.core.config import get_settings
from meemoo.core.models import ProviderKey

PLAINTEXT = "sk-ant-EXAMPLE-super-secret-value-12345"


@pytest.fixture
def key_env(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> Iterator[Path]:
    """No env key; key file lives in tmp. Returns the key-file path."""
    key_file = tmp_path / "keys" / "fernet.key"
    monkeypatch.delenv("MEEMOO_FERNET_KEY", raising=False)
    monkeypatch.setenv("MEEMOO_FERNET_KEY_FILE", str(key_file))
    monkeypatch.chdir(tmp_path)
    get_settings.cache_clear()
    yield key_file
    get_settings.cache_clear()


def test_round_trip(key_env: Path) -> None:
    token = secrets.encrypt_secret(PLAINTEXT)
    assert token != PLAINTEXT.encode()
    assert secrets.decrypt_secret(token) == PLAINTEXT


def test_key_file_generated_and_reused(key_env: Path) -> None:
    assert not key_env.exists()
    secrets.encrypt_secret(PLAINTEXT)  # first use generates the key
    assert key_env.exists()
    assert (key_env.stat().st_mode & 0o777) == 0o600
    first_key = key_env.read_bytes()
    secrets.encrypt_secret(PLAINTEXT)
    assert key_env.read_bytes() == first_key  # reused, not regenerated


def test_env_key_wins_over_file(
    key_env: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    env_key = Fernet.generate_key().decode()
    monkeypatch.setenv("MEEMOO_FERNET_KEY", env_key)
    get_settings.cache_clear()
    token = secrets.encrypt_secret(PLAINTEXT)
    assert Fernet(env_key.encode()).decrypt(token).decode() == PLAINTEXT
    assert not key_env.exists()  # no file generated when env key present


def test_missing_key_never_crashes_startup(key_env: Path) -> None:
    """Art. IX §3: no configured key → generate, don't die."""
    fernet = secrets.get_fernet()
    assert fernet.decrypt(fernet.encrypt(b"x")) == b"x"


def test_decrypt_with_wrong_key_raises_clean_error(
    key_env: Path, caplog: pytest.LogCaptureFixture
) -> None:
    token = Fernet(Fernet.generate_key()).encrypt(PLAINTEXT.encode())
    with caplog.at_level(logging.DEBUG), pytest.raises(secrets.SecretDecryptError):
        secrets.decrypt_secret(token)
    assert PLAINTEXT not in caplog.text
    assert token.decode() not in caplog.text


def test_key_material_never_in_logs(
    key_env: Path, caplog: pytest.LogCaptureFixture
) -> None:
    with caplog.at_level(logging.DEBUG):
        token = secrets.encrypt_secret(PLAINTEXT)
        secrets.decrypt_secret(token)
    assert PLAINTEXT not in caplog.text
    assert key_env.read_bytes().decode() not in caplog.text  # the Fernet key itself


def test_provider_key_repr_hides_key_material(key_env: Path) -> None:
    token = secrets.encrypt_secret(PLAINTEXT)
    row = ProviderKey(device_id=1, provider="anthropic", encrypted_key=token)
    row.id = 7
    shown = repr(row)
    assert PLAINTEXT not in shown
    assert token.decode() not in shown
    assert "anthropic" in shown  # still useful for debugging
