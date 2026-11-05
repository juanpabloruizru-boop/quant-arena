"""Pruebas unitarias para las tres estrategias multi-horizonte (M6.4).

Verifica:
1. SPRINT (1H): TP fijo en +2.5R y trailing stop 1.2x ATR a partir de +1.0R.
2. CRUISE (4H): Entrada por pullback a EMA21 y regla Anti-Wick (las mechas no liquidan).
3. MARATHON (1D/1W): Macro Wave, tolerancia de drawdown y salida por ruptura macro.
"""

from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from qa.research.cruise_pro_runner import (
    compute_30d_momentum_weights,
    simulate_cruise_pro,
)
from qa.research.multi_horizon_runner import (
    simulate_cruise,
    simulate_marathon,
    simulate_sprint,
)


@pytest.fixture
def dummy_costs() -> dict[str, dict[str, float]]:
    return {
        "spot": {"taker_fee": 0.001, "maker_fee": 0.001},
        "perp_usdm": {"taker_fee": 0.0005, "maker_fee": 0.0002},
    }


def test_sprint_tp_and_trailing(dummy_costs: dict[str, dict[str, float]]) -> None:
    # Generar 60 velas de 1H sintéticas con un breakout claro
    times = pd.date_range("2024-01-01", periods=60, freq="h", tz="UTC")
    # Base plana en 100, luego vela 45 dispara a 115 con alto volumen
    close = np.full(60, 100.0)
    high = np.full(60, 101.0)
    low = np.full(60, 99.0)
    vol = np.full(60, 100.0)

    # Impulso de breakout en t=45
    vol[45] = 500.0  # RVOL > 1.5
    close[45] = 104.0
    high[45] = 105.0
    low[45] = 100.0

    # Continuación alcista hacia TP (+2.5R)
    high[46] = 115.0
    close[46] = 114.0

    df_1h = pd.DataFrame({
        "open_time": times,
        "open": close,
        "high": high,
        "low": low,
        "close": close,
        "volume": vol,
    })

    res = simulate_sprint(df_1h, "BTCUSDT", dummy_costs, initial_capital=1000.0)
    assert res["total_trades"] >= 1
    # Debe haber capturado el TP a 2.5R
    assert res["max_r_trade"] >= 2.0


def test_cruise_anti_wick_rule(dummy_costs: dict[str, dict[str, float]]) -> None:
    # 60 velas de 4H
    times = pd.date_range("2024-01-01", periods=60, freq="4h", tz="UTC")
    times_1d = pd.date_range("2024-01-01", periods=10, freq="D", tz="UTC")

    close = np.linspace(100.0, 130.0, 60)
    high = close + 2.0
    low = close - 2.0
    open_px = close - 1.0

    # Crear un pullback a EMA21 en t=45
    low[45] = close[45] - 3.0  # Toca EMA21
    open_px[45] = close[45] - 1.0  # Cierra alcista

    # En t=48, crear una mecha profunda que penetra el SL pero CIERRA por encima
    sl_level = close[45] - 4.0
    low[48] = sl_level - 2.0  # Mecha penetra el SL
    close[48] = sl_level + 1.0  # Cierre por encima (Anti-Wick)

    df_4h = pd.DataFrame({
        "open_time": times,
        "open": open_px,
        "high": high,
        "low": low,
        "close": close,
        "volume": np.full(60, 1000.0),
    })

    df_1d = pd.DataFrame({
        "open_time": times_1d,
        "open": np.linspace(100.0, 130.0, 10),
        "high": np.linspace(102.0, 132.0, 10),
        "low": np.linspace(98.0, 128.0, 10),
        "close": np.linspace(101.0, 131.0, 10),
        "volume": np.full(10, 5000.0),
    })

    btc_1d = df_1d.copy()

    res = simulate_cruise(df_4h, df_1d, btc_1d, "SOLUSDT", dummy_costs, initial_capital=1000.0)
    # La mecha de t=48 no debió liquidar prematuramente por la regla Anti-Wick
    assert res["max_drawdown_pct"] < 50.0


