"""Simulacion del FWER del pipeline completo de H1 bajo el nulo (condicion 4, gate M1).

Mundo: GBM correlacionado BTC/ETH (rho=0.8), SIN habilidad. Rejilla completa:
variante {sma, ret} x ventana {50,100,200} x sigma_obj {0.15,0.25} = 12 celdas
x 2 activos = 24 candidatas.

Por cada mundo simulado se evalua el pipeline de decision de H1:
- C1a/C1b: regla compuesta por candidata (p de permutacion < 0.05, Delta maxDD
  vol-matched < 0 en el in-sample completo y en >=2 de 3 subperiodos), con el
  esquema de permutacion adoptado en v1.3.
- C2': Reality Check de White sobre las 24 candidatas (estadistico = max de las
  medias de los excesos diarios estrategia-vs-benchmark-vol-matched; bootstrap
  estacionario conjunto recentrado; B remuestreos).

Salidas: P(alguna candidata pasa la compuesta), P(RC rechaza), P(pipeline:
alguna compuesta Y RC rechaza) = cota del FWER familiar. Solo sintetico.
Determinista (semilla fija). Salida: reports/M0_h1_fwer.md/.json.
"""

from __future__ import annotations

import json
import math
import sys
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import numpy as np
from numpy.typing import NDArray

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "scripts"))
sys.path.insert(0, str(REPO / "src"))

import power_analysis as pa  # noqa: E402
from qa.stats.benchmarks import (  # noqa: E402
    circular_block_permutations,
    permutation_delta_stats,
    permutation_pvalue,
    random_rotations,
)

SEED = pa.SEED + 777
N_WORLDS = 200
N_PERM = 99
RC_BOOT = 200
RC_BLOCK = 20
YEARS = 8.2
COST = pa.COST_PER_SIDE
BAND = pa.BAND_FROZEN
ADOPTED_SCHEME = sys.argv[1] if len(sys.argv) > 1 else "block20"
THRESH = float(sys.argv[2]) if len(sys.argv) > 2 else 0.05
OUT_MD = REPO / "reports" / "M0_h1_fwer.md"
OUT_JSON = REPO / "reports" / "M0_h1_fwer.json"
F64 = NDArray[np.float64]

CELLS = [
    (variant, window, sobj)
    for variant in ("sma", "ret")
    for window in (50, 100, 200)
    for sobj in (0.15, 0.25)
]
ASSETS = ("BTC", "ETH")
RHO = 0.8


def _band_positions(target: F64, band: float) -> F64:
    """target (W,T) decidido al cierre de t -> posicion vigente en t+1 con banda."""
    w, t_len = target.shape
    pos = np.zeros_like(target)
    last = np.zeros(w)
    for t in range(1, t_len):
        tgt = target[:, t - 1]
        flip = (tgt > 0.0) != (last > 0.0)
        trade = flip | (np.abs(tgt - last) >= band) if band > 0 else np.ones(w, dtype=bool)
        last = np.where(trade, tgt, last)
        pos[:, t] = last
    return pos


def _cell_positions(r: F64, variant: str, window: int, sigma_obj: float) -> F64:
    w, t_len = r.shape
    close = np.exp(np.cumsum(np.log1p(r), axis=1))
    if variant == "sma":
        cs = np.cumsum(close, axis=1)
        pad = np.concatenate([np.zeros((w, 1)), cs[:, :-window]], axis=1)
        sma = np.full_like(close, np.nan)
        sma[:, window - 1 :] = (cs[:, window - 1 :] - pad) / window
        sig = np.nan_to_num(close > sma).astype(float)
    else:  # ret: suma de log-retornos de los ultimos L dias > 0
        cs = np.cumsum(np.log1p(r), axis=1)
        roll = np.full_like(r, np.nan)
        roll[:, window:] = cs[:, window:] - cs[:, :-window]
        sig = np.nan_to_num(roll > 0).astype(float)
    m1 = pa._rolling_mean(r, 20)
    m2 = pa._rolling_mean(r * r, 20)
    vol20 = np.sqrt(np.maximum(m2 - m1 * m1, 0.0)) * math.sqrt(pa.DAYS_PER_YEAR)
    with np.errstate(divide="ignore", invalid="ignore"):
        scale = np.minimum(1.0, sigma_obj / vol20)
    scale = np.nan_to_num(scale, nan=0.0)
    return _band_positions(sig * scale, BAND)


