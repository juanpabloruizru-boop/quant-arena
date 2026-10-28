"""Auditoría del historial de operaciones del USUARIO (M5b).

Métricas contables sobre operaciones CERRADAS registradas por el propio
usuario (su entrada, su SL/TP, su salida). Aritmética descriptiva — no es un
veredicto sobre ninguna estrategia ni una evaluación del preregistro
(ADR-008 addendum B).

Modelo de comisiones: ida y vuelta taker sobre nocional de entrada
(spot 0.20 %, perp 0.10 %; config/costs.yaml VERIFICADO). Múltiplo R:
pnl_neto / riesgo_inicial_usd, con riesgo_inicial = |Entry − SL|/Entry × size
(solo si la operación se registró con SL).
"""

from __future__ import annotations

from datetime import UTC
from typing import Any

import pandas as pd

from qa.agent.capital import realized_pnl_usd


def _duration_txt(opened: str | None, closed: str | None) -> str:
    if not opened or not closed:
        return "?"
    try:
        t0 = pd.Timestamp(opened)
        t1 = pd.Timestamp(closed)
        if t0.tzinfo is None:
            t0 = t0.tz_localize("UTC")
        if t1.tzinfo is None:
            t1 = t1.tz_localize("UTC")
        d = t1 - t0
        return f"{d.days}d {d.seconds // 3600}h"
    except (ValueError, TypeError):
        return "?"


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
        "generado_utc": pd.Timestamp.now(UTC).isoformat(timespec="seconds"),
    }


def run_audit(
    trades: list[dict[str, Any]], costs: dict[str, Any], capital_aportado: float | None = None
) -> dict[str, Any]:
    rows = closed_rows(trades, costs)
    return {"rows": rows, "summary": audit_summary(rows, capital_aportado)}
