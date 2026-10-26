"""Metricas riesgo/retorno (M2). Anualizacion cripto: 365 dias.

Convenciones:
- Entradas: series de retornos simples por periodo (diarios salvo que se diga).
- max_drawdown: fraccion >= 0 (0.25 = -25%).
- Convencion de signo de deltas entre estrategias: ver qa.stats.benchmarks.
"""

from __future__ import annotations

import math
from typing import Any

import numpy as np
from numpy.typing import NDArray

F64 = NDArray[np.float64]
PERIODS_PER_YEAR = 365.0


def sharpe_ann(returns: NDArray[np.floating[Any]], periods: float = PERIODS_PER_YEAR) -> float:
    r = np.asarray(returns, dtype=np.float64)
    sd = float(r.std(ddof=1))
    if sd < 1e-15 or not np.isfinite(sd):
        return 0.0
    return float(r.mean() / sd * math.sqrt(periods))


def sortino_ann(returns: NDArray[np.floating[Any]], periods: float = PERIODS_PER_YEAR) -> float:
    r = np.asarray(returns, dtype=np.float64)
    downside = r[r < 0]
    if downside.size < 2:
        return 0.0
    dd = float(np.sqrt((downside**2).mean()))
    if dd < 1e-15:
        return 0.0
    return float(r.mean() / dd * math.sqrt(periods))


def wealth_curve(returns: NDArray[np.floating[Any]]) -> F64:
    return np.asarray(np.cumprod(1.0 + np.asarray(returns, dtype=np.float64)), dtype=np.float64)


def drawdown_series(returns: NDArray[np.floating[Any]]) -> F64:
    w = wealth_curve(returns)
    peak = np.maximum.accumulate(w)
    return 1.0 - w / peak


def max_drawdown(returns: NDArray[np.floating[Any]]) -> float:
    d = drawdown_series(returns)
    return float(d.max()) if d.size else 0.0


def calmar(returns: NDArray[np.floating[Any]], periods: float = PERIODS_PER_YEAR) -> float:
    r = np.asarray(returns, dtype=np.float64)
    mdd = max_drawdown(r)
    if mdd < 1e-12:
        return 0.0
    n_years = r.size / periods
    if n_years <= 0:
        return 0.0
    total = float(np.prod(1.0 + r)) - 1.0
    cagr = (1.0 + total) ** (1.0 / n_years) - 1.0 if total > -1.0 else -1.0
    return float(cagr / mdd)


def ulcer_index(returns: NDArray[np.floating[Any]]) -> float:
    """sqrt(mean(dd^2)) en tanto por uno (Martin)."""
    d = drawdown_series(returns)
    return float(np.sqrt((d**2).mean())) if d.size else 0.0


def time_underwater_days(returns: NDArray[np.floating[Any]]) -> int:
    """Numero de periodos por debajo del maximo historico (no en maximo)."""
    w = wealth_curve(returns)
    peak = np.maximum.accumulate(w)
    return int(np.sum(w < peak - 1e-15))


def trades_from_positions(positions: NDArray[np.floating[Any]]) -> list[tuple[int, int]]:
    """Tramos contiguos (inicio, fin_exclusivo) con posicion != 0."""
    p = np.asarray(positions, dtype=np.float64)
    active = p != 0.0
    out: list[tuple[int, int]] = []
    start: int | None = None
    for i, a in enumerate(active):
        if a and start is None:
            start = i
        elif not a and start is not None:
            out.append((start, i))
            start = None
    if start is not None:
        out.append((start, len(active)))
    return out


def expectancy_R(
    returns: NDArray[np.floating[Any]],
    positions: NDArray[np.floating[Any]],
    risk_reference: float = 0.01,
) -> float:
    """Expectancy en R: P&L medio por trade / riesgo de referencia (1% por defecto).

    Definicion pre-registrada: el trade es un tramo contiguo de posicion != 0;
    su P&L es el retorno compuesto del tramo (neto, tal cual entra).
    """
    r = np.asarray(returns, dtype=np.float64)
    pnls = [float(np.prod(1.0 + r[a:b]) - 1.0) for a, b in trades_from_positions(positions)]
    if not pnls:
        return 0.0
    return float(np.mean(pnls) / risk_reference)


def metrics_summary(
    returns: NDArray[np.floating[Any]], positions: NDArray[np.floating[Any]] | None = None
) -> dict[str, float]:
    out = {
        "sharpe_ann": round(sharpe_ann(returns), 4),
        "sortino_ann": round(sortino_ann(returns), 4),
        "max_drawdown": round(max_drawdown(returns), 4),
        "calmar": round(calmar(returns), 4),
        "ulcer_index": round(ulcer_index(returns), 6),
        "time_underwater": time_underwater_days(returns),
        "total_return": round(float(np.prod(1.0 + np.asarray(returns, dtype=np.float64)) - 1.0), 6),
        "n_obs": int(np.asarray(returns).size),
    }
    if positions is not None:
        out["expectancy_R"] = round(expectancy_R(returns, positions), 4)
        out["n_trades"] = len(trades_from_positions(positions))
    return out
