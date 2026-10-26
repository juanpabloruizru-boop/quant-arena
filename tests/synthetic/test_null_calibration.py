"""Calibracion del nulo (condicion 3 del gate M0b): bajo mundos SIN habilidad,
el estadistico vol-matched debe dar E[Delta maxDD] ~ 0 y p-valores de
permutacion aproximadamente uniformes (FPR <= nominal).

Solo datos sinteticos (semilla fija). Tamanno reducido para CI; la version
grande vive en scripts/power_analysis.py (T3/T-null).
"""

from __future__ import annotations

import numpy as np

from qa.stats.benchmarks import (
    circular_block_permutations,
    permutation_delta_stats,
    permutation_pvalue,
    vol_matched_delta,
)

COST_PER_SIDE = 0.0013
BLOCK = 20
N_PERM = 99


def _sma_positions(
    close: np.ndarray, window: int, sigma_obj: float, rets: np.ndarray
) -> np.ndarray:
    """Posicion long/flat SMA + vol target 20d con banda 10pp (como H1)."""
    n = len(close)
    csum = np.concatenate(([0.0], np.cumsum(close)))
    sma = np.full(n, np.nan)
    sma[window - 1 :] = (csum[window:] - csum[:-window]) / window
    long_sig = np.where(np.isnan(sma), 0.0, (close > sma).astype(float))
    c2 = np.concatenate(([0.0], np.cumsum(rets)))
    c2sq = np.concatenate(([0.0], np.cumsum(rets * rets)))
    m1 = np.full(n, np.nan)
    m2 = np.full(n, np.nan)
    m1[19:] = (c2[20:] - c2[:-20]) / 20
    m2[19:] = (c2sq[20:] - c2sq[:-20]) / 20
    vol20 = np.sqrt(np.maximum(m2 - m1 * m1, 0.0)) * np.sqrt(365.0)
    with np.errstate(divide="ignore", invalid="ignore"):
        scale = np.minimum(1.0, sigma_obj / vol20)
    scale = np.nan_to_num(scale, nan=0.0)
    target = long_sig * scale
    pos = np.zeros(n)
    last = 0.0
    for t in range(n):
        tgt = target[t]
        flip = (tgt > 0.0) != (last > 0.0)
        if flip or abs(tgt - last) >= 0.10:
            last = tgt
        pos[t] = last
    return pos


def test_null_volmatched_mean_zero_and_uniform_p() -> None:
    rng = np.random.default_rng(20261026)
    n_paths, n_days = 60, 1500
    mu_d, sig_d = 0.15 / 365.0, 0.60 / np.sqrt(365.0)
    deltas, pvals = [], []
    for i in range(n_paths):
        r = rng.normal(mu_d, sig_d, size=n_days + 1)
        close = np.exp(np.cumsum(np.log1p(r)))
        w_full = _sma_positions(close, 200, 0.25, r)  # decision en cierre de t
        pos = w_full[:-1]  # decision en t aplicada al retorno t -> t+1
        strat = pos * r[1:]
        turn = np.abs(np.diff(pos, prepend=0.0))
        strat = strat - turn * COST_PER_SIDE
        bh = r[1:]
        deltas.append(vol_matched_delta(strat, bh))
        perms = circular_block_permutations(pos, BLOCK, N_PERM, seed=1000 + i)
        d_perm, _ = permutation_delta_stats(perms, bh, COST_PER_SIDE)
        pvals.append(permutation_pvalue(deltas[-1], d_perm))

    deltas_arr = np.asarray(deltas)
    pvals_arr = np.asarray(pvals)
    mean_d = float(deltas_arr.mean())
    se_d = float(deltas_arr.std(ddof=1) / np.sqrt(n_paths))
    # E[Delta] ~ 0 bajo el nulo: |media| <= 3 errores estandar + margen pequeno
    assert abs(mean_d) < max(3.0 * se_d, 0.02), f"E[Delta] bajo nulo = {mean_d:.4f}"
    # p-valores ~ uniformes
    assert 0.35 < pvals_arr.mean() < 0.65, f"media p = {pvals_arr.mean():.3f}"
    fpr = float((pvals_arr < 0.05).mean())
    assert fpr <= 0.10, f"FPR empirico {fpr:.3f} > 0.10 con nominal 0.05"
