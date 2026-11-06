"""Estados DESCRIPTIVOS de las 5 celdas congeladas (m3a-freeze) con datos vivos.

Este modulo NO inventa senales nuevas: reproduce las reglas ya investigadas
(H1 sma50_s25 diario, H2 L26_N10 semanal, H3 w30_t5 diario) sobre las ultimas
velas publicas y devuelve su ESTADO (posicion/cesta/funding-MA), junto con la
etiqueta de veredicto que corresponde por preregistro. No genera ordenes, ni
niveles SL/TP, ni tamannos de posicion (ver ADR-008: eso exigiria v1.5).

Marcos NO validados (4h, semanal tactico, otros activos) quedan fuera: la
watchlist solo alimenta vigilancia de riesgos (news.py).
"""

from __future__ import annotations

import math
from typing import Any

import numpy as np

try:
    import pandas as pd
except ImportError:
    import qa._pandas_compat as pd

from qa.features.indicators import (
    daily_funding_from_events,
    formation_return_weekly,
    funding_ma_annualized,
    realized_vol_ann,
    sma,
)

BAND = 0.10
VERDICT_LABELS = {
    "H1": ("SIN VENTAJA DEMOSTRADA (INCONTRASTABLE)", "holdout coherente en signo, descriptivo"),
    "H2": (
        "SIN VENTAJA DEMOSTRADA (INCONTRASTABLE)",
        "relativo vs universo EW; n=1 ano no concluye",
    ),
    "H3_BTCUSDT": (
        "VALIDADA (PASA in-sample + holdout signo)",
        "a nivel de signo; con costes x2 el edge es ~0",
    ),
    "H3_ETHUSDT": ("NO PASA (holdout)", "costes de cruces superaron al funding en 2025-26"),
}


def band_positions(target: np.ndarray, band: float = BAND) -> np.ndarray:
    """Logica de banda congelada (PRERREGISTRO s4): flips siempre operan."""
    n = target.shape[0]
    pos = np.zeros(n)
    last = 0.0
    for t in range(n):
        tgt = float(target[t])
        flip = (tgt > 0.0) != (last > 0.0)
        if flip or abs(tgt - last) >= band:
            last = tgt
        pos[t] = last
    return pos


def h1_state(daily: pd.DataFrame, sigma_obj: float = 0.25, window: int = 50) -> dict[str, Any]:
    """Estado de H1 sma50_s25 (diario, velas CERRADAS)."""
    close = np.asarray(daily["close"].to_numpy(), dtype=np.float64)
    r = np.concatenate(([0.0], close[1:] / close[:-1] - 1.0))
    ind = sma(close, window)
    sig = np.where(np.isnan(ind), 0.0, (close > ind).astype(float))
    rv = realized_vol_ann(r, 20)
    with np.errstate(divide="ignore", invalid="ignore"):
        scale = np.minimum(1.0, sigma_obj / rv)
    scale = np.nan_to_num(scale, nan=0.0)
    desired = sig * scale
    pos = band_positions(desired)
    last_close = float(close[-1])
    last_sma = float(ind[-1]) if not math.isnan(float(ind[-1])) else None
    estado = "LONG" if pos[-1] > 0 else "FLAT"
    return {
        "veredicto": VERDICT_LABELS["H1"][0],
        "nota": VERDICT_LABELS["H1"][1],
        "estado": estado,
        "posicion_regla": round(float(pos[-1]), 3),
        "objetivo_actual": round(float(desired[-1]), 3),
        "close": last_close,
        "sma50": last_sma,
        "close_vs_sma50_pct": round((last_close / last_sma - 1.0) * 100, 2) if last_sma else None,
        "vol_realizada_20d_ann": round(float(rv[-1]), 4) if not math.isnan(float(rv[-1])) else None,
        "last_candle_utc": str(daily["open_time"].iloc[-1]),
    }


def btc_macro_regime(btc_daily: pd.DataFrame, window: int = 200) -> dict[str, Any]:
    """Evalúa el Régimen Macro de Bitcoin (Close_BTC_1D vs SMA200_1D).

    Si Close < SMA200: 'BAJISTA_INVIERNO' -> Veto total a compras (LONGs) en altcoins.
    Si Close >= SMA200: 'ALCISTA_EXPANSIVO' -> Compras en altcoins habilitadas.
    """
    close = np.asarray(btc_daily["close"].to_numpy(), dtype=np.float64)
    if len(close) < window:
        sma_val = float(np.mean(close))
    else:
        sma_arr = sma(close, window)
        sma_val = float(sma_arr[-1])

    last_close = float(close[-1])
    is_bull = last_close >= sma_val
    regimen = "ALCISTA_EXPANSIVO" if is_bull else "BAJISTA_INVIERNO"
    dist_pct = round((last_close / sma_val - 1.0) * 100.0, 2) if sma_val > 0 else 0.0

    return {
        "regimen": regimen,
        "is_bullish": is_bull,
        "veto_altcoin_longs": not is_bull,
        "close_btc": last_close,
        "sma200_btc": round(sma_val, 2),
        "dist_sma200_pct": dist_pct,
        "nota": (
            "RÉGIMEN ALCISTA: LONGs agresivos habilitados"
            if is_bull
            else "INVIERNO CRIPTO: Prohibido comprar altcoins. Solo SHORTs o 100% Cash"
        ),
    }


