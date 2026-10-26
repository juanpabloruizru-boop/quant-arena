"""Deflated Sharpe Ratio (Bailey & Lopez de Prado 2014) — implementacion canonica.

DSR = Phi( (SR_hat - SR0) * sqrt(T-1) / sqrt(1 - g3*SR_hat + (g4-1)/4*SR_hat^2) )
con SR_hat por observacion (no anualizado), T observaciones, g3 asimetria,
g4 curtosis (no normalizada), y SR0 = esperanza del maximo de n_trials Sharpe
bajo el nulo dada la dispersion entre celdas.

n_trials SIEMPRE proviene del ledger de trials (qa.backtest.trials), nunca de
un numero manual (principio 3).
"""

from __future__ import annotations

import math
from statistics import NormalDist

GAMMA_EM = 0.5772156649015329
_NORM = NormalDist()


def expected_max_sr_under_null(n_trials: int, sd_trials_per_obs: float) -> float:
    """SR0 por observacion: E[max] de n_trials normales estandar x sd entre celdas."""
    n = max(2, int(n_trials))
    e_max_std = (1.0 - GAMMA_EM) * _NORM.inv_cdf(1.0 - 1.0 / n) + GAMMA_EM * _NORM.inv_cdf(
        1.0 - 1.0 / (n * math.e)
    )
    return sd_trials_per_obs * e_max_std


def deflated_sharpe(
    sr_per_obs: float,
    n_obs: int,
    n_trials: int,
    sd_trials_per_obs: float,
    skew: float,
    kurtosis: float,
) -> float:
    denom = math.sqrt(
        max(1e-12, 1.0 - skew * sr_per_obs + ((kurtosis - 1.0) / 4.0) * sr_per_obs**2)
    )
    sr0 = expected_max_sr_under_null(n_trials, sd_trials_per_obs)
    return _NORM.cdf((sr_per_obs - sr0) * math.sqrt(max(1, n_obs) - 1) / denom)


def dsr_from_daily(
    daily_returns: list[float] | object,
    n_trials: int,
    sd_trials_ann: float,
    periods_per_year: float = 365.0,
) -> float:
    """DSR desde retornos diarios: SR por observacion, momentos empiricos."""
    import numpy as np

    r = np.asarray(daily_returns, dtype=np.float64)
    sd = float(r.std(ddof=1))
    if sd < 1e-15:
        return 0.0
    sr_obs = float(r.mean()) / sd  # por observacion (diaria)
    m3 = float(((r - r.mean()) ** 3).mean()) / sd**3
    m4 = float(((r - r.mean()) ** 4).mean()) / sd**4
    return deflated_sharpe(
        sr_per_obs=sr_obs,
        n_obs=int(r.size),
        n_trials=n_trials,
        sd_trials_per_obs=sd_trials_ann / math.sqrt(periods_per_year),
        skew=m3,
        kurtosis=m4,
    )
