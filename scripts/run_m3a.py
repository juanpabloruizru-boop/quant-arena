"""Driver de M3a (una sola pasada, SOLO in-sample).

Uso:
    python scripts/run_m3a.py --family all      # H1+H2+H3+stats/Seleccion
    python scripts/run_m3a.py --family h1       # por familias (checkpoint)

Reanudable: las celdas ya registradas en ledger/trials.duckdb no repiten las
permutaciones (10 000) ni se duplican en el ledger (run_id determinista).
"""

from __future__ import annotations

import argparse
import json
import sys
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "src"))

from qa.backtest.trials import TrialLedger  # noqa: E402
from qa.research.m3a import (  # noqa: E402
    load_all,
    run_h1,
    run_h2,
    run_h3,
    select_and_verdict,
)

RESULTS = REPO / "reports" / "M3a_results.json"
SELECTED = REPO / "reports" / "M3a_selected_cells.json"


def _save(results: dict[str, Any]) -> None:
    RESULTS.parent.mkdir(parents=True, exist_ok=True)
    RESULTS.write_text(json.dumps(results, indent=2, default=str), encoding="utf-8")


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--family", default="all", help="all|h1|h2|h3|stats")
    args = ap.parse_args()
    fam = args.family.lower()

    ledger = TrialLedger(REPO)
    data = load_all(REPO)
    results: dict[str, Any] = json.loads(RESULTS.read_text()) if RESULTS.exists() else {}
    results["meta"] = {
        "mode": "M3a_in_sample_only",
        "params": {
            "n_perm": 10_000,
            "rc_boot": 2_000,
            "boot_b": 10_000,
            "cpcv": "(10,2)=45 paths",
            "pbo": "CSCV 16 splits, 1000 combos",
            "capital_usdt": 10_000.0,
            "seed": 20261027,
            "t_star": 0.025,
        },
        "updated_at_utc": datetime.now(UTC).isoformat(timespec="seconds"),
    }

    if fam in ("all", "h1"):
        results["H1"] = run_h1(REPO, ledger, data)
        _save(results)
        print("H1 listo:", results["H1"]["elapsed_s"], "s")
    if fam in ("all", "h2"):
        results["H2"] = run_h2(REPO, ledger, data)
        _save(results)
        print("H2 listo:", results["H2"]["elapsed_s"], "s")
    if fam in ("all", "h3"):
        results["H3"] = run_h3(REPO, ledger, data)
        _save(results)
        print("H3 listo:", results["H3"]["elapsed_s"], "s")
    if fam in ("all", "stats"):
        verdicts = select_and_verdict(ledger, results)
        results["selection_verdicts"] = verdicts
        _save(results)
        selected = {
            "generated_at_utc": datetime.now(UTC).isoformat(timespec="seconds"),
            "protocol": "v1.4 s7.7 (mediana CPCV; una celda por familia y activo) + s7.9 (M3a)",
            "selected_cells": {
                "H1": {a: v["selected_cell"] for a, v in verdicts["H1"]["assets"].items()},
                "H2": verdicts["H2"]["selected_cell"],
                "H3": {a: v["selected_cell"] for a, v in verdicts["H3"]["assets"].items()},
            },
            "verdicts_in_sample": {
                "H1": {
                    "family": verdicts["H1"]["family_verdict"],
                    **{a: v["verdict"] for a, v in verdicts["H1"]["assets"].items()},
                },
                "H2": verdicts["H2"]["verdict"],
                "H3": {
                    "family": verdicts["H3"]["family_verdict"],
                    **{a: v["verdict"] for a, v in verdicts["H3"]["assets"].items()},
                },
            },
        }
        SELECTED.write_text(json.dumps(selected, indent=2, sort_keys=True), encoding="utf-8")
        print(json.dumps(selected, indent=2, sort_keys=True))

    print(
        "n_trials ledger:",
        {h: ledger.n_trials(h) for h in ("H1", "H2", "H3")},
        "| total strategy:",
        ledger.n_trials(),
    )
    ledger.close()


if __name__ == "__main__":
    main()
