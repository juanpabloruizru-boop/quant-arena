"""Prueba sintetica de aceptacion 1 (M2): paseo aleatorio con deriva 0.

Bateria de estrategias aleatorias sobre GBM puro:
- la fraccion con p-valor permutado <= t* (0.025) debe ser <= ~nominal;
- la fraccion con DSR > 0.95 (n_trials = tamanno de la bateria) debe ser <= 5%;
- los IC bootstrap deben incluir 0 en la gran mayoria.
Todo sintetico, semillas fijas. Runtime objetivo < 60 s.
"""

from __future__ import annotations

import numpy as np

from qa.stats.benchmarks import (
    circular_block_permutations,
    permutation_delta_stats,
    permutation_pvalue,
)
from qa.stats.bootstrap import block_ci
from qa.stats.dsr import dsr_from_daily

SEED = 20261026
N_STRATS = 48
L = 1500
COST = 0.0013
THRESH = 0.025
N_PERM = 199


def _random_positions(rng: np.random.Generator, length: int) -> np.ndarray:
    """Exposiciones aleatorias con persistencia variable (suavizado de ruido)."""
    raw = rng.normal(size=length)
    k = int(rng.integers(5, 120))
    kernel = np.ones(k) / k
    sm = np.convolve(raw, kernel, mode="same")
    span = float(np.ptp(sm))
    w: np.ndarray = np.clip((sm - sm.min()) / (span + 1e-12), 0.0, 1.0)
    return w


def test_random_walk_battery() -> None:
    rng = np.random.default_rng(SEED)
    sig_d = 0.60 / np.sqrt(365.0)
    r = rng.normal(0.0, sig_d, size=L + 1)  # deriva 0
    bh = r[1:]

    n_sig_perm = 0
    n_sig_dsr = 0
    n_ic_excl_zero = 0
    for s in range(N_STRATS):
        pos = _random_positions(np.random.default_rng(SEED + 1000 + s), L)
        strat = pos * bh
        turnover = np.abs(np.diff(pos, prepend=0.0))
        strat = strat - turnover * COST

        # 1) permutacion (bloques 20d, t*=0.025)
        sd_bh = float(np.std(bh, ddof=1))
        sd_st = float(np.std(strat, ddof=1))
        f = sd_st / sd_bh if sd_bh > 0 else 1.0
        bench = f * bh

        def _mdd(x: np.ndarray) -> float:
            w = np.cumprod(1.0 + x)
            return float((1.0 - w / np.maximum.accumulate(w)).max())

        d_obs = _mdd(strat) - _mdd(bench)
        perms = circular_block_permutations(pos, 20, N_PERM, seed=SEED + s)
        d_perm, _ = permutation_delta_stats(perms, bh, COST)
        p = permutation_pvalue(d_obs, d_perm)
        if p <= THRESH and d_obs < 0:
            n_sig_perm += 1

        # 2) DSR con n_trials = tamanno real de la bateria
        if dsr_from_daily(strat, n_trials=N_STRATS, sd_trials_ann=0.5) > 0.95:
            n_sig_dsr += 1

        # 3) IC (senal = posicion previa vs retorno siguiente) con IC bootstrap
        sig = pos[:-1]
        fwd = bh[1:]
        n = min(sig.size, fwd.size)
        prod = sig[:n] * fwd[:n]
        _, lo, hi = block_ci(
            prod, lambda x: float(np.mean(x)) * 365.0, mean_block=20, n_boot=400, seed=SEED + s
        )
        if lo > 0 or hi < 0:
            n_ic_excl_zero += 1

    fpr_perm = n_sig_perm / N_STRATS
    fpr_dsr = n_sig_dsr / N_STRATS
    fpr_ic = n_ic_excl_zero / N_STRATS
    assert fpr_perm <= 0.10, f"FPR permutacion {fpr_perm:.3f} > 0.10"
    assert fpr_dsr <= 0.05, f"FPR DSR {fpr_dsr:.3f} > 0.05"
    assert fpr_ic <= 0.15, f"IC excluye 0 en {fpr_ic:.3f} > 0.15 de estrategias aleatorias"
