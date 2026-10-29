"""Los YAML de configuracion son la rejilla pre-registrada: deben ser consistentes.

Estos tests fijan la rejilla v1.0 (H1=12, H2=6, H3=4 celdas, total 22). Si alguien
cambia una celda, el test falla a proposito: cambiar la rejilla exige nueva version
del preregistro (docs/PREREGISTRO.md) y contar +n_trials.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from qa._yaml_compat import safe_load

REPO = Path(__file__).resolve().parents[2]
CONFIG = REPO / "config"


def _load(name: str) -> dict[str, Any]:
    data = safe_load((CONFIG / name).read_text(encoding="utf-8"))
    assert isinstance(data, dict)
    return data


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


def test_watchlist_config_valid() -> None:
    w = _load("watchlist.yaml")
    assert "watchlist" in w
    assert len(w["watchlist"]) >= 5
    assert "BTCUSDT" in w["watchlist"]
    assert "filtro_rr" in w
    assert w["filtro_rr"]["min_rr_ratio"] >= 2.0
