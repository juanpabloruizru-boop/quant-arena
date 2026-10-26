"""Benchmarks y tests de permutacion para H1 (PRERREGISTRO v1.2).

Definiciones normativas (docs/PREREGISTRO.md s6/s7, v1.2):

- Benchmark PRIMARIO de H1: **vol-matched B&H**. Factor f = sigma(estrategia) /
  sigma(B&H) computado ex-post DENTRO de cada periodo de evaluacion (solo para
  construir el benchmark; la estrategia no lo usa). Bajo el nulo de timing
  (exposicion independiente del retorno futuro), E[Delta maxDD] ~ 0.
- Benchmark de diagnostico: exposure-matched (fraccion constante e_bar). AVISO:
  por Jensen (E[w^2] >= e_bar^2) tiene sesgo sistematico EN CONTRA de reglas de
  exposicion variable bajo el nulo: no se usa como criterio (defecto 1 del
  gate M0b).
- Nulo de permutacion: el propio vector de posiciones de la estrategia,
  permutado por bloques circulares (preserva distribucion y autocorrelacion de
  la exposicion; destruye su alineacion con los retornos). Para cada
  permutacion se recalcula el estadistico completo (estrategia neta de costes
  vs SU vol-matched), y el p-valor es la fraccion de permutaciones con
  Delta maxDD igual o menor (mejor) que el observado (correccion +1 de
  Phipson & Smyth).
- Convencion de signo: Delta maxDD = maxDD(estrategia) - maxDD(benchmark).
  Delta > 0 = la estrategia tiene PEOR drawdown. Mejora = Delta < 0.

Solo matematicas puras sobre arrays: este modulo no sabe nada de datos reales.
"""

from __future__ import annotations

from typing import Any

import numpy as np
from numpy.typing import NDArray

F64 = NDArray[np.float64]


def max_drawdown(returns: NDArray[np.floating[Any]]) -> float:
    """Max drawdown (fraccion, >= 0) de una serie de retornos simples."""
    r = np.asarray(returns, dtype=np.float64)
    wealth = np.cumprod(1.0 + r)
    peak = np.maximum.accumulate(wealth)
    return float(np.max(1.0 - wealth / peak))


def vol_matched_factor(
    strat_returns: NDArray[np.floating[Any]], bh_returns: NDArray[np.floating[Any]]
) -> float:
    """f = sigma(estrategia neta) / sigma(B&H), ambas ddof=1, dentro del periodo."""
    s = float(np.std(np.asarray(strat_returns, dtype=np.float64), ddof=1))
    b = float(np.std(np.asarray(bh_returns, dtype=np.float64), ddof=1))
    if b <= 1e-15:
        return 1.0
    return s / b


def delta_maxdd(
    strat_returns: NDArray[np.floating[Any]], bench_returns: NDArray[np.floating[Any]]
) -> float:
    """Delta maxDD = maxDD(strat) - maxDD(bench). >0 = estrategia peor (convencion)."""
    return max_drawdown(strat_returns) - max_drawdown(bench_returns)


def vol_matched_delta(
    strat_returns: NDArray[np.floating[Any]], bh_returns: NDArray[np.floating[Any]]
) -> float:
    """Estadistico primario v1.2: Delta maxDD de la estrategia vs su vol-matched B&H."""
    bh = np.asarray(bh_returns, dtype=np.float64)
    f = vol_matched_factor(strat_returns, bh)
    return delta_maxdd(strat_returns, f * bh)


def exposure_matched_delta(
    strat_returns: NDArray[np.floating[Any]],
    bh_returns: NDArray[np.floating[Any]],
    positions: NDArray[np.floating[Any]],
) -> float:
    """Diagnostico v1.1 (NO criterio): Delta maxDD vs fraccion constante e_bar."""
    bh = np.asarray(bh_returns, dtype=np.float64)
    e_bar = float(np.mean(np.asarray(positions, dtype=np.float64)))
    return delta_maxdd(strat_returns, e_bar * bh)


def circular_block_permutations(
    positions: F64, block: int, n_perm: int, seed: int
) -> NDArray[np.float64]:
    """(n_perm, L) permutaciones por bloques circulares del vector de posiciones."""
    pos = np.asarray(positions, dtype=np.float64)
    length = pos.shape[0]
    block = max(1, min(int(block), length))
    rng = np.random.default_rng(seed)
    n_blocks = int(np.ceil(length / block))
    starts = rng.integers(0, length, size=(n_perm, n_blocks))
    offsets = np.arange(block)
    idx = (starts[:, :, None] + offsets[None, None, :]).reshape(n_perm, n_blocks * block)
    idx = idx[:, :length] % length
    out: NDArray[np.float64] = np.asarray(pos[idx], dtype=np.float64)
    return out


def permutation_delta_stats(
    positions_perm: NDArray[np.float64],
    asset_returns_next: NDArray[np.float64],
    cost_per_side: float,
) -> tuple[NDArray[np.float64], NDArray[np.float64]]:
    """Para cada fila de posiciones permutadas: (Delta maxDD vol-matched, Sharpe ann).

    Convencion temporal: ``positions_perm[:, t]`` es la posicion vigente durante
    ``asset_returns_next[t]`` (es decir, ya desplazada: decision en t-1, retorno
    en t). Costes = |delta posicion| * cost_per_side.
    """
    p = np.asarray(positions_perm, dtype=np.float64)
    r = np.asarray(asset_returns_next, dtype=np.float64)
    gross = p * r[None, :]
    turnover = np.abs(np.diff(p, axis=1, prepend=np.zeros((p.shape[0], 1))))
    net = gross - turnover * cost_per_side
    n_days = net.shape[1]

    wealth = np.cumprod(1.0 + net, axis=1)
    peak = np.maximum.accumulate(wealth, axis=1)
    dd_strat = np.max(1.0 - wealth / peak, axis=1)

    sd_r = float(np.std(r, ddof=1))
    sd_net = np.std(net, axis=1, ddof=1)
    f = np.where(sd_r > 1e-15, sd_net / sd_r, 1.0)
    bench = f[:, None] * r[None, :]
    wealth_b = np.cumprod(1.0 + bench, axis=1)
    peak_b = np.maximum.accumulate(wealth_b, axis=1)
    dd_bench = np.max(1.0 - wealth_b / peak_b, axis=1)

    mu_net = np.mean(net, axis=1)
    sharpe = np.where(sd_net > 1e-15, mu_net / sd_net * np.sqrt(365.0), 0.0)
    _ = n_days
    return dd_strat - dd_bench, sharpe


def permutation_pvalue(delta_obs: float, deltas_perm: NDArray[np.float64]) -> float:
    """p = (1 + #{perm <= obs}) / (1 + n_perm). Mejora = Delta mas negativo."""
    perm = np.asarray(deltas_perm, dtype=np.float64)
    return float((1 + np.sum(perm <= delta_obs)) / (1 + perm.shape[0]))
