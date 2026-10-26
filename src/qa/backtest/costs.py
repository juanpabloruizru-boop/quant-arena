"""Modelo de costes parametrizado por config/costs.yaml (M2).

- Fees por lado (taker, verificados en vivo 2026-10-26; sin descuentos).
- Slippage por tramos de participacion sobre el volumen quote del dia de
  ejecucion; por encima del ultimo tramo => trade RECHAZADO (se registra).
- Minimos de exchange (minNotional / minQty): ordenes por debajo => RECHAZADAS.
- ``stressed()``: fees y slippage x2 (stress obligatorio de todo veredicto).
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

import yaml


@dataclass(frozen=True)
class CostModel:
    spot_taker_fee: float
    perp_taker_fee: float
    slippage_tiers: tuple[tuple[float, float], ...]  # (max_participation, bps)
    max_participation: float
    min_notional_usdt: float
    stress_multiplier: float = 1.0

    @classmethod
    def from_yaml(cls, path: Path, stress: bool = False) -> CostModel:
        cfg: dict[str, Any] = yaml.safe_load(path.read_text(encoding="utf-8"))
        tiers = tuple(
            (float(t["max_participation"]), float(t["bps"])) for t in cfg["slippage"]["tiers"]
        )
        mult = float(cfg["stress"]["cost_multiplier"]) if stress else 1.0
        return cls(
            spot_taker_fee=float(cfg["spot"]["taker_fee"]) * mult,
            perp_taker_fee=float(cfg["perp_usdm"]["taker_fee"]) * mult,
            slippage_tiers=tuple((mp, bps * mult) for mp, bps in tiers),
            max_participation=max(mp for mp, _ in tiers),
            min_notional_usdt=float(cfg["spot"]["min_notional_usdt"]["default"]),
            stress_multiplier=mult,
        )

    def slippage_bps(self, participation: float) -> float | None:
        """bps de slippage para una participacion dada; None => trade inviable."""
        for max_part, bps in self.slippage_tiers:
            if participation <= max_part:
                return bps
        return None

    def side_cost_rate(self, participation: float, perp: bool = False) -> float | None:
        """Coste total de UN lado (fee+slippage) como fraccion; None => rechazo."""
        slip = self.slippage_bps(participation)
        if slip is None:
            return None
        fee = self.perp_taker_fee if perp else self.spot_taker_fee
        return fee + slip / 10_000.0
