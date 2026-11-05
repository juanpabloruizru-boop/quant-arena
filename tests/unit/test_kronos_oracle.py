from __future__ import annotations

import time

import numpy as np
import pandas as pd

from qa.agent.kronos_oracle import (
    KronosKLineTokenizer,
    KronosPredictor,
    evaluate_kronos_multi_horizon,
    predict_kline_horizon,
)
from qa.agent.skills_engine import evaluate_discipline_gate


def _make_synthetic_ohlcv(n: int = 120, seed: int = 42, drift: float = 0.002) -> pd.DataFrame:
    rng = np.random.default_rng(seed)
    closes = [100.0]
    for _ in range(n - 1):
        ret = drift + rng.normal(0.0, 0.012)
        closes.append(max(1.0, closes[-1] * (1.0 + ret)))
    closes_arr = np.array(closes, dtype=float)
    opens_arr = np.roll(closes_arr, 1)
    opens_arr[0] = closes_arr[0] * 0.998
    spread = np.abs(rng.normal(0.008, 0.003, size=n)) * closes_arr
    highs_arr = np.maximum(opens_arr, closes_arr) + spread * rng.uniform(0.3, 1.0, size=n)
    lows_arr = np.minimum(opens_arr, closes_arr) - spread * rng.uniform(0.3, 0.9, size=n)
    vols_arr = rng.uniform(500.0, 3000.0, size=n)
    return pd.DataFrame(
        {
            "open": opens_arr,
            "high": highs_arr,
            "low": lows_arr,
            "close": closes_arr,
            "volume": vols_arr,
        }
    )


def test_kronos_tokenizer_bounds_and_decode() -> None:
    df = _make_synthetic_ohlcv(100, seed=7)
    tokenizer = KronosKLineTokenizer(max_window=400, z_clip=5.0)
    enc = tokenizer.encode(df)

    coarse = enc["coarse_tokens"]
    fine = enc["fine_tokens"]
    norm = enc["normalized"]

    assert len(coarse) == 100
    assert len(fine) == 100
    assert int(coarse.min()) >= 0 and int(coarse.max()) <= 63
    assert int(fine.min()) >= 0 and int(fine.max()) <= 63

    for col in ("z_ret", "z_range", "z_vol"):
        arr = norm[col].to_numpy()
        assert float(np.min(arr)) >= -5.0, f"{col} below -5.0"
        assert float(np.max(arr)) <= 5.0, f"{col} above +5.0"

    # Test decoding back to synthetic OHLCV
    last_close = float(df["close"].iloc[-1])
    base_atr_pct = float(enc["base_atr_pct"])
    avg_vol = float(enc["avg_volume"])
    for c_tok in [0, 15, 31, 32, 48, 63]:
        for f_tok in [0, 21, 42, 63]:
            candle = tokenizer.decode_step(c_tok, f_tok, last_close, base_atr_pct, avg_vol)
            assert candle["high"] >= max(candle["open"], candle["close"])
            assert candle["low"] <= min(candle["open"], candle["close"])
            assert candle["close"] > 0.0


def test_kronos_tokenizer_causal_invariance() -> None:
    df_full = _make_synthetic_ohlcv(80, seed=99)
    df_prefix = df_full.iloc[:50].copy()

    tokenizer = KronosKLineTokenizer(max_window=400, z_clip=5.0)
    enc_prefix = tokenizer.encode(df_prefix)
    enc_full = tokenizer.encode(df_full)

    # Causal invariance: future candles 50..79 must never alter tokens 0..49
    np.testing.assert_array_equal(enc_prefix["coarse_tokens"], enc_full["coarse_tokens"][:50])
    np.testing.assert_array_equal(enc_prefix["fine_tokens"], enc_full["fine_tokens"][:50])
    np.testing.assert_allclose(
        enc_prefix["normalized"]["z_ret"].to_numpy(),
        enc_full["normalized"]["z_ret"].to_numpy()[:50],
        rtol=1e-12,
        atol=1e-12,
    )


