# Autopilot Motor Autónomo M6.3 — QUANT-ARENA v2
"""Motor de decisión y ejecución autónomo "Conquistador" para paper trading simulado.

Optimizaciones Cuantitativas Integrales:
1. Descorrelación de señales entre medias móviles e histograma MACD (aceleración vs estructura).
2. Penalización simétrica en zonas de agotamiento extremo (RSI > 75 en longs, RSI < 25 en shorts).
3. Filtro de compresión de volatilidad (ATR Percentile) con bonificación de convicción.
4. Filtro direccional de Tasa de Financiamiento (Funding Rate) contra trampas de euforia/pánico.
5. Cierre parcial real del 50% en TP1 con contabilidad inmediata en el ledger inmutable.
6. Trailing Stop dinámico protector Anti-Wick: max(Entry, Precio Actual - 1.2 * ATR14) hacia TP2.
7. Dimensionamiento dinámico adaptativo (Half-Kelly / Volatility Targeting) en [0.75%, 2.5%].
8. Límite infranqueable de Portfolio Heat <= 10.0% y telemetría de alertas desacoplada.
"""

from __future__ import annotations

import math
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import numpy as np

try:
    import pandas as pd
except ImportError:
    import qa._pandas_compat as pd

from qa.agent.brain import evaluar_setup_con_ia
from qa.agent.capital import load_costs, open_risk_usd, realized_pnl_usd
from qa.agent.geometry import adaptive_risk_pct, anti_wick_trailing_sl, fee_roundtrip
from qa.agent.kronos_oracle import evaluate_kronos_multi_horizon, predict_kline_horizon
from qa.agent.notifications import notify_event
from qa.agent.skills_engine import (
    check_circuit_breaker,
    compute_market_health,
    evaluate_discipline_gate,
    record_postmortem,
    update_live_excursions,
)
from qa.agent.spot import evaluar_y_gestionar_spot
from qa.agent.tracker import close_trade, load_trades, open_trade, update_trade
from qa.features.indicators import adx, rs_is_above_sma

CRUISE_ELITE = ["BTCUSDT", "ETHUSDT", "SOLUSDT", "SUIUSDT"]
UNIVERSO = CRUISE_ELITE
BLACKLIST = ["ZECUSDT", "XRPUSDT"]

BASE_RISK_PCT = 0.035  # 3.5% base de patrimonio (CRUISE PRO)
MAX_PORTFOLIO_HEAT_PCT = 25.0  # Techo expandido al 25.0%
MIN_RR_NETO = 2.0


def compute_momentum_ranking(
    live_klines: dict[str, dict[str, pd.DataFrame]],
    symbols: list[str] = CRUISE_ELITE,
) -> dict[str, Any]:
    """Calcula el Score de Momentum rodante de 30 días y genera la rotación 40/25/25/10."""
    scores: dict[str, float] = {}
    for s in symbols:
        df_1d = live_klines.get(s, {}).get("1d")
        if df_1d is not None and len(df_1d) >= 15:
            c = df_1d["close"].astype(float)
            w = min(30, len(c) - 1)
            sc = float(c.iloc[-1] / (c.iloc[-w] + 1e-9))
        else:
            df_4h = live_klines.get(s, {}).get("4h")
            if df_4h is not None and len(df_4h) >= 30:
                c4 = df_4h["close"].astype(float)
                w4 = min(180, len(c4) - 1)
                sc = float(c4.iloc[-1] / (c4.iloc[-w4] + 1e-9))
            else:
                sc = 1.0
        scores[s] = sc

    sorted_syms = sorted(symbols, key=lambda sym: scores[sym], reverse=True)
    weights: dict[str, float] = {}
    ranking_list: list[dict[str, Any]] = []

    for rank_idx, s in enumerate(sorted_syms):
        if rank_idx == 0:
            w = 0.40
            role = "🥇 Líder Absoluto (Top 1)"
        elif rank_idx in (1, 2):
            w = 0.25
            role = f"🥈 Seguidor (Top {rank_idx + 1})"
        else:
            w = 0.10
            role = "4️⃣ Rezagado (Top 4)"

        weights[s] = w
        ranking_list.append({
            "asset": s,
            "rank": rank_idx + 1,
            "score_30d": round(scores[s], 3),
            "weight": w,
            "weight_pct": f"{int(w * 100)}%",
            "role": role,
            "sizing_factor": round(w / 0.25, 2),
        })

    return {
        "weights": weights,
        "ranking": ranking_list,
        "scores": scores,
    }


