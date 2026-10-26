"""Prueba de aceptacion sintetica 3 (M2): reproducir buy&hold de BTC y ETH
contra una fuente INDEPENDIENTE citada (Kraken, pares XBTUSDT/ETHUSDT — misma
-quote USDT para aislar el riesgo de base USDT/USD), tolerancia +-0.5%.

Ventana: solo IN-SAMPLE (2021-01-01 -> 2025-06-30). El holdout NO se toca.

Compara tres cantidades por activo:
1. engine_bh: buy&hold ejecutado por qa.backtest.engine.run_positions
   (peso 1 constante, capital grande, participacion despreciable).
2. close_ratio: close_fin/close_ini - 1 de nuestros datos curados (identidad
   matematica del fixture B&H).
3. kraken_bh: close_fin/close_ini - 1 de las velas diarias de Kraken.

Evidencia: docs/evidence/bh_validation.json (URLs, fecha de consulta, ventana,
valores y deltas). Salida exitosa si |engine_bh - kraken_bh| <= 0.5% por activo.
"""

from __future__ import annotations

import json
import sys
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "src"))

from qa.backtest.costs import CostModel  # noqa: E402
from qa.backtest.data_access import load_in_sample  # noqa: E402
from qa.backtest.engine import run_positions  # noqa: E402
from qa.data.client import BinancePublicClient  # noqa: E402

# Ventana: la maxima cubierta por el OHLC diario de Kraken (devuelve como mucho
# las ultimas 720 velas diarias; el parametro since se ignora para historicos
# lejanos — verificado empiricamente 2026-10-26) y contenida en el IN-SAMPLE
# (holdout empieza 2025-10-26). Pares XBTUSDT/ETHUSDT: misma quote USDT que
# Binance => sin riesgo de base USDT/USD.
WINDOW_START = pd.Timestamp("2024-12-01", tz="UTC")
WINDOW_END = pd.Timestamp("2025-06-30", tz="UTC")
KRAKEN = "https://api.kraken.com"
PAIRS = {"BTCUSDT": "XBTUSDT", "ETHUSDT": "ETHUSDT"}
TOLERANCE = 0.005


def kraken_daily_ohlc(client: BinancePublicClient, pair: str) -> pd.DataFrame:
    """Velas diarias de Kraken (una peticion: devuelve las ultimas ~720)."""
    data = client.get_json(KRAKEN, "/0/public/OHLC", {"pair": pair, "interval": 1440})
    if data.get("error"):
        raise RuntimeError(f"Kraken error: {data['error']}")
    candles = data["result"].get(pair, [])
    df = pd.DataFrame(
        [
            {"time": pd.Timestamp(int(c[0]), unit="s", tz="UTC"), "close": float(c[4])}
            for c in candles
        ]
    )
    return df[(df["time"] >= WINDOW_START) & (df["time"] <= WINDOW_END)].reset_index(drop=True)


def main() -> None:
    spot = load_in_sample("spot_daily", REPO)
    out: dict[str, Any] = {
        "generated_at_utc": datetime.now(UTC).isoformat(timespec="seconds"),
        "window": [str(WINDOW_START), str(WINDOW_END)],
        "independent_source": "Kraken public OHLC (api.kraken.com/public/OHLC, interval=1440)",
        "tolerance": TOLERANCE,
        "assets": {},
    }
    ok = True
    cm = CostModel(
        spot_taker_fee=0.0,
        perp_taker_fee=0.0,
        slippage_tiers=((1.0, 0.0),),
        max_participation=1.0,
        min_notional_usdt=0.0,
    )
    with BinancePublicClient(min_interval_s=0.3) as client:
        for sym, pair in PAIRS.items():
            df = spot[spot["symbol"] == sym].sort_values("open_time")
            df = df[(df["open_time"] >= WINDOW_START) & (df["open_time"] <= WINDOW_END)]
            close = np.asarray(df["close"].to_numpy(), dtype=np.float64)
            qv = np.asarray(df["quote_volume"].to_numpy(), dtype=np.float64)
            res = run_positions(
                close,
                desired_weight=np.ones(close.shape[0]),
                quote_volume=qv,
                cost_model=cm,
                capital_usdt=1_000.0,
                band=0.0,
            )
            engine_bh = float(np.prod(1.0 + res.net_returns) - 1.0)
            close_ratio = float(close[-1] / close[0] - 1.0)
            kdf = kraken_daily_ohlc(client, pair)
            kraken_bh = float(kdf["close"].iloc[-1] / kdf["close"].iloc[0] - 1.0)
            delta = abs(engine_bh - kraken_bh)
            passed = delta <= TOLERANCE and abs(engine_bh - close_ratio) < 1e-9
            ok &= passed
            out["assets"][sym] = {
                "kraken_pair": pair,
                "n_days_qa": int(len(df)),
                "n_days_kraken": int(len(kdf)),
                "engine_bh": round(engine_bh, 6),
                "close_ratio_qa": round(close_ratio, 6),
                "kraken_bh": round(kraken_bh, 6),
                "delta_engine_kraken": round(delta, 6),
                "passed": passed,
            }
            print(sym, json.dumps(out["assets"][sym], indent=1))
    out["overall_passed"] = bool(ok)
    evid = REPO / "docs" / "evidence" / "bh_validation.json"
    evid.write_text(json.dumps(out, indent=2), encoding="utf-8")
    print("overall:", out["overall_passed"], "->", evid)
    if not ok:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
