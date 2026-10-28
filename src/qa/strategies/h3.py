"""H3 — Carry spot-perp delta-neutral (rejilla v1.4).

Senal: media movil de `window` dias del funding diario anualizado (x365) por
encima de `threshold`. Decision al cierre del dia d -> posicion activa desde
las 00:00 UTC de d+1 hasta las 00:00 del primer dia inactivo (convencion
estricta de funding del motor: entry_ts < fundingTime < exit_ts).
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import pandas as pd
from numpy.typing import NDArray

from qa.features.indicators import carry_signal, daily_funding_from_events, funding_ma_annualized


@dataclass(frozen=True)
class H3Cell:
    window_days: int  # 7 | 30
    threshold_ann: float  # 0.05 | 0.10

    @property
    def cell_id(self) -> str:
        return f"w{self.window_days}_t{int(self.threshold_ann * 100)}"

    @property
    def config(self) -> dict[str, object]:
        return {
            "family": "H3",
            "window_days": self.window_days,
            "threshold_ann": self.threshold_ann,
        }


H3_GRID: list[H3Cell] = [H3Cell(w, t) for w in (7, 30) for t in (0.05, 0.10)]
assert len(H3_GRID) == 4


def h3_signal(
    days: pd.DatetimeIndex, funding: pd.DataFrame, cell: H3Cell
) -> tuple[NDArray[np.bool_], NDArray[np.float64]]:
    """(signal_active decidido al cierre de cada dia, funding_ma anualizada)."""
    fd = daily_funding_from_events(funding).reindex(days.floor("D")).fillna(0.0)
    fma = funding_ma_annualized(fd, cell.window_days)
    sig = carry_signal(fma, cell.threshold_ann)
    return np.asarray(sig, dtype=bool), np.asarray(fma.to_numpy(), dtype=np.float64)
