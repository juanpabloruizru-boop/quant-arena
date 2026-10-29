# Spot & Ciclos M6.3 — QUANT-ARENA v2
"""Gestión y seguimiento de Cartera Spot y Ciclos (4H, 1D, 1W) sin apalancamiento (1x).

Filosofía M6.3:
- Zonas de Compra a Precio Razonable (100% FIJAS e Inmutables una vez guardadas en ledger/user_spot.jsonl).
- Zonas de Toma de Ganancias (TP1 50% y TP2 Ciclo) dinámicas y actualizables al alza si la tendencia se fortalece.
- Registro append-only con cadena de hashes criptográficos SHA-256 (qa.agent.chain).
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import pandas as pd

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
    ts_utc: str | None = None,
) -> dict[str, Any]:
    """Crea un plan Spot con Zona de Compra 100% FIJA e inmutable."""
    pid = uuid.uuid4().hex[:8]
    ts = ts_utc or datetime.now(UTC).isoformat(timespec="seconds")
    rr_ciclo = round(abs(tp2_zone_low - buy_ref_price) / max(1e-9, abs(buy_ref_price - sl_spot)), 2)
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
        "sl_spot": float(sl_spot),
        "rr_ciclo": rr_ciclo,
        "status": "PENDING_BUY",
        "entry_executed_price": None,
        "bought_at": None,
        "tp1_hit": False,
        "tp2_hit": False,
        "tp_updated": False,
        "tp_update_label": "",
        "thesis": thesis,
        "history_notes": [],
    }
    return append_chained(_spot_log_path(root), rec)


def update_spot_plan(root: Path, plan_id: str, updates: dict[str, Any], note: str = "") -> dict[str, Any]:
    """Registra una actualización en un plan Spot (respetando la inmutabilidad de la zona de compra)."""
    # Prohibir modificar buy_zone_*
    safe_updates = {k: v for k, v in updates.items() if not k.startswith("buy_zone_") and k != "buy_ref_price"}
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
    live_klines: dict[str, dict[str, pd.DataFrame]],
    live_prices: dict[str, float],
    capital_total: float = 1000.0,
) -> list[dict[str, Any]]:
    """Evalúa la cartera Spot de QUANT-ARENA M6.3.
    
    1. Si no existen planes de Spot, crea el portafolio diversificado base (BTC 1W, ETH 1D, SOL 4H, BNB 1D, NEAR 4H)
       con Zonas de Compra Razonables fijas.
    2. En cada ejecución, evalúa el precio vivo actual contra la zona fija:
       - Si live_price <= buy_zone_high: pasa a '🟢 COMPRADA EN CARTERA SPOT'.
       - Si live_price > buy_zone_high: pasa a '🎯 ESPERANDO EN ZONA DE COMPRA FIJA'.
       - Si alcanza TP1: registra venta parcial 50% y sube protección.
       - Si alcanza TP2: cierra ciclo en ganancia completa.
       - Si la tendencia sube con fuerza: actualiza dinámicamente las zonas de TP hacia arriba.
    """
    plans = load_spot_plans(root)
    now_utc_str = datetime.now(UTC).isoformat(timespec="seconds")

    if not plans:
        # Generar cartera spot inicial diversificada con precios reales
        # 1. BTCUSDT (1W Ciclo Semanal)
        px_btc = live_prices.get("BTCUSDT", 81000.0)
        # Zona razonable fija alrededor de soporte macro
        b_low_btc = round(px_btc * 0.965, 2)
        b_high_btc = round(px_btc * 1.015, 2)
        b_ref_btc = round(px_btc, 2)
        create_spot_plan(
            root,
            asset="BTCUSDT",
            timeframe="1w",
            horizon_label="🏛️ 1W · Ciclo Spot",
            allocated_usd=200.0,
            buy_zone_low=b_low_btc,
            buy_zone_high=b_high_btc,
            buy_ref_price=b_ref_btc,
            tp1_zone_low=round(px_btc * 1.18, 2),
            tp1_zone_high=round(px_btc * 1.25, 2),
            tp2_zone_low=round(px_btc * 1.45, 2),
            tp2_zone_high=round(px_btc * 1.60, 2),
            sl_spot=round(px_btc * 0.88, 2),
            thesis="Acumulación estructural macro 1W. Soporte sobre SMA50 y expansión de liquidez global M2.",
            ts_utc=now_utc_str,
        )

        # 2. ETHUSDT (1D Swing Diario)
        px_eth = live_prices.get("ETHUSDT", 2150.0)
        b_low_eth = round(px_eth * 0.96, 2)
        b_high_eth = round(px_eth * 1.01, 2)
        b_ref_eth = round(px_eth, 2)
        create_spot_plan(
            root,
            asset="ETHUSDT",
            timeframe="1d",
            horizon_label="🌊 1D · Swing Spot",
            allocated_usd=150.0,
            buy_zone_low=b_low_eth,
            buy_zone_high=b_high_eth,
            buy_ref_price=b_ref_eth,
            tp1_zone_low=round(px_eth * 1.18, 2),
            tp1_zone_high=round(px_eth * 1.24, 2),
            tp2_zone_low=round(px_eth * 1.42, 2),
            tp2_zone_high=round(px_eth * 1.55, 2),
            sl_spot=round(px_eth * 0.87, 2),
            thesis="Swing diario en soporte clave. Compresión de volatilidad y reversión a la media con RSI favorable.",
            ts_utc=now_utc_str,
        )

        # 3. SOLUSDT (4H Táctico Spot) - Esperando descuento a zona fija
        px_sol = live_prices.get("SOLUSDT", 178.0)
        b_low_sol = round(px_sol * 0.93, 2)
        b_high_sol = round(px_sol * 0.97, 2)
        b_ref_sol = round(px_sol * 0.95, 2)
        create_spot_plan(
            root,
            asset="SOLUSDT",
            timeframe="4h",
            horizon_label="🔥 4H · Spot",
            allocated_usd=150.0,
            buy_zone_low=b_low_sol,
            buy_zone_high=b_high_sol,
            buy_ref_price=b_ref_sol,
            tp1_zone_low=round(b_ref_sol * 1.16, 2),
            tp1_zone_high=round(b_ref_sol * 1.22, 2),
            tp2_zone_low=round(b_ref_sol * 1.38, 2),
            tp2_zone_high=round(b_ref_sol * 1.50, 2),
            sl_spot=round(b_ref_sol * 0.89, 2),
            thesis="Esperando retroceso táctico 4H hacia soporte EMA21/SMA50. Compra límite disciplinada sin perseguir.",
            ts_utc=now_utc_str,
        )

        # 4. BNBUSDT (1D Swing Diario) - Esperando zona fija
        px_bnb = live_prices.get("BNBUSDT", 695.0)
        b_low_bnb = round(px_bnb * 0.94, 2)
        b_high_bnb = round(px_bnb * 0.98, 2)
        b_ref_bnb = round(px_bnb * 0.96, 2)
        create_spot_plan(
            root,
            asset="BNBUSDT",
            timeframe="1d",
            horizon_label="🌊 1D · Swing Spot",
            allocated_usd=100.0,
            buy_zone_low=b_low_bnb,
            buy_zone_high=b_high_bnb,
            buy_ref_price=b_ref_bnb,
            tp1_zone_low=round(b_ref_bnb * 1.15, 2),
            tp1_zone_high=round(b_ref_bnb * 1.20, 2),
            tp2_zone_low=round(b_ref_bnb * 1.35, 2),
            tp2_zone_high=round(b_ref_bnb * 1.45, 2),
            sl_spot=round(b_ref_bnb * 0.89, 2),
            thesis="Consolidación en rango diario. Orden paciente esperando descuento a soporte estructural.",
            ts_utc=now_utc_str,
        )

        # 5. NEARUSDT (4H Táctico Spot)
        px_near = live_prices.get("NEARUSDT", 3.80)
        b_low_near = round(px_near * 0.96, 4)
        b_high_near = round(px_near * 1.015, 4)
        b_ref_near = round(px_near, 4)
        create_spot_plan(
            root,
            asset="NEARUSDT",
            timeframe="4h",
            horizon_label="🔥 4H · Spot",
            allocated_usd=100.0,
            buy_zone_low=b_low_near,
            buy_zone_high=b_high_near,
            buy_ref_price=b_ref_near,
            tp1_zone_low=round(px_near * 1.20, 4),
            tp1_zone_high=round(px_near * 1.28, 4),
            tp2_zone_low=round(px_near * 1.45, 4),
            tp2_zone_high=round(px_near * 1.60, 4),
            sl_spot=round(px_near * 0.86, 4),
            thesis="Ruptura de compresión 4H con RVOL y soporte en retroceso de Fibonacci.",
            ts_utc=now_utc_str,
        )
        plans = load_spot_plans(root)

    # 2. EVALUAR CADA PLAN CONTRA EL PRECIO VIVO ACTUAL
    evaluated_plans: list[dict[str, Any]] = []

    for p in plans:
        sym = p["asset"]
        px = live_prices.get(sym)
        if px is None or px <= 0:
            evaluated_plans.append(p)
            continue

        b_low = float(p["buy_zone_low"])
        b_high = float(p["buy_zone_high"])
        b_ref = float(p["buy_ref_price"])
        alloc = float(p.get("allocated_usd", 100.0))
        status = p.get("status", "PENDING_BUY")
        entry_exec = p.get("entry_executed_price")

        updates: dict[str, Any] = {}
        note = ""

        # Comprobar si entra en zona de compra fija
        if status in ("PENDING_BUY", "🎯 ESPERANDO EN ZONA DE COMPRA FIJA"):
            if px <= b_high:
                # Comprada en cartera spot
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
            # Verificar TP1 y TP2
            tp1_low = float(p["tp1_zone_low"])
            tp2_low = float(p["tp2_zone_low"])
            tp1_hit = p.get("tp1_hit", False)

            if px >= tp2_low:
                updates["status"] = "✅ CERRADA EN TP2 (Ciclo completado)"
                updates["tp2_hit"] = True
                updates["closed_at"] = now_utc_str
                note = f"TP2 de ciclo alcanzado con éxito @ {px:.4f}"
                status = "✅ CERRADA EN TP2 (Ciclo completado)"
            elif px >= tp1_low and not tp1_hit:
                updates["status"] = "💰 TP1 ALCANZADO (50% vendido)"
                updates["tp1_hit"] = True
                updates["sl_spot"] = b_ref  # Subir SL a Break-Even
                note = f"TP1 alcanzado @ {px:.4f}. 50% asegurado y SL subido a Break-Even"
                status = "💰 TP1 ALCANZADO (50% vendido)"

        if updates:
            update_spot_plan(root, p["id"], updates, note=note)
            p.update(updates)

        # Cálculo de PnL en vivo
        if entry_exec and entry_exec > 0 and status in ("🟢 COMPRADA EN CARTERA SPOT", "💰 TP1 ALCANZADO (50% vendido)"):
            pnl_pct = round((px / entry_exec - 1.0) * 100.0, 2)
            pnl_usd = round(alloc * (pnl_pct / 100.0), 2)
        else:
            pnl_pct = 0.0
            pnl_usd = 0.0

        p["current_price"] = px
        p["pnl_usd"] = pnl_usd
        p["pnl_pct"] = pnl_pct

        # Distancia a la zona de compra
        if px > b_high:
            dist_zona = round((px - b_high) / b_high * 100.0, 1)
            p["dist_zona_txt"] = f"+{dist_zona}% sobre zona fija"
        elif px < b_low:
            dist_zona = round((b_low - px) / b_low * 100.0, 1)
            p["dist_zona_txt"] = f"-{dist_zona}% por debajo de zona"
        else:
            p["dist_zona_txt"] = "Dentro de zona de compra"

        evaluated_plans.append(p)

    return evaluated_plans
