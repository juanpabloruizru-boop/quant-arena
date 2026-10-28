"""Forward paper (ADR-007).

v0 (M4): registro diario de ESTADOS de las 5 celdas congeladas con cadena de
hashes (``append_forward_record``).

v1 (este hito, tag ``forward-v1``): motor de fills t+1 con P&L paper.

Convenciones v1 (selladas con el tag):

- CALENDARIO: la corrida diaria (00:30 UTC del día D) usa SOLO velas diarias
  CERRADAS —``fetch_live`` ya descarta la vela en formación—; la señal se
  computa con datos ≤ D−1 y el fill se ejecuta al cierre de D−1 ⇒ fill
  estrictamente posterior al corte de información (semántica t+1 del
  backtest de investigación).
- COSTES nivel estrés (M2b/M3a): spot taker 0.10 % + 2 pb slippage; perp
  taker 0.05 % + 2 pb. Contabilidad simulada; ninguna orden real.
- CUENTAS: 4 sleeves autofinanciados (H1-BTC, H1-ETH, H3 delta-neutra
  BTC/ETH, H2 cesta) sobre capital inicial. El perp se liquida a diario
  (mark-to-market a caja); el funding REAL se abona/adeuda por evento:
  ``cash += −qty × precio × tasa`` (corto cobra tasa positiva).
- SEÑALES: solo las celdas congeladas vía ``qa.agent.signals.compute_states``
  (single source of truth; el motor no reimplementa reglas).
- AUDITORÍA: cada paso añade un registro encadenado (sha256 de la línea
  anterior) a ``ledger/forward.jsonl``. El estado mutable vive en
  ``ledger/forward_state.json`` (gitignored; la evidencia es la cadena).
"""

from __future__ import annotations

import hashlib
import json
import subprocess
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

from qa.agent.signals import BAND

ASSETS = ("BTCUSDT", "ETHUSDT")
SLEEVE_CAPITAL_FRAC = 0.25
DEFAULT_COSTS = {"spot_taker": 0.0010, "perp_taker": 0.0005, "slippage_bps": 2.0}
STATE_RELPATH = Path("ledger/forward_state.json")
MIN_NOTIONAL_PAPER = 1.0


# ---------------------------------------------------------------- cadena (v0)
def _git_sha(root: Path) -> str:
    try:
        out = subprocess.run(
            [
                "git",
                "rev-parse",
                "HEAD",
            ],
            cwd=root,
            capture_output=True,
            text=True,
            timeout=10,
        )
        return out.stdout.strip() or "unknown"
    except (OSError, subprocess.TimeoutExpired):
        return "unknown"


def _sha(line: str) -> str:
    return hashlib.sha256(line.encode("utf-8")).hexdigest()


def append_record(root: Path, rec: dict[str, Any]) -> dict[str, Any]:
    """Añade CUALQUIER registro a la cadena forward (prev_hash + git_sha)."""
    p = root / "ledger" / "forward.jsonl"
    p.parent.mkdir(parents=True, exist_ok=True)
    prev = ""
    if p.exists():
        lines = [ln for ln in p.read_text(encoding="utf-8").splitlines() if ln.strip()]
        if lines:
            prev = _sha(lines[-1])
    rec = dict(rec)
    rec.setdefault("ts_utc", datetime.now(UTC).isoformat(timespec="seconds"))
    rec.setdefault("git_sha", _git_sha(root))
    rec["prev_hash"] = prev
    line = json.dumps(rec, sort_keys=True, default=str)
    with p.open("a", encoding="utf-8") as f:
        f.write(line + "\n")
    return rec


def append_forward_record(root: Path, states: dict[str, Any]) -> dict[str, Any]:
    """Registro v0 de ESTADOS (compatibilidad con M4)."""
    cells = states.get("cells", {})
    rec = {
        "kind": "forward_state",
        "data_fetched_at": states.get("fetched_at_utc"),
        "h1": {
            a: {
                "estado": cells.get(f"H1_{a}", {}).get("estado"),
                "posicion_regla": cells.get(f"H1_{a}", {}).get("posicion_regla"),
            }
            for a in ASSETS
        },
        "h2_cesta": cells.get("H2_L26_N10", {}).get("cesta_teoretica"),
        "h3": {
            a: {
                "senal_activa": cells.get(f"H3_{a}", {}).get("senal_activa"),
                "funding_ma30_ann": cells.get(f"H3_{a}", {}).get("funding_ma30_ann"),
            }
            for a in ASSETS
        },
    }
    return append_record(root, rec)