def test_kronos_predictor_and_horizon_output() -> None:
    df = _make_synthetic_ohlcv(120, seed=123, drift=0.004)
    t0 = time.perf_counter()
    res = predict_kline_horizon(
        klines=df,
        symbol="BTCUSDT",
        timeframe="4h",
        horizon=6,
        sample_count=20,
        temperature=1.0,
        top_p=0.90,
        seed=42,
    )
    elapsed_ms = (time.perf_counter() - t0) * 1000.0

    assert elapsed_ms < 250.0  # Typically <15ms on CPU
    assert res["symbol"] == "BTCUSDT"
    assert res["timeframe"] == "4h"
    assert 0.0 <= res["bullish_prob"] <= 100.0
    assert 0.0 <= res["confidence_score"] <= 100.0
    assert res["forecast_high"] >= res["forecast_low"]
    assert res["kronos_verdict"] in ("KRONOS_BULL", "KRONOS_BEAR", "KRONOS_NEUTRAL")
    assert len(res["forecast_candles"]) == 6

    for idx, c in enumerate(res["forecast_candles"], start=1):
        assert c["step"] == idx
        assert c["high"] >= max(c["open"], c["close"])
        assert c["low"] <= min(c["open"], c["close"])


def test_kronos_predictor_empty_or_short_data() -> None:
    predictor = KronosPredictor()
    res = predictor.predict(pd.DataFrame(), symbol="SOLUSDT", timeframe="1h", horizon=6)
    assert res["kronos_verdict"] == "KRONOS_NEUTRAL"
    assert res["bullish_prob"] == 50.0
    assert isinstance(res["forecast_candles"], list)


def test_kronos_multi_horizon_helper() -> None:
    df_4h = _make_synthetic_ohlcv(60, seed=11)
    df_1h = _make_synthetic_ohlcv(60, seed=22)
    frames = {"BTCUSDT": {"4h": df_4h, "1h": df_1h}}
    multi = evaluate_kronos_multi_horizon(frames, symbols=("BTCUSDT",))
    assert "BTCUSDT" in multi
    assert "4h" in multi["BTCUSDT"]
    assert "1h" in multi["BTCUSDT"]
    assert len(multi["BTCUSDT"]["4h"]["forecast_candles"]) == 6
    assert len(multi["BTCUSDT"]["1h"]["forecast_candles"]) == 6


def test_discipline_gate_kronos_alignment() -> None:
    # 1. LONG blocked when Kronos is strongly bearish (KRONOS_BEAR & bullish_prob <= 30%)
    bear_fc = {
        "kronos_verdict": "KRONOS_BEAR",
        "bullish_prob": 20.0,
    }
    gate_blocked_long = evaluate_discipline_gate(
        symbol="BTCUSDT",
        direction="LONG",
        current_price=100.0,
        ema21=99.5,
        current_heat_pct=5.0,
        trade_risk_pct=1.0,
        max_heat_allowed=25.0,
        circuit_breaker_status="NORMAL",
        kronos_forecast=bear_fc,
    )
    assert gate_blocked_long["kronos_alignment_ok"] is False
    assert gate_blocked_long["gate_passed"] is False
    assert any("Kronos K-Line Veto" in r for r in gate_blocked_long["reasons"])

    # 2. SHORT blocked when Kronos is strongly bullish (KRONOS_BULL & bullish_prob >= 70%)
    bull_fc = {
        "kronos_verdict": "KRONOS_BULL",
        "bullish_prob": 80.0,
    }
    gate_blocked_short = evaluate_discipline_gate(
        symbol="BTCUSDT",
        direction="SHORT",
        current_price=100.0,
        ema21=100.5,
        current_heat_pct=5.0,
        trade_risk_pct=1.0,
        max_heat_allowed=25.0,
        circuit_breaker_status="NORMAL",
        kronos_forecast=bull_fc,
    )
    assert gate_blocked_short["kronos_alignment_ok"] is False
    assert gate_blocked_short["gate_passed"] is False

    # 3. LONG allowed when Kronos is aligned or neutral
    gate_ok_long = evaluate_discipline_gate(
        symbol="BTCUSDT",
        direction="LONG",
        current_price=100.0,
        ema21=99.5,
        current_heat_pct=5.0,
        trade_risk_pct=1.0,
        max_heat_allowed=25.0,
        circuit_breaker_status="NORMAL",
        kronos_forecast=bull_fc,
    )
    assert gate_ok_long["kronos_alignment_ok"] is True
    assert gate_ok_long["gate_passed"] is True
