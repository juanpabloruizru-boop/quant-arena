# Unit tests for Claude Trading Skills Engine and Motor 2: Sniper Intradía (1H)
from __future__ import annotations

from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd
import pytest

from qa.agent.skills_engine import (
    check_circuit_breaker,
    compute_market_health,
    evaluate_discipline_gate,
    load_recent_lessons,
    load_trader_memory,
    record_postmortem,
    update_live_excursions,
)
from qa.agent.sniper import (
    close_sniper_trade,
    compute_sniper_equity,
    detect_undercut_and_reclaim,
    detect_vcp_momentum_burst,
    evaluar_y_gestionar_sniper,
    load_sniper_trades,
    open_sniper_trade,
    update_sniper_trade,
    verify_sniper_chain,
)


@pytest.fixture
def tmp_ledger_root(tmp_path: Path) -> Path:
    """Fixture that initializes a temporary root directory with a ledger folder."""
    ledger_dir = tmp_path / "ledger"
    ledger_dir.mkdir(parents=True, exist_ok=True)
    return tmp_path


# =====================================================================
# 1. Tests for Skills Engine: Market Health & Exposure Coach
# =====================================================================


def test_compute_market_health_bullish() -> None:
    # Synthetic bullish data
    dates_1d = pd.date_range("2026-01-01", periods=210, freq="D", tz="UTC")
    closes_1d = np.linspace(50000, 70000, 210)
    btc_1d = pd.DataFrame({"close": closes_1d}, index=dates_1d)

    dates_4h = pd.date_range("2026-06-01", periods=100, freq="4h", tz="UTC")
    closes_4h = np.linspace(60000, 70000, 100)
    btc_4h = pd.DataFrame(
        {
            "close": closes_4h,
            "open": closes_4h - 50,
            "high": closes_4h + 100,
            "low": closes_4h - 100,
            "volume": np.ones(100) * 1000,
        },
        index=dates_4h,
    )

    live_klines: dict[str, dict[str, pd.DataFrame]] = {
        "BTCUSDT": {"1d": btc_1d, "4h": btc_4h},
        "ETHUSDT": {"4h": btc_4h},
        "SOLUSDT": {"4h": btc_4h},
        "SUIUSDT": {"4h": btc_4h},
    }
    funding_rates = {"BTCUSDT": 0.0001, "ETHUSDT": 0.0001}

    mh = compute_market_health(live_klines, funding_rates)
    assert 0 <= mh["market_health_score"] <= 100
    assert mh["posture"] in ["FULL_OFFENSE", "SELECTIVE", "REDUCE_ONLY", "CASH_PRIORITY"]
    assert mh["max_heat_pct"] in [25.0, 16.0, 8.0, 0.0]
    assert mh["btc_macro_bullish"] is True
    assert "breakdown" in mh


def test_check_circuit_breaker() -> None:
    # Case 1: Normal conditions
    normal_trades = [
        {"status": "closed", "pnl_neto_usd": 15.0, "exit_ts_utc": datetime.now(UTC).isoformat()}
    ]
    cb = check_circuit_breaker(normal_trades, current_equity=1015.0, starting_equity=1000.0)
    assert cb["status"] == "NORMAL"
    assert cb["is_halted"] is False

    # Case 2: 2 consecutive losses in <12h -> COOLDOWN_HALT
    now_iso = datetime.now(UTC).isoformat()
    earlier_iso = (datetime.now(UTC) - timedelta(hours=1)).isoformat()
    loss_trades = [
        {"status": "closed", "pnl_neto_usd": -20.0, "exit_ts_utc": now_iso},
        {"status": "closed", "pnl_neto_usd": -18.0, "exit_ts_utc": earlier_iso},
    ]
    cb_halt = check_circuit_breaker(loss_trades, current_equity=962.0, starting_equity=1000.0)
    assert cb_halt["status"] == "COOLDOWN_HALT"
    assert cb_halt["is_halted"] is True
    assert cb_halt["consecutive_losses_12h"] == 2

    # Case 3: Daily Drawdown >= 4.0% -> COOLDOWN_HALT
    cb_dd = check_circuit_breaker([], current_equity=950.0, starting_equity=1000.0)
    assert cb_dd["status"] == "COOLDOWN_HALT"
    assert cb_dd["is_halted"] is True
    assert cb_dd["daily_drawdown_pct"] >= 4.0