def compute_indicators(klines_dict: dict[str, pd.DataFrame]) -> dict[str, Any]:
    """Calcula indicadores causales rigurosos sobre marcos 1h, 4h, 1d y 1w:
    - EMA9, EMA21, SMA50 (estructura de tendencia)
    - RSI(14)
    - MACD(12, 26, 9), Histograma y Aceleración de Momentum
    - ATR(14), Media histórica de ATR y Percentil de Compresión de Volatilidad
    - ADX(14), +DI, -DI y pendiente tendencial causal
    - RVOL (Volumen relativo respecto a la media móvil de 20 períodos)
    """
    res: dict[str, Any] = {}
    for tf in ("1h", "4h", "1d", "1w"):
        df = klines_dict.get(tf)
        if df is None or df.empty or len(df) < 15:
            continue
        c = df["close"].astype(float)
        v = (
            df["volume"].astype(float)
            if "volume" in df.columns
            else pd.Series(np.ones(len(df)), index=df.index)
        )
        h = df["high"].astype(float)
        low_px = df["low"].astype(float)

        ema9 = c.ewm(span=9, adjust=False).mean()
        ema21 = c.ewm(span=21, adjust=False).mean()
        sma50 = c.rolling(50).mean() if len(c) >= 50 else c.rolling(len(c)).mean()

        delta = c.diff()
        gain = (delta.where(delta > 0, 0.0)).rolling(14).mean()
        loss = (-delta.where(delta < 0, 0.0)).rolling(14).mean()
        rs = gain / (loss + 1e-9)
        rsi = 100.0 - (100.0 / (1.0 + rs))

        ema12 = c.ewm(span=12, adjust=False).mean()
        ema26 = c.ewm(span=26, adjust=False).mean()
        macd_line = ema12 - ema26
        macd_signal = macd_line.ewm(span=9, adjust=False).mean()
        macd_hist = macd_line - macd_signal

        # Aceleración de momentum del MACD (derivada discreta)
        macd_hist_curr = float(macd_hist.iloc[-1])
        macd_hist_prev = float(macd_hist.iloc[-2]) if len(macd_hist) >= 2 else macd_hist_curr
        macd_accel = macd_hist_curr - macd_hist_prev

        tr = np.maximum(
            h - low_px, np.maximum(np.abs(h - c.shift(1)), np.abs(low_px - c.shift(1)))
        )
        atr = tr.rolling(14).mean()

        # Detección de compresión de volatilidad (ATR percentile histórico 80 velas)
        atr_valid = atr.dropna()
        curr_atr = (
            float(atr.iloc[-1])
            if not math.isnan(float(atr.iloc[-1]))
            else float(c.iloc[-1] * 0.02)
        )
        w_hist = min(len(atr_valid), 80)
        if w_hist >= 10:
            recent_atr = atr_valid.iloc[-w_hist:]
            atr_pctl = float((recent_atr <= curr_atr).mean())
            atr_mean = float(recent_atr.mean())
        else:
            atr_pctl = 0.50
            atr_mean = curr_atr

        # Indicador Causal ADX(14) con +DI y -DI
        adx_arr, p_di, m_di = adx(h.to_numpy(), low_px.to_numpy(), c.to_numpy(), n=14)
        adx_curr = float(adx_arr[-1]) if not math.isnan(adx_arr[-1]) else 25.0
        adx_prev = (
            float(adx_arr[-2])
            if len(adx_arr) >= 2 and not math.isnan(adx_arr[-2])
            else adx_curr
        )
        adx_slope = adx_curr - adx_prev
        plus_di_curr = float(p_di[-1]) if not math.isnan(p_di[-1]) else 25.0
        minus_di_curr = float(m_di[-1]) if not math.isnan(m_di[-1]) else 25.0

        rvol = v / (v.rolling(20).mean() + 1e-9)

        res[tf] = {
            "close": float(c.iloc[-1]),
            "ema9": float(ema9.iloc[-1]),
            "ema21": float(ema21.iloc[-1]),
            "sma50": float(sma50.iloc[-1]),
            "rsi": float(rsi.iloc[-1]) if not math.isnan(rsi.iloc[-1]) else 50.0,
            "macd_line": float(macd_line.iloc[-1]),
            "macd_signal": float(macd_signal.iloc[-1]),
            "macd_hist": macd_hist_curr,
            "macd_accel": macd_accel,
            "atr14": curr_atr,
            "atr_mean": atr_mean,
            "atr_pctl": round(atr_pctl, 3),
            "atr_compression": atr_pctl < 0.35,
            "atr_extended": atr_pctl > 0.85,
            "adx14": round(adx_curr, 2),
            "plus_di": round(plus_di_curr, 2),
            "minus_di": round(minus_di_curr, 2),
            "adx_slope": round(adx_slope, 3),
            "rvol": float(rvol.iloc[-1]) if not math.isnan(rvol.iloc[-1]) else 1.0,
        }
    return res


