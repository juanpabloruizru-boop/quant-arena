"""Motor forward-v1 (fills t+1): contabilidad, banda, funding y cadena."""

from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import pandas as pd

from qa.forward.paper import (
    append_record,
    init_state,
    load_state,
    run_step,
    save_state,
    sleeve_equity,
    verify_forward_chain,
)

T0 = datetime(2026, 10, 27, 0, 30, tzinfo=UTC)


def _daily(closes: list[float], start: datetime = T0) -> pd.DataFrame:
    return pd.DataFrame(
        {
            "open_time": pd.to_datetime(
                [start + pd.Timedelta(days=i) for i in range(len(closes))], utc=True
            ),
            "close": closes,
        }
    )


def _funding(rates: list[tuple[datetime, float]]) -> pd.DataFrame:
    return pd.DataFrame(
        {
            "funding_time": pd.to_datetime([r[0] for r in rates], utc=True),
            "funding_rate": [r[1] for r in rates],
        }
    )


def _run(
    tmp_path: Path,
    state: dict[str, Any],
    cells: dict[str, Any],
    now: datetime,
    weights: dict[str, float] | None = None,
    prices: dict[str, list[float]] | None = None,
    funding: dict[str, pd.DataFrame] | None = None,
    h3: dict[str, bool] | None = None,
) -> dict[str, Any]:
    prices = prices or {"BTCUSDT": [100.0] * 60, "ETHUSDT": [50.0] * 60}
    daily: dict[str, pd.DataFrame | None] = {a: _daily(c) for a, c in prices.items()}
    rec, _ = run_step(
        state,
        cells,
        weights or {},
        daily,
        funding or {},
        now,
        h3 or {"BTCUSDT": False, "ETHUSDT": False},
    )
    return append_record(tmp_path, rec)


def test_h1_fill_band_y_equidad(tmp_path: Path) -> None:
    state = init_state(10_000.0, T0)
    cells = {"H1_BTCUSDT": {"posicion_regla": 0.6}, "H1_ETHUSDT": {"posicion_regla": 0.0}}
    rec = _run(tmp_path, state, cells, T0)
    fills = [f for f in rec["fills"] if f["sleeve"] == "H1_BTCUSDT"]
    assert len(fills) == 1
    # 60 % de 2500 USDT a precio 100 → qty 15, coste 1500×0.12 % = 1.8
    assert fills[0]["qty"] == 15.0
    assert abs(fills[0]["fee_usd"] - 1.8) < 1e-6
    eq = sleeve_equity("H1_BTCUSDT", state["sleeves"]["H1_BTCUSDT"], {"BTCUSDT": 100.0})
    assert abs(eq - (2500.0 - 1.8)) < 1e-6
    # segundo paso: dentro de banda → sin fills (no sangra comisiones)
    rec2 = _run(tmp_path, state, cells, T0 + pd.Timedelta(days=1))
    assert not [f for f in rec2["fills"] if f["sleeve"] == "H1_BTCUSDT"]


def test_h1_flip_a_cero_siempre_opera(tmp_path: Path) -> None:
    state = init_state(10_000.0, T0)
    _run(tmp_path, state, {"H1_BTCUSDT": {"posicion_regla": 0.6}}, T0)
    rec = _run(tmp_path, state, {"H1_BTCUSDT": {"posicion_regla": 0.0}}, T0 + pd.Timedelta(days=1))
    fills = [f for f in rec["fills"] if f["sleeve"] == "H1_BTCUSDT"]
    assert len(fills) == 1 and fills[0]["qty"] < 0
    assert state["sleeves"]["H1_BTCUSDT"]["qty"] == 0.0


def test_h3_apertura_funding_cierre(tmp_path: Path) -> None:
    state = init_state(10_000.0, T0)
    h3on = {"BTCUSDT": True, "ETHUSDT": False}
    rec = _run(tmp_path, state, {}, T0, h3=h3on)
    op = [f for f in rec["fills"] if f["sleeve"] == "H3_BTCETH" and f["side"] == "open"]
    assert len(op) == 1 and op[0]["asset"] == "BTCUSDT"
    sl = state["sleeves"]["H3_BTCETH"]
    assert sl["spot_qty"]["BTCUSDT"] > 0 and sl["perp_qty"]["BTCUSDT"] < 0
    assert sl["spot_qty"]["ETHUSDT"] == 0.0  # ETH inactiva: sin pata
    # funding: 2 eventos posteriores, tasa +0.01 % → el corto COBRA
    q = -sl["perp_qty"]["BTCUSDT"]
    fund = _funding([(T0 + pd.Timedelta(hours=8), 0.0001), (T0 + pd.Timedelta(hours=16), 0.0001)])
    rec2 = _run(
        tmp_path,
        state,
        {},
        T0 + pd.Timedelta(days=1),
        funding={"BTCUSDT": fund},
        h3=h3on,
    )
    esperado = q * 100.0 * 0.0001 * 2
    assert abs(rec2["funding_usd"] - esperado) < 1e-6
    # cierre: señal off → liquida ambas patas
    rec3 = _run(
        tmp_path,
        state,
        {},
        T0 + pd.Timedelta(days=2),
        funding={"BTCUSDT": fund},
        h3={"BTCUSDT": False, "ETHUSDT": False},
    )
    cl = [f for f in rec3["fills"] if f["sleeve"] == "H3_BTCETH" and f["side"] == "close"]
    assert len(cl) == 1
    assert state["sleeves"]["H3_BTCETH"]["spot_qty"]["BTCUSDT"] == 0.0
    assert state["sleeves"]["H3_BTCETH"]["perp_qty"]["BTCUSDT"] == 0.0


