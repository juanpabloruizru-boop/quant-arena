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
    assert h["version"] == "1.4"
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

    sc0 = h["success_criteria"]
    assert sc0["dsr_n_trials_scope"] == "family"
    assert sc0["dsr_sd_trials_source"] == "ledger"
    sel = sc0["selection_rule"]
    assert sel["scope"] == "per_family_per_asset"
    assert sel["statistic"] == "cpcv_median"
    assert set(sel["metric_by_family"]) == {"H1", "H2", "H3"}
    proto = sc0["m3_protocol"]
    assert proto["m3a"]["n_permutations"] == 10000
    assert proto["m3a"]["rc_bootstrap_B"] == 2000
    assert proto["m3b"]["scope"] == "holdout_unico"
    assert "expected_verdict_predeclared" in h["hypotheses"]["H1"]
    sc = h["success_criteria"]
    assert sc["dsr_min"] == 0.95
    assert sc["pbo_max"] == 0.20
    assert sc["cost_stress_multiplier"] == 2.0
    assert sc["min_fraction_folds_positive"] == 0.60
    assert h["holdout"]["sealed"] is True
    # v1.1 (condiciones del gate M0)
    assert sc["dsr_gating_for"] == ["H2", "H3"]
    b1 = h1["benchmark_primary"]
    assert b1["kind"] == "vol_matched_bh"  # v1.2: exposure-matched era sesgado (Jensen)
    assert "exposure_matched_bh" in b1["diagnostics"]
    assert "verdict_policy_power" in h1
    pn = h1["permutation_null"]
    assert pn["n_permutations"] == 10000
    assert pn["block_days"] == 20
    assert pn["critical_level_t_star"] == 0.025
    assert pn["decision_statistic"] == "p_valor_permutado"
    hy = h2["data_hygiene"]
    assert hy["policy"] == "mark_only"
    assert hy["adjudication_table"] == "config/adjudications.csv"
    assert hy["delisting_convention"] == "last_observed_price"
    assert h1["rebalance_band"] == 0.10
    assert set(h1["co_metrics"]) == {"ulcer_index", "calmar", "time_underwater"}
    assert len(h1["subperiods_utc"]) == 3
    assert h1["primary_metric"] == "max_drawdown_reduction_vs_matched_exposure_bh"
    assert h1["evaluated_assets"] == ["BTCUSDT", "ETHUSDT"]
    assert "per_asset_mde_rule" in h3


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
    # higiene v1.3 (gate M1): guard solo MARCA; adjudicacion con evidencia
    dh = u["data_hygiene"]
    assert dh["guard_abs_log_return"] == 5.0
    assert dh["policy"] == "mark_only"
    assert dh["imputation"] == "never"
    assert dh["delisting_convention"] == "last_observed_price"
    assert dh["corporate_action_exclusion_days"] == 30
    assert dh["adjudication_table"] == "config/adjudications.csv"
    ea = u["exclusions_audit"]
    assert ea["leaked_into_ingest"] == 0
    assert ea["eligible"] == 702
