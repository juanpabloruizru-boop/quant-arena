"""Contabilidad de capital del USUARIO (M5b) — libro append-only con cadena.

Ecuación patrimonial que computa `qa capital status` (todo aritmética sobre
los REGISTROS DEL PROPIO USUARIO y precios públicos en vivo; ADR-008
addendum B: contabilidad personal, no consejo):

1. Capital Aportado Neto = capital inicial + adiciones − retiros.
2. PnL Realizado (neto de comisiones taker estimadas) = operaciones cerradas.
3. PnL Flotante (bruto) = operaciones abiertas a precio vivo.
4. Patrimonio Total (Equity Vivo) = 1 + 2 + 3.
5. Portfolio Heat = pérdida sobre capital APORTADO si todos los SL saltaran
   hoy simultáneamente (SL en zona de ganancia/break-even aporta $0; sin SL
   no es computable y se lista aparte).

Almacén: ledger/user_capital.jsonl (cadena de hashes, ver chain.py).
"""

from __future__ import annotations

import shutil
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from qa.agent.chain import append_chained, read_records, rewrite_chain, verify_chain_file
from qa.agent.geometry import fee_roundtrip


def capital_log_path(root: Path) -> Path:
    return root / "ledger" / "user_capital.jsonl"


def trades_log_path(root: Path) -> Path:
    return root / "ledger" / "user_trades.jsonl"


def verify_capital_chain(root: Path) -> tuple[bool, int, str]:
    return verify_chain_file(capital_log_path(root))


def _now_iso() -> str:
    return datetime.now(UTC).isoformat(timespec="seconds")


def set_capital(
    root: Path,
    amount: float,
    note: str = "",
    ts_utc: str | None = None,
    example: bool = False,
) -> dict[str, Any]:
    """Fija el capital inicial (primer registro del libro)."""
    rec = {
        "action": "set",
        "ts_utc": ts_utc or _now_iso(),
        "amount": float(amount),
        "note": note,
        "example": example,
    }
    return append_chained(capital_log_path(root), rec)


def add_capital(
    root: Path,
    amount: float,
    note: str = "",
    ts_utc: str | None = None,
    example: bool = False,
) -> dict[str, Any]:
    """Aporte adicional (o retiro si el importe es negativo)."""
    rec = {
        "action": "add",
        "ts_utc": ts_utc or _now_iso(),
        "amount": float(amount),
        "note": note,
        "example": example,
    }
    return append_chained(capital_log_path(root), rec)


def load_capital(root: Path) -> list[dict[str, Any]]:
    return read_records(capital_log_path(root))


def net_contributed(records: list[dict[str, Any]]) -> float:
    """Capital Aportado Neto = suma de todos los flujos (set + add/retiros)."""
    return sum(float(r.get("amount", 0.0)) for r in records)