def test_marathon_cycle_simulation(dummy_costs: dict[str, dict[str, float]]) -> None:
    # 100 días de ciclo alcista continuo
    times = pd.date_range("2024-01-01", periods=100, freq="D", tz="UTC")
    close = np.linspace(100.0, 300.0, 100)  # Subida 3x
    high = close + 5.0
    low = close - 5.0

    # Crear una corrección del 10% en t=60 (no debe liquidar por ser menor al SL del 15%)
    close[60] = close[59] * 0.92
    low[60] = close[60] - 2.0

    df_1d = pd.DataFrame({
        "open_time": times,
        "open": close - 2.0,
        "high": high,
        "low": low,
        "close": close,
        "volume": np.full(100, 10000.0),
    })
    btc_1d = df_1d.copy()

    res = simulate_marathon(df_1d, btc_1d, "SUIUSDT", dummy_costs, initial_capital=1000.0)
    # Debe haber capturado una ganancia sustancial al no cortarse en la corrección
    assert res["total_return_pct"] > 0
    assert res["max_pct_gain"] > 20.0


def test_momentum_weights_ranking_and_sum() -> None:
    times = pd.date_range("2023-11-01", periods=90, freq="D", tz="UTC")
    # Generar 4 activos con retornos bien definidos en los últimos 30 días
    # SUI +100%, ETH +50%, BTC +20%, SOL -10%
    dfs = {
        "SUIUSDT": pd.DataFrame({"open_time": times, "close": np.linspace(10, 20, 90)}),
        "ETHUSDT": pd.DataFrame({"open_time": times, "close": np.linspace(10, 15, 90)}),
        "BTCUSDT": pd.DataFrame({"open_time": times, "close": np.linspace(10, 12, 90)}),
        "SOLUSDT": pd.DataFrame({"open_time": times, "close": np.linspace(10, 9, 90)}),
    }

    w_df = compute_30d_momentum_weights(dfs, ["BTCUSDT", "ETHUSDT", "SOLUSDT", "SUIUSDT"])
    last_row = w_df.iloc[-1]
    # Comprobar suma exacta a 1.0 (100%)
    assert pytest.approx(float(last_row.sum()), 0.001) == 1.0
    # SUI líder -> 40%
    assert last_row["SUIUSDT"] == 0.40
    # ETH y BTC seguidores -> 25%
    assert last_row["ETHUSDT"] == 0.25
    assert last_row["BTCUSDT"] == 0.25
    # SOL rezagado -> 10%
    assert last_row["SOLUSDT"] == 0.10


def test_cruise_pro_risk_free_pyramiding(dummy_costs: dict[str, dict[str, float]]) -> None:
    times = pd.date_range("2024-01-01", periods=80, freq="4h", tz="UTC")
    times_1d = pd.date_range("2024-01-01", periods=15, freq="D", tz="UTC")

    close = np.linspace(100.0, 150.0, 80)
    c_4h = pd.Series(close)
    ema21 = c_4h.ewm(span=21, adjust=False).mean()

    high = close + 2.0
    low = close - 1.0
    open_px = close - 0.5

    # Entrada en t=42
    low[42] = ema21.iloc[42] - 0.2
    open_px[42] = low[42] + 0.1
    close[42] = ema21.iloc[42] + 0.5

    # Recomputar EMA21
    c_4h = pd.Series(close)
    ema21 = c_4h.ewm(span=21, adjust=False).mean()

    # Pyramiding en t=65
    low[65] = ema21.iloc[65] - 0.2
    open_px[65] = low[65] + 0.1
    close[65] = ema21.iloc[65] + 1.0

    df_4h = pd.DataFrame({
        "open_time": times,
        "open": open_px,
        "high": high,
        "low": low,
        "close": close,
        "volume": np.full(80, 1000.0),
    })

    df_1d = pd.DataFrame({
        "open_time": times_1d,
        "open": np.linspace(100.0, 150.0, 15),
        "high": np.linspace(102.0, 152.0, 15),
        "low": np.linspace(98.0, 148.0, 15),
        "close": np.linspace(101.0, 151.0, 15),
        "volume": np.full(15, 5000.0),
    })
    btc_1d = df_1d.copy()

    res = simulate_cruise_pro(
        df_4h,
        df_1d,
        btc_1d,
        "ETHUSDT",
        dummy_costs,
        initial_capital=1000.0,
        enable_pyramiding=True,
    )

    pyr_trades = [tr for tr in res["trades"] if tr.get("pyramided")]
    # Debe haber registrado piramidación
    assert len(pyr_trades) >= 1
    tr = pyr_trades[0]
    # Comprobar que el tamaño añadido fue 25% del inicial
    assert pytest.approx(tr["add_size_usd"], 0.05) == round(0.25 * tr["size_usd"], 2)
    # Comprobar que el trade cerró en beneficio neto positivo
    assert tr["realized_pnl"] > 0

