"""Invarianza por truncamiento del universo PIT (propiedad, hypothesis).

Para cualquier mes m: construir el universo con la historia completa o con la
historia truncada justo antes de m debe dar filas IDENTICAS para todos los
meses < m. Es la garantia de cero look-ahead del ranking PIT.
"""

from __future__ import annotations

import numpy as np
import pandas as pd
from hypothesis import given, settings
from hypothesis import strategies as st

from qa.data.pit import build_pit_from_frame

START = pd.Timestamp("2021-01-01", tz="UTC")


def _synthetic_daily(n_symbols: int, n_days: int, seed: int) -> pd.DataFrame:
    rng = np.random.default_rng(seed)
    days = pd.date_range(START, periods=n_days, freq="D")
    frames = []
    for i in range(n_symbols):
        vol = rng.lognormal(mean=rng.uniform(5, 15), sigma=0.5, size=n_days)
        frames.append(
            pd.DataFrame(
                {
                    "symbol": f"SYM{i}USDT",
                    "open_time": days,
                    "quote_volume": vol,
                }
            )
        )
    return pd.concat(frames, ignore_index=True)


@settings(max_examples=8, deadline=None)
@given(
    n_symbols=st.integers(min_value=3, max_value=8),
    n_days=st.integers(min_value=120, max_value=260),
    seed=st.integers(min_value=0, max_value=10_000),
    cut=st.integers(min_value=90, max_value=110),
)
def test_truncation_invariance(n_symbols: int, n_days: int, seed: int, cut: int) -> None:
    cut = min(cut, n_days - 30)
    full = _synthetic_daily(n_symbols, n_days, seed)
    cut_ts = START + pd.Timedelta(days=cut)
    truncated = full[full["open_time"] < cut_ts]

    pit_full = build_pit_from_frame(full)
    pit_trunc = build_pit_from_frame(truncated)
    if pit_full.empty or pit_trunc.empty:
        return
    cut_month = cut_ts.to_period("M").to_timestamp().tz_localize("UTC")
    a = pit_full[pit_full["month"] < cut_month].reset_index(drop=True)
    b = pit_trunc[pit_trunc["month"] < cut_month].reset_index(drop=True)
    pd.testing.assert_frame_equal(a, b)


def test_ranking_correctness_bruta() -> None:
    # 3 simbolos con volumenes conocidos en la ventana: el ranking debe ser exacto
    days = pd.date_range("2021-03-01", periods=61, freq="D", tz="UTC")
    rows = []
    vols = {"AAAUSDT": 100.0, "BBBUSDT": 300.0, "CCCUSDT": 200.0}
    for sym, v in vols.items():
        rows.append(pd.DataFrame({"symbol": sym, "open_time": days, "quote_volume": v}))
    # DDDUSDT listado hace poco (< 60 dias) -> fuera por edad minima
    young_days = pd.date_range("2021-04-01", periods=30, freq="D", tz="UTC")
    rows.append(pd.DataFrame({"symbol": "DDDUSDT", "open_time": young_days, "quote_volume": 999.0}))
    df = pd.concat(rows, ignore_index=True)
    pit = build_pit_from_frame(df, top_k=40, window_days=30, min_age_days=60, min_days=15)
    m_may = pit[pit["month"] == pd.Timestamp("2021-05-01", tz="UTC")]
    assert not m_may.empty
    order = m_may.sort_values("rank")["symbol"].tolist()
    assert order == ["BBBUSDT", "CCCUSDT", "AAAUSDT"]  # DDDUSDT excluido por edad
    assert set(m_may["symbol"]) == {"AAAUSDT", "BBBUSDT", "CCCUSDT"}
