"""Test trivial de humo: el paquete existe y la CLI responde como stub de M0."""

from __future__ import annotations

from pathlib import Path

import pytest
from typer.testing import CliRunner

import qa
from qa.cli import NOT_IMPLEMENTED_EXIT, app

runner = CliRunner()


def test_version() -> None:
    assert qa.__version__ == "0.1.0"


def test_cli_stubs_exit_not_implemented() -> None:
    for args in (
        ["research", "run", "--hypothesis", "H1"],
        ["stats", "report"],
        ["forward", "run"],
        ["report", "daily"],
    ):
        result = runner.invoke(app, args)
        assert result.exit_code == NOT_IMPLEMENTED_EXIT, args
        assert "NO IMPLEMENTADO" in result.stdout


def test_cli_data_verify_ok_con_manifiestos_vacios(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """`qa data verify` con QA_ROOT vacio => OK (0 ficheros), sin red."""
    monkeypatch.setenv("QA_ROOT", str(tmp_path))
    result = runner.invoke(app, ["data", "verify"])
    assert result.exit_code == 0
    assert "OK: 0 ficheros" in result.stdout
