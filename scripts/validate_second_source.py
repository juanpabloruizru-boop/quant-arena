"""Segunda fuente independiente de precios BTC/ETH, periodo completo (condicion F).

Fuente: Coinbase Exchange (api.exchange.coinbase.com), velas diarias UTC de
BTC-USD y ETH-USD (quote USD: la diferencia frente a nuestros USDT incluye el
riesgo de base USDT/USD y se reporta tal cual, sin ajustar).

Paginacion: ventanas de <=290 dias (maximo 300 velas por peticion).
Periodo: 2017-08-17 (primera vela BTCUSDT) -> 2025-10-25 (data freeze,
in-sample; el holdout NO se toca).

Metricas (calidad de datos, no de estrategia):
- diferencia de retorno acumulado del activo en ambas fuentes;
- correlacion de Pearson de los retornos diarios comunes;
- cobertura de dias.

Salida: docs/evidence/second_source_validation.json
"""

from __future__ import annotations

import json
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

from qa.backtest.data_access import load_in_sample
from qa.data.client import BinancePublicClient

REPO = Path(__file__).resolve().parents[1]
OUT = REPO / "docs" / "evidence" / "second_source_validation.json"
CB = "https://api.exchange.coinbase.com"
START = datetime(2017, 8, 17, tzinfo=UTC)
END = datetime(2025, 10, 25, 23, 59, 59, tzinfo=UTC)
PAIRS = {"BTCUSDT": "BTC-USD", "ETHUSDT": "ETH-USD"}
WINDOW_DAYS = 290


def coinbase_daily(client: BinancePublicClient, pair: str) -> pd.DataFrame:
    frames = []
    cur = START
    while cur < END:
        nxt = min(cur + timedelta(days=WINDOW_DAYS), END)
        rows = client.get_json(
            CB,
            f"/products/{pair}/candles",
            {
                "granularity": 86400,
                "start": cur.strftime("%Y-%m-%dT%H:%M:%SZ"),
                "end": nxt.strftime("%Y-%m-%dT%H:%M:%SZ"),
            },
        )
        if rows:
            frames.append(
                pd.DataFrame(
                    [
                        {"time": pd.Timestamp(int(r[0]), unit="s", tz="UTC"), "close": float(r[4])}
                        for r in rows
                    ]
                )
            )
        cur = nxt + timedelta(seconds=1)
    if not frames:
        raise RuntimeError(f"sin datos de Coinbase para {pair}")
    df = pd.concat(frames, ignore_index=True)
    df["day"] = df["time"].dt.floor("D")
    df = df.drop_duplicates(subset="day", keep="last").sort_values("day")
    return df[["day", "close"]].reset_index(drop=True)


def main() -> None:
    spot = load_in_sample("spot_daily", REPO)
    out: dict[str, Any] = {
        "generated_at_utc": datetime.now(UTC).isoformat(timespec="seconds"),
        "source": "Coinbase Exchange /products/{pair}/candles?granularity=86400 (USD quote)",
        "window": [str(START.date()), str(END.date())],
        "note": (
            "Diferencia de retorno acumulado Binance(USDT) vs Coinbase(USD): incluye "
            "riesgo de base USDT/USD del periodo; se reporta sin ajustar."
        ),
        "assets": {},
    }
    with BinancePublicClient(min_interval_s=0.35) as client:
        for sym, pair in PAIRS.items():
            cb = coinbase_daily(client, pair)
            qa = spot[spot["symbol"] == sym].sort_values("open_time")
            qa = qa[qa["open_time"] <= END]
            qa_day = qa["open_time"].dt.floor("D")
            qa_s = pd.Series(qa["close"].to_numpy(), index=qa_day)
            cb_s = pd.Series(cb["close"].to_numpy(), index=cb["day"])
            both = pd.concat([qa_s.rename("qa"), cb_s.rename("cb")], axis=1).dropna()
            # primera fecha comun: Coinbase BTC-USD existe desde 2015; ETH desde 2016;
            # la comparacion usa el solape real con nuestra serie
            r_qa = both["qa"].pct_change().dropna()
            r_cb = both["cb"].pct_change().dropna()
            n = min(len(r_qa), len(r_cb))
            corr = float(np.corrcoef(r_qa[:n], r_cb[:n])[0, 1])
            cum_qa = float(both["qa"].iloc[-1] / both["qa"].iloc[0] - 1.0)
            cum_cb = float(both["cb"].iloc[-1] / both["cb"].iloc[0] - 1.0)
            out["assets"][sym] = {
                "coinbase_pair": pair,
                "common_days": int(len(both)),
                "first_common_day": str(both.index[0].date()),
                "last_common_day": str(both.index[-1].date()),
                "cum_return_binance_usdt": round(cum_qa, 6),
                "cum_return_coinbase_usd": round(cum_cb, 6),
                "cum_return_diff_pp": round((cum_qa - cum_cb) * 100.0, 3),
                "daily_return_correlation": round(corr, 6),
            }
            print(sym, json.dumps(out["assets"][sym], indent=1))
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(out, indent=2), encoding="utf-8")
    print("->", OUT)


if __name__ == "__main__":
    main()
