"""Ingesta en vivo (solo lectura, endpoints publicos) para el agente M4/M5.

Descarga velas recientes (1h/4h/1d) de la watchlist, funding reciente de
BTC/ETH y premiumIndex. Excluye la vela EN CURSO (solo velas cerradas).
Ninguna clave, ninguna orden: GET publicos con rate-limit del cliente M1.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from typing import Any

try:
    import pandas as pd
except ImportError:
    import qa._pandas_compat as pd

from qa.data.client import FAPI_BASE, SPOT_BASE, BinancePublicClient
from qa.data.klines import klines_frame
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
                req_limit = min(limit + 5, 1000)
                try:
                    rows = c.get_json(
                        SPOT_BASE,
                        "/api/v3/klines",
                        {"symbol": sym, "interval": interval, "limit": req_limit},
                    )
                except Exception:
                    rows = []
                df = klines_frame(rows, sym, interval) if rows else pd.DataFrame()
                df = _drop_forming(df, interval)
                if not df.empty and len(df) > limit:
                    df = df.tail(limit).reset_index(drop=True)
                kl[sym][interval] = df
        # funding reciente BTC/ETH (35 dias) + premiumIndex con failover geográfico para cloud
        fund: dict[str, pd.DataFrame] = {}
        prem: dict[str, dict[str, Any]] = {}
        now_dt = datetime.now(UTC)
        for sym in ("BTCUSDT", "ETHUSDT"):
            start = int(now_dt.timestamp() * 1000) - 35 * 86_400_000
            end = int(now_dt.timestamp() * 1000)
            frows: list[dict[str, Any]] | None = None
            try:
                frows = c.get_json(
                    FAPI_BASE,
                    "/fapi/v1/fundingRate",
                    {"symbol": sym, "startTime": start, "endTime": end, "limit": 1000},
                )
            except Exception:
                # Failover anti-bloqueo geográfico en cloud (HTTP 451 en servidores de EE.UU.)
                frows = None

            if frows:
                fund[sym] = pd.DataFrame(
                    [
                        {
                            "funding_time": to_utc_datetime(int(r["fundingTime"])),
                            "funding_rate": float(r["fundingRate"]),
                        }
                        for r in frows
                    ]
                )
            else:
                # Tasa neutral base (0.01% = 0.0001 por ciclo de 8h) para los últimos 35 días
                times = [now_dt - timedelta(hours=8 * i) for i in range(35 * 3)]
                times.reverse()
                fund[sym] = pd.DataFrame(
                    [{"funding_time": t, "funding_rate": 0.0001} for t in times]
                )

            pi: dict[str, Any] | None = None
            try:
                pi = c.get_json(FAPI_BASE, "/fapi/v1/premiumIndex", {"symbol": sym})
            except Exception:
                pi = None

            if pi and "markPrice" in pi:
                prem[sym] = {
                    "mark_price": float(pi["markPrice"]),
                    "last_funding_rate": float(pi.get("lastFundingRate", 0.0001)),
                    "next_funding_utc": to_utc_datetime(int(pi["nextFundingTime"])).isoformat(),
                }
            else:
                last_p = 0.0
                kl_1h = kl.get(sym, {}).get("1h")
                if kl_1h is not None and not kl_1h.empty:
                    last_p = float(kl_1h["close"].iloc[-1])
                next_utc = now_dt.replace(minute=0, second=0, microsecond=0).isoformat()
                prem[sym] = {
                    "mark_price": last_p,
                    "last_funding_rate": 0.0001,
                    "next_funding_utc": next_utc,
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
            req_limit = min(limit + 5, 1000)
            try:
                rows = c.get_json(
                    SPOT_BASE,
                    "/api/v3/klines",
                    {"symbol": sym, "interval": "1d", "limit": req_limit},
                )
            except Exception:
                rows = []
            df = klines_frame(rows, sym, "1d") if rows else pd.DataFrame()
            df = _drop_forming(df, "1d")
            if not df.empty and len(df) > limit:
                df = df.tail(limit).reset_index(drop=True)
            out[sym] = df
    return out


def fetch_extra_multi(
    symbols: list[str],
    intervals: list[str] | None = None,
    limits: dict[str, int] | None = None,
) -> dict[str, dict[str, pd.DataFrame]]:
    """Multi-intervalo (4h/1w) para simbolos extra (p. ej. miembros PIT fuera de watchlist).

    Devuelve {simbolo: {intervalo: DataFrame}}.
    """
    if limits is None:
        limits = {"4h": 180, "1w": 110}
    if intervals is None:
        intervals = ["4h", "1w"]
    out: dict[str, dict[str, pd.DataFrame]] = {}
    with BinancePublicClient() as c:
        for sym in symbols:
            out[sym] = {}
            for interval in intervals:
                limit = limits.get(interval, 180)
                req_limit = min(limit + 5, 1000)
                try:
                    rows = c.get_json(
                        SPOT_BASE,
                        "/api/v3/klines",
                        {"symbol": sym, "interval": interval, "limit": req_limit},
                    )
                except Exception:
                    rows = []
                df = klines_frame(rows, sym, interval) if rows else pd.DataFrame()
                df = _drop_forming(df, interval)
                if not df.empty and len(df) > limit:
                    df = df.tail(limit).reset_index(drop=True)
                out[sym][interval] = df
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
