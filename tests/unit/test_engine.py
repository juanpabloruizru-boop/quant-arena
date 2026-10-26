"""Motor: convencion de timing de funding (off-by-one), costes, minimos y
reproduccion de buy&hold con fixture conocido (M2)."""

from __future__ import annotations

import numpy as np
import pandas as pd

from qa.backtest.costs import CostModel
from qa.backtest.engine import run_carry, run_positions, simple_returns


def _costmodel(fee: float = 0.001, slip_bps: float = 3.0, min_notional: float = 5.0) -> CostModel:
    return CostModel(
        spot_taker_fee=fee,
        perp_taker_fee=fee,
        slippage_tiers=((0.0001, slip_bps), (0.001, slip_bps), (0.01, 15.0), (0.05, 60.0)),
        max_participation=0.05,
        min_notional_usdt=min_notional,
    )


def test_buy_hold_fixture_exact() -> None:
    close = np.array([100.0, 110.0, 99.0, 108.9])
    r = simple_returns(close)
    assert np.allclose(r, [0.10, -0.10, 0.10])
    cm = _costmodel(fee=0.0, slip_bps=0.0, min_notional=0.0)
    # peso deseado 1.0 desde el cierre del dia 0 => captura r[1:] integro, sin costes
    res = run_positions(close, np.ones(4), np.full(4, 1e12), cm, capital_usdt=10_000.0, band=0.0)
    cum_engine = float(np.prod(1.0 + res.net_returns) - 1.0)
    cum_bh = close[-1] / close[0] - 1.0
    assert abs(cum_engine - cum_bh) < 1e-12
    assert res.rejected_trades == 0 and res.rejected_min_notional == 0


def test_min_notional_rejects_small_orders_but_allows_full_exit() -> None:
    close = 100.0 * np.ones(6)
    cm = _costmodel(min_notional=50.0)
    # capital 100 => abrir 50% = 50 USDT (OK en el limite); abrir 10% = 10 < 50 => rechazo
    dw = np.array([0.0, 0.10, 0.10, 0.0, 0.0, 0.0])
    res = run_positions(close, dw, np.full(6, 1e9), cm, capital_usdt=100.0, band=0.0)
    assert res.rejected_min_notional >= 1
    assert res.positions.sum() == 0.0  # nunca llego a abrir
    # cierre total a 0 desde posicion abierta SI se permite aunque el delta sea pequeno
    dw2 = np.array([1.0, 1.0, 0.0, 0.0, 0.0, 0.0])
    res2 = run_positions(close, dw2, np.full(6, 1e9), cm, capital_usdt=10_000.0, band=0.0)
    assert res2.positions[0] == 1.0
    assert res2.positions[-1] == 0.0


def test_participation_cap_rejects_illiquid_trade() -> None:
    close = 100.0 * np.ones(5)
    cm = _costmodel()
    # volumen diario 1000 USDT; capital 100k => participacion 100x el maximo => rechazo
    res = run_positions(
        close, np.ones(5), np.full(5, 1_000.0), cm, capital_usdt=100_000.0, band=0.0
    )
    # el trade bloqueado se reintenta cada dia mientras siga la senal (4 dias)
    assert res.rejected_trades == 4
    assert res.positions.sum() == 0.0


def test_band_avoids_micro_rebalance() -> None:
    close = 100.0 * np.ones(10)
    cm = _costmodel(fee=0.001, slip_bps=3.0)
    dw = np.full(10, 0.50)
    dw[3] = 0.55  # cambio de 5pp < banda 10pp => no opera
    dw[6:] = 0.80  # cambio >= banda => opera y se mantiene
    res = run_positions(close, dw, np.full(10, 1e9), cm, capital_usdt=10_000.0, band=0.10)
    # posiciones: entra a 0.5 (dia1), ignora 0.55, salta a 0.8 en dia7
    assert res.positions[0] == 0.5
    assert res.positions[3] == 0.5  # sin micro-rebalanceo
    assert res.positions[-1] == 0.8


def test_funding_off_by_one_convention() -> None:
    """Convencion pre-registrada: entry_ts < fundingTime < exit_ts (estricto).

    Dias d0..d4. Senal decidida al cierre: act = [F, T, T, F, F]
    => activa durante d2 y d3; entrada 00:00 de d2, salida 00:00 de d4.
    Eventos 00/08/16 cada dia. Capturados: d2 08:00, d2 16:00, d3 00:00,
    d3 08:00, d3 16:00. NO capturados: d2 00:00 (instante de entrada),
    d4 00:00 (instante de salida). Total 5 eventos.
    """
    days = pd.date_range("2024-01-01", periods=5, freq="D", tz="UTC")
    times = []
    for d in days:
        for h in (0, 8, 16):
            times.append(d + pd.Timedelta(hours=h))
    funding = pd.DataFrame({"funding_time": times, "funding_rate": [0.0001] * len(times)})
    act = np.array([False, True, True, False, False])
    cm = _costmodel(fee=0.0, slip_bps=0.0, min_notional=0.0)
    flat = np.full(5, 100.0)
    res = run_carry(days, funding, act, np.full(5, 1e12), cm, 10_000.0, flat, flat)
    assert res.funding_collected == 5 * 0.0001
    assert res.metrics["active_days"] == 2
    # sin costes, el P&L neto total = funding capturado
    assert abs(res.net_returns.sum() - 0.0005) < 1e-12


def test_funding_short_receives_positive_pays_negative() -> None:
    days = pd.date_range("2024-01-01", periods=3, freq="D", tz="UTC")
    times = [days[1] + pd.Timedelta(hours=8), days[1] + pd.Timedelta(hours=16)]
    funding = pd.DataFrame({"funding_time": times, "funding_rate": [0.0002, -0.0001]})
    act = np.array([True, True, False])  # activa en d1
    cm = _costmodel(fee=0.0, slip_bps=0.0, min_notional=0.0)
    flat = np.full(3, 100.0)
    res = run_carry(days, funding, act, np.full(3, 1e12), cm, 10_000.0, flat, flat)
    # entrada 00:00 d1; eventos 08/16 de d1 capturados: +0.0002 -0.0001
    assert abs(res.net_returns.sum() - 0.0001) < 1e-12


def test_carry_basis_convergence_pnl() -> None:
    """La prima del perp converge a la baja: el short de perp gana (r_spot-r_perp>0)."""
    days = pd.date_range("2024-01-01", periods=3, freq="D", tz="UTC")
    funding = pd.DataFrame({"funding_time": [], "funding_rate": []})
    act = np.array([True, True, False])  # activa durante d1 y d2
    spot = np.array([100.0, 100.0, 102.0])  # spot +2% en d2
    perp = np.array([101.0, 101.0, 101.0])  # perp plano: la prima se comprime
    cm = _costmodel(fee=0.0, slip_bps=0.0, min_notional=0.0)
    res = run_carry(days, funding, act, np.full(3, 1e12), cm, 10_000.0, spot, perp)
    # dia 2: r_spot = +2%, r_perp = 0% => pnl +0.02; dia 1: 0
    assert abs(res.net_returns.sum() - 0.02) < 1e-12
