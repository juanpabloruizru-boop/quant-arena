"""Potencia del PIPELINE completo de H1 (condicion B, gate M2).

Pipeline = regla compuesta por candidata (p_perm <= t*=0.025 con bloques 20d,
Delta maxDD vol-matched < 0 y >=2/3 subperiodos) Y Reality Check de White
familiar (p < 0.05) sobre las 24 candidatas (12 celdas x BTC/ETH).

Mundos con habilidad plantada: drift latente AR(1) (phi=0.995) calibrado para
que el DeltaSharpe verdadero de la celda SMA200 (neta, vs B&H crudo) valga
{0.1, 0.3, 0.5}. Ruido correlacionado BTC/ETH (rho=0.8). W=200 mundos por
efecto. Solo sintetico.

Salida: reports/M2_h1_pipeline_power.md/.json
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

import h1_fwer_simulation as fw  # noqa: E402
import power_analysis as pa  # noqa: E402
from qa.stats.benchmarks import (  # noqa: E402
    circular_block_permutations,
    permutation_delta_stats,
    permutation_pvalue,
)

SEED = 31415926
N_WORLDS = 200
N_PERM = 99
RC_BOOT = 200
T_STAR = 0.025
YEARS = 8.2
RHO = 0.8
OUT_MD = REPO / "reports" / "M2_h1_pipeline_power.md"
OUT_JSON = REPO / "reports" / "M2_h1_pipeline_power.json"
F64 = NDArray[np.float64]


def _ar1_drift_matrix(rng: np.random.Generator, n_worlds: int, n_steps: int, s_mu: float) -> F64:
    burn = 400
    total = n_steps + burn
    mu = np.zeros((n_worlds, total))
    eps = rng.normal(0.0, s_mu, size=(n_worlds, total))
    for t in range(1, total):
        mu[:, t] = pa.AR1_PHI * mu[:, t - 1] + eps[:, t]
    return np.asarray(mu[:, burn:], dtype=np.float64)


def main() -> None:
    t_days = int(round(YEARS * pa.DAYS_PER_YEAR))
    n_steps = t_days + 1
    chol = np.linalg.cholesky(np.array([[1.0, RHO], [RHO, 1.0]]))
    sig_d = 0.60 / math.sqrt(pa.DAYS_PER_YEAR)
    b1, b2 = pa.SUB_B1, pa.SUB_B2
    slices = ((0, b1), (b1, b2), (b2, t_days))
    out: dict[str, Any] = {
        "generated_at_utc": datetime.now(UTC).isoformat(timespec="seconds"),
        "n_worlds": N_WORLDS,
        "t_star": T_STAR,
        "n_perm": N_PERM,
        "rc_boot": RC_BOOT,
        "rho_assets": RHO,
        "seed": SEED,
        "effects": {},
    }
    for target in (0.1, 0.3, 0.5):
        # s_mu calibrado sobre la celda SMA200 (las demas celdas tendran sus
        # propios efectos realizados; se reportan)
        s_mu, achieved = pa.calibrate_ar1(target, 200, YEARS, n_sims=250, seed=SEED + 7)
        rng = np.random.default_rng(SEED + int(target * 100))
        z = rng.normal(size=(N_WORLDS, n_steps, 2)) @ chol.T
        drift = {a: _ar1_drift_matrix(rng, N_WORLDS, n_steps, s_mu) for a in fw.ASSETS}
        paths = {a: drift[a] + sig_d * z[:, :, i] for i, a in enumerate(fw.ASSETS)}

        comp_pass = np.zeros((N_WORLDS, len(fw.CELLS), 2), dtype=bool)
        d_sharpe_cell: dict[str, list[float]] = {}
        daily_excess: dict[tuple[int, int], F64] = {}
        for ci, (variant, window, sobj) in enumerate(fw.CELLS):
            for ai, asset in enumerate(fw.ASSETS):
                r_full = paths[asset]
                pos = fw._cell_positions(r_full[:, 1:], variant, window, sobj)
                bh = r_full[:, 1:]
                strat = pos * bh
                strat = (
                    strat
                    - np.abs(np.diff(pos, axis=1, prepend=np.zeros((N_WORLDS, 1))))
                    * pa.COST_PER_SIDE
                )
                sd_bh = np.std(bh, axis=1, ddof=1)
                sd_st = np.std(strat, axis=1, ddof=1)
                f = np.where(sd_bh > 1e-15, sd_st / sd_bh, 1.0)
                bench = f[:, None] * bh
                d_vm = fw._maxdd_rows(strat) - fw._maxdd_rows(bench)
                daily_excess[(ci, ai)] = strat - bench
                dsh = pa._sharpe_rows(strat) - pa._sharpe_rows(bh)
                d_sharpe_cell[f"{variant}{window}_{int(sobj * 100)}_{asset}"] = [
                    round(float(np.nanmean(dsh)), 3)
                ]
                sub_ok = np.zeros((N_WORLDS, 3), dtype=bool)
                for j, (a_, b_) in enumerate(slices):
                    sd_b = np.std(bh[:, a_:b_], axis=1, ddof=1)
                    sd_s = np.std(strat[:, a_:b_], axis=1, ddof=1)
                    f_sp = np.where(sd_b > 1e-15, sd_s / sd_b, 1.0)
                    d_sp = fw._maxdd_rows(strat[:, a_:b_]) - fw._maxdd_rows(
                        f_sp[:, None] * bh[:, a_:b_]
                    )
                    sub_ok[:, j] = d_sp < 0
                p_perm = np.empty(N_WORLDS)
                for i in range(N_WORLDS):
                    perms = circular_block_permutations(
                        pos[i], pa.PERM_BLOCK, N_PERM, seed=SEED + 977 * ci + 31 * ai + i
                    )
                    d_p, _ = permutation_delta_stats(perms, bh[i], pa.COST_PER_SIDE)
                    p_perm[i] = permutation_pvalue(d_vm[i], d_p)
                comp_pass[:, ci, ai] = (p_perm <= T_STAR) & (d_vm < 0) & (sub_ok.sum(axis=1) >= 2)

        d_mat = np.stack(
            [daily_excess[(ci, ai)] for ci in range(len(fw.CELLS)) for ai in range(2)]
        ).transpose(1, 0, 2)
        v_obs = d_mat.mean(axis=2).max(axis=1)
        d_centered = d_mat - d_mat.mean(axis=2, keepdims=True)
        rng2 = np.random.default_rng(SEED + 1)
        idx = fw._stationary_boot_idx(t_days, fw.RC_BLOCK, RC_BOOT, rng2)
        boot_max = np.empty((N_WORLDS, RC_BOOT))
        for i in range(N_WORLDS):
            boot_max[i] = d_centered[i][:, idx].mean(axis=2).max(axis=0)
        p_rc = (boot_max >= v_obs[:, None]).mean(axis=1)

        any_comp = comp_pass.any(axis=(1, 2))
        rc_rej = p_rc < 0.05
        pipeline = any_comp & rc_rej
        out["effects"][str(target)] = {
            "s_mu_daily": round(s_mu, 8),
            "dsharpe_sma200_calibracion": achieved,
            "dsharpe_realizado_por_celda": d_sharpe_cell,
            "power_any_composite": round(float(any_comp.mean()), 4),
            "power_rc": round(float(rc_rej.mean()), 4),
            "power_pipeline": round(float(pipeline.mean()), 4),
        }
        print(
            target,
            json.dumps(
                {
                    k: v
                    for k, v in out["effects"][str(target)].items()
                    if k != "dsharpe_realizado_por_celda"
                }
            ),
        )

    OUT_MD.write_text(
        "# Potencia del pipeline completo de H1 (condicion B, gate M2)\n\n"
        f"- Generado: {out['generated_at_utc']} | mundos: {N_WORLDS} | 24 candidatas "
        f"(12 celdas x BTC/ETH) | rho={RHO} | t*={T_STAR} | n_perm={N_PERM} | RC B={RC_BOOT}\n\n"
        "| DSharpe verdadero (SMA200, calibracion) | P(alguna compuesta) | P(RC rechaza) | "
        "**P(PIPELINE)** |\n|---|---|---|---|\n"
        + "\n".join(
            f"| {t} ({d['dsharpe_sma200_calibracion']}) | {d['power_any_composite']} | "
            f"{d['power_rc']} | **{d['power_pipeline']}** |"
            for t, d in out["effects"].items()
        )
        + "\n\nDeltaSharpe realizado por celda: ver JSON.\n",
        encoding="utf-8",
    )
    OUT_JSON.write_text(json.dumps(out, indent=2), encoding="utf-8")
    print("->", OUT_MD)


if __name__ == "__main__":
    main()
