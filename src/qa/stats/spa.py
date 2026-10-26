"""PBO via CSCV (Bailey, Borwein, Lopez de Prado, Zhu) y Reality Check de White (M2).

- ``cscv_pbo``: combina C(S, S/2) particiones (muestreadas, semilla fija);
  en cada una: la mejor celda en train -> rango relativo omega en test;
  lambda = logit(omega); PBO = P(lambda <= 0).
- ``reality_check_pvalue``: estadistico V = max_c media(excesos diarios del
  candidato c); bootstrap por bloques estacionario CON recentrado (nulo: ningun
  candidato bate al benchmark); p = fraccion de bootstraps con max >= V_obs.
"""

from __future__ import annotations

import math
from itertools import combinations
from typing import Any

import numpy as np
from numpy.typing import NDArray

from qa.stats.bootstrap import stationary_bootstrap_indices

F64 = NDArray[np.float64]


def cscv_pbo(
    returns_matrix: NDArray[np.floating[Any]],
    n_splits: int = 16,
    n_combos: int = 100,
    seed: int = 20261026,
) -> float:
    """returns_matrix: (T, k) retornos netos por periodo de cada celda/candidata."""
    m = np.asarray(returns_matrix, dtype=np.float64)
    t_obs, k = m.shape
    if k < 2 or t_obs < n_splits * 4:
        return float("nan")
    blocks = [
        np.arange(a, b)
        for a, b in zip(
            np.linspace(0, t_obs, n_splits + 1).astype(int)[:-1],
            np.linspace(0, t_obs, n_splits + 1).astype(int)[1:],
            strict=True,
        )
    ]
    all_combos = list(combinations(range(n_splits), n_splits // 2))
    rng = np.random.default_rng(seed)
    if len(all_combos) > n_combos:
        pick = rng.choice(len(all_combos), size=n_combos, replace=False)
        combos = [all_combos[i] for i in sorted(pick)]
    else:
        combos = all_combos
    n_under = 0
    n_valid = 0
    for tr_ids in combos:
        te_ids = [i for i in range(n_splits) if i not in set(tr_ids)]
        tr = np.concatenate([blocks[i] for i in tr_ids])
        te = np.concatenate([blocks[i] for i in te_ids])
        train_means = m[tr].mean(axis=0)
        best = int(np.argmax(train_means))
        test_means = m[te].mean(axis=0)
        rank = int(np.sum(test_means < test_means[best])) + 1  # 1..k
        omega = rank / (k + 1.0)
        omega = min(max(omega, 1e-6), 1.0 - 1e-6)
        lam = math.log(omega / (1.0 - omega))
        n_valid += 1
        if lam <= 0:
            n_under += 1
    return n_under / n_valid if n_valid else float("nan")


def reality_check_pvalue(
    excess_returns: NDArray[np.floating[Any]],
    mean_block: int = 20,
    n_boot: int = 500,
    seed: int = 20261026,
) -> dict[str, float]:
    """excess_returns: (T, k) exceso diario (estrategia - benchmark) por candidata."""
    m = np.asarray(excess_returns, dtype=np.float64)
    t_obs, k = m.shape
    v_obs = float(m.mean(axis=0).max())
    centered = m - m.mean(axis=0, keepdims=True)
    idx = stationary_bootstrap_indices(t_obs, mean_block, n_boot, seed)
    boot_max = np.empty(n_boot)
    for b in range(n_boot):
        boot_max[b] = centered[idx[b]].mean(axis=0).max()
    p = float((boot_max >= v_obs).mean())
    best = int(m.mean(axis=0).argmax())
    return {"v_obs": v_obs, "p_value": p, "best_candidate": best, "n_boot": n_boot}
