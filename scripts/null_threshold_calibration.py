"""Calibracion sintetica del nivel critico del test de permutacion de H1 (v1.3).

Con 5000 simulaciones del nulo (GBM, sin habilidad) se mide la distribucion
empirica del p-valor de permutacion (bloques circulares 20d, n_perm=199) y se
elige el mayor nivel discreto t* = k/200 con FPR(t*) <= 5%. Con t* se mide la
potencia bajo habilidad plantada (drift AR(1) calibrado a DeltaSharpe=0.3).
Solo evidencia sintetica; ninguna metrica sobre datos reales.

Salida: reports/M0_null_threshold_calibration.md/.json
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

OUT_MD = REPO / "reports" / "M0_null_threshold_calibration.md"
OUT_JSON = REPO / "reports" / "M0_null_threshold_calibration.json"
N_SIMS = 5000
N_PERM = 199
YEARS = 8.2
WINDOW = 200
CHUNK = 500


def collect_pvals(dgp: str, s_mu: float, seed: int) -> tuple[np.ndarray, np.ndarray]:
    """p_perm y d_vm por simulacion, en chunks de memoria acotada."""
    ps: list[np.ndarray] = []
    ds: list[np.ndarray] = []
    t_days = int(round(YEARS * pa.DAYS_PER_YEAR))
    done = 0
    ci = 0
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
            s_mu=s_mu,
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
        "n_sims": N_SIMS,
        "n_perm": N_PERM,
        "scheme": "block20",
        "window": WINDOW,
    }
    p_null, d_null = collect_pvals("gbm", 0.0, pa.SEED + 7)
    levels = np.arange(1, N_PERM + 1) / (N_PERM + 1)
    fpr_curve = [(float(t), float((p_null <= t).mean())) for t in levels]
    valid = [(t, f) for t, f in fpr_curve if f <= 0.05]
    t_star, fpr_star = valid[-1] if valid else (levels[0], float((p_null <= levels[0]).mean()))
    res["null"] = {
        "fpr_at_0.05": round(float((p_null < 0.05).mean()), 4),
        "t_star": round(float(t_star), 5),
        "fpr_at_t_star": round(fpr_star, 4),
        "mean_p": round(float(p_null.mean()), 4),
        "mean_d_vm_pp": round(float(d_null.mean()) * 100, 2),
    }
    s_mu, achieved = pa.calibrate_ar1(0.3, WINDOW, YEARS, n_sims=250, seed=pa.CAL_SEED + 31)
    p_sk, d_sk = collect_pvals("ar1_drift", s_mu, pa.SEED + 8)
    res["skill"] = {
        "s_mu_daily": round(s_mu, 8),
        "achieved_cal": achieved,
        "d_sharpe_note": "ver M0_null_scheme_comparison.json (0.3056 logrado con 5000 sims)",
        "power_at_0.05": round(float(((p_sk < 0.05) & (d_sk < 0)).mean()), 4),
        "power_at_t_star": round(float(((p_sk < t_star) & (d_sk < 0)).mean()), 4),
    }
    res["decision"] = (
        f"Adoptar block20 con nivel critico calibrado t*={t_star:.4f} "
        f"(FPR sintetico {fpr_star:.4f} <= 5%). Rotacion circular descartada: "
        "FPR 2.8% y potencia 6.8% (ver M0_null_scheme_comparison)."
    )
    OUT_MD.write_text(
        "# Calibracion del nivel critico del test de permutacion H1 (v1.3)\n\n"
        f"- Generado: {res['generated_at_utc']} | n_sims={N_SIMS} | n_perm={N_PERM} | bloques 20d\n"
        f"- FPR del nulo en p<0.05: **{res['null']['fpr_at_0.05']}**\n"
        f"- Nivel critico calibrado t*: **{res['null']['t_star']}** "
        f"(FPR {res['null']['fpr_at_t_star']})\n"
        f"- p medio del nulo: {res['null']['mean_p']} | "
        f"E[DmaxDD vm] nulo: {res['null']['mean_d_vm_pp']} pp\n"
        f"- Potencia con habilidad (DSharpe~0.3): en 0.05 = {res['skill']['power_at_0.05']}; "
        f"en t* = {res['skill']['power_at_t_star']}\n\n**Decision:** {res['decision']}\n",
        encoding="utf-8",
    )
    OUT_JSON.write_text(json.dumps(res, indent=2, ensure_ascii=False), encoding="utf-8")
    print(json.dumps(res, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
