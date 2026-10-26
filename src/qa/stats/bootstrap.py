"""Bootstrap por bloques estacionario (Politis & Romano 1994) y HAC (M2).

- ``stationary_bootstrap_indices``: remuestreo de bloques de longitud
  geometrica (media ``mean_block``) con wrap-around circular.
- ``block_ci``: IC por bootstrap del estadistico ``stat_fn`` sobre la serie.
- ``newey_west_se``: error estandar robusto HAC de la media.
"""

from __future__ import annotations

import math
from collections.abc import Callable
from typing import Any

import numpy as np
from numpy.typing import NDArray

F64 = NDArray[np.float64]


def stationary_bootstrap_indices(
    n: int, mean_block: int, n_boot: int, seed: int
) -> NDArray[np.int64]:
    rng = np.random.default_rng(seed)
    p = 1.0 / max(1, mean_block)
    max_runs = int(math.ceil(n / max(1, mean_block))) + 2
    idx = np.empty((n_boot, n), dtype=np.int64)
    starts = rng.integers(0, n, size=(n_boot, max_runs))
    lengths = rng.geometric(p, size=(n_boot, max_runs))
    offsets = np.zeros((n_boot, max_runs + 1), dtype=np.int64)
    np.cumsum(lengths, axis=1, out=offsets[:, 1:])
    for b in range(n_boot):
        pos = 0
        j = 0
        while pos < n and j < max_runs:
            take = min(int(lengths[b, j]), n - pos)
            idx[b, pos : pos + take] = (starts[b, j] + np.arange(take)) % n
            pos += take
            j += 1
        while pos < n:  # extremo raro: rellenar con un ultimo bloque
            take = min(n - pos, n)
            idx[b, pos : pos + take] = (starts[b, 0] + np.arange(take)) % n
            pos += take
    return idx


def block_ci(
    x: NDArray[np.floating[Any]],
    stat_fn: Callable[[NDArray[np.float64]], float],
    mean_block: int = 20,
    n_boot: int = 2000,
    seed: int = 20261026,
    alpha: float = 0.05,
) -> tuple[float, float, float]:
    """(stat_obs, ci_lo, ci_hi) percentil del bootstrap por bloques."""
    xa = np.asarray(x, dtype=np.float64)
    idx = stationary_bootstrap_indices(xa.shape[0], mean_block, n_boot, seed)
    stats = np.array([stat_fn(xa[i]) for i in idx])
    lo, hi = np.quantile(stats, [alpha / 2, 1 - alpha / 2])
    return float(stat_fn(xa)), float(lo), float(hi)


def newey_west_se(x: NDArray[np.floating[Any]], lag: int) -> float:
    """SE HAC (Newey-West) de la media, kernel Bartlett."""
    xa = np.asarray(x, dtype=np.float64)
    n = xa.shape[0]
    if n < 3:
        return float("inf")
    e = xa - xa.mean()
    gamma0 = float(e @ e) / n
    s = gamma0
    for L in range(1, max(0, int(lag)) + 1):
        w = 1.0 - L / (int(lag) + 1.0)
        gammaL = float(e[L:] @ e[:-L]) / n
        s += 2.0 * w * gammaL
    s = max(s, 1e-18)
    return math.sqrt(s / n)