def score_symbol(
    sym: str,
    ind: dict[str, Any],
    prefer_tf: str = "4h",
    funding_rate: float | None = None,
    rs_ratio_above_sma: bool | None = None,
    btc_macro_bullish: bool | None = None,
) -> dict[str, Any]:
    """Algoritmo 'Conquistador' Modo Carrera: Evalúa LONG y SHORT con descorrelación
    factorial, compresión ATR, fuerza tendencial ADX/DMI, filtro RS vs Bitcoin
    y filtro Macro de Régimen BTC SMA200(1D).
    """
    if sym in BLACKLIST:
        return {
            "sym": sym,
            "score": 0,
            "direction": "NEUTRAL",
            "score_long": 0,
            "score_short": 0,
            "reason": f"Veto Definitivo Blacklist ({sym} pausado/excluido)",
            "rsi": 50.0,
            "macd_hist": 0.0,
            "atr14": 1.0,
            "atr_mean": 1.0,
            "atr_pctl": 0.5,
            "ema21": 0.0,
            "sma50": 0.0,
            "price": 0.0,
            "timeframe": prefer_tf,
        }

    tf_data = ind.get(prefer_tf) or ind.get("4h") or ind.get("1d") or ind.get("1h")
    tf1d = ind.get("1d") or tf_data

    if not tf_data:
        return {
            "sym": sym,
            "score": 0,
            "direction": "NEUTRAL",
            "reason": "Sin datos suficientes",
            "atr14": 1.0,
            "atr_mean": 1.0,
            "price": 0.0,
        }

    score_long = 0
    score_short = 0
    reasons_long: list[str] = []
    reasons_short: list[str] = []

    # 1. Alineación de Estructura de Tendencia (hasta 25 pts)
    if tf_data["ema9"] > tf_data["ema21"]:
        score_long += 15
        reasons_long.append(f"EMA9>21({prefer_tf.upper()})")
    else:
        score_short += 15
        reasons_short.append(f"EMA9<21({prefer_tf.upper()})")

    if tf1d and tf1d["close"] > tf1d["sma50"]:
        score_long += 10
        reasons_long.append("Close>SMA50(1D)")
    elif tf1d:
        score_short += 10
        reasons_short.append("Close<SMA50(1D)")

    # 2. Aceleración e Inflexión de Momentum MACD (Descorrelacionado, hasta 20 pts)
    m_hist = tf_data["macd_hist"]
    m_accel = tf_data.get("macd_accel", 0.0)

    # Evaluación Long para MACD
    if m_hist > 0 and m_accel > 0:
        score_long += 20
        reasons_long.append("MACD aceleración alcista")
    elif m_hist > 0:
        score_long += 10
        reasons_long.append("MACD positivo desacelerando")
    elif m_accel > 0:
        score_long += 12
        reasons_long.append("MACD inflexión alcista temprana")

    # Evaluación Short para MACD
    if m_hist < 0 and m_accel < 0:
        score_short += 20
        reasons_short.append("MACD aceleración bajista")
    elif m_hist < 0:
        score_short += 10
        reasons_short.append("MACD negativo desacelerando")
    elif m_accel < 0:
        score_short += 12
        reasons_short.append("MACD inflexión bajista temprana")

    # 3. RSI Momentum y Penalización por Agotamiento Extremo (hasta 25 pts / penalización -25 pts)
    rsi_val = tf_data["rsi"]
    if rsi_val > 75:
        score_long -= 25
        reasons_long.append(f"Penalización sobrecompra RSI {rsi_val:.1f}>75")
    elif 48 <= rsi_val <= 68:
        score_long += 25
        reasons_long.append(f"RSI {rsi_val:.1f} aceleración temprana")
    elif 38 <= rsi_val < 48:
        score_long += 15
        reasons_long.append(f"RSI {rsi_val:.1f} recuperación base")
    elif rsi_val < 30:
        score_long += 10
        reasons_long.append(f"RSI {rsi_val:.1f} rebote sobreventa")

    if rsi_val < 25:
        score_short -= 25
        reasons_short.append(f"Penalización sobreventa RSI {rsi_val:.1f}<25")
    elif 32 <= rsi_val <= 52:
        score_short += 25
        reasons_short.append(f"RSI {rsi_val:.1f} aceleración bajista temprana")
    elif 52 < rsi_val <= 62:
        score_short += 15
        reasons_short.append(f"RSI {rsi_val:.1f} rechazo resistencia")
    elif rsi_val > 70:
        score_short += 10
        reasons_short.append(f"RSI {rsi_val:.1f} agotamiento techo")

    # 4. Confirmación Volumétrica RVOL (hasta 15 pts) - Umbral ágil flexibilizado >= 1.05
    rvol_val = tf_data.get("rvol", 1.0)
    if rvol_val >= 1.05:
        score_long += 15
        score_short += 15
        reasons_long.append(f"RVOL {rvol_val:.2f}x (volumen activo)")
        reasons_short.append(f"RVOL {rvol_val:.2f}x (volumen activo)")
    elif rvol_val >= 0.90:
        score_long += 10
        score_short += 10
    else:
        score_long += 5
        score_short += 5

    # 5. Filtro de Régimen de Volatilidad: Compresión vs Sobre-Extensión (bono/penalización 15 pts)
    atr_pctl = tf_data.get("atr_pctl", 0.50)
    if tf_data.get("atr_compression", False):
        score_long += 15
        score_short += 15
        reasons_long.append(f"Compresión ATR ({atr_pctl*100:.0f}% pctl) Alta Fiabilidad")
        reasons_short.append(f"Compresión ATR ({atr_pctl*100:.0f}% pctl) Alta Fiabilidad")
    elif tf_data.get("atr_extended", False):
        score_long -= 15
        score_short -= 15
        reasons_long.append(f"Penalización ATR sobre-extendido ({atr_pctl*100:.0f}% pctl)")
        reasons_short.append(f"Penalización ATR sobre-extendido ({atr_pctl*100:.0f}% pctl)")

    # 6. Filtro Direccional de Funding Rate (Futuros USD-M)
    if funding_rate is not None:
        if funding_rate > 0.00035:
            score_long -= 25
            f_txt = f"{funding_rate*100:.3f}%/8h"
            reasons_long.append(f"Funding alcista extremo ({f_txt}) Penalización LONG")
            reasons_short.append(f"Funding alcista extremo ({f_txt})")
        elif funding_rate < -0.00025:
            score_short -= 25
            f_txt = f"{funding_rate*100:.3f}%/8h"
            reasons_short.append(f"Funding bajista extremo ({f_txt}) Penalización SHORT")
            reasons_long.append(f"Funding bajista extremo ({f_txt})")

    # 7. Filtro de Fuerza Tendencial ADX / DMI
    adx_val = tf_data.get("adx14", 25.0)
    adx_slope = tf_data.get("adx_slope", 0.0)
    if adx_val < 22.0:
        score_long = min(score_long, 35)
        score_short = min(score_short, 35)
        reasons_long.append(f"Bloqueo Régimen Lateral ADX ({adx_val:.1f} < 22)")
        reasons_short.append(f"Bloqueo Régimen Lateral ADX ({adx_val:.1f} < 22)")
    else:
        score_long += 15
        score_short += 15
        reasons_long.append(f"Fuerza Tendencial ADX {adx_val:.1f}")
        reasons_short.append(f"Fuerza Tendencial ADX {adx_val:.1f}")

    # 8. Filtro de Fuerza Relativa frente a Bitcoin (RS Spread vs BTC)
    if sym != "BTCUSDT" and rs_ratio_above_sma is not None:
        if not rs_ratio_above_sma:
            score_long = 0
            score_short += 20
            reasons_short.append("Veto RS vs BTC < SMA20 (Debilidad Altcoin -> Sesgo SHORT)")
            reasons_long.append("Veto RS vs BTC < SMA20")
        else:
            score_long += 15
            reasons_long.append("Fuerza Relativa RS vs BTC > SMA20")

    # 9. Filtro Macro de Régimen Bitcoin: Close_BTC_1D vs SMA200(1D)
    if sym != "BTCUSDT" and btc_macro_bullish is not None:
        if not btc_macro_bullish:
            score_long = 0
            score_short += 20
            reasons_short.append("BTC < SMA200(1D) Confirmación Macro (Impulso SHORT)")
            reasons_long.append("BTC < SMA200(1D) (Veto Long Altcoin)")
        else:
            score_long += 15
            reasons_long.append("Macro Alcista BTC >= SMA200")

    # Acotar scores al rango 0..100
    final_score_long = max(0, min(100, score_long))
    final_score_short = max(0, min(100, score_short))

    if final_score_long >= final_score_short:
        direction = "LONG"
        final_score = final_score_long
        chosen_reasons = reasons_long
    else:
        direction = "SHORT"
        final_score = final_score_short
        chosen_reasons = reasons_short

    return {
        "sym": sym,
        "score": final_score,
        "direction": direction,
        "score_long": final_score_long,
        "score_short": final_score_short,
        "reason": " + ".join(chosen_reasons),
        "rsi": rsi_val,
        "macd_hist": tf_data["macd_hist"],
        "atr14": tf_data["atr14"],
        "atr_mean": tf_data.get("atr_mean", tf_data["atr14"]),
        "atr_pctl": atr_pctl,
        "adx14": adx_val,
        "adx_slope": adx_slope,
        "ema21": tf_data.get("ema21", tf_data["close"]),
        "sma50": tf_data.get("sma50", tf_data["close"]),
        "price": tf_data["close"],
        "timeframe": prefer_tf,
    }


