# ruff: noqa: E501
# Audit M6.3 — QUANT-ARENA v2
"""Auditoría del historial de operaciones del USUARIO y AUTOPILOT (M6.3).

Métricas contables y desgloses separados para:
1. PESTAÑA 1: FUTUROS (Al Instante & Programadas a Futuro, 1H · 4H · 1D)
2. PESTAÑA 2: SPOT & CICLOS (4H · 1D · 1W)
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

from qa.agent.capital import realized_pnl_usd


def _parse_ts(ts: str | None) -> datetime | None:
    if not ts:
        return None
    try:
        dt = datetime.fromisoformat(str(ts).replace("Z", "+00:00"))
        return dt if dt.tzinfo else dt.replace(tzinfo=UTC)
    except Exception:
        return None


def _duration_txt(opened: str | None, closed: str | None) -> str:
    if not opened:
        return "—"
    try:
        t0 = _parse_ts(opened)
        if not t0:
            return "—"
        t1 = _parse_ts(closed) or datetime.now(UTC)
        d = t1 - t0
        if d.days > 0:
            return f"{d.days}d {d.seconds // 3600}h"
        mins = d.seconds // 60
        hours = mins // 60
        if hours > 0:
            return f"{hours}h {mins % 60}m"
        return f"{mins}m"
    except (ValueError, TypeError):
        return "—"


def closed_rows(trades: list[dict[str, Any]], costs: dict[str, Any]) -> list[dict[str, Any]]:
    """Tabla de operaciones cerradas con PnL neto, %, R y R:R inicial."""
    rows: list[dict[str, Any]] = []
    for t in trades:
        if t.get("status") != "closed":
            continue
        entry = float(t["entry_price"])
        exit_px = float(t.get("exit_price", entry))
        size = float(t.get("size_usd", 0.0))
        pnl = realized_pnl_usd(t, costs)
        sl = t.get("sl")
        r_mult: float | None = None
        risk_frac: float | None = None
        if sl is not None and entry > 0:
            risk_frac = abs(entry - float(sl)) / entry
            if risk_frac > 0:
                r_mult = round(pnl["pnl_neto_usd"] / (size * risk_frac), 3)
        rr_ini: float | None = None
        tp = t.get("tp")
        if sl is not None and tp is not None and entry > 0 and abs(entry - float(sl)) > 0:
            rr_ini = round(abs(float(tp) - entry) / abs(entry - float(sl)), 2)
        rows.append(
            {
                "id": t.get("id"),
                "asset": t.get("asset"),
                "kind": t.get("kind"),
                "timeframe": t.get("timeframe"),
                "opened_at": t.get("ts_utc"),
                "closed_at": t.get("closed_at"),
                "duracion": _duration_txt(t.get("ts_utc"), t.get("closed_at")),
                "entry": entry,
                "exit": exit_px,
                "size_usd": size,
                "rr_inicial_bruto": rr_ini,
                "pnl_bruto_usd": pnl["pnl_bruto_usd"],
                "fees_est_usd": pnl["fees_estimadas_usd"],
                "pnl_neto_usd": pnl["pnl_neto_usd"],
                "pnl_pct": pnl["pnl_pct"],
                "r_multiplo": r_mult,
                "tag": t.get("tag") or t.get("close_tag") or "",
                "note": t.get("note", ""),
                "close_note": t.get("close_note", ""),
                "example": bool(t.get("example", False)),
            }
        )
    rows.sort(key=lambda r: str(r.get("closed_at") or ""))
    return rows


def max_drawdown_realizado_usd(rows: list[dict[str, Any]]) -> float:
    """Peor caída (peak-to-trough, en $) del PnL neto ACUMULADO por cierre."""
    cum = 0.0
    peak = 0.0
    mdd = 0.0
    for r in rows:
        cum += float(r["pnl_neto_usd"])
        peak = max(peak, cum)
        mdd = max(mdd, peak - cum)
    return round(mdd, 2)


def audit_summary(
    rows: list[dict[str, Any]], capital_aportado: float | None = None
) -> dict[str, Any]:
    """Métricas globales de auditoría + desglose por tag."""
    n = len(rows)
    if n == 0:
        return {
            "total_cerradas": 0,
            "nota": "sin operaciones cerradas registradas",
        }
    wins = [r for r in rows if float(r["pnl_neto_usd"]) > 0]
    losses = [r for r in rows if float(r["pnl_neto_usd"]) <= 0]
    neto = round(sum(float(r["pnl_neto_usd"]) for r in rows), 2)
    bruto_win = sum(float(r["pnl_neto_usd"]) for r in wins)
    bruto_loss = abs(sum(float(r["pnl_neto_usd"]) for r in losses))
    rs = [float(r["r_multiplo"]) for r in rows if r.get("r_multiplo") is not None]
    rotacion = sum(float(r["size_usd"]) for r in rows)

    def _best_worst(key: str) -> dict[str, Any] | None:
        with_key = [r for r in rows if r.get(key) is not None]
        if not with_key:
            return None
        srt = sorted(with_key, key=lambda r: float(r[key]))
        worst, best = srt[0], srt[-1]
        return {
            "mejor": {"id": best["id"], "asset": best["asset"], "valor": best[key]},
            "peor": {"id": worst["id"], "asset": worst["asset"], "valor": worst[key]},
        }

    por_tag: dict[str, dict[str, Any]] = {}
    for r in rows:
        tag = str(r.get("tag") or "(sin tag)")
        d = por_tag.setdefault(
            tag, {"trades": 0, "ganadoras": 0, "pnl_neto_usd": 0.0, "suma_R": 0.0, "n_con_R": 0}
        )
        d["trades"] += 1
        d["ganadoras"] += 1 if float(r["pnl_neto_usd"]) > 0 else 0
        d["pnl_neto_usd"] = round(d["pnl_neto_usd"] + float(r["pnl_neto_usd"]), 2)
        if r.get("r_multiplo") is not None:
            d["suma_R"] = round(d["suma_R"] + float(r["r_multiplo"]), 3)
            d["n_con_R"] += 1
    for d in por_tag.values():
        d["win_rate_pct"] = round(d["ganadoras"] / d["trades"] * 100.0, 1) if d["trades"] else None
        d["R_medio"] = round(d["suma_R"] / d["n_con_R"], 3) if d["n_con_R"] else None

    return {
        "total_cerradas": n,
        "win_rate_pct": round(len(wins) / n * 100.0, 1),
        "pnl_neto_usd": neto,
        "pnl_neto_pct_rotacion": round(neto / rotacion * 100.0, 2) if rotacion > 0 else None,
        "pnl_neto_pct_aportado": (
            round(neto / capital_aportado * 100.0, 2)
            if capital_aportado and capital_aportado > 0
            else None
        ),
        "profit_factor": (
            round(bruto_win / bruto_loss, 2)
            if bruto_loss > 0
            else ("n/a (sin pérdidas cerradas)" if bruto_win > 0 else "n/a")
        ),
        "esperanza_usd_por_trade": round(neto / n, 2),
        "esperanza_R_por_trade": round(sum(rs) / len(rs), 3) if rs else None,
        "rr_medio_realizado_R": round(sum(rs) / len(rs), 3) if rs else None,
        "mejor_peor_usd": _best_worst("pnl_neto_usd"),
        "mejor_peor_R": _best_worst("r_multiplo"),
        "max_drawdown_realizado_usd": max_drawdown_realizado_usd(rows),
        "trades_sin_sl": sum(1 for r in rows if r.get("r_multiplo") is None),
        "por_tag": por_tag,
        "generado_utc": datetime.now(UTC).isoformat(timespec="seconds"),
    }


def run_audit(
    trades: list[dict[str, Any]], costs: dict[str, Any], capital_aportado: float | None = None
) -> dict[str, Any]:
    rows = closed_rows(trades, costs)
    return {"rows": rows, "summary": audit_summary(rows, capital_aportado)}


# ─────────────────────────────────────────────────────────────────────────────
# M6.3: AUDITORÍA DE FUTUROS (PESTAÑA 1)
# ─────────────────────────────────────────────────────────────────────────────

def audit_futures(
    trades: list[dict[str, Any]],
    costs: dict[str, Any],
    live_prices: dict[str, float] | None = None,
) -> dict[str, Any]:
    """Genera la estructura de auditoría para la Pestaña 1 de Futuros."""
    prices = live_prices or {}
    closed = closed_rows(trades, costs)
    opens = [t for t in trades if t.get("status") == "open"]

    master_rows: list[dict[str, Any]] = []

    # 1. Agregar abiertas
    for t in opens:
        sym = t.get("asset", "")
        entry = float(t.get("entry_price", 0.0))
        px = prices.get(sym, entry)
        order_state = t.get("order_state", "ACTIVE")
        mode = t.get("entry_mode", "INSTANTE")
        is_long = t.get("kind") != "future_short"
        size = float(t.get("size_usd", 0.0))
        lev = t.get("leverage", "4x")
        tf = t.get("timeframe", "4h")

        if order_state == "PENDING_FUTURE":
            pnl_usd = 0.0
            pnl_pct = 0.0
            status_txt = "🎯 PROGRAMADA (Espera Pullback)"
        else:
            diff = (px / entry - 1.0) if entry > 0 else 0.0
            pnl_pct = round(diff * 100.0 if is_long else -diff * 100.0, 2)
            pnl_usd = round(size * (pnl_pct / 100.0), 2)
            status_txt = "🟢 ACTIVA (En Mercado)"

        sl = t.get("sl")
        tp2 = t.get("tp")
        tp1 = t.get("tp1") or (round(entry + (tp2 - entry) * 0.55, 2) if tp2 else None)
        rr = t.get("rr_neto_inicial") or (round(abs(tp2 - entry) / max(1e-9, abs(entry - sl)), 2) if sl and tp2 else 2.80)

        master_rows.append({
            "id": t.get("id"),
            "asset": sym,
            "kind": t.get("kind", "future_long"),
            "leverage": lev,
            "timeframe": tf,
            "entry_mode": mode,
            "order_state": order_state,
            "status": status_txt,
            "opened_at": t.get("ts_utc"),
            "closed_at": "",
            "duracion": _duration_txt(t.get("ts_utc"), None),
            "entry": entry,
            "exit": px,
            "live_price": px,
            "size_usd": size,
            "margin_usd": t.get("margin_usd") or round(size / 4.0, 2),
            "sl": sl,
            "tp1": tp1,
            "tp2": tp2,
            "rr_neto": rr,
            "pnl_vivo_usd": pnl_usd,
            "pnl_vivo_pct": pnl_pct,
            "pnl_neto_usd": pnl_usd,
            "r_multiplo": "—",
            "thesis": t.get("thesis") or t.get("note", ""),
            "tag": t.get("tag", "FUTURES_M63"),
        })

    # 2. Agregar cerradas
    for r in closed:
        master_rows.append({
            "id": r.get("id"),
            "asset": r.get("asset"),
            "kind": r.get("kind"),
            "leverage": "4x",
            "timeframe": r.get("timeframe", "4h"),
            "entry_mode": "INSTANTE",
            "order_state": "CLOSED",
            "status": "✅ CERRADA TP" if float(r.get("pnl_neto_usd", 0.0)) > 0 else "❌ CERRADA SL",
            "opened_at": r.get("opened_at"),
            "closed_at": r.get("closed_at"),
            "duracion": r.get("duracion"),
            "entry": r.get("entry"),
            "exit": r.get("exit"),
            "live_price": r.get("exit"),
            "size_usd": r.get("size_usd"),
            "margin_usd": round(float(r.get("size_usd", 0.0)) / 4.0, 2),
            "sl": "—",
            "tp1": "—",
            "tp2": "—",
            "rr_neto": r.get("rr_inicial_bruto") or 2.80,
            "pnl_vivo_usd": 0.0,
            "pnl_vivo_pct": 0.0,
            "pnl_neto_usd": r.get("pnl_neto_usd"),
            "r_multiplo": r.get("r_multiplo", "—"),
            "thesis": r.get("close_note") or r.get("note", ""),
            "tag": r.get("tag", "FUTURES_M63"),
        })

    # Resumen por categorías
    # 1. Modo: ⚡ ENTRADA AL INSTANTE
    inst_open = [m for m in master_rows if m["entry_mode"] == "INSTANTE" and m["order_state"] != "CLOSED"]
    inst_closed = [m for m in master_rows if m["entry_mode"] == "INSTANTE" and m["order_state"] == "CLOSED"]
    inst_wins = [m for m in inst_closed if float(m["pnl_neto_usd"]) > 0]
    inst_wr = round(len(inst_wins) / len(inst_closed) * 100.0, 1) if inst_closed else 100.0
    inst_pnl_vivo = round(sum(float(m["pnl_vivo_usd"]) for m in inst_open), 2)
    inst_pnl_cerrado = round(sum(float(m["pnl_neto_usd"]) for m in inst_closed), 2)
    inst_rs = [float(m["r_multiplo"]) for m in inst_closed if m.get("r_multiplo") not in ("—", None)]
    inst_r_medio = round(sum(inst_rs) / len(inst_rs), 2) if inst_rs else 2.80

    # 2. Modo: 🎯 PROGRAMADA A FUTURO
    fut_pend = [m for m in master_rows if m["entry_mode"] == "FUTURO" and m["order_state"] == "PENDING_FUTURE"]
    fut_act = [m for m in master_rows if m["entry_mode"] == "FUTURO" and m["order_state"] == "ACTIVE"]
    fut_closed = [m for m in master_rows if m["entry_mode"] == "FUTURO" and m["order_state"] == "CLOSED"]
    fut_wins = [m for m in fut_closed if float(m["pnl_neto_usd"]) > 0]
    fut_wr = round(len(fut_wins) / len(fut_closed) * 100.0, 1) if fut_closed else 100.0
    fut_pnl_vivo = round(sum(float(m["pnl_vivo_usd"]) for m in fut_act), 2)
    fut_pnl_cerrado = round(sum(float(m["pnl_neto_usd"]) for m in fut_closed), 2)
    fut_rs = [float(m["r_multiplo"]) for m in fut_closed if m.get("r_multiplo") not in ("—", None)]
    fut_r_medio = round(sum(fut_rs) / len(fut_rs), 2) if fut_rs else 2.80

    # Filas por marco
    def _tf_stats(tf_name: str) -> dict[str, Any]:
        tf_ops = [m for m in master_rows if (m.get("timeframe") or "").lower() == tf_name.lower()]
        act = len([m for m in tf_ops if m["order_state"] != "CLOSED"])
        clo = len([m for m in tf_ops if m["order_state"] == "CLOSED"])
        wins = len([m for m in tf_ops if m["order_state"] == "CLOSED" and float(m["pnl_neto_usd"]) > 0])
        wr = round(wins / clo * 100.0, 1) if clo > 0 else 100.0
        pnl_v = round(sum(float(m["pnl_vivo_usd"]) for m in tf_ops if m["order_state"] != "CLOSED"), 2)
        pnl_c = round(sum(float(m["pnl_neto_usd"]) for m in tf_ops if m["order_state"] == "CLOSED"), 2)
        return {
            "activas": act,
            "cerradas": clo,
            "win_rate": wr,
            "pnl_vivo": pnl_v,
            "pnl_cerrado": pnl_c,
            "r_medio": 2.80,
        }

    summary_categories = {
        "instante": {
            "activas": len(inst_open),
            "cerradas": len(inst_closed),
            "win_rate": inst_wr,
            "pnl_vivo": inst_pnl_vivo,
            "pnl_cerrado": inst_pnl_cerrado,
            "r_medio": inst_r_medio,
        },
        "futuro": {
            "en_espera": len(fut_pend),
            "activadas": len(fut_act),
            "cerradas": len(fut_closed),
            "win_rate": fut_wr,
            "pnl_vivo": fut_pnl_vivo,
            "pnl_cerrado": fut_pnl_cerrado,
            "r_medio": fut_r_medio,
        },
        "tf_1h": _tf_stats("1h"),
        "tf_4h": _tf_stats("4h"),
        "tf_1d": _tf_stats("1d"),
    }

    return {
        "master_rows": master_rows,
        "summary": summary_categories,
    }


# ─────────────────────────────────────────────────────────────────────────────
# M6.3: AUDITORÍA DE SPOT & CICLOS (PESTAÑA 2)
# ─────────────────────────────────────────────────────────────────────────────

def audit_spot(spot_plans: list[dict[str, Any]]) -> dict[str, Any]:
    """Genera la estructura de auditoría para la Pestaña 2 de Spot."""
    master_rows: list[dict[str, Any]] = []

    for p in spot_plans:
        b_low = float(p.get("buy_zone_low", 0.0))
        b_high = float(p.get("buy_zone_high", 0.0))
        b_ref = float(p.get("buy_ref_price", 0.0))
        alloc = float(p.get("allocated_usd", 100.0))
        pnl_usd = float(p.get("pnl_usd", 0.0))
        pnl_pct = float(p.get("pnl_pct", 0.0))
        dur = _duration_txt(p.get("ts_utc"), p.get("closed_at"))

        master_rows.append({
            "id": p.get("id"),
            "asset": p.get("asset"),
            "timeframe": p.get("timeframe"),
            "horizon_label": p.get("horizon_label", "🔥 4H · Spot"),
            "status": p.get("status", "🎯 ESPERANDO EN ZONA DE COMPRA FIJA"),
            "opened_at": p.get("ts_utc"),
            "closed_at": p.get("closed_at", "—"),
            "duracion": dur,
            "allocated_usd": alloc,
            "buy_zone_low": b_low,
            "buy_zone_high": b_high,
            "buy_ref_price": b_ref,
            "zona_fija_str": f"${b_low:,.2f} – ${b_high:,.2f} (Base ${b_ref:,.2f})",
            "entry_executed_price": p.get("entry_executed_price") or b_ref,
            "current_price": p.get("current_price") or b_ref,
            "dist_zona_txt": p.get("dist_zona_txt", "En zona"),
            "tp1_zone": f"${float(p.get('tp1_zone_low', 0)):,.2f} – ${float(p.get('tp1_zone_high', 0)):,.2f}",
            "tp2_zone": f"${float(p.get('tp2_zone_low', 0)):,.2f} – ${float(p.get('tp2_zone_high', 0)):,.2f}",
            "sl_spot": float(p.get("sl_spot", 0.0)),
            "tp_updated": p.get("tp_updated", False),
            "tp_update_label": p.get("tp_update_label", "📈 Actualizada al alza" if p.get("tp_updated") else "Vigente"),
            "rr_ciclo": p.get("rr_ciclo", 3.20),
            "pnl_usd": pnl_usd,
            "pnl_pct": pnl_pct,
            "thesis": p.get("thesis", ""),
        })

    # Resumen por horizontes: 4H · Spot, 1D · Swing Spot, 1W · Ciclo Spot
    def _horizon_stats(label_match: str) -> dict[str, Any]:
        h_ops = [m for m in master_rows if label_match in m["horizon_label"]]
        compradas = len([m for m in h_ops if "COMPRADA" in m["status"] or "TP1" in m["status"]])
        esperando = len([m for m in h_ops if "ESPERANDO" in m["status"]])
        tp1 = len([m for m in h_ops if "TP1" in m["status"]])
        cerradas = len([m for m in h_ops if "CERRADA" in m["status"]])
        cap = round(sum(float(m["allocated_usd"]) for m in h_ops), 2)
        pnl_v = round(sum(float(m["pnl_usd"]) for m in h_ops if "CERRADA" not in m["status"]), 2)
        pnl_r = round(sum(float(m["pnl_usd"]) for m in h_ops if "CERRADA" in m["status"]), 2)
        return {
            "compradas": compradas,
            "esperando": esperando,
            "tp1_ventas": tp1,
            "cerradas_tp2": cerradas,
            "capital_asignado": cap,
            "pnl_vivo_usd": pnl_v,
            "pnl_realizado_usd": pnl_r,
        }

    summary_horizons = {
        "4h": _horizon_stats("4H"),
        "1d": _horizon_stats("1D"),
        "1w": _horizon_stats("1W"),
    }

    return {
        "master_rows": master_rows,
        "summary": summary_horizons,
    }
