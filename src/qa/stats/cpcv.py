"""CPCV purgado con embargo y walk-forward purgado (M2).

Convenciones:
- ``formation``: ventana de formacion (en observaciones) de la senal: una
  muestra de train cuyo intervalo de formacion solape el test se PURGA.
- ``embargo``: buffer adicional (observaciones) despues del final de cada
  bloque de test (Lopez de Prado, cap. 7): se purga del train.
- CPCV: N splits contiguos; cada path usa n_test splits como test y el resto
  como train -> C(N, n_test) paths. Pre-registro: N=10, n_test=2 -> 45 paths.
"""

from __future__ import annotations

from itertools import combinations

import numpy as np
from numpy.typing import NDArray


def _blocks(n_obs: int, n_splits: int) -> list[NDArray[np.int64]]:
    edges = np.linspace(0, n_obs, n_splits + 1).astype(int)
    return [np.arange(a, b) for a, b in zip(edges[:-1], edges[1:], strict=True)]


def cpcv_splits(
    n_obs: int, n_splits: int = 10, n_test: int = 2, formation: int = 0, embargo: int = 0
) -> list[tuple[NDArray[np.int64], NDArray[np.int64]]]:
    """45 (o C(n_splits,n_test)) pares (train_idx, test_idx) purgados."""
    blocks = _blocks(n_obs, n_splits)
    out: list[tuple[NDArray[np.int64], NDArray[np.int64]]] = []
    for test_ids in combinations(range(n_splits), n_test):
        test_idx = np.concatenate([blocks[i] for i in test_ids])
        banned: list[NDArray[np.int64]] = []
        for i in test_ids:
            lo = max(0, blocks[i][0] - formation)
            hi = min(n_obs - 1, blocks[i][-1] + embargo)
            banned.append(np.arange(lo, hi + 1))
        banned_idx = np.concatenate(banned) if banned else np.array([], dtype=np.int64)
        train_idx = np.setdiff1d(np.arange(n_obs), banned_idx)
        out.append((train_idx, test_idx))
    return out


def walk_forward_purged(
    n_obs: int, n_folds: int = 6, embargo: int = 0, formation: int = 0, min_train: int | None = None
) -> list[tuple[NDArray[np.int64], NDArray[np.int64]]]:
    """Walk-forward rodante: train = [0, inicio_test - formation - embargo), test = bloque i."""
    edges = np.linspace(0, n_obs, n_folds + 1).astype(int)
    out: list[tuple[NDArray[np.int64], NDArray[np.int64]]] = []
    for i in range(1, n_folds + 1):
        t0, t1 = edges[i - 1], edges[i]
        if i == 1:
            continue  # el primer bloque no tiene train previo
        train_end = t0 - formation - embargo
        if min_train is not None and train_end < min_train:
            continue
        if train_end <= 0:
            continue
        train_idx = np.arange(0, train_end)
        test_idx = np.arange(t0, t1)
        out.append((train_idx, test_idx))
    return out
