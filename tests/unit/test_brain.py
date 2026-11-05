"""Pruebas unitarias para el Cerebro Cognitivo (brain.py)."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from pathlib import Path

import pandas as pd

from qa.agent.brain import (
    _is_cache_fresh,
    _local_heuristics_verdict,
    evaluar_setup_con_ia,
    format_recent_candles,
    load_brain_state,
    save_brain_state,
)


def test_format_recent_candles() -> None:
    data = {
        "open": [100.0, 105.0],
        "high": [108.0, 110.0],
        "low": [98.0, 102.0],
        "close": [106.0, 104.0],
    }
    df = pd.DataFrame(data)
    txt = format_recent_candles(df, max_candles=2)
    assert "Vela 1: 🟢 ALCISTA" in txt
    assert "Vela 2: 🔴 BAJISTA" in txt
    assert "Cuerpo:" in txt
    assert "MSup:" in txt


def test_is_cache_fresh() -> None:
    now = datetime.now(UTC)
    fresh_entry = {"timestamp_utc": now.isoformat()}
    old_entry = {"timestamp_utc": (now - timedelta(seconds=1200)).isoformat()}

    assert _is_cache_fresh(fresh_entry, max_age_seconds=900) is True
    assert _is_cache_fresh(old_entry, max_age_seconds=900) is False
    assert _is_cache_fresh({}, max_age_seconds=900) is False


def test_local_heuristics_verdict() -> None:
    ind = {"ema21": 100.0, "rsi": 75.0, "adx14": 28.0}
    # Long extendido sobre EMA21
    res = _local_heuristics_verdict(
        symbol="BTCUSDT",
        direction="LONG",
        current_price=108.0,
        indicators=ind,
        swing_high=110.0,
        swing_low=95.0,
        btc_macro_bullish=True,
    )
    assert res["veredicto"] == "ORDEN_LIMITE_PULLBACK"
    assert res["confianza"] >= 70
    assert "extendido" in res["razonamiento"].lower()

    # Altcoin en macro bajista -> Veto
    res_alt = _local_heuristics_verdict(
        symbol="SOLUSDT",
        direction="LONG",
        current_price=150.0,
        indicators=ind,
        swing_high=160.0,
        swing_low=140.0,
        btc_macro_bullish=False,
    )
    assert res_alt["veredicto"] == "VETAR_TRAMPA"
    assert "macro bajista" in res_alt["razonamiento"].lower()


def test_save_and_load_brain_state(tmp_path: Path) -> None:
    state = {
        "BTCUSDT": {
            "veredicto": "EJECUTAR_AHORA",
            "confianza": 85,
            "precio_entrada_sugerido": 68000.0,
            "razonamiento": "Test reasoning",
            "timestamp_utc": datetime.now(UTC).isoformat(),
        }
    }
    save_brain_state(state, root=tmp_path)
    loaded = load_brain_state(root=tmp_path)
    assert loaded["BTCUSDT"]["veredicto"] == "EJECUTAR_AHORA"
    assert loaded["BTCUSDT"]["confianza"] == 85


def test_evaluar_setup_con_ia_cached(tmp_path: Path) -> None:
    now_ts = datetime.now(UTC).isoformat()
    state = {
        "ETHUSDT": {
            "veredicto": "ORDEN_LIMITE_PULLBACK",
            "confianza": 80,
            "precio_entrada_sugerido": 2450.0,
            "razonamiento": "Cache hit test",
            "timestamp_utc": now_ts,
            "symbol": "ETHUSDT",
            "direction": "LONG",
            "model_used": "cache",
        }
    }
    save_brain_state(state, root=tmp_path)
    result = evaluar_setup_con_ia(
        symbol="ETHUSDT",
        direction="LONG",
        current_price=2500.0,
        indicators={"ema21": 2450.0},
        swing_high=2600.0,
        swing_low=2400.0,
        btc_macro_bullish=True,
        root=tmp_path,
        force_refresh=False,
    )
    assert result["veredicto"] == "ORDEN_LIMITE_PULLBACK"
    assert result["razonamiento"] == "Cache hit test"
