"""Los YAML de configuracion son la rejilla pre-registrada: deben ser consistentes.

Estos tests fijan la rejilla v1.0 (H1=12, H2=6, H3=4 celdas, total 22). Si alguien
cambia una celda, el test falla a proposito: cambiar la rejilla exige nueva version
del preregistro (docs/PREREGISTRO.md) y contar +n_trials.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import yaml

REPO = Path(__file__).resolve().parents[2]
CONFIG = REPO / "config"


def _load(name: str) -> dict[str, Any]:
    data = yaml.safe_load((CONFIG / name).read_text(encoding="utf-8"))
    assert isinstance(data, dict)
    return data


def test_hypotheses_grid_v1() -> None:
    h = _load("hypotheses.yaml")
    assert h["version"] == "1.0"
    cells = h["accounting"]["preregistered_cells"]
    assert cells == {"H1": 24, "H2": 6, "H3": 8, "total": 38}
    assert h["accounting"]["grid_cells_raw"] == {"H1": 12, "H2": 6, "H3": 4}

    h1 = h["hypotheses"]["H1"]
    n1 = (
        len(h1["grid"]["signal_variant"])
        * len(h1["grid"]["window"])
        * len(h1["grid"]["sigma_obj_annual"])
    )
    assert n1 == h["accounting"]["grid_cells_raw"]["H1"]
    assert n1 * len(h1["evaluated_assets"]) == cells["H1"]

    h2 = h["hypotheses"]["H2"]
    n2 = len(h2["grid"]["L_weeks"]) * len(h2["grid"]["N"])
    assert n2 == cells["H2"]  # H2: el universo es uno, no multiplica por activo

    h3 = h["hypotheses"]["H3"]
    n3 = len(h3["grid"]["window_days"]) * len(h3["grid"]["threshold_annual"])
    assert n3 == h["accounting"]["grid_cells_raw"]["H3"]
    assert n3 * len(h3["evaluated_assets"]) == cells["H3"]

    sc = h["success_criteria"]
    assert sc["dsr_min"] == 0.95
    assert sc["pbo_max"] == 0.20
    assert sc["cost_stress_multiplier"] == 2.0
    assert sc["min_fraction_folds_positive"] == 0.60
    assert h["holdout"]["sealed"] is True


def test_costs_have_status_and_provenance() -> None:
    c = _load("costs.yaml")
    assert c["spot"]["status"] == "VERIFICADO"
    assert "source" in c["spot"] and "2026-10-26" in c["spot"]["source"]
    assert c["perp_usdm"]["status"] == "VERIFICADO"
    assert c["perp_usdm"]["funding"] == "REAL"
    assert c["slippage"]["status"] == "ASUNCION"
    assert c["stress"]["cost_multiplier"] == 2.0
    assert c["spot"]["taker_fee"] == 0.001
    assert c["perp_usdm"]["taker_fee"] == 0.0005


def test_universe_is_point_in_time() -> None:
    u = _load("universe.yaml")
    assert u["pit_universe"]["point_in_time"] is True
    assert u["pit_universe"]["sizes"] == [10, 20]
    assert u["pit_universe"]["include_delisted"] is True
    assert u["quote_asset"] == "USDT"
    assert len(u["known_biases"]) >= 3
