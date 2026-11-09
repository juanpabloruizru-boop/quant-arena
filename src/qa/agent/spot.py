# Spot & Ciclos M6.5 — QUANT-ARENA v2
"""Gestión y seguimiento de Cartera Spot y Ciclos (1D / 1W) sin apalancamiento (1x).

Filosofía Cuantitativa M6.5:
1. Zonas de Compra a Precio Razonable:
   - Banda cuantitativa de acumulación [Min, Max] calculada por distancia a SMA200(1D),
     soportes estructurales semanales y compresión ATR.
   - 100% FIJAS e Inmutables una vez guardadas en ledger/user_spot.jsonl.
2. Los 3 Precios Objetivo de Venta:
   - 🎯 TP1 (Recuperación de Base - 30% de venta): Resistencia estructural previa.
   - 🎯 TP2 (Expansión de Ciclo - 40% de venta): Extensión Fibonacci 1.618.
   - 🎯 TP3 (Euforia / Clímax - 30% restante): Extensión Fibonacci 2.618 o RSI(1W) > 80.
3. Aislamiento Contable Estricto:
   - Registro append-only con cadena de hashes SHA-256 en ledger/user_spot.jsonl,
     completamente segregado del libro de futuros.
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import numpy as np

from qa.agent.chain import append_chained, read_records, verify_chain_file


def _spot_log_path(root: Path) -> Path:
    return root / "ledger" / "user_spot.jsonl"


def verify_spot_chain(root: Path) -> tuple[bool, int, str]:
    path = _spot_log_path(root)
    if not path.exists():
        return True, 0, "sin operaciones spot registradas"
    return verify_chain_file(path)


def load_spot_plans(root: Path) -> list[dict[str, Any]]:
    """Carga los planes de Spot desde user_spot.jsonl."""
    plans: dict[str, dict[str, Any]] = {}
    path = _spot_log_path(root)
    if not path.exists():
        return []
    for rec in read_records(path):
        action = rec.get("action")
        pid = rec.get("id")
        if action == "create":
            plans[pid] = dict(rec)
        elif action == "update" and pid in plans:
            updates = rec.get("updates", {})
            plans[pid].update(updates)
            if "history_notes" in rec:
                plans[pid].setdefault("history_notes", []).extend(rec["history_notes"])
        elif action == "close" and pid in plans:
            plans[pid].update({
                "status": "closed",
                "closed_at": rec.get("ts_utc"),
                "exit_price": rec.get("exit_price"),
                "close_note": rec.get("note", ""),
            })
    return list(plans.values())


def calcular_zona_razonable_y_3_tps(
    asset: str,
    frames: dict[str, Any],
    current_price: float,
) -> dict[str, Any]:
    """Calcula cuantitativamente la Banda de Compra a Precio Razonable y los 3 TP de Ciclo."""
    df_1d = frames.get("1d")
    df_1w = frames.get("1w")
    nd = 4 if current_price < 10 else 2

    # 1. Distancia a SMA200(1D) y compresión ATR
    if df_1d is not None and len(df_1d) >= 20:
        c_1d = df_1d["close"].astype(float)
        w200 = min(200, len(c_1d))
        sma200_1d = float(c_1d.rolling(w200).mean().iloc[-1])
        dist_sma200_pct = round((current_price / sma200_1d - 1.0) * 100.0, 1)

        h_1d = df_1d["high"].astype(float)
        l_1d = df_1d["low"].astype(float)
        tr = np.maximum(
            h_1d - l_1d, np.maximum(np.abs(h_1d - c_1d.shift(1)), np.abs(l_1d - c_1d.shift(1)))
        )
        atr_1d = float(tr.rolling(14).mean().iloc[-1])
    else:
        sma200_1d = current_price * 0.95
        dist_sma200_pct = 5.0
        atr_1d = current_price * 0.03

    # 2. Soportes y Resistencias Semanales / Diarios
    if df_1w is not None and len(df_1w) >= 8:
        l_1w = df_1w["low"].astype(float)
        h_1w = df_1w["high"].astype(float)
        w_look = min(26, len(df_1w))
        support_macro = float(l_1w.iloc[-w_look:].min())
        resistance_macro = float(h_1w.iloc[-w_look:].max())
    elif df_1d is not None and len(df_1d) >= 20:
        l_1d = df_1d["low"].astype(float)
        h_1d = df_1d["high"].astype(float)
        support_macro = float(l_1d.iloc[-60:].min())
        resistance_macro = float(h_1d.iloc[-60:].max())
    else:
        support_macro = current_price * 0.85
        resistance_macro = current_price * 1.30

    range_ciclo = max(resistance_macro - support_macro, current_price * 0.35)

    # 3. Banda Cuantitativa de Compra Razonable [Min, Max]
    buy_zone_min = round(max(support_macro * 0.98, current_price * 0.88), nd)
    buy_zone_max = round(min(max(support_macro * 1.08, sma200_1d * 1.04), current_price * 1.03), nd)
    if buy_zone_max <= buy_zone_min:
        buy_zone_max = round(buy_zone_min * 1.08, nd)

    base_ref = current_price if current_price <= buy_zone_max else buy_zone_max

    # 4. Los 3 Precios Objetivo de Venta
    # 🎯 TP1 (Recuperación de Base - 30% venta): Resistencia estructural previa
    tp1 = round(max(resistance_macro, base_ref * 1.25), nd)
    tp1_gain_pct = round((tp1 / current_price - 1.0) * 100.0, 1)

    # 🎯 TP2 (Expansión de Ciclo - 40% venta): Extensión Fibonacci 1.618
    tp2 = round(support_macro + 1.618 * range_ciclo, nd)
    if tp2 <= tp1:
        tp2 = round(base_ref * 1.618, nd)
    tp2_gain_pct = round((tp2 / current_price - 1.0) * 100.0, 1)

    # 🎯 TP3 (Euforia / Clímax - 30% restante): Extensión Fibonacci 2.618
    tp3 = round(support_macro + 2.618 * range_ciclo, nd)
    if tp3 <= tp2:
        tp3 = round(base_ref * 2.618, nd)
    tp3_gain_pct = round((tp3 / current_price - 1.0) * 100.0, 1)

    sl_ciclo = round(support_macro * 0.88, nd)

    if current_price < buy_zone_min:
        zone_status = "⚠️ ACUMULACIÓN PROFUNDA (< Zona Mínima)"
        zone_badge = "b-warn"
    elif current_price <= buy_zone_max:
        zone_status = "🟢 EN ZONA DE COMPRA RAZONABLE"
        zone_badge = "b-ok"
    else:
        dist_over = round((current_price / buy_zone_max - 1.0) * 100.0, 1)
        zone_status = f"🎯 ESPERANDO DESCUENTO (+{dist_over}% sobre zona)"
        zone_badge = "b-futuro"

    return {
        "buy_zone_min": buy_zone_min,
        "buy_zone_max": buy_zone_max,
        "support_macro": support_macro,
        "resistance_macro": resistance_macro,
        "dist_sma200_pct": dist_sma200_pct,
        "atr_1d": atr_1d,
        "tp1": tp1,
        "tp1_pct": tp1_gain_pct,
        "tp2": tp2,
        "tp2_pct": tp2_gain_pct,
        "tp3": tp3,
        "tp3_pct": tp3_gain_pct,
        "sl_ciclo": sl_ciclo,
        "zone_status": zone_status,
        "zone_badge": zone_badge,
    }


def create_spot_plan(
    root: Path,
    asset: str,
    timeframe: str,
    horizon_label: str,
    allocated_usd: float,
    buy_zone_low: float,
    buy_zone_high: float,
    buy_ref_price: float,
    tp1_zone_low: float,
    tp1_zone_high: float,
    tp2_zone_low: float,
    tp2_zone_high: float,
    sl_spot: float,
    thesis: str,
    tp3_price: float | None = None,
    ts_utc: str | None = None,
) -> dict[str, Any]:
    """Crea un plan Spot con Zona de Compra 100% FIJA e inmutable y los 3 TPs de ciclo."""
    pid = uuid.uuid4().hex[:8]
    ts = ts_utc or datetime.now(UTC).isoformat(timespec="seconds")
    rr_ciclo = round(
        abs(tp2_zone_low - buy_ref_price) / max(1e-9, abs(buy_ref_price - sl_spot)), 2
    )
    rec = {
        "action": "create",
        "id": pid,
        "ts_utc": ts,
        "asset": asset.upper(),
        "timeframe": timeframe.lower(),
        "horizon_label": horizon_label,
        "allocated_usd": float(allocated_usd),
        "buy_zone_low": float(buy_zone_low),
        "buy_zone_high": float(buy_zone_high),
        "buy_ref_price": float(buy_ref_price),
        "tp1_zone_low": float(tp1_zone_low),
        "tp1_zone_high": float(tp1_zone_high),
        "tp2_zone_low": float(tp2_zone_low),
        "tp2_zone_high": float(tp2_zone_high),
        "tp3_price": float(tp3_price) if tp3_price else round(tp2_zone_high * 1.45, 2),
        "sl_spot": float(sl_spot),
        "rr_ciclo": rr_ciclo,
        "status": "PENDING_BUY",
        "entry_executed_price": None,
        "bought_at": None,
        "tp1_hit": False,
        "tp2_hit": False,
        "tp3_hit": False,
        "tp_updated": False,
        "tp_update_label": "",
        "thesis": thesis,
        "history_notes": [],
    }
    return append_chained(_spot_log_path(root), rec)


def update_spot_plan(
    root: Path, plan_id: str, updates: dict[str, Any], note: str = ""
) -> dict[str, Any]:
    """Registra una actualización en un plan Spot (respetando la inmutabilidad de la zona fija)."""
    safe_updates = {
        k: v
        for k, v in updates.items()
        if not k.startswith("buy_zone_") and k != "buy_ref_price"
    }
    rec: dict[str, Any] = {
        "action": "update",
        "id": plan_id,
        "ts_utc": datetime.now(UTC).isoformat(timespec="seconds"),
        "updates": safe_updates,
    }
    if note:
        rec["history_notes"] = [note]
    return append_chained(_spot_log_path(root), rec)


def evaluar_y_gestionar_spot(
    root: Path,
    live_klines: dict[str, dict[str, Any]],
    live_prices: dict[str, float],
    capital_total: float = 1000.0,
) -> list[dict[str, Any]]:
    """Evalúa la cartera Spot de QUANT-ARENA M6.5.

    1. Si no existen planes de Spot, crea el portafolio diversificado base
       (BTC 1W, ETH 1D, SOL 1D, SUI 1W, BNB 1D) con Zonas de Compra Razonables fijas.
    2. En cada ejecución, evalúa el precio vivo actual contra la banda cuantitativa
       y proyecta los 3 Precios Objetivo de Venta (TP1 30%, TP2 40%, TP3 30%).
    """
    plans = load_spot_plans(root)
    now_utc_str = datetime.now(UTC).isoformat(timespec="seconds")

    if not plans:
        # Generar cartera spot inicial diversificada con precios reales
        # 1. BTCUSDT (1W Ciclo Semanal)
        px_btc = live_prices.get("BTCUSDT", 81000.0)
        z_btc = calcular_zona_razonable_y_3_tps("BTCUSDT", live_klines.get("BTCUSDT", {}), px_btc)
        create_spot_plan(
            root,
            asset="BTCUSDT",
            timeframe="1w",
            horizon_label="🏛️ 1W · Ciclo Spot",
            allocated_usd=250.0,
            buy_zone_low=z_btc["buy_zone_min"],
            buy_zone_high=z_btc["buy_zone_max"],
            buy_ref_price=px_btc,
            tp1_zone_low=z_btc["tp1"],
            tp1_zone_high=round(z_btc["tp1"] * 1.05, 2),
            tp2_zone_low=z_btc["tp2"],
            tp2_zone_high=round(z_btc["tp2"] * 1.08, 2),
            tp3_price=z_btc["tp3"],
            sl_spot=z_btc["sl_ciclo"],
            thesis=(
                "Acumulación macro 1W. Soporte sobre SMA50 y expansión de ciclo institucional ETF."
            ),
            ts_utc=now_utc_str,
        )

        # 2. ETHUSDT (1D Swing Spot)
        px_eth = live_prices.get("ETHUSDT", 2300.0)
        z_eth = calcular_zona_razonable_y_3_tps("ETHUSDT", live_klines.get("ETHUSDT", {}), px_eth)
        create_spot_plan(
            root,
            asset="ETHUSDT",
            timeframe="1d",
            horizon_label="🌊 1D · Swing Spot",
            allocated_usd=250.0,
            buy_zone_low=z_eth["buy_zone_min"],
            buy_zone_high=z_eth["buy_zone_max"],
            buy_ref_price=px_eth,
            tp1_zone_low=z_eth["tp1"],
            tp1_zone_high=round(z_eth["tp1"] * 1.05, 2),
            tp2_zone_low=z_eth["tp2"],
            tp2_zone_high=round(z_eth["tp2"] * 1.08, 2),
            tp3_price=z_eth["tp3"],
            sl_spot=z_eth["sl_ciclo"],
            thesis=(
                "Swing diario en soporte clave. Compresión de volatilidad y reversión a la media."
            ),
            ts_utc=now_utc_str,
        )

        # 3. SOLUSDT (1D Spot Ciclo)
        px_sol = live_prices.get("SOLUSDT", 175.0)
        z_sol = calcular_zona_razonable_y_3_tps("SOLUSDT", live_klines.get("SOLUSDT", {}), px_sol)
        create_spot_plan(
            root,
            asset="SOLUSDT",
            timeframe="1d",
            horizon_label="🌊 1D · Spot",
            allocated_usd=250.0,
            buy_zone_low=z_sol["buy_zone_min"],
            buy_zone_high=z_sol["buy_zone_max"],
            buy_ref_price=px_sol,
            tp1_zone_low=z_sol["tp1"],
            tp1_zone_high=round(z_sol["tp1"] * 1.05, 2),
            tp2_zone_low=z_sol["tp2"],
            tp2_zone_high=round(z_sol["tp2"] * 1.08, 2),
            tp3_price=z_sol["tp3"],
            sl_spot=z_sol["sl_ciclo"],
            thesis="Zona de acumulación paciente esperando retroceso a soporte estructural.",
            ts_utc=now_utc_str,
        )

        # 4. SUIUSDT (1W Ciclo Alpha)
        px_sui = live_prices.get("SUIUSDT", 2.10)
        z_sui = calcular_zona_razonable_y_3_tps("SUIUSDT", live_klines.get("SUIUSDT", {}), px_sui)
        create_spot_plan(
            root,
            asset="SUIUSDT",
            timeframe="1w",
            horizon_label="🏛️ 1W · Ciclo Alpha",
            allocated_usd=250.0,
            buy_zone_low=z_sui["buy_zone_min"],
            buy_zone_high=z_sui["buy_zone_max"],
            buy_ref_price=px_sui,
            tp1_zone_low=z_sui["tp1"],
            tp1_zone_high=round(z_sui["tp1"] * 1.05, 4),
            tp2_zone_low=z_sui["tp2"],
            tp2_zone_high=round(z_sui["tp2"] * 1.08, 4),
            tp3_price=z_sui["tp3"],
            sl_spot=z_sui["sl_ciclo"],
            thesis=(
                "Motor alfa primario de ciclo. Banda cuantitativa calculada para expansión 3x-8x."
            ),
            ts_utc=now_utc_str,
        )
        plans = load_spot_plans(root)

    # 2. EVALUAR CADA PLAN CONTRA EL PRECIO VIVO ACTUAL Y PROYECTAR LOS 3 TPs
    evaluated_plans: list[dict[str, Any]] = []

    for p in plans:
        sym = p["asset"]
        px = live_prices.get(sym)
        if px is None or px <= 0:
            evaluated_plans.append(p)
            continue

        frames = live_klines.get(sym, {})
        z_metrics = calcular_zona_razonable_y_3_tps(sym, frames, px)

        b_low = float(p.get("buy_zone_low", z_metrics["buy_zone_min"]))
        b_high = float(p.get("buy_zone_high", z_metrics["buy_zone_max"]))
        b_ref = float(p.get("buy_ref_price", px))
        alloc = float(p.get("allocated_usd", 100.0))
        status = p.get("status", "PENDING_BUY")
        entry_exec = p.get("entry_executed_price")

        # 3 Precios Objetivo Cuantitativos
        tp1 = float(p.get("tp1_zone_low") or z_metrics["tp1"])
        tp2 = float(p.get("tp2_zone_low") or z_metrics["tp2"])
        tp3 = float(p.get("tp3_price") or z_metrics["tp3"])

        tp1_pct = round((tp1 / px - 1.0) * 100.0, 1)
        tp2_pct = round((tp2 / px - 1.0) * 100.0, 1)
        tp3_pct = round((tp3 / px - 1.0) * 100.0, 1)

        updates: dict[str, Any] = {}
        note = ""

        # Comprobar entrada en zona de compra razonable
        if status in ("PENDING_BUY", "🎯 ESPERANDO EN ZONA DE COMPRA FIJA"):
            if px <= b_high:
                entry_exec = px
                updates["status"] = "🟢 COMPRADA EN CARTERA SPOT"
                updates["entry_executed_price"] = px
                updates["bought_at"] = now_utc_str
                note = f"Entrada ejecutada dentro de zona fija @ {px:.4f}"
                status = "🟢 COMPRADA EN CARTERA SPOT"
            else:
                updates["status"] = "🎯 ESPERANDO EN ZONA DE COMPRA FIJA"
                status = "🎯 ESPERANDO EN ZONA DE COMPRA FIJA"
        elif status == "🟢 COMPRADA EN CARTERA SPOT":
            # Verificar escalamiento de los 3 TPs
            if px >= tp3:
                updates["status"] = "🏆 CERRADA EN TP3 (Ciclo 100% Completado)"
                updates["tp3_hit"] = True
                updates["closed_at"] = now_utc_str
                note = f"TP3 de clímax alcanzado con éxito @ {px:.4f}"
                status = "🏆 CERRADA EN TP3 (Ciclo 100% Completado)"
            elif px >= tp2 and not p.get("tp2_hit"):
                updates["status"] = "🚀 TP2 ALCANZADO (40% vendido - 70% total)"
                updates["tp2_hit"] = True
                note = f"TP2 de ciclo alcanzado @ {px:.4f}. 40% adicional asegurado."
                status = "🚀 TP2 ALCANZADO (40% vendido - 70% total)"
            elif px >= tp1 and not p.get("tp1_hit"):
                updates["status"] = "💰 TP1 ALCANZADO (30% vendido - Base recuperada)"
                updates["tp1_hit"] = True
                updates["sl_spot"] = b_ref
                note = f"TP1 alcanzado @ {px:.4f}. 30% asegurado y SL subido a Break-Even."
                status = "💰 TP1 ALCANZADO (30% vendido - Base recuperada)"

        if updates:
            update_spot_plan(root, p["id"], updates, note=note)
            p.update(updates)

        # Cálculo de PnL en vivo
        if entry_exec and entry_exec > 0 and (
            "COMPRADA" in status or "TP1" in status or "TP2" in status
        ):
            pnl_pct = round((px / entry_exec - 1.0) * 100.0, 2)
            pnl_usd = round(alloc * (pnl_pct / 100.0), 2)
        else:
            pnl_pct = 0.0
            pnl_usd = 0.0

        p["current_price"] = px
        p["pnl_usd"] = pnl_usd
        p["pnl_pct"] = pnl_pct

        # Campos enriquecidos para el Dashboard y Reportes
        p["buy_zone_min"] = b_low
        p["buy_zone_max"] = b_high
        p["tp1"] = tp1
        p["tp1_pct"] = tp1_pct
        p["tp2"] = tp2
        p["tp2_pct"] = tp2_pct
        p["tp3"] = tp3
        p["tp3_pct"] = tp3_pct
        p["dist_sma200_pct"] = z_metrics["dist_sma200_pct"]

        # Distancia a la zona de compra razonable
        if px > b_high:
            dist_zona = round((px - b_high) / b_high * 100.0, 1)
            p["dist_zona_txt"] = f"+{dist_zona}% sobre zona razonable"
            p["zone_status"] = f"🎯 ESPERANDO DESCUENTO (+{dist_zona}%)"
            p["zone_badge"] = "b-futuro"
        elif px < b_low:
            dist_zona = round((b_low - px) / b_low * 100.0, 1)
            p["dist_zona_txt"] = f"-{dist_zona}% por debajo de zona"
            p["zone_status"] = "⚠️ ACUMULACIÓN PROFUNDA (< Zona Mínima)"
            p["zone_badge"] = "b-warn"
        else:
            p["dist_zona_txt"] = "Dentro de zona de compra razonable"
            p["zone_status"] = "🟢 EN ZONA DE COMPRA RAZONABLE"
            p["zone_badge"] = "b-ok"

        evaluated_plans.append(p)

    return evaluated_plans