def h2_state(members: list[str], klines_daily: dict[str, pd.DataFrame]) -> dict[str, Any]:
    """Cesta teorica HOY de L26_N10 (formacion 26 semanas saltando la ultima)."""
    closes: dict[str, pd.Series] = {}
    for sym, df in klines_daily.items():
        if df is None or df.empty:
            continue
        d = df.copy()
        open_col = d["open_time"]
        if hasattr(open_col.dt, "tz") and open_col.dt.tz is not None:
            open_col = open_col.dt.tz_localize(None)
        d["week"] = open_col.dt.to_period("W-SUN").dt.start_time
        wk = d.groupby("week")["close"].last()
        closes[sym] = wk
    panel = pd.DataFrame(closes)
    L = 26
    form = pd.DataFrame(
        {s: formation_return_weekly(panel[s].to_numpy(), L) for s in panel.columns},
        index=panel.index,
    )
    last = form.iloc[-1] if len(form) else pd.Series(dtype=float)
    elig = [(s, float(v)) for s, v in last.items() if np.isfinite(v)]
    elig.sort(key=lambda x: -x[1])
    n_sel = max(1, math.ceil(len(elig) / 3)) if elig else 0
    basket = [s for s, _ in elig[:n_sel]]
    return {
        "veredicto": VERDICT_LABELS["H2"][0],
        "nota": VERDICT_LABELS["H2"][1],
        "universo_top10_actual": members,
        "formacion_26w": {s: round(v, 4) for s, v in elig},
        "cesta_teoretica": basket,
        "n_eligibles": len(elig),
    }


def h3_state(
    funding: pd.DataFrame, window_days: int = 30, threshold: float = 0.05
) -> dict[str, Any]:
    """Estado del carry w30_t5: MA anualizada del funding vs umbral."""
    fd = daily_funding_from_events(funding)
    fma30 = funding_ma_annualized(fd, window_days)
    fma7 = funding_ma_annualized(fd, 7)
    last30 = float(fma30.iloc[-1]) if len(fma30) and not math.isnan(float(fma30.iloc[-1])) else None
    last7 = float(fma7.iloc[-1]) if len(fma7) and not math.isnan(float(fma7.iloc[-1])) else None
    activa = bool(last30 is not None and last30 > threshold)
    return {
        "funding_ma30_ann": round(last30, 5) if last30 is not None else None,
        "funding_ma7_ann": round(last7, 5) if last7 is not None else None,
        "umbral": threshold,
        "senal_activa": activa,
        "estado": "ACTIVA (MA30 > 5% anual)" if activa else "INACTIVA (MA30 <= 5% anual)",
    }


def compute_states(live: dict[str, Any], pit_members_top10: list[str]) -> dict[str, Any]:
    """Estados de las 5 celdas congeladas a partir de la ingesta viva."""
    kl = live["klines"]
    states: dict[str, Any] = {"fetched_at_utc": live["fetched_at_utc"], "cells": {}}
    for asset in ("BTCUSDT", "ETHUSDT"):
        d1 = kl.get(asset, {}).get("1d")
        if d1 is None or d1.empty:
            continue
        states["cells"][f"H1_{asset}"] = h1_state(d1)
        f = live["funding"].get(asset)
        if f is not None and not f.empty:
            st = h3_state(f.rename(columns={"funding_time": "funding_time"}))
            st["veredicto"] = VERDICT_LABELS[f"H3_{asset}"][0]
            st["nota"] = VERDICT_LABELS[f"H3_{asset}"][1]
            prem = live["premium"].get(asset, {})
            st["last_funding_rate"] = prem.get("last_funding_rate")
            st["next_funding_utc"] = prem.get("next_funding_utc")
            states["cells"][f"H3_{asset}"] = st
    # H2: necesita diarias de los miembros top-10 actuales
    member_kl = {
        s: kl[s]["1d"] for s in pit_members_top10 if s in kl and kl[s].get("1d") is not None
    }
    if member_kl:
        states["cells"]["H2_L26_N10"] = h2_state(pit_members_top10, member_kl)
    return states
