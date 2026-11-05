"""Descarga paginada de klines spot y futures USDT-M (M1).

Reglas:
- El limite real de /api/v3/klines es 1000 filas (verificado 2026-10-26: pedir
  1500/1501 devuelve 1000 sin error): se pagina con startTime.
- Timestamps normalizados a ms UTC (deteccion por magnitud, nunca asumida).
- Se excluye el dia en curso: ``end_ms`` lo fija el llamador al ultimo dia
  UTC completo (data freeze).
"""

from __future__ import annotations

from typing import Any

try:
    import pandas as pd
except ImportError:
    import qa._pandas_compat as pd

from qa.data.client import JsonClient
from qa.data.timestamps import assert_consistent_units, to_ms, to_utc_datetime

SPOT_KLINES_COLS: list[str] = [
    "open_time",
    "open",
    "high",
    "low",
    "close",
    "volume",
    "close_time",
    "quote_volume",
    "n_trades",
    "taker_buy_base",
    "taker_buy_quote",
]
INTERVAL_MS = {"1d": 86_400_000, "4h": 14_400_000, "1h": 3_600_000}


def fetch_klines_paged(
    client: JsonClient,
    base_url: str,
    path: str,
    symbol: str,
    interval: str,
    start_ms: int,
    end_ms: int,
    limit: int = 1000,
    max_pages: int = 200,
) -> list[list[Any]]:
    """Pagina klines [start_ms, end_ms] y devuelve filas crudas deduplicadas."""
    step = INTERVAL_MS.get(interval)
    if step is None:
        if max_pages > 1:
            raise ValueError(f"intervalo {interval} no soportado en paginacion fija")
        # peticion unica sin paginacion (p. ej. klines mensuales '1M')
        rows = client.get_json(
            base_url,
            path,
            {
                "symbol": symbol,
                "interval": interval,
                "startTime": start_ms,
                "endTime": end_ms,
                "limit": limit,
            },
        )
        if not isinstance(rows, list) or not rows:
            return []
        opens = [int(r[0]) for r in rows]
        assert_consistent_units(opens, "ms")
        dedup = {int(r[0]): r for r in rows}
        return [dedup[k] for k in sorted(dedup)]
    out: dict[int, list[Any]] = {}
    cursor = start_ms
    for _ in range(max_pages):
        rows = client.get_json(
            base_url,
            path,
            {
                "symbol": symbol,
                "interval": interval,
                "startTime": cursor,
                "endTime": end_ms,
                "limit": limit,
            },
        )
        if not isinstance(rows, list) or not rows:
            break
        opens = [int(r[0]) for r in rows]
        assert_consistent_units(opens, "ms")
        for r in rows:
            out[int(r[0])] = r
        nxt = max(opens) + step
        if nxt <= cursor or len(rows) < limit:
            break
        cursor = nxt
    return [out[k] for k in sorted(out)]


def klines_frame(rows: list[list[Any]], symbol: str, interval: str) -> pd.DataFrame:
    """Filas crudas -> DataFrame tipado con open_time en UTC."""
    recs: list[dict[str, Any]] = []
    for r in rows:
        if len(r) < 11:
            raise ValueError(f"fila de klines con {len(r)} columnas (<11) en {symbol}")
        recs.append(
            {
                "symbol": symbol,
                "interval": interval,
                "open_time": to_utc_datetime(to_ms(int(r[0]))),
                "open": float(r[1]),
                "high": float(r[2]),
                "low": float(r[3]),
                "close": float(r[4]),
                "volume": float(r[5]),
                "close_time": to_utc_datetime(to_ms(int(r[6]))),
                "quote_volume": float(r[7]),
                "n_trades": int(r[8]),
                "taker_buy_base": float(r[9]),
                "taker_buy_quote": float(r[10]),
            }
        )
    df = pd.DataFrame.from_records(recs)
    if df.empty:
        return pd.DataFrame(
            columns=[
                "symbol",
                "interval",
                "open_time",
                "open",
                "high",
                "low",
                "close",
                "volume",
                "close_time",
                "quote_volume",
                "n_trades",
                "taker_buy_base",
                "taker_buy_quote",
            ]
        )
    return df.sort_values("open_time").reset_index(drop=True)
