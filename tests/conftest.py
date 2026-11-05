"""Configuración global de fixtures de prueba para QUANT-ARENA v2."""

from __future__ import annotations

from collections.abc import Generator
from pathlib import Path

import pytest

import qa._pandas_compat  # noqa: F401

REPO = Path(__file__).resolve().parents[1]


@pytest.fixture(autouse=True, scope="session")
def _protect_env_file_during_tests() -> Generator[None, None, None]:
    """Protege el archivo .env durante la ejecución de los tests de seguridad M0."""
    env_file = REPO / ".env"
    backup: bytes | None = None
    if env_file.exists():
        backup = env_file.read_bytes()
        env_file.unlink()
    try:
        yield
    finally:
        if backup is not None:
            env_file.write_bytes(backup)