def verify_forward_chain(root: Path) -> tuple[bool, int, str]:
    p = root / "ledger" / "forward.jsonl"
    if not p.exists():
        return True, 0, "sin registros forward"
    lines = [ln for ln in p.read_text(encoding="utf-8").splitlines() if ln.strip()]
    prev = ""
    for i, ln in enumerate(lines):
        rec = json.loads(ln)
        if rec.get("prev_hash", "") != prev:
            return False, len(lines), f"cadena forward rota en linea {i + 1}"
        prev = _sha(ln)
    return True, len(lines), "cadena forward valida"


# ----------------------------------------------------------------- motor v1
def _fee(notional: float, leg: str, costs: dict[str, float]) -> float:
    base = costs["spot_taker"] if leg == "spot" else costs["perp_taker"]
    return float(notional * (base + costs["slippage_bps"] / 10_000.0))


def init_state(
    capital: float, now: datetime, costs: dict[str, float] | None = None
) -> dict[str, Any]:
    per = capital * SLEEVE_CAPITAL_FRAC
    costs = dict(costs or DEFAULT_COSTS)
    return {
        "version": "forward-v1",
        "created_utc": now.isoformat(),
        "initial_capital_usdt": capital,
        "costs": costs,
        "sleeves": {
            "H1_BTCUSDT": {"capital": per, "cash": per, "qty": 0.0},
            "H1_ETHUSDT": {"capital": per, "cash": per, "qty": 0.0},
            "H3_BTCETH": {
                "capital": per,
                "cash": per,
                "active": {a: False for a in ASSETS},
                "spot_qty": {a: 0.0 for a in ASSETS},
                "perp_qty": {a: 0.0 for a in ASSETS},
                "perp_last": {a: None for a in ASSETS},
                "last_funding_ts": now.isoformat(),
            },
            "H2_basket": {"capital": per, "cash": per, "qty": {}, "last_week": None},
        },
        "last_step_utc": None,
    }


def _close_price(daily: pd.DataFrame | None) -> float | None:
    if daily is None or daily.empty:
        return None
    return float(np.asarray(daily["close"].to_numpy(), dtype=float)[-1])


def step_h1(
    sleeve: dict[str, Any],
    price: float,
    target_exposure: float,
    costs: dict[str, float],
    now: datetime,
    asset: str,
) -> list[dict[str, Any]]:
    """Ajusta al objetivo de la regla congelada (banda ±10 pp ya aplicada en
    signals). Umbral notional mínimo para no sangrar con micro-ajustes."""
    equity = float(sleeve["cash"]) + float(sleeve["qty"]) * price
    if equity <= 0:
        return []
    # Banda congelada (PREREGISTRO s4): dentro de ±BAND no se toca nada; los
    # flips de signo siempre operan. Sin esto, la deriva de comisiones sobre
    # el patrimonio provocaria micro-rebalanceos que sangran costes (bug ya
    # visto en M2 con senal sembrada).
    cur_expo = float(sleeve["qty"]) * price / equity
    flip = (target_exposure > 0.0) != (cur_expo > 0.0)
    if not flip and abs(target_exposure - cur_expo) < BAND:
        return []
    target_qty = target_exposure * equity / price
    delta = target_qty - float(sleeve["qty"])
    if abs(delta) * price < MIN_NOTIONAL_PAPER:
        return []
    notional = abs(delta) * price
    fee = _fee(notional, "spot", costs)
    sleeve["cash"] = float(sleeve["cash"]) - delta * price - fee
    sleeve["qty"] = target_qty
    return [
        {
            "sleeve": f"H1_{asset}",
            "asset": asset,
            "leg": "spot",
            "side": "rebalance",
            "qty": round(delta, 8),
            "price": price,
            "notional": round(notional, 2),
            "fee_usd": round(fee, 4),
            "target_exposure": target_exposure,
            "ts": now.isoformat(),
        }
    ]


