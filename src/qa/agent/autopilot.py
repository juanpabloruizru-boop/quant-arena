# Autopilot Motor Autónomo M6 — QUANT-ARENA v2
"""Motor de decisión y ejecución autónomo "Conquistador" para paper trading simulado.

Cuando se ejecuta `qa agent run`, este módulo actúa como un Trader Cuantitativo
Autónomo sobre una cuenta simulada de $1,000 USD, gestionando operaciones abiertas,
abriendo nuevas posiciones y registrando todo en ledger/user_trades.jsonl
respetando la cadena de hashes criptográficos SHA-256 (tracker.py / chain.py).
"""

from __future__ import annotations

import math
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

from qa.agent.tracker import close_trade, load_trades, open_trade

UNIVERSO = [
    "BTCUSDT", "ETHUSDT", "SOLUSDT", "BNBUSDT", "XRPUSDT",
    "ZECUSDT", "NEARUSDT", "SUIUSDT", "UNIUSDT", "DOGEUSDT",
]

RISK_PCT_POR_OP = 0.015  # 1.5% del patrimonio ($15 USD sobre $1,000)
MAX_OPERACIONES_ABIERTAS = 5
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
    for tf in ("1h", "4h", "1d"):
        df = klines_dict.get(tf)
        if df is None or df.empty or len(df) < 20:
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


def score_symbol(sym: str, ind: dict[str, Any]) -> dict[str, Any]:
    """Algoritmo 'Conquistador': Evalúa LONG y SHORT sobre 1h, 4h y 1d y calcula Score 0..100."""
    tf4 = ind.get("4h") or ind.get("1d") or ind.get("1h")
    tf1d = ind.get("1d") or tf4
    tf1h = ind.get("1h") or tf4

    if not tf4:
        return {"sym": sym, "score": 0, "direction": "NEUTRAL", "reason": "Sin datos suficientes"}

    score_long = 0
    score_short = 0
    reasons_long: list[str] = []
    reasons_short: list[str] = []

    # 1. Alineación EMAs (4h y 1d) (hasta 30 pts)
    if tf4["ema9"] > tf4["ema21"]:
        score_long += 20
        reasons_long.append("EMA9>21(4H)")
    else:
        score_short += 20
        reasons_short.append("EMA9<21(4H)")

    if tf1d and tf1d["close"] > tf1d["sma50"]:
        score_long += 10
        reasons_long.append("Close>SMA50(1D)")
    elif tf1d:
        score_short += 10
        reasons_short.append("Close<SMA50(1D)")

    # 2. MACD Histograma (hasta 25 pts)
    if tf4["macd_hist"] > 0:
        score_long += 25
        reasons_long.append("MACD_hist alcista")
    else:
        score_short += 25
        reasons_short.append("MACD_hist bajista")

    # 3. RSI momentum y zonas dinámicas (hasta 25 pts)
    rsi_4h = tf4["rsi"]
    if 50 <= rsi_4h <= 72:
        score_long += 25
        reasons_long.append(f"RSI {rsi_4h:.1f} momentum alcista")
    elif rsi_4h < 35:
        score_long += 20
        reasons_long.append(f"RSI {rsi_4h:.1f} rebote sobreventa")

    if 28 <= rsi_4h <= 50:
        score_short += 25
        reasons_short.append(f"RSI {rsi_4h:.1f} momentum bajista")
    elif rsi_4h > 65:
        score_short += 20
        reasons_short.append(f"RSI {rsi_4h:.1f} agotamiento sobrecompra")

    # 4. RVOL (hasta 20 pts)
    rvol_val = tf4.get("rvol", 1.0)
    if rvol_val >= 1.0:
        score_long += 20
        score_short += 20
        reasons_long.append(f"RVOL {rvol_val:.1f}x")
        reasons_short.append(f"RVOL {rvol_val:.1f}x")
    else:
        score_long += 10
        score_short += 10

    # Determinar dirección ganadora
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
        "rsi": rsi_4h,
        "macd_hist": tf4["macd_hist"],
        "atr14": tf4["atr14"],
        "price": tf4["close"],
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
    return {
        "dist_sl": dist_sl,
        "sl": round(sl, 4 if entry < 10 else 2),
        "tp1": round(tp1, 4 if entry < 10 else 2),
        "tp2": round(tp2, 4 if entry < 10 else 2),
        "rr_neto": rr_neto,
    }


