"""Comparacion de esquemas de permutacion para el nulo de H1 (condicion 3, gate M1).

Esquemas:
- ``block20``: permutacion por bloques circulares de 20 dias (v1.2). Con
  exposiciones persistentes de meses (SMA), rompe la autocorrelacion de la
  exposicion y puede descalibrar el FPR.
- ``rotation``: rotacion circular aleatoria del vector COMPLETO de posiciones.
  Preserva la autocorrelacion exactamente; solo destruye la alineacion con los
  retornos.

Protocolo (solo sintetico):
- FPR bajo GBM (nulo): 5000 simulaciones por esquema, tolerancia exigida por el
  orquestador: FPR en [3.5%, 6.5%] (nominal 5%).
- Potencia bajo habilidad plantada: drift AR(1) calibrado a DeltaSharpe=0.3
  neto vs B&H crudo (calibracion con 250 sims), 5000 simulaciones por esquema.
- Adopcion: esquema con FPR dentro de tolerancia y mas cercano a 5%; a igual
  calibracion, el de mayor potencia. Decision tomada SOLO con evidencia
  sintetica, antes de tocar datos reales de estrategia.

Salida: reports/M0_null_scheme_comparison.md/.json. Determinista (semillas).
"""

from __future__ import annotations

import json
import sys
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "scripts"))

import power_analysis as pa  # noqa: E402

OUT_MD = REPO / "reports" / "M0_null_scheme_comparison.md"
OUT_JSON = REPO / "reports" / "M0_null_scheme_comparison.json"
N_SIMS = 5000
N_PERM = 199
YEARS = 8.2
WINDOW = 200
TOL = (0.035, 0.065)


def main() -> None:
    out: dict[str, Any] = {
        "generated_at_utc": datetime.now(UTC).isoformat(timespec="seconds"),
        "n_sims": N_SIMS,
        "n_perm": N_PERM,
        "tolerancia_fpr": TOL,
        "schemes": {},
    }

    # FPR bajo nulo (GBM)
    for scheme in ("block20", "rotation"):
        agg = pa.simulate_h1_v12(
            dgp="gbm",
            years=YEARS,
            window=WINDOW,
            n_sims=N_SIMS,
            seed=pa.SEED + 7,
            n_perm=N_PERM,
            null_scheme=scheme,
        )
        out["schemes"][scheme] = {
            "null_fpr_p05": agg.fpr_perm_p05,
            "null_fpr_composite": agg.power_composite,
            "null_mean_p": agg.mean_p_perm,
            "null_mean_d_vm_pp": agg.mean_d_maxdd_volmatched_pp,
        }

    # Calibracion del mundo con habilidad (DeltaSharpe verdadero = 0.3)
    s_mu, achieved = pa.calibrate_ar1(0.3, WINDOW, YEARS, n_sims=250, seed=pa.CAL_SEED + 31)
    out["calibration"] = {"target": 0.3, "s_mu_daily": s_mu, "achieved_cal": achieved}

    for scheme in ("block20", "rotation"):
        agg = pa.simulate_h1_v12(
            dgp="ar1_drift",
            years=YEARS,
            window=WINDOW,
            n_sims=N_SIMS,
            seed=pa.SEED + 8,
            s_mu=s_mu,
            n_perm=N_PERM,
            null_scheme=scheme,
        )
        out["schemes"][scheme].update(
            {
                "skill_dsharpe_achieved": agg.mean_d_sharpe_raw,
                "skill_power_p05": agg.fpr_perm_p05,
                "skill_power_signed": agg.power_perm_signed,
                "skill_power_composite": agg.power_composite,
                "skill_subperiods_ge2of3": agg.frac_subperiods_ge2of3,
            }
        )

    # Decision (regla fijada ANTES de ver resultados, en el docstring)
    def score(sc: str) -> tuple[float, float]:
        d = out["schemes"][sc]
        fpr = float(d["null_fpr_p05"])
        in_tol = TOL[0] <= fpr <= TOL[1]
        dist = abs(fpr - 0.05)
        return (0.0 if in_tol else 1.0 + dist, -float(d["skill_power_composite"] or 0.0))

    ranked = sorted(out["schemes"], key=score)
    adopted = ranked[0]
    out["adopted"] = adopted
    out["decision_rule"] = (
        "FPR dentro de [3.5%,6.5%] y mas cercano a 5%; empate -> mayor potencia "
        "compuesta. Solo evidencia sintetica."
    )

    OUT_MD.write_text(
        "# Comparacion de esquemas de permutacion (nulo H1) - condicion 3 gate M1\n\n"
        f"- Generado: {out['generated_at_utc']} | n_sims={N_SIMS} | n_perm={N_PERM}\n"
        f"- Tolerancia FPR exigida: {TOL}\n\n"
        "| esquema | FPR nulo (p<0.05) | FPR compuesta | p medio nulo | "
        "DSharpe logrado | potencia p<0.05 | potencia compuesta | >=2/3 subp. |\n"
        "|---|---|---|---|---|---|---|---|\n"
        + "\n".join(
            f"| {sc} | {d['null_fpr_p05']} | {d['null_fpr_composite']} | {d['null_mean_p']} | "
            f"{d['skill_dsharpe_achieved']} | {d['skill_power_signed']} | "
            f"{d['skill_power_composite']} | {d['skill_subperiods_ge2of3']} |"
            for sc, d in out["schemes"].items()
        )
        + f"\n\n**Esquema adoptado (v1.3): `{adopted}`** — {out['decision_rule']}\n"
        + f"\nCalibracion habilidad: s_mu={s_mu:.8f} (logrado en calibracion: {achieved})\n",
        encoding="utf-8",
    )
    OUT_JSON.write_text(json.dumps(out, indent=2, ensure_ascii=False), encoding="utf-8")
    print(json.dumps(out["schemes"], indent=2))
    print("ADOPTADO:", adopted)
    print(f"-> {OUT_MD}")


if __name__ == "__main__":
    main()
