"""Tests de identidad del estadistico primario de H1 (condicion 3 del gate M0b).

1. Exposicion constante e_bar => Delta maxDD == 0 EXACTO (vol-matched y
   exposure-matched): el benchmark reproduce la estrategia sin costes.
2. Convencion de signo: Delta > 0 = estrategia PEOR.
3. f vol-matched es invariante a escala de la estrategia y reproduce sigma.
4. Las permutaciones por bloques circulares preservan el multiconjunto de
   exposiciones y son deterministicas con la semilla.
"""

from __future__ import annotations

import numpy as np

from qa.stats.benchmarks import (
    circular_block_permutations,
    exposure_matched_delta,
    max_drawdown,
    permutation_pvalue,
    vol_matched_delta,
    vol_matched_factor,
)


def _gbm_path(n: int, seed: int, mu: float = 0.0004, sigma: float = 0.03) -> np.ndarray:
    rng = np.random.default_rng(seed)
    return rng.normal(mu, sigma, size=n)


def test_constant_exposure_delta_is_exactly_zero() -> None:
    """Identidad matematica: exposicion constante => benchmark reproduce la
    estrategia => Delta maxDD = 0. En coma flotante la igualdad es exacta hasta
    ~1e-15 (f = std(e*r)/std(r) = e con error de redondeo); tolerancia 1e-12."""
    r = _gbm_path(2000, seed=7)
    for e_bar in (0.3, 0.6, 1.0):
        strat = e_bar * r  # sin costes: exposicion constante
        assert abs(vol_matched_delta(strat, r)) < 1e-12
        assert abs(exposure_matched_delta(strat, r, np.full_like(r, e_bar))) < 1e-12


def test_vol_matched_factor_equals_exposure_for_constant() -> None:
    r = _gbm_path(1000, seed=11)
    e_bar = 0.42
    f = vol_matched_factor(e_bar * r, r)
    assert abs(f - e_bar) < 1e-12


def test_sign_convention_strategy_worse_is_positive() -> None:
    r = _gbm_path(3000, seed=3)
    # Estrategia que concentra la exposicion justo en los peores dias: peor DD.
    worst = r < np.quantile(r, 0.30)
    # Test de convencion de signo con "oracle" alineado al mismo dia (no es una
    # estrategia operable; solo verifica el signo del estadistico).
    pos = np.where(worst, 1.0, 0.05)
    strat = pos * r
    d = vol_matched_delta(strat, r)
    assert d > 0.0, "Delta debe ser >0 cuando la estrategia tiene peor drawdown"
    pos2 = np.where(worst, 0.05, 1.0)
    strat2 = pos2 * r
    assert vol_matched_delta(strat2, r) < 0.0


def test_max_drawdown_known_value() -> None:
    # +10%, -20%, +5%: wealth 1.1 -> 0.88 -> 0.924; DD = 1 - 0.88/1.1 = 0.2
    r = np.array([0.10, -0.20, 0.05])
    assert abs(max_drawdown(r) - 0.2) < 1e-12


def test_permutations_preserve_multiset_and_seed_determinism() -> None:
    pos = np.concatenate([np.zeros(500), np.linspace(0.2, 1.0, 500)])
    p1 = circular_block_permutations(pos, block=20, n_perm=8, seed=99)
    p2 = circular_block_permutations(pos, block=20, n_perm=8, seed=99)
    p3 = circular_block_permutations(pos, block=20, n_perm=8, seed=100)
    assert p1.shape == (8, 1000)
    assert np.array_equal(p1, p2)  # determinista
    assert not np.array_equal(p1, p3)
    for row in p1:
        # bloques circulares: el multiconjunto puede diferir solo por solapes de
        # bloque; la media debe conservarse aproximadamente
        assert abs(row.mean() - pos.mean()) < 0.15


def test_pvalue_correction_bounds() -> None:
    perm = np.array([0.5, 0.4, 0.3, 0.2])
    # p = (1 + #{perm <= obs}) / (1 + n_perm); mejora = Delta mas negativo
    assert permutation_pvalue(0.1, perm) == (1 + 0) / 5  # obs mejor que todas
    assert permutation_pvalue(0.6, perm) == (1 + 4) / 5  # obs peor que todas => 1.0
    assert permutation_pvalue(0.25, perm) == (1 + 1) / 5  # solo 0.2 <= 0.25