def gestionar_y_ejecutar(
    root: Path,
    live_klines: dict[str, dict[str, pd.DataFrame]],
    capital_total: float = 1000.0,
    max_open_ops: int = 5,
    live_prices: dict[str, float] | None = None,
) -> dict[str, Any]:
    """Gestiona posiciones abiertas (SL, TP1, TP2) y abre nuevas operaciones
    respetando el score multi-indicador y la cadena criptográfica de user_trades.jsonl.
    """
    trades = load_trades(root)
    open_trades = [t for t in trades if t.get("status") == "open"]

    # Precios actuales por símbolo: usar live_prices (ticker/price spot) o último close disponible
    prices: dict[str, float] = {}
    if live_prices:
        prices.update(live_prices)
    for s in UNIVERSO:
        if s not in prices:
            frames = live_klines.get(s, {})
            for tf in ("1h", "4h", "1d"):
                df = frames.get(tf)
                if df is not None and not df.empty:
                    prices[s] = float(df["close"].iloc[-1])
                    break

    # 1. GESTIONAR OPERACIONES ABIERTAS
    cerradas_ahora: list[str] = []
    modificadas: list[str] = []

    for t in open_trades:
        sym = t.get("asset")
        px = prices.get(sym)
        if px is None:
            continue
        entry = float(t.get("entry_price", 0.0))
        sl = float(t.get("sl", 0.0))
        tp2 = float(t.get("tp", 0.0))
        tp1 = float(t.get("tp1", entry + (tp2 - entry) * 0.55))
        is_long = t.get("kind") != "future_short"
        tp1_hit = bool(t.get("tp1_hit", False))

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
            modificadas.append(t["id"])

    # Recargar tras cierres
    trades = load_trades(root)
    open_trades = [t for t in trades if t.get("status") == "open"]
    activos_abiertos = {t["asset"] for t in open_trades}

    # 2. EVALUAR Y ABRIR NUEVAS POSICIONES SI HAY MENOS DE 5
    scores_dict: dict[str, Any] = {}
    evaluated_list: list[dict[str, Any]] = []

    for s in UNIVERSO:
        frames = live_klines.get(s, {})
        ind = compute_indicators(frames)
        sc = score_symbol(s, ind)
        sc["ind"] = ind
        # Asegurar precio vivo exacto
        px_real = prices.get(s, sc.get("price", 0.0))
        sc["price"] = px_real
        scores_dict[s] = sc
        evaluated_list.append(sc)

    # Ordenar por score descendente
    evaluated_list.sort(key=lambda x: x["score"], reverse=True)

    nuevas_abiertas: list[dict[str, Any]] = []
    slots_disponibles = max_open_ops - len(open_trades)

    if slots_disponibles > 0:
        for cand in evaluated_list:
            if slots_disponibles <= 0:
                break
            sym = cand["sym"]
            if sym in activos_abiertos:
                continue

            px = prices.get(sym, cand["price"])
            if px <= 0:
                continue

            direction = cand["direction"]
            score = cand["score"]
            reason = cand["reason"]
            atr14 = cand["atr14"]

            # Niveles R:R calculados estrictamente desde el precio vivo
            geom = calcular_niveles_rr(px, atr14, direction)
            sl = geom["sl"]
            tp1 = geom["tp1"]
            tp2 = geom["tp2"]
            rr_neto = geom["rr_neto"]

            # Sizing: Riesgo 1.5% del capital ($15 USD)
            riesgo_usd = capital_total * RISK_PCT_POR_OP
            dist_sl_pct = abs(px - sl) / px
            leverage = 4
            kind = "future_long" if direction == "LONG" else "future_short"
            tamano_usd = round(riesgo_usd / dist_sl_pct, 2)
            margen_usd = round(tamano_usd / leverage, 2)

            note_text = (
                f"{direction} {leverage}x (4H) · Score {score}/100 · {reason} · R:R {rr_neto}x "
                f"| Margen: ${margen_usd} | TP1: {tp1} | TP2: {tp2}"
            )

            trade_rec = open_trade(
                root,
                asset=sym,
                kind=kind,
                timeframe="4h",
                entry_price=px,
                size_usd=tamano_usd,
                sl=sl,
                tp=tp2,
                note=note_text,
                example=False,
                tag="AUTOPILOT_M6",
                rr_neto_inicial=rr_neto,
                rr_forzado=False,
            )
            # Añadir metadatos en memoria para el render actual
            trade_rec["tp1"] = tp1
            trade_rec["tp2"] = tp2
            trade_rec["leverage"] = f"{leverage}x"
            trade_rec["margin_usd"] = margen_usd
            trade_rec["risk_usd"] = riesgo_usd
            trade_rec["rr_neto"] = rr_neto
            trade_rec["reason_open"] = note_text

            nuevas_abiertas.append(trade_rec)
            activos_abiertos.add(sym)
            slots_disponibles -= 1

    return {
        "scores": scores_dict,
        "nuevas_abiertas": nuevas_abiertas,
        "cerradas_ahora": cerradas_ahora,
        "open_trades_count": len(open_trades) + len(nuevas_abiertas),
    }


def autonomous_run(capital_inicial: float = 1000.0) -> dict[str, Any]:
    """Punto de entrada compatible."""
    from qa.agent.live import fetch_live
    from qa.data.paths import get_root
    root = get_root()
    live = fetch_live(UNIVERSO)
    return gestionar_y_ejecutar(root, live["klines"], capital_inicial)
