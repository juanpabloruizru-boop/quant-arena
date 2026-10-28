"""Test trivial de humo: el paquete existe y la CLI responde como stub de M0."""

from __future__ import annotations

from pathlib import Path

import pytest
from typer.testing import CliRunner

import qa
from qa.cli import app

runner = CliRunner()


def test_version() -> None:
    assert qa.__version__ == "0.1.0"


def test_cli_report_daily_points_to_agent() -> None:
    """M4/M5: ya no hay stubs; `report daily` redirige al dashboard."""
    result = runner.invoke(app, ["report", "daily"])
    assert result.exit_code == 0
    assert "qa agent run" in result.stdout


def test_cli_stats_report_ledger_vacio(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("QA_ROOT", str(tmp_path))
    result = runner.invoke(app, ["stats", "report"])
    assert result.exit_code == 0
    assert "Ledger de trials vacio" in result.stdout


def test_cli_data_verify_ok_con_manifiestos_vacios(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """`qa data verify` con QA_ROOT vacio => OK (0 ficheros), sin red."""
    monkeypatch.setenv("QA_ROOT", str(tmp_path))
    result = runner.invoke(app, ["data", "verify"])
    assert result.exit_code == 0
    assert "OK: 0 ficheros" in result.stdout