def test_h3_perp_mark_to_market_diario(tmp_path: Path) -> None:
    """Perp corto: si el precio SUBE, la caja del sleeve BAJA (liquidación diaria)."""
    state = init_state(10_000.0, T0)
    h3on = {"BTCUSDT": True, "ETHUSDT": False}
    _run(tmp_path, state, {}, T0, h3=h3on, prices={"BTCUSDT": [100.0] * 60, "ETHUSDT": [50.0] * 60})
    cash_antes = state["sleeves"]["H3_BTCETH"]["cash"]
    _run(
        tmp_path,
        state,
        {},
        T0 + pd.Timedelta(days=1),
        h3=h3on,
        prices={"BTCUSDT": [110.0] * 60, "ETHUSDT": [50.0] * 60},
    )
    q_perp = state["sleeves"]["H3_BTCETH"]["perp_qty"]["BTCUSDT"]
    # PnL perp = q×(110−100) (negativo para corto); spot sin realizar (marca)
    delta_cash = state["sleeves"]["H3_BTCETH"]["cash"] - cash_antes
    assert abs(delta_cash - q_perp * 10.0) < 1e-6


def test_h2_rebalanceo_semanal(tmp_path: Path) -> None:
    state = init_state(10_000.0, T0)
    w = {"BTCUSDT": 0.5, "ETHUSDT": 0.5}
    rec = _run(tmp_path, state, {}, T0, weights=w)
    assert len([f for f in rec["fills"] if f["sleeve"] == "H2_basket"]) == 2
    # misma semana ISO → sin rebalanceo
    rec2 = _run(tmp_path, state, {}, T0 + pd.Timedelta(days=1), weights=w)
    assert not [f for f in rec2["fills"] if f["sleeve"] == "H2_basket"]
    # semana siguiente con precio distinto → rebalancea
    lunes = T0 + pd.Timedelta(days=7)
    rec3 = _run(
        tmp_path,
        state,
        {},
        lunes,
        weights=w,
        prices={"BTCUSDT": [120.0] * 60, "ETHUSDT": [50.0] * 60},
    )
    assert len([f for f in rec3["fills"] if f["sleeve"] == "H2_basket"]) >= 1


def test_cadena_y_estado_roundtrip(tmp_path: Path) -> None:
    state = init_state(10_000.0, T0)
    _run(tmp_path, state, {"H1_BTCUSDT": {"posicion_regla": 0.6}}, T0)
    save_state(tmp_path, state)
    st2 = load_state(tmp_path)
    assert st2 is not None and st2["sleeves"] == state["sleeves"]
    _run(tmp_path, state, {"H1_BTCUSDT": {"posicion_regla": 0.0}}, T0 + pd.Timedelta(days=1))
    ok, n, msg = verify_forward_chain(tmp_path)
    assert ok and n == 2
    # editar una línea CON sucesor rompe la cadena (la última línea sólo es
    # detectable contra hashes externos: git/OTS — limitación documentada)
    p = tmp_path / "ledger" / "forward.jsonl"
    lines = p.read_text(encoding="utf-8").splitlines()
    lines[0] = lines[0].replace('"forward_v1_step"', '"manipulado"')
    p.write_text("\n".join(lines) + "\n", encoding="utf-8")
    ok2, _, _ = verify_forward_chain(tmp_path)
    assert not ok2


def test_registro_incluye_trazabilidad(tmp_path: Path) -> None:
    state = init_state(10_000.0, T0)
    rec = _run(tmp_path, state, {"H1_BTCUSDT": {"posicion_regla": 0.6}}, T0)
    assert rec["kind"] == "forward_v1_step"
    assert rec["prices_used"]["BTCUSDT"] == 100.0
    assert rec["total_equity_usdt"] > 0
    assert "prev_hash" in rec and "git_sha" in rec