def step_h3(
    sleeve: dict[str, Any],
    prices: dict[str, float],
    active: dict[str, bool],
    funding: dict[str, pd.DataFrame],
    costs: dict[str, float],
    now: datetime,
) -> tuple[list[dict[str, Any]], float]:
    """Pata delta-neutra por activo: spot largo + perp corto cuando la señal
    congelada (MA30d anualizada > 5 %) está activa; funding real por evento."""
    fills: list[dict[str, Any]] = []
    funding_usd = 0.0
    last_funding_ts = pd.Timestamp(sleeve["last_funding_ts"])
    new_last = last_funding_ts
    for asset in ASSETS:
        px = prices.get(asset)
        if px is None:
            continue
        q = float(sleeve["perp_qty"][asset])
        prev = sleeve["perp_last"][asset]
        if q != 0.0 and prev is not None:
            sleeve["cash"] = float(sleeve["cash"]) + q * (px - float(prev))
        sleeve["perp_last"][asset] = px
        if q != 0.0:
            f = funding.get(asset)
            if f is not None and not f.empty and "funding_time" in f.columns:
                ft = pd.to_datetime(f["funding_time"], utc=True)
                mask = ft > last_funding_ts
                for rate in f.loc[mask, "funding_rate"].astype(float):
                    pay = -q * px * rate
                    sleeve["cash"] = float(sleeve["cash"]) + pay
                    funding_usd += pay
                if mask.any():
                    cand = ft[mask].max()
                    new_last = max(new_last, cand)
    sleeve["last_funding_ts"] = new_last.isoformat()
    for asset in ASSETS:
        px = prices.get(asset)
        if px is None:
            continue
        want = bool(active.get(asset, False))
        have = bool(sleeve["active"][asset])
        if want and not have:
            q = (float(sleeve["cash"]) * 0.5) / px  # mitad de la caja por pata spot
            notional = q * px
            fee = _fee(notional, "spot", costs) + _fee(notional, "perp", costs)
            sleeve["cash"] = float(sleeve["cash"]) - notional - fee
            sleeve["spot_qty"][asset] = q
            sleeve["perp_qty"][asset] = -q
            sleeve["perp_last"][asset] = px
            sleeve["active"][asset] = True
            fills.append(
                {
                    "sleeve": "H3_BTCETH",
                    "asset": asset,
                    "leg": "spot+perp",
                    "side": "open",
                    "qty": round(q, 8),
                    "price": px,
                    "notional": round(notional, 2),
                    "fee_usd": round(fee, 4),
                    "ts": now.isoformat(),
                }
            )
        elif not want and have:
            q = float(sleeve["spot_qty"][asset])
            if q > 0:
                notional = q * px
                fee = _fee(notional, "spot", costs) + _fee(notional, "perp", costs)
                sleeve["cash"] = float(sleeve["cash"]) + notional - fee
                fills.append(
                    {
                        "sleeve": "H3_BTCETH",
                        "asset": asset,
                        "leg": "spot+perp",
                        "side": "close",
                        "qty": round(-q, 8),
                        "price": px,
                        "notional": round(notional, 2),
                        "fee_usd": round(fee, 4),
                        "ts": now.isoformat(),
                    }
                )
            sleeve["spot_qty"][asset] = 0.0
            sleeve["perp_qty"][asset] = 0.0
            sleeve["perp_last"][asset] = px
            sleeve["active"][asset] = False
    return fills, funding_usd


