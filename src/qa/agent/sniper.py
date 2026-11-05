# Motor 2: "Sniper Intradía (1H — Stockbee / VCP)" — QUANT-ARENA v2
"""Motor cuantitativo intradía de alta selectividad y precisión sobre marco 1H.

Características:
1. Libro contable segregado e inmutable: ledger/user_sniper.jsonl (cadena SHA-256).
2. Capital simulado independiente: $1,000.00 USD (cero contaminación de Cruise PRO 4H).
3. Máximo 2 posiciones intradía abiertas simultáneas.
4. Patrones de entrada de alta precisión:
   - UNDERCUT_AND_RECLAIM (Stockbee Exhaustion Hammer): Barrido de liquidez bajo el
     mínimo de 5 velas de 1H con mecha de rechazo >= 40% del rango y cierre recuperador.
   - VCP_MOMENTUM_BURST (Minervini Volatility Contraction): Contracción de rango en 4 velas
     (< 0.70x ATR14) con posterior ruptura expansiva y RVOL >= 1.35x alineada a 4H.
5. Salidas rápidas y asimétricas:
   - SL inicial: extremo de mecha o 1.2x ATR14(1H).
   - TP1 (+1.8R): toma parcial del 50% y elevación inmediata de SL a Break-Even (Entry).
   - TP2 (+3.0R): toma de beneficio final del 50% restante.
6. Validación obligatoria por PreTradeDisciplineGate y Jefe de Mesa IA (brain.py).
7. Alertas a Telegram con prefijo "🎯 SNIPER INTRADÍA (1H)".
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import numpy as np

try:
    import pandas as pd
except ImportError:
    import qa._pandas_compat as pd

from qa.agent.brain import evaluar_setup_con_ia
from qa.agent.capital import load_costs
from qa.agent.chain import append_chained, read_records, verify_chain_file
from qa.agent.geometry import fee_roundtrip
from qa.agent.kronos_oracle import predict_kline_horizon
from qa.agent.notifications import notify_event
from qa.agent.skills_engine import (
    evaluate_discipline_gate,
    record_postmortem,
    update_live_excursions,
)
from qa.data.paths import get_root

SNIPER_ELITE = ["BTCUSDT", "ETHUSDT", "SOLUSDT", "SUIUSDT"]
MAX_SNIPER_POSITIONS = 2
SNIPER_BASE_RISK_USD = 20.0  # 2.0% de $1,000 USD
SNIPER_LEVERAGE = "5x"
SNIPER_LEV_NUM = 5


# =====================================================================
# 1. Contabilidad y Ledger Criptográfico Segregado
# =====================================================================


def _sniper_log_path(root: Path | None = None) -> Path:
    r = root or get_root()
    return r / "ledger" / "user_sniper.jsonl"


def verify_sniper_chain(root: Path | None = None) -> tuple[bool, int, str]:
    path = _sniper_log_path(root)
    if not path.exists():
        return True, 0, "sin operaciones sniper registradas"
    return verify_chain_file(path)


def load_sniper_trades(root: Path | None = None) -> list[dict[str, Any]]:
    """Carga las operaciones de Sniper desde user_sniper.jsonl respetando updates."""
    trades: dict[str, dict[str, Any]] = {}
    path = _sniper_log_path(root)
    if not path.exists():
        return []

    for rec in read_records(path):
        action = rec.get("action")
        tid = rec.get("id")
        if not tid:
            continue
        if action == "open":
            t = dict(rec)
            t["status"] = "open"
            trades[tid] = t
        elif action == "update" and tid in trades:
            updates = rec.get("updates", {})
            trades[tid].update(updates)
        elif action == "close" and tid in trades:
            trades[tid]["status"] = "closed"
            trades[tid]["exit_price"] = rec.get("exit_price")
            trades[tid]["exit_ts_utc"] = rec.get("ts_utc")
            trades[tid]["pnl_neto_usd"] = float(rec.get("pnl_neto_usd", 0.0))
            trades[tid]["close_tag"] = rec.get("tag", "MANUAL_CLOSE")
            trades[tid]["close_note"] = rec.get("note", "")

    return list(trades.values())


def open_sniper_trade(
    root: Path,
    asset: str,
    direction: str = "LONG",
    entry_price: float = 0.0,
    sl: float = 0.0,
    tp1: float = 0.0,
    tp2: float = 0.0,
    size_usd: float = 100.0,
    risk_usd: float = 20.0,
    dist_sl: float = 1.0,
    pattern: str = "",
    thesis: str = "",
    kind: str | None = None,
    ai_verdict: str = "EJECUTAR_AHORA",
    ai_confidence: int = 80,
    ai_reasoning: str = "",
) -> dict[str, Any]:
    """Registra una nueva posición en el libro independiente user_sniper.jsonl."""
    if kind is not None:
        direction = "SHORT" if "short" in kind.lower() else "LONG"
    tid = uuid.uuid4().hex[:8]
    now_iso = datetime.now(UTC).isoformat(timespec="seconds")
    trade_kind = "future_long" if direction == "LONG" else "future_short"
    margin_usd = round(size_usd / SNIPER_LEV_NUM, 2)

    rec = {
        "action": "open",
        "id": tid,
        "ts_utc": now_iso,
        "asset": asset.upper(),
        "kind": trade_kind,
        "timeframe": "1h",
        "entry_price": float(entry_price),
        "size_usd": float(size_usd),
        "initial_size_usd": float(size_usd),
        "sl": float(sl),
        "initial_sl": float(sl),
        "tp1": float(tp1),
        "tp2": float(tp2),
        "tp1_hit": False,
        "risk_usd": float(risk_usd),
        "dist_sl": float(dist_sl),
        "leverage": SNIPER_LEVERAGE,
        "margin_usd": margin_usd,
        "pattern": pattern,
        "thesis": thesis,
        "ai_verdict": ai_verdict,
        "ai_confidence": ai_confidence,
        "ai_reasoning": ai_reasoning,
        "mfe_r": 0.0,
        "mae_r": 0.0,
        "status": "open",
        "partial_realized_pnl_usd": 0.0,
        "partial_fees_usd": 0.0,
        "partial_closed_size_usd": 0.0,
        "partial_exits": [],
    }
    append_chained(_sniper_log_path(root), rec)
    return rec


def update_sniper_trade(
    root: Path,
    trade_id: str,
    updates: dict[str, Any],
    note: str = "",
) -> None:
    rec = {
        "action": "update",
        "id": trade_id,
        "ts_utc": datetime.now(UTC).isoformat(timespec="seconds"),
        "updates": updates,
        "note": note,
    }
    append_chained(_sniper_log_path(root), rec)


def close_sniper_trade(
    root: Path,
    trade_id: str,
    exit_price: float,
    pnl_neto_usd: float,
    note: str = "",
    tag: str = "SNIPER_EXIT",
) -> dict[str, Any]:
    rec = {
        "action": "close",
        "id": trade_id,
        "ts_utc": datetime.now(UTC).isoformat(timespec="seconds"),
        "exit_price": float(exit_price),
        "pnl_neto_usd": round(float(pnl_neto_usd), 2),
        "note": note,
        "tag": tag,
    }
    append_chained(_sniper_log_path(root), rec)
    return rec


def compute_sniper_equity(
    trades: list[dict[str, Any]],
    live_prices: dict[str, float],
    starting_capital: float = 1000.0,
) -> dict[str, Any]:
    """Calcula el balance y equity en tiempo real de la cuenta Sniper ($1,000 USD base)."""
    realized_pnl = 0.0
    floating_pnl = 0.0
    closed_count = 0
    wins = 0

    for t in trades:
        if t.get("status") == "closed":
            p = float(t.get("pnl_neto_usd") or 0.0)
            realized_pnl += p
            closed_count += 1
            if p > 0:
                wins += 1
        elif t.get("status") == "open":
            sym = t.get("asset", "")
            px = live_prices.get(sym, float(t.get("entry_price", 0.0)))
            entry = float(t.get("entry_price", 0.0))
            sz = float(t.get("size_usd", 0.0))
            is_long = t.get("kind") != "future_short"
            if entry > 0:
                p_gross = sz * ((px / entry) - 1.0) if is_long else sz * (1.0 - (px / entry))
                p_fee = sz * 0.0007  # taker fee aproximado
                floating_pnl += (p_gross - p_fee)

    total_equity = starting_capital + realized_pnl + floating_pnl
    win_rate = (wins / closed_count * 100.0) if closed_count > 0 else 0.0

    return {
        "starting_capital": starting_capital,
        "realized_pnl": round(realized_pnl, 2),
        "floating_pnl": round(floating_pnl, 2),
        "total_equity": round(total_equity, 2),
        "closed_count": closed_count,
        "win_rate": round(win_rate, 1),
    }


# =====================================================================
# 2. Detección de Patrones Sniper de Alta Precisión (1H)
# =====================================================================


def detect_undercut_and_reclaim(
    df_1h: pd.DataFrame,
    df_4h: pd.DataFrame | None = None,
) -> dict[str, Any] | None:
    """Stockbee Exhaustion Hammer:

    Barrido de liquidez bajo el mínimo de 5 velas de 1H con mecha de rechazo
    inferior >= 40% del rango total de la vela y cierre recuperador con volumen.
    """
    if df_1h is None or len(df_1h) < 10:
        return None

    c = df_1h["close"].astype(float)
    o = df_1h["open"].astype(float)
    h = df_1h["high"].astype(float)
    low_px = df_1h["low"].astype(float)
    v = (
        df_1h["volume"].astype(float)
        if "volume" in df_1h.columns
        else pd.Series(np.ones(len(df_1h)), index=df_1h.index)
    )

    last_idx = len(df_1h) - 1
    c_last = float(c.iloc[last_idx])
    o_last = float(o.iloc[last_idx])
    h_last = float(h.iloc[last_idx])
    l_last = float(low_px.iloc[last_idx])

    # Mínimo de las 5 velas anteriores (t-5 a t-1)
    min_low_5 = float(low_px.iloc[last_idx - 5 : last_idx].min())

    # 1. Condición de barrido: el mínimo perforó el soporte anterior
    swept_liquidity = l_last < min_low_5

    # 2. Mecha inferior de absorción >= 40% del rango
    candle_range = h_last - l_last
    if candle_range <= 0:
        return None
    lower_wick = min(o_last, c_last) - l_last
    wick_ratio = lower_wick / (candle_range + 1e-9)
    strong_rejection = wick_ratio >= 0.40

    # 3. Cierre recuperador sobre el mínimo previo y vela de absorción
    reclaimed = c_last >= min_low_5 and c_last >= o_last

    # 4. Volumen RVOL >= 1.15
    v_mean_20 = float(v.iloc[max(0, last_idx - 20) : last_idx].mean())
    rvol = float(v.iloc[last_idx] / (v_mean_20 + 1e-9)) if v_mean_20 > 0 else 1.0

    if swept_liquidity and strong_rejection and reclaimed and rvol >= 1.10:
        sl = round(l_last * 0.998, 4 if c_last < 10 else 2)
        dist_sl = abs(c_last - sl)
        tp1 = round(c_last + 1.8 * dist_sl, 4 if c_last < 10 else 2)
        tp2 = round(c_last + 3.0 * dist_sl, 4 if c_last < 10 else 2)

        return {
            "pattern": "UNDERCUT_AND_RECLAIM",
            "direction": "LONG",
            "entry_price": c_last,
            "sl": sl,
            "tp1": tp1,
            "tp2": tp2,
            "dist_sl": dist_sl,
            "rvol": round(rvol, 2),
            "wick_ratio": round(wick_ratio * 100.0, 1),
            "swept_level": min_low_5,
            "reason": (
                f"Stockbee Undercut: Barrido de soporte {min_low_5:.2f} con mecha "
                f"de rechazo del {wick_ratio*100:.0f}% y RVOL {rvol:.2f}x"
            ),
        }

    return None


def detect_vcp_momentum_burst(
    df_1h: pd.DataFrame,
    df_4h: pd.DataFrame | None = None,
) -> dict[str, Any] | None:
    """Minervini Volatility Contraction Pattern:

    Contracción del rango en 4 velas (< 0.70x ATR14) seguida de vela de ruptura expansiva
    con RVOL >= 1.35x a favor de la tendencia de 4H.
    """
    if df_1h is None or len(df_1h) < 22:
        return None

    c = df_1h["close"].astype(float)
    h = df_1h["high"].astype(float)
    low_px = df_1h["low"].astype(float)
    v = (
        df_1h["volume"].astype(float)
        if "volume" in df_1h.columns
        else pd.Series(np.ones(len(df_1h)), index=df_1h.index)
    )

    last_idx = len(df_1h) - 1

    # Calcular ATR14 de 1H
    tr = np.maximum(h - low_px, np.maximum(np.abs(h - c.shift(1)), np.abs(low_px - c.shift(1))))
    atr14_series = tr.rolling(14).mean().dropna()
    if len(atr14_series) < 10:
        return None
    curr_atr = float(atr14_series.iloc[-1])

    # Contracción previa en velas t-4 a t-1
    ranges_4 = h.iloc[last_idx - 4 : last_idx] - low_px.iloc[last_idx - 4 : last_idx]
    avg_prev_range = float(ranges_4.mean())
    contraction_confirmed = avg_prev_range < (0.70 * curr_atr)

    # Vela actual t: expansión
    burst_range = float(h.iloc[last_idx] - low_px.iloc[last_idx])
    is_expanding = burst_range >= (1.10 * curr_atr)

    # RVOL >= 1.35
    v_mean = float(v.iloc[max(0, last_idx - 20) : last_idx].mean())
    rvol = float(v.iloc[last_idx] / (v_mean + 1e-9)) if v_mean > 0 else 1.0

    # Tendencia de 4H
    trend_long = True
    if df_4h is not None and len(df_4h) >= 21:
        c4 = df_4h["close"].astype(float)
        ema9 = float(c4.ewm(span=9, adjust=False).mean().iloc[-1])
        ema21 = float(c4.ewm(span=21, adjust=False).mean().iloc[-1])
        trend_long = ema9 >= ema21

    c_last = float(c.iloc[last_idx])
    prior_high_4 = float(h.iloc[last_idx - 4 : last_idx].max())
    prior_low_4 = float(low_px.iloc[last_idx - 4 : last_idx].min())

    if contraction_confirmed and is_expanding and rvol >= 1.30:
        if trend_long and c_last > prior_high_4:
            sl = round(c_last - 1.2 * curr_atr, 4 if c_last < 10 else 2)
            dist_sl = abs(c_last - sl)
            return {
                "pattern": "VCP_MOMENTUM_BURST",
                "direction": "LONG",
                "entry_price": c_last,
                "sl": sl,
                "tp1": round(c_last + 1.8 * dist_sl, 4 if c_last < 10 else 2),
                "tp2": round(c_last + 3.0 * dist_sl, 4 if c_last < 10 else 2),
                "dist_sl": dist_sl,
                "rvol": round(rvol, 2),
                "atr14": curr_atr,
                "reason": (
                    f"Minervini VCP: Contracción {avg_prev_range:.2f} < 0.70*ATR con "
                    f"ruptura alcista expansiva y RVOL {rvol:.2f}x"
                ),
            }
        elif not trend_long and c_last < prior_low_4:
            sl = round(c_last + 1.2 * curr_atr, 4 if c_last < 10 else 2)
            dist_sl = abs(c_last - sl)
            return {
                "pattern": "VCP_MOMENTUM_BURST",
                "direction": "SHORT",
                "entry_price": c_last,
                "sl": sl,
                "tp1": round(c_last - 1.8 * dist_sl, 4 if c_last < 10 else 2),
                "tp2": round(c_last - 3.0 * dist_sl, 4 if c_last < 10 else 2),
                "dist_sl": dist_sl,
                "rvol": round(rvol, 2),
                "atr14": curr_atr,
                "reason": (
                    f"Minervini VCP: Contracción {avg_prev_range:.2f} < 0.70*ATR con "
                    f"ruptura bajista expansiva y RVOL {rvol:.2f}x"
                ),
            }

    return None


# =====================================================================
# 3. Motor Operativo Sniper: Gestión de Abiertas y Apertura de Nuevas
# =====================================================================


def evaluar_y_gestionar_sniper(
    root: Path,
    live_klines: dict[str, dict[str, pd.DataFrame]],
    live_prices: dict[str, float],
    starting_capital: float = 1000.0,
    news_items: list[Any] | None = None,
    funding_rates: dict[str, float] | None = None,
) -> dict[str, Any]:
    """Bucle operativo del Motor 2: Sniper Intradía (1H).

    1. Monitorea y gestiona salidas rápidas de operaciones abiertas (+1.8R BE, +3.0R TP2, SL).
    2. Actualiza en caliente el MFE y MAE en R de cada operación.
    3. Si hay cupo (< 2 abiertas), busca patrones Undercut & Reclaim o VCP Burst.
    4. Valida por PreTradeDisciplineGate y por Jefe de Mesa IA (brain.py).
    """
    try:
        costs = load_costs(root)
    except Exception:
        costs = {"future_long": {"taker": 0.0005}, "future_short": {"taker": 0.0005}}
    trades = load_sniper_trades(root)
    open_trades = [t for t in trades if t.get("status") == "open"]
    cerradas_ahora: list[str] = []

    # 1. GESTIONAR POSICIONES SNIPER ABIERTAS
    for t in open_trades:
        sym = t.get("asset", "")
        px = live_prices.get(sym, float(t.get("entry_price", 0.0)))
        if px <= 0:
            continue

        # Actualizar MFE y MAE en vivo
        update_live_excursions(t, px)
        update_sniper_trade(
            root,
            t["id"],
            {"mfe_r": t["mfe_r"], "mae_r": t["mae_r"]},
            note="Actualización telemetría MFE/MAE",
        )

        entry = float(t.get("entry_price", px))
        sl = float(t.get("sl", entry * 0.98))
        tp1 = float(t.get("tp1", entry * 1.02))
        tp2 = float(t.get("tp2", entry * 1.04))
        is_long = t.get("kind") != "future_short"
        tp1_hit = bool(t.get("tp1_hit", False))

        # Check TP2 final (+3.0R): Cierre total
        tp2_reached = px >= tp2 if is_long else px <= tp2
        if tp2 > 0 and tp2_reached:
            sz_curr = float(t.get("size_usd", 0.0))
            ratio = (tp2 / entry) - 1.0 if is_long else 1.0 - (tp2 / entry)
            pnl_bruto = sz_curr * ratio
            fees = sz_curr * fee_roundtrip("future_long", costs)
            pnl_net = pnl_bruto - fees

            close_sniper_trade(
                root,
                t["id"],
                exit_price=tp2,
                pnl_neto_usd=pnl_net,
                note=f"🎯 TP2 (+3.0R) alcanzado en Sniper @ {tp2}",
                tag="SNIPER_TP2_EXIT",
            )
            t["status"] = "closed"
            cerradas_ahora.append(t["id"])
            record_postmortem(root, t, exit_price=tp2, pnl_neto_usd=pnl_net)
            notify_event(
                "TRADE_CLOSED",
                {
                    "asset": sym,
                    "tag": "SNIPER_TP2_EXIT",
                    "exit_price": tp2,
                    "pnl_neto_usd": pnl_net,
                    "pnl_pct": (pnl_net / sz_curr) * 100.0 if sz_curr > 0 else 0.0,
                    "note": f"🎯 SNIPER TP2 Alcanzado (+3.0R) en {sym}. PnL: +${pnl_net:.2f} USD",
                },
            )
            continue

        # Check SL hit
        sl_reached = px <= sl if is_long else px >= sl
        if sl_reached:
            sz_curr = float(t.get("size_usd", 0.0))
            ratio = (sl / entry) - 1.0 if is_long else 1.0 - (sl / entry)
            pnl_bruto = sz_curr * ratio
            fees = sz_curr * fee_roundtrip("future_long", costs)
            pnl_net = pnl_bruto - fees

            tag_exit = "SNIPER_BE_EXIT" if tp1_hit else "SNIPER_SL_EXIT"
            close_sniper_trade(
                root,
                t["id"],
                exit_price=sl,
                pnl_neto_usd=pnl_net,
                note=f"Salida de protección Sniper @ {sl} ({tag_exit})",
                tag=tag_exit,
            )
            t["status"] = "closed"
            cerradas_ahora.append(t["id"])
            record_postmortem(root, t, exit_price=sl, pnl_neto_usd=pnl_net)
            notify_event(
                "TRADE_CLOSED",
                {
                    "asset": sym,
                    "tag": tag_exit,
                    "exit_price": sl,
                    "pnl_neto_usd": pnl_net,
                    "pnl_pct": (pnl_net / sz_curr) * 100.0 if sz_curr > 0 else 0.0,
                    "note": f"Salida Sniper en {sym} ({tag_exit}). PnL: ${pnl_net:+.2f} USD",
                },
            )
            continue

        # Check TP1 hit (+1.8R): Cierre parcial del 50% y mover SL a Break-Even
        tp1_reached = px >= tp1 if is_long else px <= tp1
        if tp1_reached and not tp1_hit:
            sz_curr = float(t.get("size_usd", 0.0))
            part_sz = round(sz_curr * 0.50, 2)
            rem_sz = round(sz_curr - part_sz, 2)
            pnl_part_bruto = (
                part_sz * ((tp1 / entry) - 1.0) if is_long else part_sz * (1.0 - (tp1 / entry))
            )
            fees_part = part_sz * fee_roundtrip("future_long", costs)
            pnl_part_net = pnl_part_bruto - fees_part

            # Break-even estricto: SL anclado a entry
            new_sl = entry

            part_exits = list(t.get("partial_exits") or [])
            part_exits.append(
                {
                    "ts_utc": datetime.now(UTC).isoformat(timespec="seconds"),
                    "exit_price": tp1,
                    "closed_size_usd": part_sz,
                    "pnl_neto_usd": round(pnl_part_net, 2),
                    "tag": "SNIPER_TP1_PARTIAL_50",
                }
            )

            updates = {
                "tp1_hit": True,
                "size_usd": rem_sz,
                "sl": new_sl,
                "partial_realized_pnl_usd": round(
                    float(t.get("partial_realized_pnl_usd", 0.0)) + pnl_part_net, 2
                ),
                "partial_closed_size_usd": round(
                    float(t.get("partial_closed_size_usd", 0.0)) + part_sz, 2
                ),
                "partial_exits": part_exits,
            }
            update_sniper_trade(
                root,
                t["id"],
                updates,
                note=f"🎯 TP1 Sniper (+1.8R) @ {tp1}. 50% cerrado y SL elevado a BE ({new_sl})",
            )
            t.update(updates)
            notify_event(
                "TP1_PARTIAL",
                {
                    "asset": sym,
                    "exit_price": tp1,
                    "pnl_usd": round(pnl_part_net, 2),
                    "new_sl": new_sl,
                    "remaining_size_usd": rem_sz,
                    "note": f"🎯 SNIPER TP1: 50% caja asegurada en {sym} y Stop en Break-Even.",
                },
            )

    # Recargar trades tras cierres
    trades = load_sniper_trades(root)
    open_trades = [t for t in trades if t.get("status") == "open"]
    open_assets = {t["asset"] for t in open_trades}

    # 2. ESCANEO Y APERTURA DE NUEVAS OPORTUNIDADES SNIPER (Cupo máx 2)
    nuevas_sniper: list[dict[str, Any]] = []
    slots = MAX_SNIPER_POSITIONS - len(open_trades)
    kronos_1h_map: dict[str, dict[str, Any]] = {}

    for sym_k in SNIPER_ELITE:
        df_1h_k = live_klines.get(sym_k, {}).get("1h")
        kronos_1h_map[sym_k] = predict_kline_horizon(
            df_1h_k, symbol=sym_k, timeframe="1h", horizon=6
        )

    if slots > 0:
        for sym in SNIPER_ELITE:
            if slots <= 0:
                break
            if sym in open_assets:
                continue

            frames = live_klines.get(sym, {})
            df_1h = frames.get("1h")
            df_4h = frames.get("4h")
            if df_1h is None or len(df_1h) < 15:
                continue

            px = live_prices.get(sym, float(df_1h["close"].iloc[-1]))
            if px <= 0:
                continue

            # Buscar Patrones
            setup = detect_undercut_and_reclaim(df_1h, df_4h)
            if not setup:
                setup = detect_vcp_momentum_burst(df_1h, df_4h)

            if not setup:
                continue

            dir_c = setup["direction"]
            entry_px = float(setup["entry_price"])
            sl_px = float(setup["sl"])
            tp1_px = float(setup["tp1"])
            tp2_px = float(setup["tp2"])
            dist_sl = float(setup["dist_sl"])
            pattern_name = setup["pattern"]
            reason_txt = setup["reason"]
            kronos_1h = kronos_1h_map.get(sym) or {}

            # Obtener EMA21 de 1H para el Gate
            c_1h = df_1h["close"].astype(float)
            e21_1h = (
                float(c_1h.ewm(span=21, adjust=False).mean().iloc[-1])
                if len(c_1h) >= 21
                else entry_px
            )

            # Pre-Trade Discipline Gate (incluye alineación con Kronos 1H)
            gate = evaluate_discipline_gate(
                symbol=sym,
                direction=dir_c,
                current_price=entry_px,
                ema21=e21_1h,
                current_heat_pct=(len(open_trades) * 2.0),
                trade_risk_pct=2.0,
                max_heat_allowed=16.0,
                circuit_breaker_status="NORMAL",
                news_items=news_items,
                funding_rate=(funding_rates or {}).get(sym),
                kronos_forecast=kronos_1h,
            )
            if not gate["gate_passed"]:
                continue

            # Validación Cognitiva con el Jefe de Mesa IA (Gemini 2.5 Flash + Kronos)
            sw_high_1h = float(df_1h["high"].iloc[-15:].max())
            sw_low_1h = float(df_1h["low"].iloc[-15:].min())
            ai_eval = evaluar_setup_con_ia(
                symbol=sym,
                direction=dir_c,
                current_price=entry_px,
                indicators={"ema21": e21_1h, "rsi14": 52.0, "atr14": dist_sl},
                swing_high=sw_high_1h,
                swing_low=sw_low_1h,
                btc_macro_bullish=True,
                news_headlines=[getattr(n, "title", str(n)) for n in (news_items or [])[:5]],
                klines_4h=df_4h,
                root=root,
                kronos_forecast=kronos_1h,
            )

            if ai_eval.get("veredicto") == "VETAR_TRAMPA":
                continue

            # Sizing exacto: $20.00 USD de riesgo con 5x apalancamiento
            risk_usd = SNIPER_BASE_RISK_USD
            dist_sl_pct = dist_sl / (entry_px + 1e-9)
            if dist_sl_pct <= 0:
                dist_sl_pct = 0.015
            size_usd = round(risk_usd / max(0.005, dist_sl_pct), 2)

            thesis = (
                f"🎯 SNIPER INTRADÍA (1H) · {pattern_name} · {dir_c} {SNIPER_LEVERAGE} · "
                f"{reason_txt} · [🧠 IA {ai_eval.get('model_used', 'Gemini')}: "
                f"{ai_eval.get('razonamiento', '')}]"
            )

            trade_rec = open_sniper_trade(
                root,
                asset=sym,
                direction=dir_c,
                entry_price=entry_px,
                sl=sl_px,
                tp1=tp1_px,
                tp2=tp2_px,
                size_usd=size_usd,
                risk_usd=risk_usd,
                dist_sl=dist_sl,
                pattern=pattern_name,
                thesis=thesis,
                ai_verdict=ai_eval.get("veredicto", "EJECUTAR_AHORA"),
                ai_confidence=int(ai_eval.get("confianza", 80)),
                ai_reasoning=str(ai_eval.get("razonamiento", "")),
            )
            nuevas_sniper.append(trade_rec)
            open_assets.add(sym)
            slots -= 1

            notify_event(
                "ORDER_OPEN",
                {
                    "asset": sym,
                    "timeframe": "1h",
                    "kind": trade_rec["kind"],
                    "leverage": SNIPER_LEVERAGE,
                    "entry_price": entry_px,
                    "sl": sl_px,
                    "tp1": tp1_px,
                    "tp2": tp2_px,
                    "score": 90,
                    "risk_usd": risk_usd,
                    "risk_pct": 0.02,
                    "thesis": thesis,
                    "entry_mode": "INSTANTE",
                    "ai_reasoning": ai_eval.get("razonamiento"),
                    "ai_verdict": f"🎯 SNIPER 1H ({pattern_name})",
                },
            )

    equity_status = compute_sniper_equity(
        load_sniper_trades(root), live_prices, starting_capital=starting_capital
    )

    return {
        "status": "ok",
        "open_trades": [t for t in load_sniper_trades(root) if t.get("status") == "open"],
        "closed_count": equity_status["closed_count"],
        "equity_status": equity_status,
        "nuevas_abiertas": nuevas_sniper,
        "cerradas_ahora": cerradas_ahora,
        "kronos_1h": kronos_1h_map,
    }
