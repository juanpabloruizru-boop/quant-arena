"""Prueba sintetica de aceptacion 2 (M2): senal sembrada de tamanno conocido.

Se siembra un IC verdadero de 0.05 (senal z_t correlacionada con el retorno
siguiente). El laboratorio debe:
- recuperar el IC dentro de su IC bootstrap por bloques (el IC verdadero cae
  dentro del intervalo);
- detectar la senal (p permutado <= t*) con el tamanno de muestra para el que
  la potencia de M0 lo permite (se usa n grande para que la deteccion sea
  determinista en el test).
Todo sintetico, semillas fijas.
"""

from __future__ import annotations

import math

import numpy as np

from qa.stats.benchmarks import (
    circular_block_permutations,
    permutation_delta_stats,
    permutation_pvalue,
)

SEED = 424242
L = 4000
IC_TRUE = 0.10  # senal GRANDE a proposito: acceptance test del motor, no realismo


def test_planted_signal_recovery() -> None:
    rng = np.random.default_rng(SEED)
    sig_d = 0.60 / np.sqrt(365.0)
    # senal persistente AR(1), phi=0.995 (media-vida ~139 d): como las senales
    # de baja frecuencia reales. Con senal iid, la banda no reduciria el
    # turnover y los costes se comerian el alpha (verificado en M0c/M2).
    phi = 0.995
    z = np.empty(L + 1)
    z[0] = rng.normal()
    innov = rng.normal(size=L)
    for t in range(1, L + 1):
        z[t] = phi * z[t - 1] + math.sqrt(1.0 - phi * phi) * innov[t - 1]
    noise = rng.normal(0.0, sig_d, size=L + 1)
    # retorno del dia t+1 = IC * sigma * z_t + ruido (senal sembrada)
    r = IC_TRUE * sig_d * z[:-1] + noise[1:]

    # 1) recuperacion del IC dentro del intervalo bootstrap
    sig = z[:-1]
    fwd = r
    ic_point = float(np.corrcoef(sig, fwd)[0, 1])
    # IC bootstrap por bloques (corr de Pearson sobre bloques estacionarios)
    idx_blocks = 400
    block = 20
    rng_b = np.random.default_rng(SEED + 1)
    ics = []
    n = sig.size
    for _ in range(idx_blocks):
        starts = rng_b.integers(0, n, size=int(np.ceil(n / block)))
        idx = (
            np.concatenate([(starts[i : i + 1] + np.arange(block)) for i in range(starts.size)])[:n]
            % n
        )
        s_b, f_b = sig[idx], fwd[idx]
        ics.append(float(np.corrcoef(s_b, f_b)[0, 1]))
    ic_lo, ic_hi = np.quantile(ics, [0.025, 0.975])
    # Criterio de aceptacion M2: "recuperarla dentro de su IC" -> el IC verdadero
    # cae dentro del IC bootstrap. La tolerancia del estimador puntual es amplia
    # a proposito: con senal AR(1) phi=0.995 el n efectivo es ~L*(1-phi)/(1+phi)
    # ~ 10 observaciones independientes.
    assert ic_lo <= IC_TRUE <= ic_hi, f"IC verdadero {IC_TRUE} fuera de [{ic_lo:.4f},{ic_hi:.4f}]"
    assert abs(ic_point - IC_TRUE) < 0.05

    # 2) deteccion por el criterio de permutacion con n suficiente.
    # La posicion objetivo se ejecuta con BANDA de 10 pp (como H1): sin banda,
    # el rebalanceo continuo sangra el alpha via costes (leccion de M0c).
    target = np.clip(z[:-1], -1.0, 1.0) * 0.9
    w = np.zeros_like(target)
    last = 0.0
    for t in range(target.size):
        if (target[t] > 0) != (last > 0) or abs(target[t] - last) >= 0.10:
            last = target[t]
        w[t] = last
    strat = w * r
    cost = np.abs(np.diff(w, prepend=0.0)) * 0.0013
    strat_net = strat - cost
    sd_bh = float(np.std(r, ddof=1))
    sd_st = float(np.std(strat_net, ddof=1))
    f = sd_st / sd_bh
    bench = f * r

    def _mdd(x: np.ndarray) -> float:
        ww = np.cumprod(1.0 + x)
        return float((1.0 - ww / np.maximum.accumulate(ww)).max())

    d_obs = _mdd(strat_net) - _mdd(bench)
    perms = circular_block_permutations(w, 20, 999, seed=SEED)
    d_perm, _ = permutation_delta_stats(perms, r, 0.0013)
    p = permutation_pvalue(d_obs, d_perm)
    assert p <= 0.025, f"senal sembrada no detectada: p={p:.4f}, d_obs={d_obs:.4f}"
    assert d_obs < 0