def _maxdd_rows(returns: F64) -> F64:
    wealth = np.cumprod(1.0 + returns, axis=1)
    peak = np.maximum.accumulate(wealth, axis=1)
    out: F64 = np.asarray(np.max(1.0 - wealth / peak, axis=1), dtype=np.float64)
    return out


def _stationary_boot_idx(length: int, mean_block: int, n_boot: int, rng: Any) -> NDArray[np.int64]:
    idx = np.empty((n_boot, length), dtype=np.int64)
    p = 1.0 / mean_block
    for b in range(n_boot):
        pos = 0
        while pos < length:
            start = rng.integers(0, length)
            run = rng.geometric(p)
            take = min(run, length - pos)
            idx[b, pos : pos + take] = (start + np.arange(take)) % length
            pos += take
    return idx


def main() -> None:
    rng = np.random.default_rng(SEED)
    t_days = int(round(YEARS * pa.DAYS_PER_YEAR))
    n_steps = t_days + 1

    chol = np.linalg.cholesky(np.array([[1.0, RHO], [RHO, 1.0]]))
    z = rng.normal(size=(N_WORLDS, n_steps, 2)) @ chol.T
    mu_d = math.log1p(0.15) / pa.DAYS_PER_YEAR
    sig_d = 0.60 / math.sqrt(pa.DAYS_PER_YEAR)
    paths = {a: mu_d + sig_d * z[:, :, i] for i, a in enumerate(ASSETS)}

    b1, b2 = pa.SUB_B1, pa.SUB_B2
    slices = ((0, b1), (b1, b2), (b2, t_days))

    comp_pass = np.zeros((N_WORLDS, len(CELLS), len(ASSETS)), dtype=bool)
    daily_excess: dict[tuple[int, int], F64] = {}

    for ci, (variant, window, sobj) in enumerate(CELLS):
        for ai, asset in enumerate(ASSETS):
            r_full = paths[asset]
            pos = _cell_positions(r_full[:, 1:], variant, window, sobj)
            bh = r_full[:, 1:]
            strat = pos * bh
            strat = strat - np.abs(np.diff(pos, axis=1, prepend=np.zeros((N_WORLDS, 1)))) * COST
            sd_bh = np.std(bh, axis=1, ddof=1)
            sd_st = np.std(strat, axis=1, ddof=1)
            f = np.where(sd_bh > 1e-15, sd_st / sd_bh, 1.0)
            bench = f[:, None] * bh
            d_vm = _maxdd_rows(strat) - _maxdd_rows(bench)
            daily_excess[(ci, ai)] = strat - bench

            sub_ok = np.zeros((N_WORLDS, 3), dtype=bool)
            for j, (a, b) in enumerate(slices):
                sd_b = np.std(bh[:, a:b], axis=1, ddof=1)
                sd_s = np.std(strat[:, a:b], axis=1, ddof=1)
                f_sp = np.where(sd_b > 1e-15, sd_s / sd_b, 1.0)
                sub_ok[:, j] = (
                    _maxdd_rows(strat[:, a:b]) - _maxdd_rows(f_sp[:, None] * bh[:, a:b])
                ) < 0

            p_perm = np.empty(N_WORLDS)
            for i in range(N_WORLDS):
                if ADOPTED_SCHEME == "rotation":
                    perms = random_rotations(pos[i], N_PERM, seed=SEED + 1000 * ci + 10 * ai + i)
                else:
                    perms = circular_block_permutations(
                        pos[i], pa.PERM_BLOCK, N_PERM, seed=SEED + 1000 * ci + 10 * ai + i
                    )
                d_p, _ = permutation_delta_stats(perms, bh[i], COST)
                p_perm[i] = permutation_pvalue(d_vm[i], d_p)
            comp_pass[:, ci, ai] = (p_perm <= THRESH) & (d_vm < 0) & (sub_ok.sum(axis=1) >= 2)

    # Reality Check de White sobre las 24 candidatas
    d_mat = np.stack(
        [daily_excess[(ci, ai)] for ci in range(len(CELLS)) for ai in range(len(ASSETS))]
    )
    d_mat = d_mat.transpose(1, 0, 2)  # (worlds, candidates, days)
    v_obs = d_mat.mean(axis=2).max(axis=1)  # (worlds,)
    d_centered = d_mat - d_mat.mean(axis=2, keepdims=True)
    rng2 = np.random.default_rng(SEED + 1)
    idx = _stationary_boot_idx(t_days, RC_BLOCK, RC_BOOT, rng2)
    p_rc = np.empty(N_WORLDS)
    boot_max = np.empty((N_WORLDS, RC_BOOT))
    for i in range(N_WORLDS):
        sample = d_centered[i][:, idx].mean(axis=2)  # (candidates, RC_BOOT)
        boot_max[i] = sample.max(axis=0)
    p_rc = (boot_max >= v_obs[:, None]).mean(axis=1)

    any_comp = comp_pass.any(axis=(1, 2))
    rc_rej = p_rc < 0.05
    pipeline = any_comp & rc_rej

    res: dict[str, Any] = {
        "generated_at_utc": datetime.now(UTC).isoformat(timespec="seconds"),
        "scheme": ADOPTED_SCHEME,
        "n_worlds": N_WORLDS,
        "n_candidates": len(CELLS) * len(ASSETS),
        "rho_assets": RHO,
        "n_perm": N_PERM,
        "threshold": THRESH,
        "rc_boot": RC_BOOT,
        "seed": SEED,
        "fwer_composite_any": round(float(any_comp.mean()), 4),
        "fwer_pipeline_any_and_rc": round(float(pipeline.mean()), 4),
        "rc_fpr": round(float(rc_rej.mean()), 4),
        "se_binomial": round(math.sqrt(0.05 * 0.95 / N_WORLDS), 4),
        "per_asset_composite_any": {
            a: round(float(comp_pass[:, :, ai].any(axis=1).mean()), 4)
            for ai, a in enumerate(ASSETS)
        },
        "per_cell_composite_rate": {
            f"{v}{w}_{int(s * 100)}": round(float(comp_pass[:, ci, :].mean()), 4)
            for ci, (v, w, s) in enumerate(CELLS)
        },
    }
    OUT_MD.write_text(
        "# FWER del pipeline H1 bajo el nulo (condicion 4, gate M1)\n\n"
        f"- Generado: {res['generated_at_utc']} | mundos: {N_WORLDS} | esquema: {ADOPTED_SCHEME}\n"
        f"- 24 candidatas (12 celdas x BTC/ETH), GBM correlacionado rho={RHO}, sin habilidad\n"
        f"- **P(alguna candidata pasa la regla compuesta)**: {res['fwer_composite_any']} "
        f"(SE binomial ~{res['se_binomial']})\n"
        f"- **P(RC p<0.05)**: {res['rc_fpr']}\n"
        f"- **P(pipeline completo: compuesta Y RC)**: {res['fwer_pipeline_any_and_rc']}\n"
        f"- Por activo: {res['per_asset_composite_any']}\n"
        f"- Tasa por celda: {res['per_cell_composite_rate']}\n",
        encoding="utf-8",
    )
    OUT_JSON.write_text(json.dumps(res, indent=2, ensure_ascii=False), encoding="utf-8")
    print(json.dumps(res, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
