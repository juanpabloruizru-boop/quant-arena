"""Features/indicadores CAUSALES (M2).

Regla de oro: el valor en t solo usa datos hasta t (inclusive). Todos los
indicadores pasan el test de invarianza por truncamiento:
    f(x[:t+1])[t] == f(x)[t]
NaN durante el warmup (nunca se rellenan hacia atras).
"""

from __future__ import annotations

from typing import Any

import numpy as np
import pandas as pd
from numpy.typing import NDArray

F64 = NDArray[np.float64]


def _as_array(x: pd.Series | NDArray[np.floating[Any]]) -> F64:
    return np.asarray(x, dtype=np.float64)


def sma(close: pd.Series | NDArray[np.floating[Any]], n: int) -> F64:
    """Media movil simple de los ultimos n valores (incluido el actual)."""
    if n < 1:
        raise ValueError("n debe ser >= 1")
    x = _as_array(close)
    out = np.full(x.shape, np.nan)
    c = np.cumsum(x)
    out[n - 1 :] = (c[n - 1 :] - np.concatenate(([0.0], c[:-n]))) / n
    return out


def rolling_sum(x: pd.Series | NDArray[np.floating[Any]], n: int) -> F64:
    """Suma de los ultimos n valores (incluido el actual)."""
    if n < 1:
        raise ValueError("n debe ser >= 1")
    a = _as_array(x)
    out = np.full(a.shape, np.nan)
    c = np.cumsum(a)
    out[n - 1 :] = c[n - 1 :] - np.concatenate(([0.0], c[:-n]))
    return out


def rolling_mean(x: pd.Series | NDArray[np.floating[Any]], n: int) -> F64:
    return rolling_sum(x, n) / n


def realized_vol_ann(
    returns: pd.Series | NDArray[np.floating[Any]], n: int = 20, periods_per_year: float = 365.0
) -> F64:
    """Volatilidad realizada anualizada de los ultimos n retornos (ddof=1)."""
    r = _as_array(returns)
    if r.shape[0] < n:
        return np.full(r.shape, np.nan)
    m1 = rolling_mean(r, n)
    m2 = rolling_mean(r * r, n)
    var = np.maximum(m2 - m1 * m1, 0.0)
    # correccion ddof: var poblacional * n/(n-1)
    var = var * (n / (n - 1.0))
    out: F64 = np.asarray(np.sqrt(var) * np.sqrt(periods_per_year), dtype=np.float64)
    return out


def daily_funding_from_events(funding: pd.DataFrame) -> pd.Series:
    """Agrega eventos de funding (8h) a suma diaria UTC.

    ``funding``: columnas funding_time (tz-aware UTC) y funding_rate.
    Devuelve Serie indexada por fecha UTC con la suma de tasas del dia.
    """
    if funding.empty:
        return pd.Series(dtype=float, name="funding_daily")
    d = funding.copy()
    d["day"] = pd.to_datetime(d["funding_time"]).dt.floor("D")
    out = d.groupby("day")["funding_rate"].sum().astype(float)
    out.name = "funding_daily"
    return out


def funding_ma_annualized(funding_daily: pd.Series, window_days: int) -> pd.Series:
    """Media movil (dias) del funding diario, anualizada x365. Causal."""
    ma = rolling_mean(funding_daily.to_numpy(), window_days) * 365.0
    return pd.Series(ma, index=funding_daily.index, name="funding_ma_ann")


def log_returns(close: pd.Series | NDArray[np.floating[Any]]) -> F64:
    """log-return diario: lr[t] = log(close[t]/close[t-1]); NaN en t=0. Causal."""
    x = _as_array(close)
    out = np.full(x.shape, np.nan)
    out[1:] = np.log(x[1:] / x[:-1])
    return out


def ret_L_days(close: pd.Series | NDArray[np.floating[Any]], L: int) -> F64:
    """Retorno acumulado de L dias (log): log(close[t]/close[t-L]). Causal.

    Es la feature de la variante `ret` de H1 (senal: ret_L_days[t] > 0).
    """
    x = _as_array(close)
    out = np.full(x.shape, np.nan)
    out[L:] = np.log(x[L:] / x[:-L])
    return out


def formation_return_weekly(weekly_close: pd.Series | NDArray[np.floating[Any]], L: int) -> F64:
    """Formacion de H2 en la semana w: retorno de las L semanas que terminan en
    w-1, EXCLUYENDO la ultima semana completada (w-1):

        f[w] = close[w-1-1] / close[w-1-L] - 1   (saltando la semana w-1)

    Convencion: decision en el inicio de la semana w con datos hasta el cierre de
    w-2 (la 'ultima semana' w-1 se salta). Causal: f[w] solo usa closes
    anteriores a w.
    """
    x = _as_array(weekly_close)
    out = np.full(x.shape, np.nan)
    # f[w] = x[w-2]/x[w-2-L] - 1, definido para w >= L+2 (salta la semana w-1)
    n = x.shape[0]
    if n >= L + 3:
        out[L + 2 :] = x[L : n - 2] / x[: n - L - 2] - 1.0
    return out


def carry_signal(
    funding_ma_ann: pd.Series | NDArray[np.floating[Any]], threshold: float
) -> NDArray[np.bool_]:
    """Senal de H3: media movil anualizada del funding > umbral. Causal
    (NaN durante el warmup => False, nunca True por datos futuros)."""
    x = _as_array(funding_ma_ann)
    return np.where(np.isnan(x), False, x > threshold)
