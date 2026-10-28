"""Correlacion Binance-Coinbase por anio y con desfase +-1 dia (condicion H3, gate M2b).

Explica la correlacion global 0.990/0.993 del informe M2b:
- desglose por anio (esperable: menor en 2017-18, mayor reciente);
- correlaciones con desfase +-1 dia (si la alineacion temporal es correcta, el
  desfase 0 debe dominar claramente);
- dias con mayor discrepancia absoluta.

Salida: docs/evidence/second_source_correlation.json
"""

from __future__ import annotations

import json
import sys
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import pandas as pd

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "scripts"))

from qa.backtest.data_access import load_in_sample  # noqa: E402
from qa.data.client import BinancePublicClient  # noqa: E402
from validate_second_source import coinbase_daily  # noqa: E402

OUT = REPO / "docs" / "evidence" / "second_source_correlation.json"
PAIRS = {"BTCUSDT": "BTC-USD", "ETHUSDT": "ETH-USD"}


def main() -> None:
    spot = load_in_sample("spot_daily", REPO)
    out: dict[str, Any] = {
        "generated_at_utc": datetime.now(UTC).isoformat(timespec="seconds"),
        "source": "Coinbase Exchange /products/{pair}/candles (USD) vs Binance curado (USDT)",
        "assets": {},
    }
    with BinancePublicClient(min_interval_s=0.35) as client:
        for sym, pair in PAIRS.items():
            cb = coinbase_daily(client, pair)
            qa = spot[spot["symbol"] == sym].sort_values("open_time")
            qa_s = pd.Series(qa["close"].to_numpy(), index=qa["open_time"].dt.floor("D"))
            cb_s = pd.Series(cb["close"].to_numpy(), index=cb["day"])
            both = pd.concat([qa_s.rename("qa"), cb_s.rename("cb")], axis=1).dropna()
            r = pd.DataFrame(
                {"qa": both["qa"].pct_change(), "cb": both["cb"].pct_change()}
            ).dropna()
            entry: dict[str, Any] = {
                "n_days": int(len(r)),
                "corr_lag0": round(float(r["qa"].corr(r["cb"])), 5),
                "corr_lag_minus1_cb_leads": round(float(r["qa"].corr(r["cb"].shift(-1))), 5),
                "corr_lag_plus1_qa_leads": round(float(r["qa"].corr(r["cb"].shift(1))), 5),
                "by_year": {},
            }
            years = pd.DatetimeIndex(r.index).year
            for year, g in r.groupby(years):
                entry["by_year"][str(year)] = {
                    "n": int(len(g)),
                    "corr": round(float(g["qa"].corr(g["cb"])), 5),
                }
            diff = (r["qa"] - r["cb"]).abs()
            worst = diff.sort_values(ascending=False).head(5)
            entry["worst_days"] = [
                {"date": str(pd.Timestamp(str(d)).date()), "abs_diff_pp": round(float(v) * 100, 2)}
                for d, v in worst.items()
            ]
            entry["mean_abs_diff_bps"] = round(float(diff.mean()) * 10_000, 2)
            out["assets"][sym] = entry
            print(sym, json.dumps(entry, indent=1))
    OUT.write_text(json.dumps(out, indent=2), encoding="utf-8")
    print("->", OUT)


if __name__ == "__main__":
    main()
