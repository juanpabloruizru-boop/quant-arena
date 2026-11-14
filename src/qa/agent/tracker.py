"""Tracker de operaciones del USUARIO (M4/M5 operativo).

Filosofia (ADR-008): el agente es un LIBRO DE REGISTRO + contexto descriptivo.
Las operaciones son decisiones del usuario con su dinero; aqui se anotan sus
PROPIOS parametros (entrada, tamanno, SL, TP) y el agente devuelve:
- PnL actual ($ y %), distancia a SU SL y a SU TP;
- contexto de tendencia (solo para BTC/ETH 1D, donde existe regla investigada);
- alertas de riesgo (choques tecnicos / noticias) que afectan al activo.
NUNCA emite ordenes (comprar/vender/subir stop/cerrar): eso seria advice sobre
reglas no validadas. El formato de "estado de seguimiento" es descriptivo:
`SIN ALERTAS` o `REVISAR: <motivos>` (motivos = hechos observados).

Almacen: ledger/user_trades.jsonl append-only con cadena de hashes.
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from qa.agent.chain import append_chained, read_records, verify_chain_file

KINDS = ("spot", "future_long", "future_short")


def _log_path(root: Path) -> Path:
    return root / "ledger" / "user_trades.jsonl"


def _append(root: Path, record: dict[str, Any]) -> dict[str, Any]:
    return append_chained(_log_path(root), record)


def verify_chain(root: Path) -> tuple[bool, int, str]:
    ok, n, msg = verify_chain_file(_log_path(root))
    if not _log_path(root).exists():
        return True, 0, "sin operaciones registradas"
    return ok, n, msg


def open_trade(
    root: Path,
    asset: str,
    kind: str,
    timeframe: str,
    entry_price: float,
    size_usd: float,
    sl: float | None,
    tp: float | None,
    note: str = "",
    example: bool = False,
    tag: str = "",
    ts_utc: str | None = None,
    rr_neto_inicial: float | None = None,
    rr_forzado: bool = False,
    entry_mode: str = "INSTANTE",
    order_state: str = "ACTIVE",
    target_entry: float | None = None,
    leverage: str = "4x",
    margin_usd: float | None = None,
    risk_usd: float | None = None,
    tp1: float | None = None,
    tp2: float | None = None,
    thesis: str = "",
    ai_reasoning: str = "",
    tp3: float | None = None,
    tp1_price: float | None = None,
    tp2_price: float | None = None,
    tp3_price: float | None = None,
    rr_ratio: str | float | None = None,
) -> dict[str, Any]:
    """Registra una operación abierta POR EL USUARIO o AUTOPILOT (tag/ts opcionales, M6.3).

    `rr_neto_inicial` y `rr_forzado` dejan traza del filtro de disciplina
    R:R >= min_rr en el momento del registro (auditable a posteriori).
    """
    if kind not in KINDS:
        raise ValueError(f"kind debe ser uno de {KINDS}")
    rec = {
        "action": "open",
        "id": uuid.uuid4().hex[:8],
        "ts_utc": ts_utc or datetime.now(UTC).isoformat(timespec="seconds"),
        "asset": asset.upper(),
        "kind": kind,
        "timeframe": timeframe,
        "entry_price": float(entry_price),
        "size_usd": float(size_usd),
        "initial_size_usd": float(size_usd),
        "partial_realized_pnl_usd": 0.0,
        "partial_fees_usd": 0.0,
        "partial_closed_size_usd": 0.0,
        "partial_exits": [],
        "sl": None if sl is None else float(sl),
        "tp": None if tp is None else float(tp),
        "note": note,
        "tag": tag,
        "example": example,
        "rr_neto_inicial": rr_neto_inicial,
        "rr_forzado": rr_forzado,
        "entry_mode": entry_mode,
        "order_state": order_state,
        "target_entry": None if target_entry is None else float(target_entry),
        "leverage": leverage,
        "margin_usd": None if margin_usd is None else float(margin_usd),
        "risk_usd": None if risk_usd is None else float(risk_usd),
        "tp1": None if tp1 is None else float(tp1),
        "tp2": None if tp2 is None else float(tp2),
        "tp3": None if tp3 is None else float(tp3),
        "tp1_price": (
            float(tp1_price)
            if tp1_price is not None
            else (float(tp1) if tp1 is not None else None)
        ),
        "tp2_price": (
            float(tp2_price)
            if tp2_price is not None
            else (float(tp2) if tp2 is not None else None)
        ),
        "tp3_price": (
            float(tp3_price)
            if tp3_price is not None
            else (float(tp3) if tp3 is not None else None)
        ),
        "rr_ratio": rr_ratio or (f"1 : {rr_neto_inicial:.1f}" if rr_neto_inicial else "1 : 3.0"),
        "thesis": thesis,
        "ai_reasoning": ai_reasoning,
    }
    return _append(root, rec)


def update_trade(
    root: Path,
    trade_id: str,
    updates: dict[str, Any],
    note: str = "",
    ts_utc: str | None = None,
) -> dict[str, Any]:
    """Registra una actualización sobre una operación (activación de programada, mover SL a BE)."""
    rec = {
        "action": "update",
        "id": trade_id,
        "ts_utc": ts_utc or datetime.now(UTC).isoformat(timespec="seconds"),
        "updates": updates,
        "note": note,
    }
    return _append(root, rec)


def close_trade(
    root: Path,
    trade_id: str,
    exit_price: float,
    note: str = "",
    tag: str = "",
    ts_utc: str | None = None,
    example: bool = False,
    pnl_neto_usd: float | None = None,
) -> dict[str, Any]:
    from qa.agent.capital import load_costs, realized_pnl_usd

    matched_open: dict[str, Any] | None = None
    if _log_path(root).exists():
        for t in load_trades(root):
            if t.get("id") == trade_id:
                matched_open = t
                break

    rec: dict[str, Any] = {
        "action": "close",
        "id": trade_id,
        "ts_utc": ts_utc or datetime.now(UTC).isoformat(timespec="seconds"),
        "exit_price": float(exit_price),
        "note": note,
        "tag": tag,
        "example": example,
    }

    if matched_open:
        rec["asset"] = matched_open.get("asset")
        rec["kind"] = matched_open.get("kind")
        rec["timeframe"] = matched_open.get("timeframe", "4h")
        rec["entry_price"] = matched_open.get("entry_price")
        rec["size_usd"] = matched_open.get("size_usd")
        rec["risk_usd"] = matched_open.get("risk_usd")
        rec["leverage"] = matched_open.get("leverage", "4x")
        rec["sl"] = matched_open.get("sl")
        rec["tp"] = matched_open.get("tp")
        rec["tp1"] = matched_open.get("tp1")
        rec["tp2"] = matched_open.get("tp2")
        rec["tp3"] = matched_open.get("tp3")
        rec["tp1_price"] = matched_open.get("tp1_price") or matched_open.get("tp1")
        rec["tp2_price"] = matched_open.get("tp2_price") or matched_open.get("tp2")
        rec["tp3_price"] = matched_open.get("tp3_price") or matched_open.get("tp3")
        rec["rr_ratio"] = matched_open.get("rr_ratio")
        if pnl_neto_usd is not None:
            rec["pnl_neto_usd"] = float(pnl_neto_usd)
        else:
            try:
                costs = load_costs(root)
                calc_trade = dict(matched_open)
                calc_trade["exit_price"] = float(exit_price)
                res_pnl = realized_pnl_usd(calc_trade, costs)
                rec["pnl_neto_usd"] = res_pnl["pnl_neto_usd"]
            except Exception:
                pass
    elif pnl_neto_usd is not None:
        rec["pnl_neto_usd"] = float(pnl_neto_usd)

    return _append(root, rec)


def load_trades(root: Path) -> list[dict[str, Any]]:
    """Replay del log: operaciones abiertas (con exit si cerradas)."""
    opens: dict[str, dict[str, Any]] = {}
    for rec in read_records(_log_path(root)):
        if rec.get("action") == "open":
            opens[rec["id"]] = dict(rec)
        elif rec.get("action") == "close" and rec.get("id") in opens:
            updates: dict[str, Any] = {
                "status": "closed",
                "closed_at": rec["ts_utc"],
                "exit_price": rec["exit_price"],
                "close_note": rec.get("note", ""),
                "close_reason": rec.get("note", ""),
            }
            if rec.get("tag"):
                updates["close_tag"] = rec["tag"]
            if "pnl_neto_usd" in rec:
                updates["pnl_neto_usd"] = float(rec["pnl_neto_usd"])
                updates["pnl_usd"] = float(rec["pnl_neto_usd"])
                updates["realized_pnl_usd"] = float(rec["pnl_neto_usd"])
            if "r_multiplo" in rec:
                updates["r_multiplo"] = rec["r_multiplo"]
            opens[rec["id"]].update(updates)
        elif rec.get("action") == "update" and rec.get("id") in opens:
            opens[rec["id"]].update(rec.get("updates", {}))
    for t in opens.values():
        t.setdefault("status", "open")
        t.setdefault("entry", t.get("entry_price"))
        t.setdefault("sl_price", t.get("sl"))
        t.setdefault("tp_price", t.get("tp"))
        t.setdefault("tp1_price", t.get("tp1"))
        t.setdefault("tp2_price", t.get("tp2"))
        t.setdefault("tp3_price", t.get("tp3"))
        t.setdefault("timeframe", "4h")
    return list(opens.values())


def diagnose(
    trade: dict[str, Any],
    price_now: float | None,
    trend_context: str,
    alerts: list[str],
) -> dict[str, Any]:
    """Diagnostico DESCRIPTIVO de una operacion (sin ordenes)."""
    out: dict[str, Any] = {"id": trade["id"], "asset": trade["asset"], "kind": trade["kind"]}
    if trade.get("status") == "closed" or price_now is None:
        out["estado_seguimiento"] = (
            "CERRADA por el usuario" if trade.get("status") == "closed" else "sin precio vivo"
        )
        return out
    direction = -1.0 if trade["kind"] == "future_short" else 1.0
    entry = float(trade["entry_price"])
    out["price_now"] = price_now

    if trade.get("order_state") == "PENDING_FUTURE":
        out["pnl_pct"] = 0.0
        out["pnl_usd"] = 0.0
        out["dist_entry_pct"] = round(abs(price_now - entry) / entry * 100.0, 2)
    else:
        is_short = str(trade.get("kind", "")).lower() == "future_short"
        pnl_pct = (entry - price_now) / entry if is_short else (price_now - entry) / entry
        out["pnl_pct"] = round(pnl_pct * 100, 3)
        out["pnl_usd"] = round(pnl_pct * float(trade.get("size_usd", 0.0)), 2)
    if trade.get("sl"):
        out["dist_sl_pct"] = round(
            (price_now - float(trade["sl"])) / price_now * 100 * direction, 2
        )
    if trade.get("tp"):
        out["dist_tp_pct"] = round(
            (float(trade["tp"]) - price_now) / price_now * 100 * direction, 2
        )
    out["contexto_tendencia"] = trend_context
    out["alertas"] = alerts
    if alerts:
        out["estado_seguimiento"] = "REVISAR (hechos observados, no es una orden): " + "; ".join(
            alerts
        )
    else:
        out["estado_seguimiento"] = f"SIN ALERTAS — contexto: {trend_context}"
    return out