def test_evaluate_discipline_gate() -> None:
    # 1. All checks passing
    gate_ok = evaluate_discipline_gate(
        symbol="BTCUSDT",
        direction="LONG",
        current_price=65000.0,
        ema21=64800.0,
        current_heat_pct=10.0,
        trade_risk_pct=3.0,
        max_heat_allowed=16.0,
        circuit_breaker_status="NORMAL",
    )
    assert gate_ok["gate_passed"] is True

    # 2. Blocked by heat limit
    gate_heat = evaluate_discipline_gate(
        symbol="BTCUSDT",
        direction="LONG",
        current_price=65000.0,
        ema21=64800.0,
        current_heat_pct=15.0,
        trade_risk_pct=3.0,
        max_heat_allowed=16.0,
        circuit_breaker_status="NORMAL",
    )
    assert gate_heat["gate_passed"] is False
    assert gate_heat["exposure_allowed"] is False

    # 3. Blocked by circuit breaker
    gate_cb = evaluate_discipline_gate(
        symbol="BTCUSDT",
        direction="LONG",
        current_price=65000.0,
        ema21=64800.0,
        current_heat_pct=5.0,
        trade_risk_pct=2.0,
        max_heat_allowed=16.0,
        circuit_breaker_status="COOLDOWN_HALT",
    )
    assert gate_cb["gate_passed"] is False
    assert gate_cb["circuit_breaker_ok"] is False

    # 4. Blocked by Anti-Chasing (> 1.8% from EMA21)
    gate_chase = evaluate_discipline_gate(
        symbol="BTCUSDT",
        direction="LONG",
        current_price=67000.0,
        ema21=64800.0,  # ~3.4% above EMA21
        current_heat_pct=5.0,
        trade_risk_pct=2.0,
        max_heat_allowed=16.0,
        circuit_breaker_status="NORMAL",
    )
    assert gate_chase["gate_passed"] is False
    assert gate_chase["anti_chasing_ok"] is False


def test_mfe_mae_and_postmortem(tmp_ledger_root: Path) -> None:
    trade: dict[str, Any] = {
        "id": "T-TEST-01",
        "asset": "BTCUSDT",
        "kind": "future_long",
        "entry_price": 60000.0,
        "sl": 59000.0,  # 1R = 1000 USD
        "dist_sl": 1000.0,
        "mfe_r": 0.0,
        "mae_r": 0.0,
    }

    # Price moves to 63000 (+3.0R)
    update_live_excursions(trade, 63000.0)
    assert trade["mfe_r"] == 3.0
    assert trade["mae_r"] == 0.0

    # Price dips to 59500 (-0.5R)
    update_live_excursions(trade, 59500.0)
    assert trade["mfe_r"] == 3.0
    assert trade["mae_r"] == -0.5

    # Record post-mortem
    rec = record_postmortem(
        root=tmp_ledger_root,
        trade=trade,
        exit_price=62500.0,
        pnl_neto_usd=120.0,
    )
    assert rec["diagnostic"] == "CLEAN_TREND_WIN"

    # Verify persistence
    mem = load_trader_memory(tmp_ledger_root)
    assert len(mem) == 1
    assert mem[0]["diagnostic"] == "CLEAN_TREND_WIN"

    lessons = load_recent_lessons(tmp_ledger_root)
    assert len(lessons) == 1
    assert "CLEAN_TREND_WIN" in lessons[0]


# =====================================================================
# 2. Tests for Motor 2: Sniper Intradía (1H) Patterns & Ledger
# =====================================================================


def test_detect_undercut_and_reclaim() -> None:
    # Create 10 candles: candle 9 sweeps low of previous 5 with 45% lower wick and reclaims
    n = 15
    dates = pd.date_range("2026-06-01", periods=n, freq="1h", tz="UTC")
    closes = np.array([
        100.0, 101.0, 102.0, 101.5, 101.0, 100.5, 100.2, 100.0,
        100.1, 100.8, 101.0, 101.2, 101.0, 101.1, 101.2,
    ])
    opens = closes - 0.2
    highs = closes + 0.5
    lows = closes - 0.5

    # Configure candle 14 to undercut low of candles 9..13
    min_prev_5 = float(lows[9:14].min())
    lows[14] = min_prev_5 - 0.8  # sweeps below minimum
    opens[14] = min_prev_5 + 0.2
    closes[14] = min_prev_5 + 0.5  # reclaims
    highs[14] = min_prev_5 + 0.6  # lower wick is from lows[14] to min(opens[14], closes[14])
    # Total range: highs[14] - lows[14] = 1.4
    # Lower wick: opens[14] - lows[14] = 1.0 (1.0 / 1.4 = 71% >= 40%)

    volumes = np.ones(n) * 100.0
    volumes[14] = 150.0  # RVOL 1.5x

    df = pd.DataFrame(
        {"open": opens, "high": highs, "low": lows, "close": closes, "volume": volumes},
        index=dates,
    )

    pat = detect_undercut_and_reclaim(df)
    assert pat is not None
    assert pat["pattern"] == "UNDERCUT_AND_RECLAIM"
    assert pat["direction"] == "LONG"
    assert pat["rvol"] >= 1.10


