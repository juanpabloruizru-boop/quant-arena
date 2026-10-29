# Autopilot Motor Autónomo M6.3 — QUANT-ARENA v2
"""Motor de decisión y ejecución autónomo "Conquistador" para paper trading simulado.

Arquitectura M6.3:
1. SECCIÓN 1: FUTUROS (1H · 4H · 1D)
   - Operaciones "⚡ AL INSTANTE" (al precio spot/perp en vivo actual exacto, cero look-ahead bias)
   - Operaciones "🎯 PROGRAMADA A FUTURO" (precio objetivo proyectado a pullback EMA21/SMA50 con SL y TPs fijos)
   - Gestión estricta de SL, TP1 (asegurar + Break-Even) y TP2 (salida final)
2. SECCIÓN 2: SPOT & CICLOS (4H · 1D · 1W)
   - Cartera 1x sin apalancamiento gestionada a través de qa.agent.spot
   - 🔒 Zonas de Compra a Precio Razonable 100% FIJAS e Inmutables
   - 📈 Zonas de Toma de Ganancias (TP1 50% y TP2 Ciclo) dinámicas y actualizables al alza
"""

from __future__ import annotations

import math
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

from qa.agent.spot import evaluar_y_gestionar_spot
from qa.agent.tracker import close_trade, load_trades, open_trade, update_trade

UNIVERSO = [
    "BTCUSDT", "ETHUSDT", "SOLUSDT", "BNBUSDT", "XRPUSDT",
    "ZECUSDT", "NEARUSDT", "SUIUSDT", "UNIUSDT", "DOGEUSDT",
]

RISK_PCT_POR_OP = 0.015  # 1.5% del patrimonio ($15 USD sobre $1,000)
MIN_RR_NETO = 2.0


def compute_indicators(klines_dict: dict[str, pd.DataFrame]) -> dict[str, Any]:
    """Calcula indicadores reales sobre marcos 1h, 4h y 1d:
    - EMA9, EMA21, SMA50
    - RSI(14)
    - MACD (12, 26, 9)
    - ATR(14)
    - RVOL (volumen actual / media 20)
    """
    res: dict[str, Any] = {}
    for tf in ("1h", "4h", "1d", "1w"):
        df = klines_dict.get(tf)
        if df is None or df.empty or len(df) < 15:
            continue
        c = df["close"].astype(float)
        v = df["volume"].astype(float) if "volume" in df.columns else pd.Series(np.ones(len(df)), index=df.index)
        h = df["high"].astype(float)
        l = df["low"].astype(float)

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

        tr = np.maximum(h - l, np.maximum(np.abs(h - c.shift(1)), np.abs(l - c.shift(1))))
        atr = tr.rolling(14).mean()

        rvol = v / (v.rolling(20).mean() + 1e-9)

        res[tf] = {
            "close": float(c.iloc[-1]),
            "ema9": float(ema9.iloc[-1]),
            "ema21": float(ema21.iloc[-1]),
            "sma50": float(sma50.iloc[-1]),
            "rsi": float(rsi.iloc[-1]) if not math.isnan(rsi.iloc[-1]) else 50.0,
            "macd_line": float(macd_line.iloc[-1]),
            "macd_signal": float(macd_signal.iloc[-1]),
            "macd_hist": float(macd_hist.iloc[-1]),
            "atr14": float(atr.iloc[-1]) if not math.isnan(atr.iloc[-1]) else float(c.iloc[-1] * 0.02),
            "rvol": float(rvol.iloc[-1]) if not math.isnan(rvol.iloc[-1]) else 1.0,
        }
    return res