def step_h2(
    sleeve: dict[str, Any],
    prices: dict[str, float],
    weights: dict[str, float],
    week_key: str,
    costs: dict[str, float],
    now: datetime,
) -> list[dict[str, Any]]:
    """Rebalanceo semanal (solo cuando cambia la semana ISO) a la cesta PIT."""
    fills: list[dict[str, Any]] = []
    if sleeve.get("last_week") == week_key or not weights:
        return fills
    qty: dict[str, float] = sleeve["qty"]
    equity = float(sleeve["cash"]) + sum(q * prices.get(a, 0.0) for a, q in qty.items())
    for asset, w in weights.items():
        px = prices.get(asset)
        if px is None or px <= 0:
            continue
        target_q = w * equity / px
        delta = target_q - float(qty.get(asset, 0.0))
        if abs(delta) * px < MIN_NOTIONAL_PAPER:
            continue
        fee = _fee(abs(delta) * px, "spot", costs)
        sleeve["cash"] = float(sleeve["cash"]) - delta * px - fee
        qty[asset] = target_q
        fills.append(
            {
                "sleeve": "H2_basket",
                "asset": asset,
                "leg": "spot",
                "side": "rebalance_semanal",
                "qty": round(delta, 8),
                "price": px,
                "notional": round(abs(delta) * px, 2),
                "fee_usd": round(fee, 4),
                "weight": w,
                "ts": now.isoformat(),
            }
        )
    sleeve["last_week"] = week_key
    return fills


def sleeve_equity(sleeve_name: str, sleeve: dict[str, Any], prices: dict[str, float]) -> float:
    if sleeve_name.startswith("H1"):
        asset = sleeve_name.split("_", 1)[1]
        return float(sleeve["cash"]) + float(sleeve["qty"]) * prices.get(asset, 0.0)
    if sleeve_name == "H3_BTCETH":
        # perp liquidado a diario: su PnL ya está en caja
        return float(sleeve["cash"]) + sum(
            float(q) * prices.get(a, 0.0) for a, q in sleeve["spot_qty"].items()
        )
    return float(sleeve["cash"]) + sum(
        float(q) * prices.get(a, 0.0) for a, q in sleeve["qty"].items()
    )


def run_step(
    state: dict[str, Any],
    cells: dict[str, Any],
    h2_weights: dict[str, float],
    daily_closes: dict[str, pd.DataFrame | None],
    funding: dict[str, pd.DataFrame],
    now: datetime,
    h3_active: dict[str, bool],
) -> tuple[dict[str, Any], dict[str, float]]:
    """UN paso forward sobre las 5 celdas congeladas → (registro, patrimonios).

    ``h3_active`` por activo lo determina el llamador con ``compute_states``
    (single source of truth: el motor no reimplementa reglas).
    """
    costs: dict[str, float] = state.get("costs", DEFAULT_COSTS)
    raw = {a: _close_price(df) for a, df in daily_closes.items()}
    prices: dict[str, float] = {a: p for a, p in raw.items() if p is not None}
    fills: list[dict[str, Any]] = []
    sleeves = state["sleeves"]
    for asset in ASSETS:
        if asset in prices:
            target = float(cells.get(f"H1_{asset}", {}).get("posicion_regla", 0.0) or 0.0)
            fills += step_h1(sleeves[f"H1_{asset}"], prices[asset], target, costs, now, asset)
    f3, funding_usd = step_h3(sleeves["H3_BTCETH"], prices, h3_active, funding, costs, now)
    fills += f3
    fills += step_h2(sleeves["H2_basket"], prices, h2_weights, now.strftime("%G-W%V"), costs, now)
    equities = {name: round(sleeve_equity(name, sl, prices), 2) for name, sl in sleeves.items()}
    total = round(sum(equities.values()), 2)
    state["last_step_utc"] = now.isoformat()
    record: dict[str, Any] = {
        "kind": "forward_v1_step",
        "fills": fills,
        "funding_usd": round(funding_usd, 4),
        "h3_active": h3_active,
        "h1_targets": {a: cells.get(f"H1_{a}", {}).get("posicion_regla") for a in ASSETS},
        "h2_weights": h2_weights,
        "prices_used": {a: round(p, 4) for a, p in prices.items()},
        "sleeve_equity_usdt": equities,
        "total_equity_usdt": total,
        "total_return_pct": round((total / float(state["initial_capital_usdt"]) - 1.0) * 100.0, 4),
        "state_version": state["version"],
    }
    return record, equities


def load_state(root: Path) -> dict[str, Any] | None:
    p = root / STATE_RELPATH
    if not p.exists():
        return None
    out: dict[str, Any] = json.loads(p.read_text(encoding="utf-8"))
    return out


def save_state(root: Path, state: dict[str, Any]) -> None:
    p = root / STATE_RELPATH
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(state, indent=1, ensure_ascii=False), encoding="utf-8")
