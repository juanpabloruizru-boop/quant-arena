"""Tests sinteticos minimos de las estrategias pre-registradas (M3)."""

from __future__ import annotations

import numpy as np
import pandas as pd

from qa.backtest.costs import CostModel
from qa.strategies.h1 import H1Cell, h1_desired_weights
from qa.strategies.h2 import H2Cell, build_h2, build_weekly_panel
from qa.strategies.h3 import H3Cell, h3_signal


def test_h1_weights_causal_and_bounded() -> None:
    rng = np.random.default_rng(0)
    n = 600
    close = 100.0 * np.exp(np.cumsum(rng.normal(0.0005, 0.02, n)))
    cell = H1Cell("sma", 50, 0.25)
    w_full = h1_desired_weights(close, cell)
    assert w_full.shape == close.shape
    assert np.all(w_full[:49] == 0.0)  # warmup flat (SMA50 + vol20)
    assert np.all((w_full >= 0.0) & (w_full <= 1.0))
    # causalidad: cambiar el futuro no altera el pasado
    close2 = close.copy()
    close2[300:] *= 1.5
    w2 = h1_desired_weights(close2, cell)
    assert np.allclose(w2[:300], w_full[:300])
    # variante ret
    cell_r = H1Cell("ret", 50, 0.15)
    w_r = h1_desired_weights(close, cell_r)
    assert np.all(w_r[:49] == 0.0)
    assert np.all((w_r >= 0.0) & (w_r <= 1.0))


def _synthetic_h2_inputs(n_weeks: int = 40) -> tuple[pd.DataFrame, pd.DataFrame, list[str]]:
    weeks = pd.date_range("2021-01-04", periods=n_weeks, freq="7D", tz="UTC")
    syms = [f"S{i}USDT" for i in range(10)]
    # S0 sube siempre (ganador claro); el resto ruido plano
    rng = np.random.default_rng(7)
    rows = []
    for wi, w in enumerate(weeks):
        for si, s in enumerate(syms):
            base = 100.0 * (1.05**wi if si == 0 else 1.0)
            noise = 1.0 if si == 0 else float(rng.normal(1.0, 0.01))
            for day in range(5):
                rows.append(
                    {
                        "symbol": s,
                        "open_time": w + pd.Timedelta(days=day),
                        "close": base * noise,
                        "quote_volume": 1e8,
                    }
                )
    daily = pd.DataFrame(rows)
    # PIT: todos los 10 simbolos en top10/top20 cada mes
    months = sorted({w.to_period("M").to_timestamp().tz_localize("UTC") for w in weeks})
    pit_rows = []
    for m in months:
        for rank, s in enumerate(syms, start=1):
            pit_rows.append(
                {
                    "month": m,
                    "rank": rank,
                    "symbol": s,
                    "trailing_mean": 1e8,
                    "n_days": 30,
                    "in_top10": rank <= 10,
                    "in_top20": rank <= 20,
                }
            )
    pit = pd.DataFrame(pit_rows)
    return daily, pit, syms


def test_h2_selects_winner_and_respects_rupture() -> None:
    daily, pit, syms = _synthetic_h2_inputs()
    panel = build_weekly_panel(daily)
    cm = CostModel(
        spot_taker_fee=0.001,
        perp_taker_fee=0.0005,
        slippage_tiers=((0.05, 3.0),),
        max_participation=0.05,
        min_notional_usdt=5.0,
    )
    cell = H2Cell(L_weeks=4, N=10)
    adj_empty = pd.DataFrame(columns=["symbol", "event_date_utc", "classification"])
    res = build_h2(panel, pit, adj_empty, cell, cm, capital_usdt=10_000.0)
    assert res.weeks_used > 20
    assert "S0USDT" in res.last_basket  # el ganador entra en el tercil superior

    # ruptura corporate_action en la ventana de formacion final => S0 excluido
    last_week = pd.Timestamp(res.last_week).tz_localize("UTC") if res.last_week else None
    assert last_week is not None
    ev = last_week - pd.Timedelta(days=10)  # dentro de la ventana de formacion
    adj = pd.DataFrame(
        [{"symbol": "S0USDT", "event_date_utc": ev, "classification": "corporate_action"}]
    )
    res2 = build_h2(panel, pit, adj, cell, cm, capital_usdt=10_000.0)
    assert "S0USDT" not in res2.last_basket


def test_h3_signal_threshold_and_warmup() -> None:
    days = pd.date_range("2024-01-01", periods=60, freq="D", tz="UTC")
    times = []
    for d in days:
        for h in (0, 8, 16):
            times.append(d + pd.Timedelta(hours=h))
    funding = pd.DataFrame({"funding_time": times, "funding_rate": [0.0002] * len(times)})
    cell_on = H3Cell(window_days=7, threshold_ann=0.05)  # 0.0002*3*365 = 0.219 > 0.05
    sig, fma = h3_signal(days, funding, cell_on)
    assert not sig[:6].any()  # warmup de 7 dias
    assert sig[10:].all()
    assert np.isclose(fma[10], 0.0002 * 3 * 365, rtol=1e-9)
    cell_off = H3Cell(window_days=7, threshold_ann=0.50)  # 0.219 < 0.5
    sig2, _ = h3_signal(days, funding, cell_off)
    assert not sig2.any()