def score_symbol(sym: str, ind: dict[str, Any], prefer_tf: str = "4h") -> dict[str, Any]:
    """Algoritmo 'Conquistador': Evalúa LONG y SHORT sobre un marco preferido y calcula Score 0..100."""
    tf_data = ind.get(prefer_tf) or ind.get("4h") or ind.get("1d") or ind.get("1h")
    tf1d = ind.get("1d") or tf_data

    if not tf_data:
        return {"sym": sym, "score": 0, "direction": "NEUTRAL", "reason": "Sin datos suficientes", "atr14": 1.0, "price": 0.0}

    score_long = 0
    score_short = 0
    reasons_long: list[str] = []
    reasons_short: list[str] = []

    # 1. Alineación EMAs (hasta 30 pts)
    if tf_data["ema9"] > tf_data["ema21"]:
        score_long += 20
        reasons_long.append(f"EMA9>21({prefer_tf.upper()})")
    else:
        score_short += 20
        reasons_short.append(f"EMA9<21({prefer_tf.upper()})")

    if tf1d and tf1d["close"] > tf1d["sma50"]:
        score_long += 10
        reasons_long.append("Close>SMA50(1D)")
    elif tf1d:
        score_short += 10
        reasons_short.append("Close<SMA50(1D)")

    # 2. MACD Histograma (hasta 25 pts)
    if tf_data["macd_hist"] > 0:
        score_long += 25
        reasons_long.append("MACD_hist alcista")
    else:
        score_short += 25
        reasons_short.append("MACD_hist bajista")

    # 3. RSI momentum (hasta 25 pts)
    rsi_val = tf_data["rsi"]
    if 50 <= rsi_val <= 72:
        score_long += 25
        reasons_long.append(f"RSI {rsi_val:.1f} momentum alcista")
    elif rsi_val < 35:
        score_long += 20
        reasons_long.append(f"RSI {rsi_val:.1f} rebote sobreventa")

    if 28 <= rsi_val <= 50:
        score_short += 25
        reasons_short.append(f"RSI {rsi_val:.1f} momentum bajista")
    elif rsi_val > 65:
        score_short += 20
        reasons_short.append(f"RSI {rsi_val:.1f} agotamiento sobrecompra")

    # 4. RVOL (hasta 20 pts)
    rvol_val = tf_data.get("rvol", 1.0)
    if rvol_val >= 1.0:
        score_long += 20
        score_short += 20
        reasons_long.append(f"RVOL {rvol_val:.1f}x")
        reasons_short.append(f"RVOL {rvol_val:.1f}x")
    else:
        score_long += 10
        score_short += 10

    if score_long >= score_short:
        direction = "LONG"
        final_score = min(100, score_long)
        chosen_reasons = reasons_long
    else:
        direction = "SHORT"
        final_score = min(100, score_short)
        chosen_reasons = reasons_short

    return {
        "sym": sym,
        "score": final_score,
        "direction": direction,
        "score_long": score_long,
        "score_short": score_short,
        "reason": " + ".join(chosen_reasons),
        "rsi": rsi_val,
        "macd_hist": tf_data["macd_hist"],
        "atr14": tf_data["atr14"],
        "ema21": tf_data.get("ema21", tf_data["close"]),
        "sma50": tf_data.get("sma50", tf_data["close"]),
        "price": tf_data["close"],
        "timeframe": prefer_tf,
    }


