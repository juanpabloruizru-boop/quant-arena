"""Ingesta en vivo (solo lectura, endpoints publicos) para el agente M4/M5.

Descarga velas recientes (1h/4h/1d) de la watchlist, funding reciente de
BTC/ETH y premiumIndex. Excluye la vela EN CURSO (solo velas cerradas).
Ninguna clave, ninguna orden: GET publicos con rate-limit del cliente M1.
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

import pandas as pd

from qa.data.client import FAPI_BASE, SPOT_BASE, BinancePublicClient
from qa.data.klines import fetch_klines_paged, klines_frame
from qa.data.timestamps import to_utc_datetime

LIMITS = {"1h": 96, "4h": 180, "1d": 400, "1w": 110}


def _drop_forming(df: pd.DataFrame, interval: str) -> pd.DataFrame:
    """Descarta la vela en curso (close_time en el futuro)."""
    now = datetime.now(UTC)
    if df.empty:
        return df
    return df[df["close_time"] < now].copy()


def fetch_live(watchlist: list[str]) -> dict[str, Any]:
    """Una pasada de ingesta en vivo. Devuelve DataFrames por simbolo/intervalo."""
    out: dict[str, Any] = {"fetched_at_utc": datetime.now(UTC).isoformat(timespec="seconds")}
    kl: dict[str, dict[str, pd.DataFrame]] = {}
    with BinancePublicClient() as c:
        for sym in watchlist:
            kl[sym] = {}
            for interval, limit in LIMITS.items():
                now_ms = int(datetime.now(UTC).timestamp() * 1000)
                rows = fetch_klines_paged(
                    c,
                    SPOT_BASE,
                    "/api/v3/klines",
                    sym,
                    interval,
                    start_ms=now_ms - _span_ms(interval, limit),
                    end_ms=now_ms,
                    limit=limit,
                    max_pages=1 if interval != "1d" else 1,
                )
                # fetch_klines_paged pagina hacia adelante desde start; con un
                # solo max_pages y limit adecuado traemos la cola reciente
                df = klines_frame(rows, sym, interval) if rows else pd.DataFrame()
                if not df.empty and len(df) > limit:
                    df = df.tail(limit).reset_index(drop=True)
                kl[sym][interval] = _drop_forming(df, interval)
        # funding reciente BTC/ETH (35 dias) + premiumIndex
        fund: dict[str, pd.DataFrame] = {}
        prem: dict[str, dict[str, Any]] = {}
        for sym in ("BTCUSDT", "ETHUSDT"):
            start = int(datetime.now(UTC).timestamp() * 1000) - 35 * 86_400_000
            end = int(datetime.now(UTC).timestamp() * 1000)
            frows = c.get_json(
                FAPI_BASE,
                "/fapi/v1/fundingRate",
                {"symbol": sym, "startTime": start, "endTime": end, "limit": 1000},
            )
            fund[sym] = pd.DataFrame(
                [
                    {
                        "funding_time": to_utc_datetime(int(r["fundingTime"])),
                        "funding_rate": float(r["fundingRate"]),
                    }
                    for r in (frows or [])
                ]
            )
            pi = c.get_json(FAPI_BASE, "/fapi/v1/premiumIndex", {"symbol": sym})
            prem[sym] = {
                "mark_price": float(pi["markPrice"]),
                "last_funding_rate": float(pi["lastFundingRate"]),
                "next_funding_utc": to_utc_datetime(int(pi["nextFundingTime"])).isoformat(),
            }
    out["klines"] = kl
    out["funding"] = fund
    out["premium"] = prem
    return out


def _span_ms(interval: str, limit: int) -> int:
    step = {"1h": 3_600_000, "4h": 14_400_000, "1d": 86_400_000, "1w": 604_800_000}[interval]
    return int(step * limit * 1.05) + step


def fetch_extra_daily(symbols: list[str], limit: int = 400) -> dict[str, pd.DataFrame]:
    """Diarias recientes para simbolos fuera de la watchlist (miembros PIT de H2)."""
    out: dict[str, pd.DataFrame] = {}
    with BinancePublicClient() as c:
        for sym in symbols:
            now_ms = int(datetime.now(UTC).timestamp() * 1000)
            rows = fetch_klines_paged(
                c,
                SPOT_BASE,
                "/api/v3/klines",
                sym,
                "1d",
                start_ms=now_ms - int(86_400_000 * limit * 1.05),
                end_ms=now_ms,
                limit=limit,
                max_pages=1,
            )
            df = klines_frame(rows, sym, "1d") if rows else pd.DataFrame()
            if not df.empty and len(df) > limit:
                df = df.tail(limit).reset_index(drop=True)
            out[sym] = _drop_forming(df, "1d")
    return out


def last_price(live: dict[str, Any], symbol: str) -> float | None:
    kl = live.get("klines", {}).get(symbol, {}).get("1h")
    if kl is None or kl.empty:
        return None
    return float(kl["close"].iloc[-1])


def fetch_prices(symbols: list[str]) -> dict[str, float]:
    """Último precio spot por símbolo (ticker/price): solo lectura, tolerante a fallos.

    Se usa para la contabilidad del usuario (M5b) sin descargar velas completas.
    """
    out: dict[str, float] = {}
    syms = sorted(set(symbols))
    if not syms:
        return out
    with BinancePublicClient() as c:
        for s in syms:
            try:
                r = c.get_json(SPOT_BASE, "/api/v3/ticker/price", {"symbol": s})
                if r and "price" in r:
                    out[s] = float(r["price"])
            except Exception:
                continue
    return out