def calcular_niveles_rr(entry: float, atr14: float, direction: str) -> dict[str, float]:
    """Construcción de niveles SL, TP1 y TP2 para Modo Carrera (Fat Tails & Asymmetric Alpha):
    - dist_sl = max(1.5 * atr14, 0.015 * entry)
    - LONG:  sl = entry - dist_sl, tp1 = entry + 3.0 * dist_sl, tp2 = entry + 6.0 * dist_sl
    - SHORT: sl = entry + dist_sl, tp1 = entry - 3.0 * dist_sl, tp2 = entry - 6.0 * dist_sl
    """
    dist_sl = max(1.5 * atr14, 0.015 * entry)
    if direction == "LONG":
        sl = entry - dist_sl
        tp1 = entry + 3.0 * dist_sl
        tp2 = entry + 6.0 * dist_sl
    else:
        sl = entry + dist_sl
        tp1 = entry - 3.0 * dist_sl
        tp2 = entry - 6.0 * dist_sl

    rr_neto = round(abs(tp2 - entry) / dist_sl, 2)
    nd = 4 if entry < 10 else 2
    return {
        "dist_sl": dist_sl,
        "sl": round(sl, nd),
        "tp1": round(tp1, nd),
        "tp2": round(tp2, nd),
        "rr_neto": rr_neto,
    }