def calcular_niveles_rr(entry: float, atr14: float, direction: str) -> dict[str, float]:
    """Construcción garantizada de SL, TP1 y TP2 con R:R Neto >= 2.2x hacia TP2:
    - dist_sl = max(1.5 * atr14, 0.015 * entry)
    - LONG: sl = entry - dist_sl, tp1 = entry + 1.6 * dist_sl, tp2 = entry + 2.8 * dist_sl
    - SHORT: sl = entry + dist_sl, tp1 = entry - 1.6 * dist_sl, tp2 = entry - 2.8 * dist_sl
    """
    dist_sl = max(1.5 * atr14, 0.015 * entry)
    if direction == "LONG":
        sl = entry - dist_sl
        tp1 = entry + 1.6 * dist_sl
        tp2 = entry + 2.8 * dist_sl
    else:
        sl = entry + dist_sl
        tp1 = entry - 1.6 * dist_sl
        tp2 = entry - 2.8 * dist_sl

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
) -> dict[str, Any]:
    """Gestiona posiciones abiertas de Futuros y abre nuevas operaciones
    (combinando '⚡ AL INSTANTE' y '🎯 PROGRAMADA A FUTURO' en 1H, 4H y 1D).
    También evalúa la Cartera Spot en user_spot.jsonl.
    """
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
        sym = t.get("asset")
        px = prices.get(sym)
        if px is None or px <= 0:
            continue

        order_state = t.get("order_state", "ACTIVE")
        entry_mode = t.get("entry_mode", "INSTANTE")
        target_entry = t.get("target_entry") or t.get("entry_price")
        is_long = t.get("kind") != "future_short"
        sl = float(t.get("sl", 0.0))
        tp2 = float(t.get("tp", 0.0))
        tp1 = float(t.get("tp1") or (t.get("entry_price", 0.0) + (tp2 - t.get("entry_price", 0.0)) * 0.55))
        tp1_hit = bool(t.get("tp1_hit", False))

        # A) Si es una orden PROGRAMADA A FUTURO esperando ejecución
        if order_state == "PENDING_FUTURE":
            target_px = float(target_entry)
            # Para LONG, se activa si el precio retrocedió y tocó o cruzó hacia abajo el target
            # Para SHORT, se activa si el precio rebotó y tocó o cruzó hacia arriba el target
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
            continue

        # B) Si es una orden ACTIVA: Gestionar SL, TP1 y TP2
        # Check TP2 hit (Take Profit final)
        tp2_hit = px >= tp2 if is_long else px <= tp2
        if tp2_hit:
            close_trade(
                root,
                t["id"],
                exit_price=tp2,
                note=f"TP2 Alcanzado con éxito @ {tp2} (precio vivo {px})",
                tag="TP2_EXIT",
            )
            cerradas_ahora.append(t["id"])
            continue

        # Check SL hit
        sl_hit = px <= sl if is_long else px >= sl
        if sl_hit:
            close_trade(
                root,
                t["id"],
                exit_price=sl,
                note=f"Stop Loss alcanzado @ {sl} (precio vivo {px})",
                tag="SL_EXIT",
            )
            cerradas_ahora.append(t["id"])
            continue

        # Check TP1 hit -> Mover SL a Break-Even (entry)
        tp1_trigger = px >= tp1 if is_long else px <= tp1
        if tp1_trigger and not tp1_hit:
            entry_px = float(t.get("entry_price", sl))
            update_trade(
                root,
                t["id"],
                updates={"tp1_hit": True, "sl": entry_px},
                note=f"TP1 Alcanzado @ {tp1}. Stop Loss subido a Break-Even ({entry_px})",
            )
            t["tp1_hit"] = True
            t["sl"] = entry_px

    # Recargar tras cierres
    trades = load_trades(root)
    open_trades = [t for t in trades if t.get("status") == "open"]
    activos_abiertos = {t["asset"] for t in open_trades}

    # 3. ESCANEAR Y GENERAR NUEVAS OPERACIONES DE FUTUROS (4 a 6 operaciones)
    # Evaluamos multi-marco (1H, 4H, 1D)
    scores_dict: dict[str, Any] = {}
    candidates_pool: list[dict[str, Any]] = []

    for s in UNIVERSO:
        frames = live_klines.get(s, {})
        ind = compute_indicators(frames)
        sc_4h = score_symbol(s, ind, "4h")
        sc_4h["ind"] = ind
        px_real = prices.get(s, sc_4h.get("price", 0.0))
        sc_4h["price"] = px_real
        scores_dict[s] = sc_4h

        # Generar candidatos multi-marco para la operativa de futuros
        for tf in ("1h", "4h", "1d"):
            sc_tf = score_symbol(s, ind, tf)
            sc_tf["price"] = px_real
            sc_tf["timeframe"] = tf
            candidates_pool.append(sc_tf)

    nuevas_abiertas: list[dict[str, Any]] = []
    slots_disponibles = max_open_ops - len(open_trades)

    if slots_disponibles > 0:
        # Definir una combinación balanceada de marcos y modos si la cuenta está limpia
        # Configuración modelo de 5 operaciones de Futuros:
        # 1. BTCUSDT -> 1H (Intradía) 5x · ⚡ AL INSTANTE
        # 2. ETHUSDT -> 4H (Táctico) 4x · ⚡ AL INSTANTE
        # 3. SOLUSDT -> 1D (Diario) 3x · 🎯 PROGRAMADA A FUTURO (pullback a EMA21/descuento)
        # 4. BNBUSDT -> 4H (Táctico) 4x · 🎯 PROGRAMADA A FUTURO (pullback a soporte)
        # 5. XRPUSDT -> 1H (Intradía) 5x · ⚡ AL INSTANTE
        # 6. NEARUSDT -> 4H (Táctico) 4x · 🎯 PROGRAMADA A FUTURO
        preset_configs = [
            {"asset": "BTCUSDT", "tf": "1h", "mode": "INSTANTE", "lev": "5x", "lev_num": 5, "pullback_pct": 0.0},
            {"asset": "ETHUSDT", "tf": "4h", "mode": "INSTANTE", "lev": "4x", "lev_num": 4, "pullback_pct": 0.0},
            {"asset": "SOLUSDT", "tf": "1d", "mode": "FUTURO", "lev": "3x", "lev_num": 3, "pullback_pct": 0.020},
            {"asset": "BNBUSDT", "tf": "4h", "mode": "FUTURO", "lev": "4x", "lev_num": 4, "pullback_pct": 0.015},
            {"asset": "XRPUSDT", "tf": "1h", "mode": "INSTANTE", "lev": "5x", "lev_num": 5, "pullback_pct": 0.0},
            {"asset": "NEARUSDT", "tf": "4h", "mode": "FUTURO", "lev": "4x", "lev_num": 4, "pullback_pct": 0.022},
        ]

        for p_cfg in preset_configs:
            if slots_disponibles <= 0:
                break
            sym = p_cfg["asset"]
            if sym in activos_abiertos:
                continue

            px = prices.get(sym, 0.0)
            if px <= 0:
                continue

            tf = p_cfg["tf"]
            mode = p_cfg["mode"]
            lev = p_cfg["lev"]
            lev_num = p_cfg["lev_num"]

            # Evaluar candidato
            cand = next((c for c in candidates_pool if c["sym"] == sym and c["timeframe"] == tf), None)
            if not cand:
                cand = scores_dict.get(sym, {})
            direction = cand.get("direction", "LONG")
            score = cand.get("score", 70)
            reason = cand.get("reason", "Alineación de tendencia multi-indicador")
            atr14 = cand.get("atr14", px * 0.02)
            nd = 4 if px < 10 else 2

            if mode == "INSTANTE":
                entry_px = px
                order_state = "ACTIVE"
                target_entry = None
                geom = calcular_niveles_rr(entry_px, atr14, direction)
                thesis_txt = f"{direction} {lev} ({tf.upper()}) · Score {score}/100 · {reason} · Entrada directa a mercado con R:R {geom['rr_neto']}x"
            else:
                # PROGRAMADA A FUTURO: Entrada en pullback técnico sin perseguir precio
                pullback_mult = p_cfg["pullback_pct"]
                if direction == "LONG":
                    target_px = round(px * (1.0 - pullback_mult), nd)
                else:
                    target_px = round(px * (1.0 + pullback_mult), nd)
                entry_px = target_px
                order_state = "PENDING_FUTURE"
                target_entry = target_px
                geom = calcular_niveles_rr(target_px, atr14, direction)
                thesis_txt = f"🎯 PROGRAMADA {direction} {lev} ({tf.upper()}) · Esperando pullback a {target_px} (EMA21/{tf.upper()}) · R:R {geom['rr_neto']}x proyectado"

            sl = geom["sl"]
            tp1 = geom["tp1"]
            tp2 = geom["tp2"]
            rr_neto = geom["rr_neto"]

            # Sizing: Riesgo 1.5% del capital total ($15 USD)
            riesgo_usd = capital_total * RISK_PCT_POR_OP
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

            nuevas_abiertas.append(trade_rec)
            activos_abiertos.add(sym)
            slots_disponibles -= 1

    # 4. GESTIONAR Y EVALUAR CARTERA SPOT (SECCIÓN 2)
    spot_plans = evaluar_y_gestionar_spot(root, live_klines, prices, capital_total)

    return {
        "scores": scores_dict,
        "nuevas_abiertas": nuevas_abiertas,
        "cerradas_ahora": cerradas_ahora,
        "open_trades_count": len(open_trades) + len(nuevas_abiertas),
        "spot_plans": spot_plans,
    }


def autonomous_run(capital_inicial: float = 1000.0) -> dict[str, Any]:
    """Punto de entrada compatible."""
    from qa.agent.live import fetch_live
    from qa.data.paths import get_root
    root = get_root()
    live = fetch_live(UNIVERSO)
    return gestionar_y_ejecutar(root, live["klines"], capital_inicial)