def movimientos(records: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Tabla histórica de movimientos con acumulado."""
    out: list[dict[str, Any]] = []
    acc = 0.0
    for r in records:
        acc += float(r.get("amount", 0.0))
        out.append(
            {
                "ts_utc": r.get("ts_utc", "?"),
                "tipo": "inicial" if r.get("action") == "set" else "flujo",
                "amount": float(r.get("amount", 0.0)),
                "acumulado": round(acc, 2),
                "note": r.get("note", ""),
                "example": bool(r.get("example", False)),
            }
        )
    return out


def realized_pnl_usd(trade: dict[str, Any], costs: dict[str, Any]) -> dict[str, Any]:
    """PnL de una operación CERRADA: bruto, comisiones estimadas y neto.

    Modelo de comisiones (documentado, coherente con costs.yaml VERIFICADO):
    ida y vuelta taker sobre el nocional de entrada (spot 0.20 %, perp 0.10 %).
    Incluye de forma integrada cualquier ganancia/comisión de cierres parciales previos (TP1).
    """
    entry = float(trade["entry_price"])
    exit_px = float(trade.get("exit_price", entry))
    size = float(trade.get("size_usd", 0.0))
    direction = -1.0 if trade.get("kind") == "future_short" else 1.0
    bruto_rem = size * (exit_px / entry - 1.0) * direction
    fees_rem = size * fee_roundtrip(str(trade.get("kind", "spot")), costs)
    neto_rem = bruto_rem - fees_rem

    # Integración de cierres parciales si existieron
    part_neto = float(trade.get("partial_realized_pnl_usd", 0.0))
    part_fees = float(trade.get("partial_fees_usd", 0.0))
    part_bruto = part_neto + part_fees

    total_bruto = bruto_rem + part_bruto
    total_fees = fees_rem + part_fees
    total_neto = neto_rem + part_neto

    part_closed = float(trade.get("partial_closed_size_usd", 0.0))
    initial_size = float(trade.get("initial_size_usd") or (size + part_closed))
    if initial_size > 0:
        pct = (total_neto / initial_size) * 100.0
    else:
        pct = (exit_px / entry - 1.0) * 100.0 * direction
    return {
        "pnl_bruto_usd": round(total_bruto, 2),
        "fees_estimadas_usd": round(total_fees, 2),
        "pnl_neto_usd": round(total_neto, 2),
        "pnl_pct": round(pct, 3),
    }


def open_risk_usd(trade: dict[str, Any]) -> float | None:
    """Riesgo APORTADO de una operación abierta si su SL saltara hoy.

    Long: size × max(0, 1 − SL/Entry) · Short: size × max(0, SL/Entry − 1).
    SL en zona de ganancia/break-even (más allá de la entrada) aporta $0.
    Sin SL no es computable -> None (el riesgo no está acotado).
    """
    sl = trade.get("sl")
    entry = float(trade.get("entry_price", 0.0))
    if sl is None or entry <= 0:
        return None
    size = float(trade.get("size_usd", 0.0))
    direction = -1.0 if trade.get("kind") == "future_short" else 1.0
    frac = (1.0 - float(sl) / entry) * direction
    return round(size * max(0.0, frac), 2)


def compute_status(
    capital_records: list[dict[str, Any]],
    trades: list[dict[str, Any]],
    prices: dict[str, float],
    costs: dict[str, Any],
) -> dict[str, Any]:
    """Ecuación patrimonial completa (1)-(5). `prices`: precio vivo por activo."""
    aportado = round(net_contributed(capital_records), 2)
    closed = [t for t in trades if t.get("status") == "closed"]
    opened = [t for t in trades if t.get("status") != "closed"]

    realized = 0.0
    fees_closed = 0.0
    for t in closed:
        r = realized_pnl_usd(t, costs)
        realized += r["pnl_neto_usd"]
        fees_closed += r["fees_estimadas_usd"]

    # Incorporar PnL ya realizado de cierres parciales (TP1) en operaciones aún abiertas
    for t in opened:
        realized += float(t.get("partial_realized_pnl_usd", 0.0))
        fees_closed += float(t.get("partial_fees_usd", 0.0))

    realized = round(realized, 2)
    fees_closed = round(fees_closed, 2)

    floating = 0.0
    fees_open_est = 0.0
    floating_detail: list[dict[str, Any]] = []
    sin_precio: list[str] = []
    for t in opened:
        if t.get("order_state") == "PENDING_FUTURE":
            floating_detail.append(
                {
                    "id": t.get("id"),
                    "asset": t["asset"],
                    "price_now": prices.get(t["asset"]),
                    "pnl_usd": 0.0,
                }
            )
            continue
        px = prices.get(t["asset"])
        size = float(t.get("size_usd", 0.0))
        entry = float(t.get("entry_price", 0.0))
        direction = -1.0 if t.get("kind") == "future_short" else 1.0
        fees_open_est += size * fee_roundtrip(str(t.get("kind", "spot")), costs)
        if px is None or entry <= 0:
            sin_precio.append(t.get("id", "?"))
            floating_detail.append({"id": t.get("id"), "asset": t["asset"], "pnl_usd": None})
            continue
        pnl = size * (px / entry - 1.0) * direction
        floating += pnl
        floating_detail.append(
            {"id": t.get("id"), "asset": t["asset"], "price_now": px, "pnl_usd": round(pnl, 2)}
        )
    floating = round(floating, 2)

    patrimonio = round(aportado + realized + floating, 2)

    heat = 0.0
    heat_detail: list[dict[str, Any]] = []
    sin_sl: list[str] = []
    for t in opened:
        risk = open_risk_usd(t)
        if risk is None:
            sin_sl.append(f"{t.get('id', '?')} ({t['asset']})")
            heat_detail.append(
                {"id": t.get("id"), "asset": t["asset"], "riesgo_usd": None, "sin_sl": True}
            )
            continue
        heat += risk
        heat_detail.append(
            {"id": t.get("id"), "asset": t["asset"], "riesgo_usd": risk, "sin_sl": False}
        )
    heat = round(heat, 2)

    def _pct(x: float) -> float | None:
        return round(x / aportado * 100.0, 2) if aportado > 0 else None

    return {
        "sin_registros": not capital_records,
        "capital_aportado_neto": aportado,
        "movimientos": movimientos(capital_records),
        "pnl_realizado_usd": realized,
        "pnl_realizado_pct_aportado": _pct(realized),
        "comisiones_cerradas_est_usd": round(fees_closed, 2),
        "pnl_flotante_usd": floating,
        "pnl_flotante_pct_aportado": _pct(floating),
        "comisiones_abiertas_est_usd": round(fees_open_est, 2),
        "flotante_detalle": floating_detail,
        "sin_precio_vivo": sin_precio,
        "patrimonio_total": patrimonio,
        "portfolio_heat_usd": heat,
        "portfolio_heat_pct_patrimonio": (
            round(heat / patrimonio * 100.0, 2) if patrimonio > 0 else None
        ),
        "heat_detalle": heat_detail,
        "abiertas_sin_sl": sin_sl,
        "n_abiertas": len(opened),
        "n_cerradas": len(closed),
    }


def reset_examples(root: Path) -> dict[str, Any]:
    """Borra TODOS los registros `example: true` de capital y operaciones.

    - Solo toca registros marcados EJEMPLO (los reales jamás se eliminan).
    - Copia de seguridad previa en ledger/backup/*.pre_reset_<ts>.jsonl.
    - Reconstruye las cadenas de hashes y las reverifica.
    """
    ts = datetime.now(UTC).strftime("%Y%m%dT%H%M%SZ")
    backup_dir = root / "ledger" / "backup"
    backup_dir.mkdir(parents=True, exist_ok=True)
    summary: dict[str, Any] = {"backups": [], "capital_removed": 0, "trades_removed": 0}

    cap_path = capital_log_path(root)
    trd_path = trades_log_path(root)
    for p in (cap_path, trd_path):
        if p.exists():
            b = backup_dir / f"{p.stem}.pre_reset_{ts}.jsonl"
            shutil.copyfile(p, b)
            summary["backups"].append(str(b.relative_to(root)))

    cap = read_records(cap_path)
    cap_keep = [r for r in cap if not r.get("example")]
    summary["capital_removed"] = len(cap) - len(cap_keep)
    rewrite_chain(cap_path, cap_keep)

    trd = read_records(trd_path)
    example_ids = {r["id"] for r in trd if r.get("action") == "open" and r.get("example")}
    trd_keep = [
        r
        for r in trd
        if not (r.get("example") or (r.get("action") == "close" and r.get("id") in example_ids))
    ]
    summary["trades_removed"] = len(trd) - len(trd_keep)
    rewrite_chain(trd_path, trd_keep)

    ok_c, n_c, msg_c = verify_chain_file(cap_path)
    ok_t, n_t, msg_t = verify_chain_file(trd_path)
    summary["capital_chain"] = {"ok": ok_c, "lineas": n_c, "msg": msg_c}
    summary["trades_chain"] = {"ok": ok_t, "lineas": n_t, "msg": msg_t}
    summary["ts_utc"] = ts
    return summary


def load_costs(root: Path) -> dict[str, Any]:
    """Comisiones VERIFICADAS de config/costs.yaml (fuente única)."""
    import yaml

    data = yaml.safe_load((root / "config" / "costs.yaml").read_text(encoding="utf-8"))
    assert isinstance(data, dict)
    return data


def load_rr_config(root: Path) -> dict[str, Any]:
    """Sección `filtro_rr` de config/watchlist.yaml, con valores por defecto."""
    import yaml

    data = yaml.safe_load((root / "config" / "watchlist.yaml").read_text(encoding="utf-8"))
    assert isinstance(data, dict)
    sec = data.get("filtro_rr") or {}
    return {
        "min_rr": float(sec.get("min_rr_ratio", 2.0)),
        "reward_mult": float(sec.get("reward_atr_mult", 3.0)),
        "risk_mult": float(sec.get("risk_atr_mult_min", 1.0)),
        "risk_pcts": tuple(float(x) for x in sec.get("risk_pcts", (0.5, 1.0, 2.0))),
    }