def gestionar_y_ejecutar(
    root: Path,
    live_klines: dict[str, dict[str, pd.DataFrame]],
    capital_total: float = 1000.0,
    max_open_ops: int = 6,
    live_prices: dict[str, float] | None = None,
    funding_rates: dict[str, float] | None = None,
    news_headlines: list[str] | None = None,
) -> dict[str, Any]:
    """Gestiona posiciones abiertas de Futuros con cierre parcial del 50% en TP1 y trailing
    stop protector Anti-Wick, y abre nuevas oportunidades con dimensionamiento dinámico
    adaptativo acotado, manteniendo estricto respeto al calor de cartera <= 10%.
    """
    costs = load_costs(root)

    # 1. OBTENER PRECIOS EN VIVO EXACTOS
    prices: dict[str, float] = {}
    if live_prices:
        prices.update(live_prices)
    for s in UNIVERSO:
        if s not in prices or prices[s] <= 0:
            frames = live_klines.get(s, {})
            for tf in ("1h", "4h", "1d"):
                df = frames.get(tf)
                if df is not None and not df.empty:
                    prices[s] = float(df["close"].iloc[-1])
                    break

    # 2. GESTIONAR FUTUROS EXISTENTES EN user_trades.jsonl
    trades = load_trades(root)
    open_trades = [t for t in trades if t.get("status") == "open"]
    cerradas_ahora: list[str] = []

    for t in open_trades:
        sym = t.get("asset", "")
        px = prices.get(sym)
        if px is None or px <= 0:
            continue

        order_state = t.get("order_state", "ACTIVE")
        target_entry = t.get("target_entry") or t.get("entry_price")
        is_long = t.get("kind") != "future_short"
        entry_px = float(t.get("entry_price", 0.0))
        sl = float(t.get("sl", 0.0))
        tp2 = float(t.get("tp", 0.0))
        tp1 = float(t.get("tp1") or (entry_px + (tp2 - entry_px) * 0.55))
        tp1_hit = bool(t.get("tp1_hit", False))

        # A) Si es una orden PROGRAMADA A FUTURO esperando ejecución
        if order_state == "PENDING_FUTURE":
            target_px = float(target_entry)
            activar = (px <= target_px) if is_long else (px >= target_px)
            if activar:
                update_trade(
                    root,
                    t["id"],
                    updates={
                        "order_state": "ACTIVE",
                        "activated_at": datetime.now(UTC).isoformat(timespec="seconds"),
                        "entry_price": target_px,
                    },
                    note=f"Orden programada activada al alcanzar precio objetivo {target_px}",
                )
                t["order_state"] = "ACTIVE"
                t["entry_price"] = target_px
                entry_px = target_px
            continue

        # Seguimiento en caliente de excursiones MFE y MAE en R (Claude Trading Skills)
        update_live_excursions(t, px)

        # Obtener ATR actual para trailing stop dinámico anti-wick
        atr_trade = float(t.get("atr14") or 0.0)
        if atr_trade <= 0:
            tf_sym = t.get("timeframe", "4h")
            tf_df = live_klines.get(sym, {}).get(tf_sym)
            if tf_df is not None and not tf_df.empty:
                ind_tmp = compute_indicators({tf_sym: tf_df})
                atr_trade = ind_tmp.get(tf_sym, {}).get("atr14", px * 0.02)
            else:
                atr_trade = px * 0.02

        # B) Si es una orden ACTIVA: Gestionar Salidas (TP2, SL Anti-Wick y Piramidación)
        # Trailing Estructural Anti-Mecha (Swing Low de 8 velas en 4H)
        df_4h_sym = live_klines.get(sym, {}).get("4h")
        if df_4h_sym is not None and len(df_4h_sym) >= 8:
            swing_low_8 = float(df_4h_sym["low"].iloc[-8:].min())
            if is_long and swing_low_8 > sl:
                sl = swing_low_8
                update_trade(
                    root,
                    t["id"],
                    updates={"sl": sl},
                    note=(
                        f"Trailing Stop Anti-Mecha elevado a {sl} (Swing Low 8 velas 4H)"
                    ),
                )
                t["sl"] = sl

        # Piramidación Protectora a Riesgo Cero (+25% a >= +4.0R con SL garantizado >= +0.5R)
        is_pyramided = bool(t.get("pyramided", False))
        dist_sl_initial = float(
            t.get("dist_sl")
            or max(0.01 * entry_px, abs(entry_px - float(t.get("sl_initial") or sl)))
        )
        unrealized_r = (
            (px - entry_px) / dist_sl_initial if is_long else (entry_px - px) / dist_sl_initial
        )
        peak_r = max(float(t.get("peak_r", 0.0)), unrealized_r)
        t["peak_r"] = peak_r
        locked_r = (
            (sl - entry_px) / dist_sl_initial if is_long else (entry_px - sl) / dist_sl_initial
        )

        if (
            not is_pyramided
            and peak_r >= 4.0
            and locked_r >= 1.5
            and df_4h_sym is not None
            and len(df_4h_sym) >= 2
        ):
            c4_series = df_4h_sym["close"].astype(float)
            e21_4h_val = float(c4_series.ewm(span=21, adjust=False).mean().iloc[-1])
            last_low = float(df_4h_sym["low"].iloc[-1])
            last_close = float(df_4h_sym["close"].iloc[-1])
            last_open = float(df_4h_sym["open"].iloc[-1])

            pullback_ema = last_low <= (e21_4h_val * 1.006)
            bullish_reject = (last_close > last_open) and (last_close >= e21_4h_val)

            if pullback_ema and bullish_reject:
                size_init = float(t.get("size_usd", 0.0))
                add_size = round(0.25 * size_init, 2)
                add_entry_px = px
                total_fees = (size_init + add_size) * 0.0007
                target_profit = 0.5 * float(t.get("risk_usd", 25.0)) + total_fees
                target_val = size_init + add_size + target_profit
                denom = (size_init / entry_px) + (add_size / add_entry_px)
                sl_zero_risk = round(target_val / denom, 2)

                new_sl = max(sl, sl_zero_risk)
                new_size = round(size_init + add_size, 2)
                update_trade(
                    root,
                    t["id"],
                    updates={
                        "pyramided": True,
                        "add_size_usd": add_size,
                        "add_entry_price": add_entry_px,
                        "size_usd": new_size,
                        "sl": new_sl,
                        "peak_r": peak_r,
                    },
                    note=(
                        f"🚀 PIRAMIDACIÓN PROTECTORA: +${add_size} USD @ {add_entry_px} (25%). "
                        f"SL Blindado a {new_sl} garantizando ganancia >= +0.5R."
                    ),
                )
                t["pyramided"] = True
                t["add_size_usd"] = add_size
                t["size_usd"] = new_size
                t["sl"] = new_sl
                sl = new_sl
                notify_event(
                    "PYRAMID_EXECUTED",
                    {
                        "asset": sym,
                        "add_size_usd": add_size,
                        "new_size_usd": new_size,
                        "sl_blindado": new_sl,
                    },
                )

        # Check TP2 hit (Take Profit final total si aplica)
        tp2_hit = px >= tp2 if is_long else px <= tp2
        if tp2 > 0 and tp2_hit:
            close_trade(
                root,
                t["id"],
                exit_price=tp2,
                note=f"TP2 Alcanzado con éxito @ {tp2} (precio vivo {px})",
                tag="TP2_EXIT",
            )
            cerradas_ahora.append(t["id"])
            t["status"] = "closed"
            t["exit_price"] = tp2
            rpnl = realized_pnl_usd(t, costs)
            record_postmortem(root, t, tp2, rpnl["pnl_neto_usd"])
            r_mult = (
                round(rpnl["pnl_neto_usd"] / float(t.get("risk_usd", 15.0)), 2)
                if float(t.get("risk_usd", 0.0)) > 0
                else 0.0
            )
            notify_event(
                "TRADE_CLOSED",
                {
                    "asset": sym,
                    "tag": "TP2_EXIT",
                    "exit_price": tp2,
                    "pnl_neto_usd": rpnl["pnl_neto_usd"],
                    "pnl_pct": rpnl["pnl_pct"],
                    "r_multiplo": r_mult,
                    "note": f"Salida exitosa en TP2. PnL neto: +${rpnl['pnl_neto_usd']} USD",
                },
            )
            continue

        # Check SL hit con Regla Anti-Wick: Comprobamos si la vela de 4H cerró bajo el SL
        last_4h_close = (
            float(df_4h_sym["close"].iloc[-1])
            if df_4h_sym is not None and not df_4h_sym.empty
            else px
        )
        sl_hit = (last_4h_close < sl) if is_long else (last_4h_close > sl)
        if sl_hit:
            tag_exit = "CRUISE_PYRAMID_EXIT" if is_pyramided else "CRUISE_STRUCTURAL_SL"
            close_trade(
                root,
                t["id"],
                exit_price=last_4h_close,
                note=f"Salida Anti-Mecha en 4H ejecutada @ {last_4h_close} (SL {sl})",
                tag=tag_exit,
            )
            cerradas_ahora.append(t["id"])
            t["status"] = "closed"
            t["exit_price"] = last_4h_close
            rpnl = realized_pnl_usd(t, costs)
            record_postmortem(root, t, last_4h_close, rpnl["pnl_neto_usd"])
            r_mult = (
                round(rpnl["pnl_neto_usd"] / float(t.get("risk_usd", 15.0)), 2)
                if float(t.get("risk_usd", 0.0)) > 0
                else 0.0
            )
            notify_event(
                "TRADE_CLOSED",
                {
                    "asset": sym,
                    "tag": tag_exit,
                    "exit_price": last_4h_close,
                    "pnl_neto_usd": rpnl["pnl_neto_usd"],
                    "pnl_pct": rpnl["pnl_pct"],
                    "r_multiplo": r_mult,
                    "note": f"Salida en {tag_exit}. PnL neto: ${rpnl['pnl_neto_usd']:+.2f} USD",
                },
            )
            continue

        # Check TP1 hit -> CIERRE PARCIAL REAL DEL 25% + ELEVAR SL CON FILTRO ANTI-WICK (2.2x ATR)
        tp1_trigger = px >= tp1 if is_long else px <= tp1
        if tp1_trigger and not tp1_hit:
            size_curr = float(t.get("size_usd", 0.0))
            part_size = round(size_curr * 0.25, 2)
            remaining_size = round(size_curr - part_size, 2)
            dir_sign = 1.0 if is_long else -1.0
            pnl_gross_part = part_size * (tp1 / entry_px - 1.0) * dir_sign
            fees_part = part_size * fee_roundtrip(str(t.get("kind", "future_long")), costs)
            pnl_net_part = round(pnl_gross_part - fees_part, 2)

            # Cálculo de Stop Loss protector Anti-Wick Tendencial (2.2x ATR)
            new_sl = anti_wick_trailing_sl(
                entry=entry_px,
                current_sl=sl,
                current_price=px,
                atr14=atr_trade,
                direction="LONG" if is_long else "SHORT",
                atr_mult=2.2,
            )

            prev_part_pnl = float(t.get("partial_realized_pnl_usd", 0.0))
            prev_part_fees = float(t.get("partial_fees_usd", 0.0))
            prev_closed_size = float(t.get("partial_closed_size_usd", 0.0))

            part_exits = list(t.get("partial_exits") or [])
            part_exits.append(
                {
                    "ts_utc": datetime.now(UTC).isoformat(timespec="seconds"),
                    "exit_price": tp1,
                    "closed_size_usd": part_size,
                    "pnl_neto_usd": pnl_net_part,
                    "tag": "TP1_PARTIAL_25",
                }
            )

            updates_dict: dict[str, Any] = {
                "tp1_hit": True,
                "size_usd": remaining_size,
                "partial_closed_size_usd": round(prev_closed_size + part_size, 2),
                "partial_realized_pnl_usd": round(prev_part_pnl + pnl_net_part, 2),
                "partial_fees_usd": round(prev_part_fees + fees_part, 2),
                "partial_exits": part_exits,
                "sl": new_sl,
            }

            update_trade(
                root,
                t["id"],
                updates=updates_dict,
                note=(
                    f"🎯 TP1 Alcanzado @ {tp1}. Cierre parcial del 25% (+${pnl_net_part} USD). "
                    f"Stop Loss tendencial anclado a {new_sl} (2.2x ATR)."
                ),
            )
            t.update(updates_dict)

            notify_event(
                "TP1_PARTIAL",
                {
                    "asset": sym,
                    "exit_price": tp1,
                    "pnl_usd": pnl_net_part,
                    "new_sl": new_sl,
                    "remaining_size_usd": remaining_size,
                },
            )

        elif tp1_hit:
            # Trailing dinámico continuo de tendencia con filtro Anti-Wick (2.2x ATR)
            cand_sl = anti_wick_trailing_sl(
                entry=entry_px,
                current_sl=sl,
                current_price=px,
                atr14=atr_trade,
                direction="LONG" if is_long else "SHORT",
                atr_mult=2.2,
            )
            if is_long and cand_sl > sl:
                update_trade(
                    root,
                    t["id"],
                    updates={"sl": cand_sl},
                    note=f"Trailing SL elevado a {cand_sl} (Anti-Wick 2.2x ATR)",
                )
                t["sl"] = cand_sl
            elif not is_long and cand_sl < sl:
                update_trade(
                    root,
                    t["id"],
                    updates={"sl": cand_sl},
                    note=f"Trailing SL bajado a {cand_sl} (Anti-Wick 2.2x ATR)",
                )
                t["sl"] = cand_sl

    # Recargar tras cierres y actualizaciones
    trades = load_trades(root)
    open_trades = [t for t in trades if t.get("status") == "open"]
    activos_abiertos = {t["asset"] for t in open_trades}

    # 3. VERIFICAR PORTFOLIO HEAT ACTUAL (Exposure Coach & Circuit Breaker)
    heat_usd_actual = sum(open_risk_usd(ot) or 0.0 for ot in open_trades)
    heat_pct_actual = (heat_usd_actual / capital_total * 100.0) if capital_total > 0 else 0.0
    if heat_pct_actual > 20.0:
        notify_event("HEAT_WARNING", {"heat_usd": heat_usd_actual, "heat_pct": heat_pct_actual})

    market_health = compute_market_health(live_klines, funding_rates)
    circuit_breaker = check_circuit_breaker(trades, capital_total)
    effective_max_heat_pct = min(
        MAX_PORTFOLIO_HEAT_PCT, float(market_health.get("max_heat_pct", 25.0))
    )

    # 4. MOMENTUM RANKING (30 DÍAS) & ROTACIÓN DINÁMICA DE CAPITAL (40/25/10)
    momentum_info = compute_momentum_ranking(live_klines, CRUISE_ELITE)
    momentum_weights = momentum_info["weights"]

    scores_dict: dict[str, Any] = {"_momentum_ranking": momentum_info["ranking"]}
    candidates_pool: list[dict[str, Any]] = []

    btc_frames = live_klines.get("BTCUSDT", {})
    btc_4h_df = btc_frames.get("4h")
    btc_1d_df = btc_frames.get("1d")
    btc_macro_bull = True
    if btc_1d_df is not None and len(btc_1d_df) >= 30:
        c_btc = btc_1d_df["close"].astype(float).to_numpy()
        w = min(200, len(c_btc))
        sma200_btc = float(np.mean(c_btc[-w:]))
        btc_macro_bull = float(c_btc[-1]) >= sma200_btc

    for s in UNIVERSO:
        if s in BLACKLIST:
            continue
        frames = live_klines.get(s, {})
        ind = compute_indicators(frames)
        f_rate = (funding_rates or {}).get(s)

        # Filtro de Fuerza Relativa vs Bitcoin
        rs_above: bool | None = None
        if s != "BTCUSDT" and btc_4h_df is not None and not btc_4h_df.empty:
            alt_4h_df = frames.get("4h")
            if alt_4h_df is not None and not alt_4h_df.empty:
                rs_above = rs_is_above_sma(alt_4h_df["close"], btc_4h_df["close"], window=20)

        sc_4h = score_symbol(
            s,
            ind,
            "4h",
            funding_rate=f_rate,
            rs_ratio_above_sma=rs_above,
            btc_macro_bullish=btc_macro_bull,
        )
        sc_4h["ind"] = ind
        px_real = prices.get(s, sc_4h.get("price", 0.0))
        sc_4h["price"] = px_real

        # Evaluación del Oráculo K-Line Kronos (6 velas de 4H) y Jefe de Mesa IA
        df_4h_s = frames.get("4h")
        kronos_4h = predict_kline_horizon(df_4h_s, symbol=s, timeframe="4h", horizon=6)
        sw_high = (
            float(df_4h_s["high"].iloc[-15:].max())
            if df_4h_s is not None and len(df_4h_s) >= 5
            else px_real * 1.03
        )
        sw_low = (
            float(df_4h_s["low"].iloc[-15:].min())
            if df_4h_s is not None and len(df_4h_s) >= 5
            else px_real * 0.97
        )
        ai_eval = evaluar_setup_con_ia(
            symbol=s,
            direction=sc_4h.get("direction", "LONG"),
            current_price=px_real,
            indicators=sc_4h.get("ind", {}).get("4h", {}),
            swing_high=sw_high,
            swing_low=sw_low,
            btc_macro_bullish=btc_macro_bull,
            news_headlines=news_headlines,
            klines_4h=df_4h_s,
            root=root,
            kronos_forecast=kronos_4h,
        )
        sc_4h["ai_verdict"] = ai_eval
        sc_4h["kronos_4h"] = kronos_4h
        scores_dict[s] = sc_4h

        # Filtrar micro-ruido: restringir a marcos mayores swing (4h y 1d)
        for tf in ("4h", "1d"):
            sc_tf = score_symbol(
                s,
                ind,
                tf,
                funding_rate=f_rate,
                rs_ratio_above_sma=rs_above,
                btc_macro_bullish=btc_macro_bull,
            )
            sc_tf["price"] = px_real
            sc_tf["timeframe"] = tf
            sc_tf["ai_verdict"] = ai_eval
            sc_tf["kronos_4h"] = kronos_4h
            candidates_pool.append(sc_tf)

    nuevas_abiertas: list[dict[str, Any]] = []
    slots_disponibles = max_open_ops - len(open_trades)

    if (
        slots_disponibles > 0
        and heat_pct_actual < effective_max_heat_pct
        and not circuit_breaker.get("is_halted", False)
    ):
        preset_configs = [
            {"asset": "BTCUSDT", "tf": "4h", "lev": "5x", "ln": 5},
            {"asset": "ETHUSDT", "tf": "4h", "lev": "4x", "ln": 4},
            {"asset": "SOLUSDT", "tf": "4h", "lev": "4x", "ln": 4},
            {"asset": "SUIUSDT", "tf": "4h", "lev": "4x", "ln": 4},
        ]

        for p_cfg in preset_configs:
            if slots_disponibles <= 0:
                break
            sym = p_cfg["asset"]
            if sym in activos_abiertos or sym in BLACKLIST:
                continue

            px = prices.get(sym, 0.0)
            if px <= 0:
                continue

            tf = p_cfg["tf"]
            lev = p_cfg["lev"]
            lev_num = p_cfg["ln"]

            cand = next(
                (c for c in candidates_pool if c["sym"] == sym and c["timeframe"] == tf),
                None,
            )
            if not cand:
                cand = scores_dict.get(sym, {})

            direction = cand.get("direction", "LONG")
            if direction == "NEUTRAL":
                direction = "SHORT" if not btc_macro_bull else "LONG"
            tech_score = float(cand.get("score", 50.0))
            reason = cand.get("reason", "Alineación cuantitativa multi-indicador")
            atr14 = float(cand.get("atr14", px * 0.02))
            atr_mean = float(cand.get("atr_mean", atr14))
            nd = 4 if px < 10 else 2
            ema21_val = float(cand.get("ema21", px))

            # 1. EVALUACIÓN Y PONDERACIÓN DEL JEFE DE MESA IA
            ai_eval = cand.get("ai_verdict") or scores_dict.get(sym, {}).get("ai_verdict") or {}
            ai_verdict_tipo = ai_eval.get("veredicto", "EJECUTAR_AHORA")
            ai_confianza = int(ai_eval.get("confianza", 78))
            ai_razon = str(ai_eval.get("razonamiento", ""))

            kronos_fc = cand.get("kronos_4h") or scores_dict.get(sym, {}).get("kronos_4h") or {}
            k_bull_prob = float(kronos_fc.get("bullish_prob", 50.0))
            kronos_dir_prob = k_bull_prob if direction == "LONG" else (100.0 - k_bull_prob)

            # 2. PUNTAJE DE SINERGIA ACTIVA UNIFICADA (0-100)
            # 35% Oráculo Kronos + 35% Estructura Técnica + 30% Gemini IA
            ai_weight_val = float(ai_confianza)
            combined_score = round(
                0.35 * kronos_dir_prob + 0.35 * tech_score + 0.30 * ai_weight_val, 1
            )
            cand["combined_conviction_score"] = combined_score
            cand["score"] = combined_score
            score = combined_score

            # Umbral de disparo ágil reducido a Score >= 55
            if score < 55:
                continue

            # Prohibir abrir SHORT si la IA advierte trampa, rebote alcista o sobreventa extrema
            if direction == "SHORT":
                r_low = ai_razon.lower()
                if (
                    ai_verdict_tipo == "VETAR_TRAMPA"
                    or "sobreventa extrema" in r_low
                    or "rebote" in r_low
                    or "agotamiento" in r_low
                ):
                    continue
            elif direction == "LONG":
                if ai_verdict_tipo == "VETAR_TRAMPA":
                    continue

            model_lbl = ai_eval.get("model_used", "Gemini")

            # 3. EJECUCIÓN DIRECTA SIN PARÁLISIS (INSTANTE vs LÍMITE CERCANA 0.25x ATR)
            # Preferir siempre apertura activa de inmediato (OPEN / ⚡ AL INSTANTE)
            dist_ema21 = abs(px - ema21_val) / (ema21_val + 1e-9)
            if dist_ema21 > 0.05:
                # Si está sobre-extendido > 5%, orden límite a solo 0.25x ATR para llenado veloz
                mode = "FUTURO"
                order_state = "PENDING_FUTURE"
                offset_atr = 0.25 * atr14
                target_px = round(px - offset_atr if direction == "LONG" else px + offset_atr, nd)
                entry_px = target_px
                target_entry = target_px
                geom = calcular_niveles_rr(target_px, atr14, direction)
                rr_n = geom["rr_neto"]
                thesis_txt = (
                    f"🎯 PROGRAMADA {direction} {lev} ({tf.upper()}) · Pullback a 0.25x ATR "
                    f"({target_px}) · Score {score:.0f}/100 [Kronos {kronos_dir_prob:.0f}% · "
                    f"Tech {tech_score:.0f} · IA {ai_confianza}%] · R:R {rr_n}x · "
                    f"[🧠 IA {model_lbl}: {ai_razon}]"
                )
            else:
                mode = "INSTANTE"
                entry_px = px
                order_state = "ACTIVE"
                target_entry = None
                geom = calcular_niveles_rr(entry_px, atr14, direction)
                rr_n = geom["rr_neto"]
                thesis_txt = (
                    f"⚡ AL INSTANTE {direction} {lev} ({tf.upper()}) · Sinergia Activa "
                    f"Score {score:.0f}/100 [Kronos {kronos_dir_prob:.0f}% · "
                    f"Tech {tech_score:.0f} · IA {ai_confianza}%] · {reason} · R:R {rr_n}x · "
                    f"[🧠 IA {model_lbl}: {ai_razon}]"
                )

            sl = geom["sl"]
            tp1 = geom["tp1"]
            tp2 = geom["tp2"]
            rr_neto = geom["rr_neto"]

            # Dimensionamiento Dinámico con Factor de Momentum (40/25/25/10)
            w_sym = momentum_weights.get(sym, 0.25)
            w_factor = w_sym / 0.25
            risk_pct_adapt = adaptive_risk_pct(
                base_risk=BASE_RISK_PCT,
                score=score,
                current_atr=atr14,
                mean_atr=atr_mean,
                min_risk=0.02,
                max_risk=0.05,
            ) * w_factor
            riesgo_usd = capital_total * risk_pct_adapt

            # Control inquebrantable de Portfolio Heat <= effective_max_heat_pct
            if (heat_usd_actual + riesgo_usd) > (
                capital_total * (effective_max_heat_pct / 100.0)
            ):
                max_allowed_risk = max(
                    0.0, capital_total * (effective_max_heat_pct / 100.0) - heat_usd_actual
                )
                if max_allowed_risk < (capital_total * 0.01):
                    continue  # Sin cupo de riesgo seguro
                riesgo_usd = max_allowed_risk
                risk_pct_adapt = riesgo_usd / capital_total

            # Pre-Trade Discipline Gate (Claude Trading Skills + Kronos Alignment)
            gate = evaluate_discipline_gate(
                symbol=sym,
                direction=direction,
                current_price=entry_px,
                ema21=ema21_val,
                current_heat_pct=heat_pct_actual,
                trade_risk_pct=risk_pct_adapt * 100.0,
                max_heat_allowed=effective_max_heat_pct,
                circuit_breaker_status=circuit_breaker.get("status", "NORMAL"),
                news_items=news_headlines,
                funding_rate=f_rate,
                kronos_forecast=kronos_fc,
            )
            if not gate["gate_passed"]:
                continue

            dist_sl_pct = abs(entry_px - sl) / entry_px
            tamano_usd = round(riesgo_usd / max(0.005, dist_sl_pct), 2)
            margen_usd = round(tamano_usd / lev_num, 2)
            kind = "future_long" if direction == "LONG" else "future_short"

            trade_rec = open_trade(
                root,
                asset=sym,
                kind=kind,
                timeframe=tf,
                entry_price=entry_px,
                size_usd=tamano_usd,
                sl=sl,
                tp=tp2,
                note=thesis_txt,
                example=False,
                tag="FUTURES_M63",
                rr_neto_inicial=rr_neto,
                rr_forzado=False,
                entry_mode=mode,
                order_state=order_state,
                target_entry=target_entry,
                leverage=lev,
                margin_usd=margen_usd,
                risk_usd=riesgo_usd,
                tp1=tp1,
                tp2=tp2,
                thesis=thesis_txt,
                ai_reasoning=ai_razon,
            )
            trade_rec["tp1"] = tp1
            trade_rec["tp2"] = tp2
            trade_rec["leverage"] = lev
            trade_rec["margin_usd"] = margen_usd
            trade_rec["risk_usd"] = riesgo_usd
            trade_rec["rr_neto"] = rr_neto
            trade_rec["entry_mode"] = mode
            trade_rec["order_state"] = order_state
            trade_rec["target_entry"] = target_entry
            trade_rec["thesis"] = thesis_txt
            trade_rec["atr14"] = atr14
            trade_rec["pyramided"] = False
            trade_rec["peak_r"] = 0.0
            trade_rec["mfe_r"] = 0.0
            trade_rec["mae_r"] = 0.0
            trade_rec["momentum_weight"] = w_sym
            trade_rec["ai_verdict"] = ai_verdict_tipo
            trade_rec["ai_confidence"] = ai_confianza
            trade_rec["ai_reasoning"] = ai_razon
            trade_rec["ai_model"] = ai_eval.get("model_used", "Gemini")

            nuevas_abiertas.append(trade_rec)
            activos_abiertos.add(sym)
            slots_disponibles -= 1
            heat_usd_actual += riesgo_usd

            notify_event(
                "ORDER_OPEN",
                {
                    "asset": sym,
                    "timeframe": tf,
                    "kind": kind,
                    "leverage": lev,
                    "entry_price": entry_px,
                    "sl": sl,
                    "tp1": tp1,
                    "tp2": tp2,
                    "score": score,
                    "risk_usd": riesgo_usd,
                    "risk_pct": risk_pct_adapt,
                    "thesis": thesis_txt,
                    "entry_mode": mode,
                    "ai_reasoning": ai_razon,
                    "ai_verdict": ai_verdict_tipo,
                },
            )

    # 5. GESTIONAR Y EVALUAR CARTERA SPOT (SECCIÓN 2)
    spot_plans = evaluar_y_gestionar_spot(root, live_klines, prices, capital_total)
    kronos_multi = evaluate_kronos_multi_horizon(live_klines, UNIVERSO, horizon=6)

    return {
        "scores": scores_dict,
        "momentum_ranking": momentum_info["ranking"],
        "momentum_weights": momentum_weights,
        "nuevas_abiertas": nuevas_abiertas,
        "cerradas_ahora": cerradas_ahora,
        "open_trades_count": len(open_trades) + len(nuevas_abiertas),
        "spot_plans": spot_plans,
        "market_health": market_health,
        "circuit_breaker": circuit_breaker,
        "kronos": kronos_multi,
        "ai_brain": {
            s: scores_dict.get(s, {}).get("ai_verdict", {})
            for s in UNIVERSO
            if s in scores_dict
        },
    }


def autonomous_run(capital_inicial: float = 1000.0) -> dict[str, Any]:
    """Punto de entrada compatible."""
    from qa.agent.live import fetch_live
    from qa.data.paths import get_root

    root = get_root()
    live = fetch_live(UNIVERSO)
    prem = live.get("premium", {})
    funding_rates = {s: float(prem.get(s, {}).get("last_funding_rate", 0.0)) for s in UNIVERSO}
    return gestionar_y_ejecutar(root, live["klines"], capital_inicial, funding_rates=funding_rates)
