"""Estrategias pre-registradas (v1.4). Nada se ejecuta sin trial en el ledger.

Convencion temporal comun: decision al CIERRE del dia t -> posicion vigente el
dia t+1. Cero look-ahead (todas las features pasan los tests de truncamiento).
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import numpy as np
from numpy.typing import NDArray

from qa.features.indicators import realized_vol_ann, ret_L_days, sma

F64 = NDArray[np.float64]
BAND_FROZEN = 0.10  # PRERREGISTRO s4 (grado de libertad congelado)
VOL_WINDOW = 20


@dataclass(frozen=True)
class H1Cell:
    variant: str  # "sma" | "ret"
    window: int  # 50 | 100 | 200
    sigma_obj: float  # 0.15 | 0.25

    @property
    def cell_id(self) -> str:
        return f"{self.variant}{self.window}_s{int(self.sigma_obj * 100)}"

    @property
    def config(self) -> dict[str, object]:
        return {
            "family": "H1",
            "variant": self.variant,
            "window": self.window,
            "sigma_obj": self.sigma_obj,
            "band": BAND_FROZEN,
            "vol_window": VOL_WINDOW,
        }


H1_GRID: list[H1Cell] = [
    H1Cell(v, w, s) for v in ("sma", "ret") for w in (50, 100, 200) for s in (0.15, 0.25)
]
assert len(H1_GRID) == 12


def h1_desired_weights(close: NDArray[np.floating[Any]], cell: H1Cell) -> F64:
    """Peso deseado decidido al cierre de cada dia (misma longitud que close).

    senal: sma -> close[t] > SMA(window)[t]; ret -> ret_L_days[t] > 0.
    tamanno: min(1, sigma_obj / vol_realizada_20d anualizada). Warmup => flat.
    """
    c = np.asarray(close, dtype=np.float64)
    if cell.variant == "sma":
        ind = sma(c, cell.window)
        sig = np.where(np.isnan(ind), 0.0, (c > ind).astype(float))
    else:
        ind = ret_L_days(c, cell.window)
        sig = np.where(np.isnan(ind), 0.0, (ind > 0).astype(float))
    r = np.concatenate(([0.0], c[1:] / c[:-1] - 1.0))  # r[t] = retorno del dia t
    rv = realized_vol_ann(r, VOL_WINDOW)
    with np.errstate(divide="ignore", invalid="ignore"):
        scale = np.minimum(1.0, cell.sigma_obj / rv)
    scale = np.nan_to_num(scale, nan=0.0)
    return np.asarray(sig * scale, dtype=np.float64)
