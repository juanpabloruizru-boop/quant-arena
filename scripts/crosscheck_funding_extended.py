"""Cross-check ampliado de funding (condicion 5, gate M1).

Compara el funding historico descargado del API (data/raw/funding/*.parquet)
contra los dumps MENSUALES independientes de data.binance.vision, para >=12
meses aleatorios (semilla fija) repartidos 2019-2025, en BTC y ETH.

Reporta por mes: filas del dump, filas del API, comunes y discrepancias
(tolerancia exacta 1e-12 sobre la tasa). Salida:
docs/evidence/funding_crosscheck_extended.json
"""

from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

from qa.data.client import BinancePublicClient
from qa.data.paths import raw_dir
from qa.data.vision import parse_csv_zip

REPO = Path(__file__).resolve().parents[1]
OUT = REPO / "docs" / "evidence" / "funding_crosscheck_extended.json"
SEED = 20261026
BUCKET = "https://s3-ap-northeast-1.amazonaws.com/data.binance.vision"


def _months(
    rng: np.random.Generator, start: tuple[int, int], end: tuple[int, int], k: int
) -> list[str]:
    y0, m0 = start
    y1, m1 = end
    idx0 = y0 * 12 + (m0 - 1)
    idx1 = y1 * 12 + (m1 - 1)
    picks = sorted(rng.choice(np.arange(idx0, idx1 + 1), size=k, replace=False))
    return [f"{int(p) // 12}-{int(p) % 12 + 1:02d}" for p in picks]


def main() -> None:
    rng = np.random.default_rng(SEED)
    plan = {
        "BTCUSDT": _months(rng, (2019, 10), (2025, 9), 7),
        "ETHUSDT": _months(rng, (2020, 1), (2025, 9), 7),
    }
    out: dict[str, Any] = {
        "generated_at_utc": datetime.now(UTC).isoformat(timespec="seconds"),
        "seed": SEED,
        "months": plan,
        "results": [],
    }
    total_common = total_mismatch = 0
    with BinancePublicClient() as client:
        for sym, months in plan.items():
            api = pd.read_parquet(raw_dir(REPO) / "funding" / f"{sym}.parquet")
            api_map = {
                int(t.timestamp() * 1000): float(x)
                for t, x in zip(api["funding_time"], api["funding_rate"], strict=True)
            }
            for ym in months:
                key = f"data/futures/um/monthly/fundingRate/{sym}/{sym}-fundingRate-{ym}.zip"
                try:
                    content = client.get_bytes(f"{BUCKET}/{key}")
                    rows = parse_csv_zip(content)
                except RuntimeError as e:
                    out["results"].append({"symbol": sym, "month": ym, "error": repr(e)[:150]})
                    continue
                if rows and len(rows[0]) >= 4:
                    dmap = {int(r[1]): float(r[2]) for r in rows}
                else:
                    dmap = {int(r[0]): float(r[2]) for r in rows}
                common = sorted(set(dmap) & set(api_map))
                mism = [t for t in common if abs(dmap[t] - api_map[t]) > 1e-12]
                total_common += len(common)
                total_mismatch += len(mism)
                out["results"].append(
                    {
                        "symbol": sym,
                        "month": ym,
                        "dump_rows": len(dmap),
                        "api_common": len(common),
                        "dump_only": len(set(dmap) - set(api_map)),
                        "api_only_in_month": None,
                        "mismatched": len(mism),
                    }
                )
    out["total_common"] = total_common
    out["total_mismatched"] = total_mismatch
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(out, indent=2, ensure_ascii=False), encoding="utf-8")
    for r in out["results"]:
        print(r)
    print(f"TOTAL comunes={total_common} discrepancias={total_mismatch}")


if __name__ == "__main__":
    main()
