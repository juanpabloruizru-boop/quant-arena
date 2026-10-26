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
