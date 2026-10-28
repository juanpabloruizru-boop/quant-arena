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

import hashlib
import json
import uuid
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

KINDS = ("spot", "future_long", "future_short")


def _sha(line: str) -> str:
    return hashlib.sha256(line.encode("utf-8")).hexdigest()


def _log_path(root: Path) -> Path:
    return root / "ledger" / "user_trades.jsonl"


def _append(root: Path, record: dict[str, Any]) -> dict[str, Any]:
    p = _log_path(root)
    p.parent.mkdir(parents=True, exist_ok=True)
    prev = ""
    if p.exists():
        lines = [ln for ln in p.read_text(encoding="utf-8").splitlines() if ln.strip()]
        if lines:
            prev = _sha(lines[-1])
    record = dict(record)
    record["prev_hash"] = prev
    line = json.dumps(record, sort_keys=True, default=str)
    with p.open("a", encoding="utf-8") as f:
        f.write(line + "\n")
    return record


def verify_chain(root: Path) -> tuple[bool, int, str]:
    p = _log_path(root)
    if not p.exists():
        return True, 0, "sin operaciones registradas"
    lines = [ln for ln in p.read_text(encoding="utf-8").splitlines() if ln.strip()]
    prev = ""
    for i, ln in enumerate(lines):
        rec = json.loads(ln)
        if rec.get("prev_hash", "") != prev:
            return False, len(lines), f"cadena rota en la linea {i + 1}"
        prev = _sha(ln)
    return True, len(lines), "cadena valida"


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
) -> dict[str, Any]:
    if kind not in KINDS:
        raise ValueError(f"kind debe ser uno de {KINDS}")
    rec = {
        "action": "open",
        "id": uuid.uuid4().hex[:8],
        "ts_utc": datetime.now(UTC).isoformat(timespec="seconds"),
        "asset": asset.upper(),
        "kind": kind,
        "timeframe": timeframe,
        "entry_price": float(entry_price),
        "size_usd": float(size_usd),
        "sl": None if sl is None else float(sl),
        "tp": None if tp is None else float(tp),
        "note": note,
        "example": example,
    }
    return _append(root, rec)


def close_trade(root: Path, trade_id: str, exit_price: float, note: str = "") -> dict[str, Any]:
    rec = {
        "action": "close",
        "id": trade_id,
        "ts_utc": datetime.now(UTC).isoformat(timespec="seconds"),
        "exit_price": float(exit_price),
        "note": note,
    }
    return _append(root, rec)


def load_trades(root: Path) -> list[dict[str, Any]]:
    """Replay del log: operaciones abiertas (con exit si cerradas)."""
    p = _log_path(root)
    if not p.exists():
        return []
    opens: dict[str, dict[str, Any]] = {}
    for ln in p.read_text(encoding="utf-8").splitlines():
        if not ln.strip():
            continue
        rec = json.loads(ln)
        if rec.get("action") == "open":
            opens[rec["id"]] = rec
        elif rec.get("action") == "close" and rec.get("id") in opens:
            opens[rec["id"]].update(
                status="closed",
                closed_at=rec["ts_utc"],
                exit_price=rec["exit_price"],
                close_note=rec.get("note", ""),
            )
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
