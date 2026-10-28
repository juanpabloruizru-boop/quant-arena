"""Telemetría descriptiva (M5 final) — hechos matemáticos del precio.

TODO lo que se compute aquí es estadística descriptiva observable de series
de precios (SMA, ATR, distancias, cotas ±k×ATR, escala aritmética sobre un
capital de referencia). NINGUNA de estas cifras es una hipótesis evaluada ni
una señal de trading (ADR-008, ratificado por el orquestador 2026-10-28):
las etiquetas del dashboard deben mantenerlo explícito.
"""

from __future__ import annotations

import math
from datetime import UTC
from typing import Any

import numpy as np
import pandas as pd

from qa.features.indicators import sma

ATR_WINDOW = 14


def atr(df: pd.DataFrame, n: int = ATR_WINDOW) -> float:
    """ATR(n) en unidades de precio (Wilder simplificado: media de TR)."""
    if len(df) < n + 1:
        return float("nan")
    h = df["high"].to_numpy(dtype=float)
    lo = df["low"].to_numpy(dtype=float)
    c = df["close"].to_numpy(dtype=float)
    pc = np.concatenate(([c[0]], c[:-1]))
    tr = np.maximum(h - lo, np.maximum(np.abs(h - pc), np.abs(lo - pc)))
    return float(tr[-n:].mean())


def _frame_stats(df: pd.DataFrame | None) -> dict[str, Any]:
    if df is None or df.empty or len(df) < 20:
        return {"disponible": False}
    close = np.asarray(df["close"].to_numpy(), dtype=float)
    last = float(close[-1])
    prev = float(close[-2])
    s50 = sma(close, 50)
    s50_last = float(s50[-1]) if not math.isnan(float(s50[-1])) else None
    a = atr(df)
    row: dict[str, Any] = {
        "disponible": True,
        "precio": last,
        "cambio_ultima_vela_pct": round((last / prev - 1.0) * 100, 2),
        "sma50": round(s50_last, 4) if s50_last else None,
        "dist_sma50_pct": round((last / s50_last - 1.0) * 100, 2) if s50_last else None,
        "lado_sma50": ("por encima" if last > s50_last else "por debajo") if s50_last else "n/d",
        "atr14": round(a, 4) if a == a else None,
        "atr14_pct": round(a / last * 100, 2) if a == a else None,
        "n_velas": int(len(df)),
    }
    return row


def watchlist_telemetry(klines: dict[str, dict[str, pd.DataFrame]]) -> dict[str, dict[str, Any]]:
    """Telemetría 4H/1D/1W por símbolo: precio, SMA50, ATR14, cambio."""
    out: dict[str, dict[str, Any]] = {}
    for sym, frames in klines.items():
        row: dict[str, Any] = {}
        for tf in ("4h", "1d", "1w"):
            row[tf] = _frame_stats(frames.get(tf))
        d1 = frames.get("1d")
        if d1 is not None and len(d1) >= 2:
            c = d1["close"].to_numpy(dtype=float)
            row["cambio_24h_pct"] = round((float(c[-1]) / float(c[-2]) - 1.0) * 100, 2)
        else:
            row["cambio_24h_pct"] = None
        out[sym] = row
    return out


def h1_levels(daily: pd.DataFrame, posicion_regla: float, capital_ref_usd: float) -> dict[str, Any]:
    """Niveles observables de la celda H1 (marco diario).

    - nivel_giro_sma50: precio donde close cruza la SMA50 (la regla congelada
      pasaría mecánicamente a FLAT por debajo / LONG por encima; es el valor
      de la media hoy, no una recomendación).
    - bandas_c-2xATR / c+3xATR: referencias puramente estadísticas de rango.
    - escala_usd: aritmética exposición × capital de referencia (informativa).
    """
    close = np.asarray(daily["close"].to_numpy(), dtype=float)
    last = float(close[-1])
    s50 = sma(close, 50)
    a = atr(daily)
    return {
        "precio": round(last, 2),
        "nivel_sma50": round(float(s50[-1]), 2) if not math.isnan(float(s50[-1])) else None,
        "distancia_a_sma50_pct": round((last / float(s50[-1]) - 1.0) * 100, 2)
        if not math.isnan(float(s50[-1]))
        else None,
        "atr14_usd": round(a, 2) if a == a else None,
        "atr14_pct": round(a / last * 100, 2) if a == a else None,
        "banda_inf_c_menos_2atr": round(last - 2 * a, 2) if a == a else None,
        "banda_sup_c_mas_3atr": round(last + 3 * a, 2) if a == a else None,
        "exposicion_regla": round(float(posicion_regla), 3),
        "escala_usd_sobre_capital_ref": round(float(posicion_regla) * capital_ref_usd, 2),
        "capital_ref_usd": capital_ref_usd,
    }


def trade_geometry(trade: dict[str, Any], price_now: float | None) -> dict[str, Any]:
    """Métricas geométricas de la operación del usuario (sus propios niveles)."""
    out: dict[str, Any] = {}
    opened = trade.get("opened_at") or trade.get("ts_utc")
    if opened:
        try:
            t0 = pd.Timestamp(opened)
            if t0.tzinfo is None:
                t0 = t0.tz_localize("UTC")
            delta = pd.Timestamp.now(UTC) - t0
            out["tiempo_abierta"] = f"{delta.days}d {delta.seconds // 3600}h"
        except (ValueError, TypeError):
            out["tiempo_abierta"] = "?"
    entry = float(trade.get("entry_price", 0.0))
    sl = trade.get("sl")
    tp = trade.get("tp")
    direction = -1.0 if trade.get("kind") == "future_short" else 1.0
    if price_now and sl and tp and entry > 0:
        d_sl0 = abs(entry - float(sl)) / entry
        d_tp0 = abs(float(tp) - entry) / entry
        d_sl = abs(price_now - float(sl)) / price_now
        d_tp = abs(float(tp) - price_now) / price_now
        out["rr_inicial_tp_sl"] = round(d_tp0 / d_sl0, 2) if d_sl0 > 0 else None
        out["rr_actual_tp_sl"] = round(d_tp / d_sl, 2) if d_sl > 0 else None
        out["dist_sl_pct"] = round(d_sl * 100 * direction, 2)
        out["dist_tp_pct"] = round(d_tp * 100 * direction, 2)
    return out
