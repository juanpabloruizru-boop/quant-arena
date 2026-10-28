"""Geometría descriptiva de riesgo/beneficio del USUARIO (M5b).

Todo aquí es aritmética sobre precios y niveles (hechos matemáticos
observables), compatible con ADR-008 (addendum B): NO se sugieren entradas,
SL ni TP; se mide la asimetría de los niveles que el propio usuario elige o
de la geometría SMA50/ATR del precio, contra el umbral de disciplina que el
propio usuario configura (`min_rr_ratio` en config/watchlist.yaml).

Convenciones de comisiones (fuente: config/costs.yaml, VERIFICADO 2026-10-27):
- spot taker 0.100 % por lado -> ida y vuelta 0.200 %;
- perp USDM taker 0.050 % por lado -> ida y vuelta 0.100 %.
"""

from __future__ import annotations

import math
from typing import Any

DEFAULT_RISK_PCTS = (0.5, 1.0, 2.0)


def fee_taker_side(kind: str, costs: dict[str, Any]) -> float:
    """Comisión taker POR LADO según el tipo de instrumento (costs.yaml)."""
    if kind == "spot":
        return float(costs["spot"]["taker_fee"])
    return float(costs["perp_usdm"]["taker_fee"])


def fee_roundtrip(kind: str, costs: dict[str, Any]) -> float:
    """Comisión estimada de ida y vuelta (2 × taker) sobre el nocional."""
    return 2.0 * fee_taker_side(kind, costs)


def rr_neto_trade(entry: float, sl: float, tp: float, fee_rt: float) -> float | None:
    """R:R Neto = (|TP − Entry| − fees) / (|Entry − SL| + fees), en precios.

    `fee_rt` es la comisión ida y vuelta en fracción del precio de entrada
    (p. ej. 0.002 spot). Devuelve None si no hay riesgo definido (SL = Entry).
    """
    risk_p = abs(entry - sl)
    if entry <= 0 or risk_p <= 0:
        return None
    fee_p = entry * fee_rt
    reward_p = abs(tp - entry)
    return (reward_p - fee_p) / (risk_p + fee_p)


def check_rr_discipline(
    entry: float,
    sl: float,
    tp: float,
    kind: str,
    costs: dict[str, Any],
    min_rr: float,
) -> dict[str, Any]:
    """Estado del filtro de disciplina R:R para los niveles del usuario."""
    fee_rt = fee_roundtrip(kind, costs)
    rr = rr_neto_trade(entry, sl, tp, fee_rt)
    if rr is None:
        return {
            "rr_neto": None,
            "cumple": None,
            "aviso": "sin SL distinto de la entrada: el filtro R:R no es evaluable",
        }
    cumple = rr >= min_rr
    aviso = (
        f"ALERTA DE DISCIPLINA: R:R Neto = {rr:.2f}x (< mínimo {min_rr:.1f}x configurado por JP)"
        if not cumple
        else f"FILTRO R:R >= {min_rr:.1f}: CUMPLE (R:R Neto {rr:.2f}x)"
    )
    return {"rr_neto": round(rr, 3), "cumple": cumple, "aviso": aviso, "fee_rt": fee_rt}


def breakeven_neto(entry: float, kind: str, costs: dict[str, Any], long: bool) -> float:
    """Precio donde el PnL neto de comisiones taker es exactamente 0.

    Long: entry × (1+f)/(1−f) · Short: entry × (1−f)/(1+f), con f = taker/lado.
    """
    f = fee_taker_side(kind, costs)
    return entry * (1.0 + f) / (1.0 - f) if long else entry * (1.0 - f) / (1.0 + f)


def tp_minimo_para_rr(
    entry: float, sl: float, kind: str, costs: dict[str, Any], long: bool, k: float
) -> float | None:
    """TP que satisface R:R Neto = k con los niveles de entrada/SL dados.

    Aritmética inversa de `rr_neto_trade` (el TP es la incógnita). No es un
    objetivo sugerido: es el valor que cumple la regla de disciplina del usuario.
    """
    risk_p = abs(entry - sl)
    if entry <= 0 or risk_p <= 0:
        return None
    fee_p = entry * fee_roundtrip(kind, costs)
    reward_p = k * (risk_p + fee_p) + fee_p
    return entry + reward_p if long else entry - reward_p


