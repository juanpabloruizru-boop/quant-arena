"""Valores conocidos de metricas + modulos estadisticos (M2)."""

from __future__ import annotations

import numpy as np

from qa.stats.bootstrap import newey_west_se, stationary_bootstrap_indices
from qa.stats.cpcv import cpcv_splits, walk_forward_purged
from qa.stats.dsr import deflated_sharpe
from qa.stats.metrics import (
    expectancy_R,
    max_drawdown,
    sharpe_ann,
    time_underwater_days,
    trades_from_positions,
    ulcer_index,
)
from qa.stats.spa import cscv_pbo, reality_check_pvalue


def test_max_drawdown_known() -> None:
    r = np.array([0.10, -0.20, 0.05])
    assert abs(max_drawdown(r) - 0.2) < 1e-12


def test_ulcer_and_underwater_known() -> None:
    r = np.array([0.0, -0.10, 0.0, 0.05, 0.06])
    # wealth: 1, .9, .9, .945, 1.0017 -> dd: 0,.1,.1,.055,0
    u = ulcer_index(r)
    expected = np.sqrt((0.1**2 + 0.1**2 + 0.055**2) / 5)
    assert abs(u - expected) < 1e-6
    assert time_underwater_days(r) == 3


def test_trades_and_expectancy() -> None:
    pos = np.array([0.0, 1.0, 1.0, 0.0, 0.5, 0.0])
    assert trades_from_positions(pos) == [(1, 3), (4, 5)]
    r = np.array([0.0, 0.02, 0.01, -0.05, 0.03, 0.0])
    e = expectancy_R(r, pos, risk_reference=0.01)
    trade1 = (1.02 * 1.01) - 1.0
    trade2 = 1.03 - 1.0
    assert abs(e - ((trade1 + trade2) / 2) / 0.01) < 1e-9


def test_sharpe_sign_and_scale() -> None:
    rng = np.random.default_rng(0)
    r = rng.normal(0.001, 0.01, 1000)
    assert sharpe_ann(r) > 0
    assert abs(sharpe_ann(r * 2.0) - sharpe_ann(r)) < 1e-9  # invariante a escala


def test_dsr_monotone_in_sharpe_and_trials() -> None:
    base = deflated_sharpe(0.01, 2000, 22, 0.5 / np.sqrt(365), 0.0, 3.0)
    better = deflated_sharpe(0.02, 2000, 22, 0.5 / np.sqrt(365), 0.0, 3.0)
    more_trials = deflated_sharpe(0.01, 2000, 200, 0.5 / np.sqrt(365), 0.0, 3.0)
    assert better > base > more_trials
    assert 0.0 <= base <= 1.0


def test_cpcv_splits_count_and_purge() -> None:
    splits = cpcv_splits(1000, n_splits=10, n_test=2, formation=20, embargo=10)
    assert len(splits) == 45
    for tr, te in splits:
        assert len(np.intersect1d(tr, te)) == 0
        # purga+embargo por segmento contiguo de test
        cuts = np.where(np.diff(te) != 1)[0] + 1
        for seg in np.split(te, cuts):
            lo, hi = int(seg[0]) - 20, int(seg[-1]) + 10
            assert not ((tr >= lo) & (tr <= hi)).any()


def test_walk_forward_purged_no_overlap() -> None:
    folds = walk_forward_purged(900, n_folds=6, embargo=20, formation=10)
    assert len(folds) >= 4
    for tr, te in folds:
        assert tr.max() + 10 + 20 <= te.min()


def test_stationary_bootstrap_shape_and_range() -> None:
    idx = stationary_bootstrap_indices(500, 20, 100, seed=7)
    assert idx.shape == (100, 500)
    assert idx.min() >= 0 and idx.max() < 500


def test_newey_west_ge_naive_con_autocorrelacion() -> None:
    rng = np.random.default_rng(3)
    e = rng.normal(0, 1, 2000)
    x = np.empty_like(e)
    x[0] = e[0]
    for t in range(1, len(e)):
        x[t] = 0.7 * x[t - 1] + e[t]
    se_hac = newey_west_se(x, lag=10)
    se_naive = x.std(ddof=1) / np.sqrt(len(x))
    assert se_hac > se_naive  # HAC detecta la autocorrelacion


def test_pbo_range_and_rc_null() -> None:
    rng = np.random.default_rng(11)
    m = rng.normal(0, 0.01, size=(800, 6))
    pbo = cscv_pbo(m, n_splits=8, n_combos=20, seed=5)
    assert 0.0 <= pbo <= 1.0
    # mini-calibracion del RC bajo ruido puro: <=2 rechazos en 10 datasets (5% nominal)
    rejects = 0
    for sd in range(10):
        mm = np.random.default_rng(100 + sd).normal(0, 0.01, size=(800, 6))
        rc = reality_check_pvalue(mm, mean_block=20, n_boot=300, seed=200 + sd)
        assert 0.0 <= rc["p_value"] <= 1.0
        if rc["p_value"] < 0.05:
            rejects += 1
    assert rejects <= 2, f"RC rechaza {rejects}/10 bajo ruido puro"
