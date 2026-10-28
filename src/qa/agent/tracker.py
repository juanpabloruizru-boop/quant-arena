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
) -> dict[str, Any]:
    """Registra una operación abierta POR EL USUARIO (tag/ts opcionales, M5b).

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
        "sl": None if sl is None else float(sl),
        "tp": None if tp is None else float(tp),
        "note": note,
        "tag": tag,
        "example": example,
        "rr_neto_inicial": rr_neto_inicial,
        "rr_forzado": rr_forzado,
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
) -> dict[str, Any]:
    rec = {
        "action": "close",
        "id": trade_id,
        "ts_utc": ts_utc or datetime.now(UTC).isoformat(timespec="seconds"),
        "exit_price": float(exit_price),
        "note": note,
        "tag": tag,
        "example": example,
    }
    return _append(root, rec)


def load_trades(root: Path) -> list[dict[str, Any]]:
    """Replay del log: operaciones abiertas (con exit si cerradas)."""
    opens: dict[str, dict[str, Any]] = {}
    for rec in read_records(_log_path(root)):
        if rec.get("action") == "open":
            opens[rec["id"]] = rec
        elif rec.get("action") == "close" and rec.get("id") in opens:
            updates: dict[str, Any] = {
                "status": "closed",
                "closed_at": rec["ts_utc"],
                "exit_price": rec["exit_price"],
                "close_note": rec.get("note", ""),
            }
            if rec.get("tag"):
                updates["close_tag"] = rec["tag"]
            opens[rec["id"]].update(updates)
    for t in opens.values():
        t.setdefault("status", "open")
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
    pnl_pct = (price_now / entry - 1.0) * direction
    out["price_now"] = price_now
    out["pnl_pct"] = round(pnl_pct * 100, 3)
    out["pnl_usd"] = round(pnl_pct * float(trade["size_usd"]), 2)
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
