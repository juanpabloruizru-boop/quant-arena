"""Driver de M3b (apertura unica del holdout).

Modos:
  --dry       : prueba de fontaneria sobre un PSEUDO-holdout in-sample
                (2024-10-26 -> 2025-10-25). NO toca el holdout real, NO
                escribe ledger, salida a /tmp/M3b_dry.json.
  --official  : apertura unica autorizada (gate M3a). Requiere en el entorno
                QA_HOLDOUT_UNLOCK=1 y QA_HOLDOUT_KEY=<clave del usuario>.
                Descifra cada fichero UNA vez (3 entradas nuevas en
                ledger/holdout_access.log: spot, futures, funding), evalua las
                5 celdas congeladas + escalado de capital en la misma corrida,
                registra trials kind='holdout_evaluation' y escribe
                reports/M3b_results.json.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import pandas as pd

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "src"))

from qa.backtest.costs import CostModel  # noqa: E402
from qa.research.m3b import (  # noqa: E402
    HOLDOUT_START,
    M3bFrames,
    evaluate_all,
    record_trials,
    verdicts_from_results,
)


def _frames_dry(root: Path) -> M3bFrames:
    from qa.backtest.data_access import load_in_sample

    spot = load_in_sample("spot_daily", root)
    fut = load_in_sample("futures_daily", root)
    fund = load_in_sample("funding", root)
    pit = pd.read_parquet(root / "data" / "curated" / "pit_universe.parquet")
    pseudo = pd.Timestamp("2024-10-26", tz="UTC")
    # el "pseudo-holdout" es el ultimo ano in-sample (fontaneria, no ciencia)
    spot = spot[spot["open_time"] < pd.Timestamp("2025-10-26", tz="UTC")]
    fut = fut[fut["open_time"] < pd.Timestamp("2025-10-26", tz="UTC")]
    fund = fund[fund["funding_time"] < pd.Timestamp("2025-10-26", tz="UTC")]
    return M3bFrames(spot, fut, fund, pit, pseudo)


def _frames_official(root: Path) -> M3bFrames:
    from qa.backtest.data_access import load_holdout, load_in_sample

    purpose = "M3b evaluacion unica oficial (autorizada gate M3a, 2026-10-28)"
    spot = pd.concat(
        [load_in_sample("spot_daily", root), load_holdout("spot_daily", root, purpose)],
        ignore_index=True,
    )
    fut = pd.concat(
        [load_in_sample("futures_daily", root), load_holdout("futures_daily", root, purpose)],
        ignore_index=True,
    )
    fund = pd.concat(
        [load_in_sample("funding", root), load_holdout("funding", root, purpose)],
        ignore_index=True,
    )
    pit = pd.read_parquet(root / "data" / "curated" / "pit_universe.parquet")
    return M3bFrames(spot, fut, fund, pit, HOLDOUT_START)


def _access_log_lines(root: Path) -> int:
    p = root / "ledger" / "holdout_access.log"
    return len(p.read_text().strip().splitlines()) if p.exists() else 0


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--dry", action="store_true")
    ap.add_argument("--official", action="store_true")
    args = ap.parse_args()
    if args.dry == args.official:
        raise SystemExit("elige exactamente uno: --dry | --official")
    root = REPO
    cm = CostModel.from_yaml(root / "config" / "costs.yaml")
    cm2 = CostModel.from_yaml(root / "config" / "costs.yaml", stress=True)

    if args.dry:
        frames = _frames_dry(root)
        results = evaluate_all(frames, cm, cm2, root)
        results["DRY_RUN"] = "PSEUDO-holdout in-sample 2024-10-26..2025-10-25; solo fontaneria"
        results["verdicts_mecanica"] = verdicts_from_results(results)
        Path("/tmp/M3b_dry.json").write_text(
            json.dumps(results, indent=2, default=str), encoding="utf-8"
        )
        print("DRY OK -> /tmp/M3b_dry.json")
        print(json.dumps(results["verdicts_mecanica"], indent=2))
        return

    # ---- oficial ----
    before = _access_log_lines(root)
    assert before == 2, f"holdout_access.log debe tener 2 entradas antes de M3b (tiene {before})"
    frames = _frames_official(root)
    after_load = _access_log_lines(root)
    assert after_load == before + 3, f"descifrados {after_load - before} ficheros (esperados 3)"

    results = evaluate_all(frames, cm, cm2, root)
    results["verdicts"] = verdicts_from_results(results)
    results["access_log"] = {"before": before, "after_load": after_load}

    from qa.backtest.trials import TrialLedger

    ledger = TrialLedger(root)
    n = record_trials(root, ledger, results)
    results["trials_recorded"] = n
    results["n_trials_strategy_sin_cambios"] = {h: ledger.n_trials(h) for h in ("H1", "H2", "H3")}
    ledger.close()

    out = root / "reports" / "M3b_results.json"
    out.write_text(json.dumps(results, indent=2, default=str), encoding="utf-8")
    final_lines = _access_log_lines(root)
    print("ACCESOS holdout: antes", before, "| tras carga", after_load, "| finales", final_lines)
    print("trials registrados (kind=holdout_evaluation):", n)
    print(
        "n_trials strategy por familia (debe seguir 24/6/8):",
        results["n_trials_strategy_sin_cambios"],
    )
    print(json.dumps(results["verdicts"], indent=2))
    print("->", out)


if __name__ == "__main__":
    main()
