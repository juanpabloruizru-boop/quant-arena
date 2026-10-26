"""Descarga paginada de funding historico real (USDT-M) (M1).

Quirk verificado 2026-10-26: startTime=0 es IGNORADO (devuelve recientes).
Por eso la paginacion arranca siempre de una fecha explicita y avanza con
``fundingTime + 1`` de la ultima fila.
"""

from __future__ import annotations

from typing import Any

import pandas as pd

from qa.data.client import JsonClient
from qa.data.timestamps import assert_consistent_units, to_utc_datetime


def fetch_funding_paged(
    client: JsonClient,
    symbol: str,
    start_ms: int,
    end_ms: int,
    limit: int = 1000,
    max_pages: int = 100,
) -> list[dict[str, Any]]:
    out: dict[int, dict[str, Any]] = {}
    cursor = start_ms
    for _ in range(max_pages):
        rows = client.get_json(
            "https://fapi.binance.com",
            "/fapi/v1/fundingRate",
            {"symbol": symbol, "startTime": cursor, "endTime": end_ms, "limit": limit},
        )
        if not isinstance(rows, list) or not rows:
            break
        times = [int(r["fundingTime"]) for r in rows]
        assert_consistent_units(times, "ms")
        for r in rows:
            out[int(r["fundingTime"])] = r
        nxt = max(times) + 1
        if nxt <= cursor or len(rows) < limit:
            break
        cursor = nxt
    return [out[k] for k in sorted(out)]


def funding_frame(rows: list[dict[str, Any]], symbol: str) -> pd.DataFrame:
    recs = [
        {
            "symbol": symbol,
            "funding_time": to_utc_datetime(int(r["fundingTime"])),
            "funding_rate": float(r["fundingRate"]),
            "mark_price": float(r["markPrice"]) if r.get("markPrice") else None,
        }
        for r in rows
    ]
    df = pd.DataFrame.from_records(recs)
    if df.empty:
        return pd.DataFrame(columns=["symbol", "funding_time", "funding_rate", "mark_price"])
    return df.sort_values("funding_time").reset_index(drop=True)
