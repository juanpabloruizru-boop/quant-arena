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

from qa.agent.geometry import rr_tendencia
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


def _frame_stats(
    df: pd.DataFrame | None,
    fee_rt: float = 0.002,
    min_rr: float = 2.0,
    reward_mult: float = 3.0,
    risk_mult: float = 1.0,
) -> dict[str, Any]:
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
    # Geometría R:R descriptiva (filtro de disciplina del usuario, M5b):
    # solo aplica con precio por encima de la SMA50 del marco.
    row["rr_geom"] = rr_tendencia(
        last,
        s50_last,
        float(a) if a == a else None,
        fee_rt=fee_rt,
        min_rr=min_rr,
        reward_mult=reward_mult,
        risk_mult=risk_mult,
    )
    return row


def watchlist_telemetry(
    klines: dict[str, dict[str, pd.DataFrame]],
    fee_rt: float = 0.002,
    min_rr: float = 2.0,
    reward_mult: float = 3.0,
    risk_mult: float = 1.0,
) -> dict[str, dict[str, Any]]:
    """Telemetría 4H/1D/1W por símbolo: precio, SMA50, ATR14, cambio, R:R geom."""
    out: dict[str, dict[str, Any]] = {}
    for sym, frames in klines.items():
        row: dict[str, Any] = {}
        for tf in ("4h", "1d", "1w"):
            row[tf] = _frame_stats(frames.get(tf), fee_rt, min_rr, reward_mult, risk_mult)
        d1 = frames.get("1d")
        if d1 is not None and len(d1) >= 2:
            c = d1["close"].to_numpy(dtype=float)
            row["cambio_24h_pct"] = round((float(c[-1]) / float(c[-2]) - 1.0) * 100, 2)
        else:
            row["cambio_24h_pct"] = None
        out[sym] = row
    return out


def h1_levels(
    daily: pd.DataFrame,
    posicion_regla: float,
    capital_base_usd: float,
    fee_rt_spot: float = 0.002,
    min_rr: float = 2.0,
    reward_mult: float = 3.0,
    risk_mult: float = 1.0,
    capital_base_origen: str = "config capital_ref_usd",
) -> dict[str, Any]:
    """Niveles observables de la celda H1 (marco diario).

    - nivel_giro_sma50: precio donde close cruza la SMA50 (la regla congelada
      pasaría mecánicamente a FLAT por debajo / LONG por encima; es el valor
      de la media hoy, no una recomendación).
    - bandas_c-2xATR / c+3xATR: referencias puramente estadísticas de rango.
    - escala_usd: aritmética exposición × capital de referencia (informativa).
    - rr_filtro (M5b): geometría R:R descriptiva de una entrada nueva HOY
      contra la disciplina min_rr del usuario. Si NO CUMPLE, la escala
      teórica se muestra BLOQUEADA ($0) en el dashboard: es el filtro de
      asimetría que el propio usuario configuró, no un juicio del sistema.
    """
    close = np.asarray(daily["close"].to_numpy(), dtype=float)
    last = float(close[-1])
    s50 = sma(close, 50)
    a = atr(daily)
    s50_last = float(s50[-1]) if not math.isnan(float(s50[-1])) else None
    atr_val = float(a) if a == a else None
    rr_f = rr_tendencia(last, s50_last, atr_val, fee_rt_spot, min_rr, reward_mult, risk_mult)
    bloqueada = bool(rr_f.get("aplica") and rr_f.get("cumple") is False)
    return {
        "precio": round(last, 2),
        "nivel_sma50": round(s50_last, 2) if s50_last else None,
        "distancia_a_sma50_pct": round((last / s50_last - 1.0) * 100, 2) if s50_last else None,
        "atr14_usd": round(a, 2) if a == a else None,
        "atr14_pct": round(a / last * 100, 2) if a == a else None,
        "banda_inf_c_menos_2atr": round(last - 2 * a, 2) if a == a else None,
        "banda_sup_c_mas_3atr": round(last + 3 * a, 2) if a == a else None,
        "exposicion_regla": round(float(posicion_regla), 3),
        "escala_usd_sobre_capital_ref": round(float(posicion_regla) * capital_base_usd, 2),
        "capital_ref_usd": capital_base_usd,
        "capital_base_origen": capital_base_origen,
        "rr_filtro": rr_f,
        "escala_bloqueada_por_rr": bloqueada,
    }


def trade_geometry(
    trade: dict[str, Any],
    price_now: float | None,
    atr_marco: float | None = None,
    fee_taker_lado: float | None = None,
) -> dict[str, Any]:
    """Métricas geométricas de la operación del usuario (sus propios niveles).

    M5b añade (si se pasan ATR del marco del trade y comisión taker por lado):
    - break-even neto: precio donde el PnL tras comisiones taker ida y vuelta
      es exactamente 0, y si el precio actual ya lo superó;
    - cota descriptiva 2×ATR: precio actual ∓ 2×ATR(14) del marco del trade
      (referencia estadística de rango, NO un stop sugerido).
    """
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
    if entry > 0 and fee_taker_lado is not None:
        f = float(fee_taker_lado)
        be = entry * (1.0 + f) / (1.0 - f) if direction > 0 else entry * (1.0 - f) / (1.0 + f)
        out["breakeven_neto"] = round(be, 6)
        if price_now:
            supero = price_now >= be if direction > 0 else price_now <= be
            out["supero_breakeven"] = supero
            out["breakeven_txt"] = (
                "precio por ENCIMA del break-even neto"
                if supero
                else "precio por DEBAJO del break-even neto"
            )
    if price_now and atr_marco is not None and atr_marco == atr_marco:
        cota = (
            price_now - 2.0 * float(atr_marco)
            if direction > 0
            else price_now + 2.0 * float(atr_marco)
        )
        out["cota_2atr"] = round(cota, 6)
        out["atr_marco_usado"] = round(float(atr_marco), 6)
    return out