def test_detect_vcp_momentum_burst() -> None:
    # 30 candles: candles 25..28 contracted range, candle 29 expands with volume
    n = 30
    dates = pd.date_range("2026-06-01", periods=n, freq="1h", tz="UTC")
    closes = np.linspace(100, 105, n)
    opens = closes - 0.2
    highs = closes + 1.0
    lows = closes - 1.0
    volumes = np.ones(n) * 100.0

    # Compress candles 25..28 (< 0.7x ATR)
    for i in range(25, 29):
        highs[i] = closes[i] + 0.15
        lows[i] = closes[i] - 0.15

    # Candle 29: Expands with high volume
    highs[29] = closes[29] + 1.8
    lows[29] = closes[29] - 0.2
    closes[29] = highs[29] - 0.05
    volumes[29] = 250.0  # RVOL 2.5x

    df = pd.DataFrame(
        {"open": opens, "high": highs, "low": lows, "close": closes, "volume": volumes},
        index=dates,
    )

    pat = detect_vcp_momentum_burst(df)
    assert pat is not None
    assert pat["pattern"] == "VCP_MOMENTUM_BURST"
    assert pat["direction"] == "LONG"
    assert pat["rvol"] >= 1.30


def test_sniper_cryptographic_ledger_and_equity(tmp_ledger_root: Path) -> None:
    # 1. Open trade
    trade = open_sniper_trade(
        root=tmp_ledger_root,
        asset="BTCUSDT",
        kind="future_long",
        entry_price=60000.0,
        size_usd=1000.0,
        sl=59000.0,
        tp1=61800.0,
        tp2=63000.0,
        risk_usd=20.0,
        dist_sl=1000.0,
        pattern="UNDERCUT_AND_RECLAIM",
        thesis="Hammer sweep test",
    )
    assert trade["asset"] == "BTCUSDT"
    assert trade["status"] == "open"

    # 2. Verify SHA-256 chain
    ok, n_rec, msg = verify_sniper_chain(tmp_ledger_root)
    assert ok is True
    assert n_rec == 1

    # 3. Update trade
    update_sniper_trade(
        tmp_ledger_root,
        trade["id"],
        updates={"mfe_r": 1.5, "mae_r": -0.2},
        note="Live telemetry update",
    )
    ok_up, n_rec_up, _ = verify_sniper_chain(tmp_ledger_root)
    assert ok_up is True
    assert n_rec_up == 2

    # 4. Check equity computation with open position
    live_prices = {"BTCUSDT": 61000.0}
    trades_list = load_sniper_trades(tmp_ledger_root)
    eq = compute_sniper_equity(trades_list, live_prices, starting_capital=1000.0)
    assert eq["starting_capital"] == 1000.0
    assert eq["floating_pnl"] > 0
    assert eq["total_equity"] > 1000.0

    # 5. Close trade
    closed = close_sniper_trade(
        tmp_ledger_root,
        trade["id"],
        exit_price=63000.0,
        pnl_neto_usd=48.0,
        tag="TP2_EXIT",
        note="Target 2 reached",
    )
    assert closed.get("action") == "close"
    reloaded_closed = [t for t in load_sniper_trades(tmp_ledger_root) if t["id"] == trade["id"]][0]
    assert reloaded_closed["status"] == "closed"
    assert closed["pnl_neto_usd"] > 0

    # 6. Verify chain again
    ok_cl, n_rec_cl, _ = verify_sniper_chain(tmp_ledger_root)
    assert ok_cl is True
    assert n_rec_cl == 3

    # 7. Check equity computation with closed position
    trades_closed = load_sniper_trades(tmp_ledger_root)
    eq_closed = compute_sniper_equity(trades_closed, live_prices, starting_capital=1000.0)
    assert eq_closed["closed_count"] == 1
    assert eq_closed["realized_pnl"] > 0
    assert eq_closed["win_rate"] == 100.0


def test_evaluar_y_gestionar_sniper_e2e(tmp_ledger_root: Path) -> None:
    # Test evaluation loop runs cleanly and respects maximum 2 open positions
    dates = pd.date_range("2026-06-01", periods=30, freq="1h", tz="UTC")
    closes = np.linspace(60000, 62000, 30)
    df = pd.DataFrame(
        {
            "open": closes - 50,
            "high": closes + 100,
            "low": closes - 100,
            "close": closes,
            "volume": np.ones(30) * 500,
        },
        index=dates,
    )
    live_klines = {
        "BTCUSDT": {"1h": df, "4h": df},
        "ETHUSDT": {"1h": df, "4h": df},
        "SOLUSDT": {"1h": df, "4h": df},
        "SUIUSDT": {"1h": df, "4h": df},
    }
    live_prices = {"BTCUSDT": 62000.0, "ETHUSDT": 3400.0, "SOLUSDT": 180.0, "SUIUSDT": 2.5}

    res = evaluar_y_gestionar_sniper(
        root=tmp_ledger_root,
        live_klines=live_klines,
        live_prices=live_prices,
        starting_capital=1000.0,
    )
    assert res["status"] == "ok"
    assert "equity_status" in res
    assert len(res["open_trades"]) <= 2
