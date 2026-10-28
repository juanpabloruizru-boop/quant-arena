"""Invarianza por truncamiento de TODAS las features (principio 2).

f(x[:t+1])[t] == f(x)[t] para todo t valido: el valor en t no puede cambiar
por datos futuros. Se prueba con hypothesis (propiedad) y casos fijos.
"""

from __future__ import annotations

import numpy as np
import pandas as pd
from hypothesis import given, settings
from hypothesis import strategies as st

from qa.features.indicators import (
    realized_vol_ann,
    rolling_mean,
    rolling_sum,
    sma,
)


@settings(max_examples=25, deadline=None)
@given(
    n=st.integers(min_value=2, max_value=40),
    window=st.integers(min_value=2, max_value=20),
    data=st.data(),
)
def test_sma_truncation_invariance(n: int, window: int, data: st.DataObject) -> None:
    x = data.draw(
        st.lists(
            st.floats(min_value=-1e3, max_value=1e3, allow_nan=False, allow_infinity=False),
            min_size=n,
            max_size=n,
        )
    )
    arr = np.asarray(x)
    full = sma(arr, window)
    for t in range(window - 1, n):
        partial = sma(arr[: t + 1], window)
        assert np.isclose(partial[t], full[t], rtol=1e-12, atol=1e-12), (t, partial[t], full[t])


@settings(max_examples=25, deadline=None)
@given(
    n=st.integers(min_value=25, max_value=60),
    window=st.integers(min_value=5, max_value=20),
    data=st.data(),
)
def test_rolling_and_vol_truncation_invariance(n: int, window: int, data: st.DataObject) -> None:
    x = np.asarray(
        data.draw(
            st.lists(
                st.floats(min_value=-0.5, max_value=0.5, allow_nan=False, allow_infinity=False),
                min_size=n,
                max_size=n,
            )
        )
    )
    for fn in (rolling_sum, rolling_mean, realized_vol_ann):
        full = fn(x, window)
        for t in range(window - 1, n):
            partial = fn(x[: t + 1], window)
            assert np.isclose(partial[t], full[t], rtol=1e-10, atol=1e-12), (fn.__name__, t)


def test_sma_known_values() -> None:
    x = np.array([1.0, 2.0, 3.0, 4.0, 5.0])
    out = sma(x, 3)
    assert np.isnan(out[0]) and np.isnan(out[1])
    assert out[2] == 2.0 and out[3] == 3.0 and out[4] == 4.0


def test_realized_vol_constant_returns() -> None:
    x = np.full(30, 0.01)
    v = realized_vol_ann(x, 20)
    assert np.isclose(v[-1], 0.0, atol=1e-12)


@settings(max_examples=10, deadline=None)
@given(
    n=st.integers(min_value=40, max_value=90),
    window=st.integers(min_value=3, max_value=15),
    data=st.data(),
)
def test_funding_ma_truncation_invariance(n: int, window: int, data: st.DataObject) -> None:
    """funding_ma_annualized tambien cumple f(x[:t+1])[t] == f(x)[t]."""
    from qa.features.indicators import funding_ma_annualized

    vals = np.asarray(
        data.draw(
            st.lists(
                st.floats(min_value=-0.001, max_value=0.001, allow_nan=False, allow_infinity=False),
                min_size=n,
                max_size=n,
            )
        )
    )
    idx = pd.date_range("2024-01-01", periods=n, freq="D", tz="UTC")
    full = funding_ma_annualized(pd.Series(vals, index=idx), window)
    for t in range(window - 1, n):
        partial = funding_ma_annualized(pd.Series(vals[: t + 1], index=idx[: t + 1]), window)
        assert np.isclose(partial.iloc[t], full.iloc[t], rtol=1e-10, atol=1e-12)


def test_funding_helpers() -> None:
    from qa.features.indicators import daily_funding_from_events, funding_ma_annualized

    times = pd.to_datetime(
        [
            "2024-01-01 00:00",
            "2024-01-01 08:00",
            "2024-01-01 16:00",
            "2024-01-02 00:00",
            "2024-01-02 08:00",
            "2024-01-02 16:00",
        ]
    ).tz_localize("UTC")
    df = pd.DataFrame({"funding_time": times, "funding_rate": [0.0001] * 6})
    daily = daily_funding_from_events(df)
    assert len(daily) == 2
    assert np.isclose(daily.iloc[0], 0.0003)
    ma = funding_ma_annualized(daily, 2)
    assert np.isclose(ma.iloc[1], 0.0003 * 365.0)


@settings(max_examples=15, deadline=None)
@given(
    n=st.integers(min_value=60, max_value=140),
    L=st.integers(min_value=5, max_value=30),
    data=st.data(),
)
def test_ret_L_days_truncation_invariance(n: int, L: int, data: st.DataObject) -> None:
    """H5: retorno de L dias (variante 'ret' de H1)."""
    from qa.features.indicators import ret_L_days

    x = np.asarray(
        data.draw(
            st.lists(
                st.floats(min_value=1.0, max_value=1e5, allow_nan=False, allow_infinity=False),
                min_size=n,
                max_size=n,
            )
        )
    )
    full = ret_L_days(x, L)
    for t in range(L, n):
        partial = ret_L_days(x[: t + 1], L)
        assert np.isclose(partial[t], full[t], rtol=1e-12, atol=1e-12)


@settings(max_examples=15, deadline=None)
@given(
    n=st.integers(min_value=30, max_value=80),
    L=st.integers(min_value=4, max_value=12),
    data=st.data(),
)
def test_formation_weekly_truncation_invariance(n: int, L: int, data: st.DataObject) -> None:
    """H5: formacion de H2 (L semanas saltando la ultima)."""
    from qa.features.indicators import formation_return_weekly

    x = np.asarray(
        data.draw(
            st.lists(
                st.floats(min_value=1.0, max_value=1e5, allow_nan=False, allow_infinity=False),
                min_size=n,
                max_size=n,
            )
        )
    )
    full = formation_return_weekly(x, L)
    for w in range(L + 2, n):
        partial = formation_return_weekly(x[: w + 1], L)
        assert np.isclose(partial[w], full[w], rtol=1e-12, atol=1e-12)
    # semantica: salta la ultima semana y usa L semanas
    w = n - 1
    assert np.isclose(full[w], x[w - 2] / x[w - 2 - L] - 1.0, rtol=1e-12)


def test_carry_signal_truncation_invariance() -> None:
    """H5: senal de carry de H3 (umbral sobre MA anualizada de funding)."""
    from qa.features.indicators import carry_signal, funding_ma_annualized

    idx = pd.date_range("2024-01-01", periods=120, freq="D", tz="UTC")
    rates = np.linspace(0.00002, 0.0004, 120)  # funding creciente (determinista)
    series = pd.Series(rates, index=idx)
    full = carry_signal(funding_ma_annualized(series, 30), 0.05)
    for t in range(29, 120):
        partial = carry_signal(funding_ma_annualized(series.iloc[: t + 1], 30), 0.05)
        assert bool(partial[t]) == bool(full[t]), t
    # warmup nunca enciende la senal
    assert not full[:29].any()
    # semantica: al superar el umbral anualizado (0.0004*365=0.146 > 0.05) enciende
    assert full[-1]
