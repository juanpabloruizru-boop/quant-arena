"""Validacion del nivel critico t*=0.025 (condicion A, gate M2).

El t* se calibro bajo GBM. Aqui se valida el FPR con SEMILLAS NUEVAS y en los
mundos alternativos vol-MS y vol-MS+Poisson (todos sin habilidad de timing).
Objetivo del orquestador: FPR(p <= t*) en [3.5%, 6.5%]. Si algun mundo sale de
rango, se reporta y se propone v1.4 (solo sintetica).

Salida: reports/M2_tstar_validation.md/.json. Determinista (semillas nuevas
fijas, distintas de las de calibracion).
"""

from __future__ import annotations

import json
import sys
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import numpy as np

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "scripts"))

import power_analysis as pa  # noqa: E402

OUT_MD = REPO / "reports" / "M2_tstar_validation.md"
OUT_JSON = REPO / "reports" / "M2_tstar_validation.json"
T_STAR = 0.025
N_SIMS = 5000
N_PERM = 199
YEARS = 8.2
WINDOW = 200
CHUNK = 500
WORLD_SEEDS = {  # semillas NUEVAS (las de calibracion fueron SEED+7/SEED+8)
    "gbm": 987_654_321,
    "ms_vol": 555_444_333,
    "ms_vol_jump": 246_813_579,
}
TARGET = (0.035, 0.065)


def collect(dgp: str, seed: int) -> tuple[np.ndarray, np.ndarray]:
    ps: list[np.ndarray] = []
    ds: list[np.ndarray] = []
    t_days = int(round(YEARS * pa.DAYS_PER_YEAR))
    done, ci = 0, 0
    while done < N_SIMS:
        m = min(CHUNK, N_SIMS - done)
        part = pa._simulate_chunk(
            dgp=dgp,
            t_days=t_days,
            window=WINDOW,
            sigma_obj=0.25,
            band=pa.BAND_FROZEN,
            cost_per_side=pa.COST_PER_SIDE,
            n_sims=m,
            seed=seed + 10_007 * ci,
            perm_offset=done,
            mu_ann=0.15,
            sigma_ann=0.60,
            s_mu=0.0,
            n_perm=N_PERM,
            null_scheme="block20",
        )
        p = part["p_perm"]
        assert p is not None
        ps.append(p)
        ds.append(part["d_vm"])
        done += m
        ci += 1
    return np.concatenate(ps), np.concatenate(ds)


def main() -> None:
    res: dict[str, Any] = {
        "generated_at_utc": datetime.now(UTC).isoformat(timespec="seconds"),
        "t_star": T_STAR,
        "n_sims": N_SIMS,
        "n_perm": N_PERM,
        "target_fpr": TARGET,
        "note_semillas": "semillas nuevas, distintas de las de calibracion (SEED+7/8)",
        "worlds": {},
    }
    all_ok = True
    for dgp, seed in WORLD_SEEDS.items():
        p, d = collect(dgp, seed)
        fpr_le = float((p <= T_STAR).mean())
        fpr_lt = float((p < T_STAR).mean())
        in_range = TARGET[0] <= fpr_le <= TARGET[1]
        all_ok &= in_range
        res["worlds"][dgp] = {
            "seed": seed,
            "fpr_p_le_tstar": round(fpr_le, 4),
            "fpr_p_lt_tstar": round(fpr_lt, 4),
            "fpr_p_lt_005": round(float((p < 0.05).mean()), 4),
            "mean_p": round(float(p.mean()), 4),
            "mean_d_vm_pp": round(float(d.mean()) * 100, 2),
            "in_target_range": in_range,
        }
        print(dgp, json.dumps(res["worlds"][dgp]))
    res["overall_in_range"] = all_ok
    OUT_MD.write_text(
        "# Validacion de t* = 0.025 (condicion A, gate M2)\n\n"
        f"- Generado: {res['generated_at_utc']} | n_sims={N_SIMS} por mundo | n_perm={N_PERM}\n"
        f"- Semillas NUEVAS (no las de calibracion). Objetivo FPR(p<=t*) en {TARGET}.\n\n"
        "| mundo | semilla | FPR p<=t* | FPR p<t* | FPR p<0.05 | p medio | "
        "E[DmaxDD vm] pp | en rango |\n"
        "|---|---|---|---|---|---|---|---|\n"
        + "\n".join(
            f"| {w} | {d['seed']} | {d['fpr_p_le_tstar']} | {d['fpr_p_lt_tstar']} | "
            f"{d['fpr_p_lt_005']} | {d['mean_p']} | {d['mean_d_vm_pp']} | "
            f"{'SI' if d['in_target_range'] else 'NO'} |"
            for w, d in res["worlds"].items()
        )
        + f"\n\n**Overall en rango: {all_ok}**\n",
        encoding="utf-8",
    )
    OUT_JSON.write_text(json.dumps(res, indent=2), encoding="utf-8")
    print("overall_in_range:", all_ok, "->", OUT_MD)


if __name__ == "__main__":
    main()
