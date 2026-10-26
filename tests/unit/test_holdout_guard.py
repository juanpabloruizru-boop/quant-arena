"""Guard de holdout en RUNTIME (condicion del gate M1).

- Sin QA_HOLDOUT_UNLOCK: el motor se NIEGA a cargar *_holdout.parquet.
- Con QA_HOLDOUT_UNLOCK=1: carga y escribe fila append-only en
  ledger/holdout_access.log con sha256 del fichero, git SHA y proposito.
"""

from __future__ import annotations

import json
from pathlib import Path

import pandas as pd
import pytest

from qa.backtest.data_access import HoldoutSealedError, load_holdout, load_in_sample


@pytest.fixture()
def fake_root(tmp_path: Path) -> Path:
    (tmp_path / "holdout_sealed").mkdir()
    (tmp_path / "data" / "curated").mkdir(parents=True)
    df = pd.DataFrame({"symbol": ["BTCUSDT"], "close": [1.0]})
    df.to_parquet(tmp_path / "holdout_sealed" / "spot_daily_holdout.parquet")
    df.to_parquet(tmp_path / "data" / "curated" / "spot_daily_in_sample.parquet")
    return tmp_path


def test_holdout_refused_without_env(fake_root: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("QA_HOLDOUT_UNLOCK", raising=False)
    with pytest.raises(HoldoutSealedError):
        load_holdout("spot_daily", fake_root, purpose="test")
    assert not (fake_root / "ledger" / "holdout_access.log").exists()


def test_holdout_unlock_logs_append_only(fake_root: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("QA_HOLDOUT_UNLOCK", "1")
    df = load_holdout("spot_daily", fake_root, purpose="evaluacion-unica-M3")
    assert len(df) == 1
    log = fake_root / "ledger" / "holdout_access.log"
    assert log.exists()
    lines = log.read_text().strip().splitlines()
    assert len(lines) == 1
    entry = json.loads(lines[0])
    assert len(entry["sha256"]) == 64
    assert entry["purpose"] == "evaluacion-unica-M3"
    assert "git_sha" in entry
    # segunda lectura => segunda fila (append-only, nunca sobrescribe)
    load_holdout("spot_daily", fake_root, purpose="segunda-lectura")
    assert len(log.read_text().strip().splitlines()) == 2


def test_in_sample_loads_without_unlock(fake_root: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("QA_HOLDOUT_UNLOCK", raising=False)
    df = load_in_sample("spot_daily", fake_root)
    assert len(df) == 1
