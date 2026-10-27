"""Sellado cifrado del holdout (condicion E, gate M2): flujo completo."""

from __future__ import annotations

import json
import shutil
from pathlib import Path

import pandas as pd
import pytest

from qa.backtest.data_access import HoldoutSealedError, load_holdout
from qa.backtest.seal import is_sealed, key_fingerprint, open_holdout_file, seal_holdout

needs_gpg = pytest.mark.skipif(shutil.which("gpg") is None, reason="gpg no disponible")


@pytest.fixture()
def root(tmp_path: Path) -> Path:
    (tmp_path / "holdout_sealed").mkdir()
    df = pd.DataFrame({"symbol": ["BTCUSDT", "ETHUSDT"], "close": [1.0, 2.0]})
    df.to_parquet(tmp_path / "holdout_sealed" / "spot_daily_holdout.parquet")
    return tmp_path


@needs_gpg
def test_seal_encrypts_removes_plaintext_and_logs(root: Path) -> None:
    plain = root / "holdout_sealed" / "spot_daily_holdout.parquet"
    sha_before = pd.read_parquet(plain).to_json()
    key = seal_holdout(root)
    assert len(key) == 64  # 32 bytes en hex
    assert not plain.exists()  # plaintext borrado
    assert (root / "holdout_sealed" / "spot_daily_holdout.parquet.gpg").exists()
    marker = json.loads((root / "holdout_sealed" / "SEALED.json").read_text())
    assert marker["key_fingerprint"] == key_fingerprint(key)
    log = (root / "ledger" / "holdout_seal.log").read_text().strip().splitlines()
    assert len(log) == 1
    entry = json.loads(log[0])
    assert entry["action"] == "seal" and len(entry["sha256_plaintext"]) == 64
    # segunda llamada de sellado => error (idempotencia protegida)
    with pytest.raises(RuntimeError):
        seal_holdout(root)
    assert sha_before  # referencia usada


@needs_gpg
def test_open_requires_correct_key(root: Path) -> None:
    key = seal_holdout(root)
    tmp = open_holdout_file(root, "spot_daily", key, "test")
    assert pd.read_parquet(tmp).shape == (2, 2)
    tmp.unlink()
    with pytest.raises(PermissionError):
        open_holdout_file(root, "spot_daily", "f" * 64, "test")


@needs_gpg
def test_open_detects_tampered_marker_sha(root: Path) -> None:
    key = seal_holdout(root)
    marker_path = root / "holdout_sealed" / "SEALED.json"
    marker = json.loads(marker_path.read_text())
    marker["files"]["spot_daily_holdout.parquet"]["sha256_plaintext"] = "0" * 64
    marker_path.write_text(json.dumps(marker))
    with pytest.raises((RuntimeError, PermissionError)):
        open_holdout_file(root, "spot_daily", key, "test")


@needs_gpg
def test_load_holdout_sealed_requires_unlock_and_key(
    root: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    key = seal_holdout(root)
    monkeypatch.delenv("QA_HOLDOUT_UNLOCK", raising=False)
    monkeypatch.setenv("QA_HOLDOUT_KEY", key)
    with pytest.raises(HoldoutSealedError):
        load_holdout("spot_daily", root, purpose="t")
    monkeypatch.setenv("QA_HOLDOUT_UNLOCK", "1")
    monkeypatch.delenv("QA_HOLDOUT_KEY", raising=False)
    with pytest.raises(HoldoutSealedError, match="QA_HOLDOUT_KEY"):
        load_holdout("spot_daily", root, purpose="t")
    monkeypatch.setenv("QA_HOLDOUT_KEY", key)
    df = load_holdout("spot_daily", root, purpose="verificacion-tecnica")
    assert len(df) == 2
    access = (root / "ledger" / "holdout_access.log").read_text().strip().splitlines()
    assert len(access) == 1
    assert is_sealed(root)