def position_calc(
    entry: float,
    sl: float,
    equity_usd: float,
    risk_pct: float,
) -> dict[str, Any] | None:
    """Escala aritmética de riesgo por operación (etiqueta: informativo).

    risk_usd = equity × risk_pct/100 · size_usd = risk_usd / |entry−sl|/entry
    (fracción de distancia al SL) · unidades = size_usd / entry.
    """
    if entry <= 0 or equity_usd <= 0:
        return None
    risk_frac = abs(entry - sl) / entry
    if risk_frac <= 0:
        return None
    risk_usd = equity_usd * risk_pct / 100.0
    size_usd = risk_usd / risk_frac
    return {
        "risk_pct": risk_pct,
        "risk_usd": round(risk_usd, 2),
        "size_usd": round(size_usd, 2),
        "unidades": round(size_usd / entry, 8),
        "size_pct_equity": round(size_usd / equity_usd * 100.0, 1),
    }


def trade_calc(
    entry: float,
    sl: float,
    tp: float,
    kind: str,
    costs: dict[str, Any],
    min_rr: float,
    equity_usd: float,
    risk_pcts: tuple[float, ...] = DEFAULT_RISK_PCTS,
) -> dict[str, Any]:
    """Calculadora aritmética completa de una configuración del usuario."""
    long = kind != "future_short"
    if tp > 0:
        disc = check_rr_discipline(entry, sl, tp, kind, costs, min_rr)
    else:
        disc = {
            "rr_neto": None,
            "cumple": None,
            "aviso": "sin TP: el filtro R:R no es evaluable",
        }
    be = breakeven_neto(entry, kind, costs, long)
    filas = [f for f in (position_calc(entry, sl, equity_usd, p) for p in risk_pcts) if f]
    return {
        "kind": kind,
        "long": long,
        "entry": entry,
        "sl": sl,
        "tp": tp,
        "equity_usd": equity_usd,
        "min_rr": min_rr,
        "rr_neto": disc["rr_neto"],
        "cumple_filtro": disc["cumple"],
        "aviso_filtro": disc.get("aviso", ""),
        "breakeven_neto": round(be, 6),
        "tp_min_2r": _r(tp_minimo_para_rr(entry, sl, kind, costs, long, 2.0)),
        "tp_min_3r": _r(tp_minimo_para_rr(entry, sl, kind, costs, long, 3.0)),
        "filas_riesgo": filas,
    }


def _r(x: float | None) -> float | None:
    return round(x, 6) if x is not None and not math.isnan(x) else None


def rr_tendencia(
    close: float,
    sma50: float | None,
    atr14: float | None,
    fee_rt: float,
    min_rr: float,
    reward_mult: float = 3.0,
    risk_mult: float = 1.0,
) -> dict[str, Any]:
    """Geometría R:R descriptiva de un activo en tendencia alcista (Close>SMA50).

    - Risk_dist  = max(Close − SMA50, risk_mult × ATR14) + fee_rt × Close
      (distancia al nivel de invalidación de tendencia + coste ida y vuelta).
    - Reward_dist = reward_mult × ATR14 − (Close − SMA50)
      (expansión estadística del marco menos lo ya recorrido desde la SMA50).
    - R:R geométrico neto = Reward_dist / Risk_dist.

    Es una regla de rango ESTADÍSTICA documentada (no una hipótesis evaluada
    ni una señal): mide la asimetría de una entrada nueva hipotética HOY.
    """
    base: dict[str, Any] = {
        "aplica": False,
        "rr": None,
        "cumple": None,
        "label": "FILTRO R:R: NO APLICA",
    }
    if sma50 is None or atr14 is None or math.isnan(atr14) or atr14 <= 0 or close <= 0:
        base["motivo"] = "datos insuficientes en el marco"
        return base
    if close <= sma50:
        base["motivo"] = "precio bajo SMA50: sin tendencia alcista en el marco"
        base["label"] = "FILTRO R:R: NO APLICA (precio bajo SMA50)"
        return base
    ext = close - sma50
    risk_dist = max(ext, risk_mult * atr14) + fee_rt * close
    reward_dist = reward_mult * atr14 - ext
    rr = reward_dist / risk_dist
    cumple = rr >= min_rr and reward_dist > 0
    if cumple:
        label = f"FILTRO R:R >= {min_rr:.1f}: CUMPLE (Asimetría {rr:.2f}x)"
    else:
        label = (
            f"FILTRO R:R >= {min_rr:.1f}: NO CUMPLE (Asimetría {rr:.2f}x < {min_rr:.1f}"
            " — Extendido)"
        )
    return {
        "aplica": True,
        "extension_desde_sma50": round(ext, 6),
        "extension_pct": round(ext / close * 100.0, 2),
        "risk_dist": round(risk_dist, 6),
        "reward_dist": round(reward_dist, 6),
        "rr": round(rr, 3),
        "cumple": cumple,
        "label": label,
        "min_rr": min_rr,
    }
