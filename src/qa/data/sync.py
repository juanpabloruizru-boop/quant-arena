"""Orquestacion de la ingesta M1 (fases A-F), resumible y determinista.

Fases:
  A  meta        exchangeInfo spot + futures (foto del dia)
  B  monthly     klines mensuales spot de todos los USDT elegibles (ranking PIT)
  C  pool        union del top-60 mensual por quote volume (+ BTC/ETH forzados)
  D  daily       klines diarias spot del pool, desde su primer mes hasta el freeze
  E  futures     klines diarias perp USDT-M de BTC/ETH
  F  funding     funding historico real BTC/ETH (API paginada) + cross-check
                 contra el dump mensual de data.binance.vision (2020-01)

Regla de congelacion: ``freeze_end`` = ultimo dia UTC COMPLETO antes de la
ejecucion (hoy-1). Nada del dia en curso entra en el dataset.
Prohibido en M1: ninguna metrica de estrategia (retorno/Sharpe/drawdown).
"""

from __future__ import annotations

import hashlib
import json
import time
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

import pandas as pd

from qa.data.client import FAPI_BASE, SPOT_BASE, BinancePublicClient
from qa.data.funding import fetch_funding_paged, funding_frame
from qa.data.klines import fetch_klines_paged, klines_frame
from qa.data.manifest import Manifest, read_json_gz, write_json, write_json_gz
from qa.data.paths import config_dir, manifests_dir, raw_dir
from qa.data.timestamps import to_ms
from qa.data.vision import list_keys, parse_csv_zip

STABLE_BASES = {
    "USDC",
    "FDUSD",
    "TUSD",
    "BUSD",
    "DAI",
    "USDP",
    "AEUR",
    "EUR",
    "GBP",
    "XUSD",
    "USD1",
    "PAX",
    "UST",
    "USTC",
    "USDD",
    "GUSD",
    "PYUSD",
    "USDE",
}
WRAPPED_BASES = {"WBTC", "WBETH", "WBNB", "BTCB", "PAXG"}
LEV_SUFFIXES = ("UP", "DOWN", "BULL", "BEAR")


def compute_freeze_end(now_utc: datetime | None = None) -> datetime:
    """Ultimo dia UTC completo (hoy-1) a las 23:59:59.999."""
    now = now_utc or datetime.now(UTC)
    last_full_day = now.astimezone(UTC).date() - timedelta(days=1)
    return datetime.combine(last_full_day, datetime.max.time(), tzinfo=UTC).replace(
        microsecond=999000
    )


def is_eligible_base(base: str) -> bool:
    if base in STABLE_BASES or base in WRAPPED_BASES:
        return False
    return not any(base.endswith(s) and base[: -len(s)] for s in LEV_SUFFIXES)


def eligible_symbols(exchange_info: dict[str, Any]) -> list[dict[str, str]]:
    out = []
    for s in exchange_info.get("symbols", []):
        if (
            s.get("quoteAsset") == "USDT"
            and s.get("status") in ("TRADING", "BREAK")
            and is_eligible_base(s.get("baseAsset", ""))
        ):
            out.append({"symbol": s["symbol"], "base": s["baseAsset"], "status": s["status"]})
    return sorted(out, key=lambda d: d["symbol"])


def _to_parquet(df: pd.DataFrame, path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    df.to_parquet(path, index=False, engine="pyarrow")


# ---------------------------------------------------------------------------
# Fases
# ---------------------------------------------------------------------------
def phase_meta(client: BinancePublicClient, root: Path, log: dict[str, Any]) -> None:
    man = Manifest(root, "meta")
    for name, base, path in (
        ("exchangeinfo_spot", SPOT_BASE, "/api/v3/exchangeInfo"),
        ("exchangeinfo_fapi", FAPI_BASE, "/fapi/v1/exchangeInfo"),
    ):
        data = client.get_json(base, path)
        p = write_json_gz(root, f"data/raw/meta/{name}.json.gz", data)
        man.add_file(p, rows=len(data.get("symbols", [])), source=base + path)
    log["meta"] = "ok"


def phase_monthly(client: BinancePublicClient, root: Path, log: dict[str, Any]) -> None:
    raw = read_json_gz(raw_dir(root) / "meta" / "exchangeinfo_spot.json.gz")
    symbols = eligible_symbols(raw)
    man = Manifest(root, "spot_monthly")
    done = {Path(p).stem for p in man.paths()}
    freeze_ms = to_ms(int(log["freeze_end_ms"]))
    n_new = 0
    for i, s in enumerate(symbols):
        sym = s["symbol"]
        if sym in done:
            continue
        rows = fetch_klines_paged(
            client, SPOT_BASE, "/api/v3/klines", sym, "1M", 0, freeze_ms, max_pages=1
        )
        if not rows:
            continue
        df = klines_frame(rows, sym, "1M")
        out = raw_dir(root) / "spot_monthly" / f"{sym}.parquet"
        _to_parquet(df, out)
        man.add_file(
            out,
            rows=len(df),
            source=f"{SPOT_BASE}/api/v3/klines",
            params={"symbol": sym, "interval": "1M"},
        )
        n_new += 1
        if (i + 1) % 100 == 0:
            log["monthly_progress"] = f"{i + 1}/{len(symbols)}"
    # fallback vision: simbolos con dump pero sin datos en el API (NBTUSDT)
    extra = _vision_extra_symbols(client, root, man, freeze_ms)
    log["monthly"] = {"eligible": len(symbols), "downloaded_now": n_new, "vision_extra": extra}


def _vision_extra_symbols(
    client: BinancePublicClient, root: Path, man: Manifest, freeze_ms: int
) -> list[str]:
    """Simbolos USDT presentes en los dumps y ausentes del exchangeInfo actual."""
    known = {Path(p).stem for p in man.paths()}
    extras: list[str] = []
    for sym in ("NBTUSDT",):  # unico caso verificado el 2026-10-26 (sondeo M0c)
        if sym in known:
            continue
        keys = list_keys(client, f"data/spot/monthly/klines/{sym}/1d/")
        if not keys:
            continue
        frames = []
        for k in sorted(keys):
            content = client.get_bytes(
                f"https://s3-ap-northeast-1.amazonaws.com/data.binance.vision/{k}"
            )
            rows = parse_csv_zip(content)
            frames.append(klines_frame([r[:11] for r in rows], sym, "1M"))
        df = pd.concat(frames, ignore_index=True).sort_values("open_time")
        df = df[df["open_time"] <= pd.Timestamp(freeze_ms, unit="ms", tz="UTC")]
        out = raw_dir(root) / "spot_monthly" / f"{sym}.parquet"
        _to_parquet(df, out)
        man.add_file(
            out,
            rows=len(df),
            source="data.binance.vision monthly",
            params={"symbol": sym, "interval": "1M"},
        )
        extras.append(sym)
    return extras


def phase_pool(root: Path, log: dict[str, Any]) -> list[str]:
    frames = [
        pd.read_parquet(p) for p in sorted((raw_dir(root) / "spot_monthly").glob("*.parquet"))
    ]
    monthly = pd.concat(frames, ignore_index=True)
    monthly["month"] = monthly["open_time"].dt.to_period("M")
    top = monthly.sort_values("quote_volume", ascending=False).groupby("month", sort=True).head(60)
    pool = sorted(set(top["symbol"]) | {"BTCUSDT", "ETHUSDT"})
    audit: dict[str, Any] = {
        "rule": "union del top-60 mensual por quote_volume entre USDT elegibles + BTC/ETH forzados",
        "n_symbols_monthly_universe": int(monthly["symbol"].nunique()),
        "n_pool": len(pool),
        "first_month_in_top60": (top.groupby("symbol")["month"].min().astype(str).to_dict()),
        "pool": pool,
    }
    write_json(root, "data/manifests/ingest_pool.json", audit)
    log["pool"] = {"n_pool": len(pool), "monthly_universe": int(monthly["symbol"].nunique())}
    return pool


def phase_daily(
    client: BinancePublicClient, root: Path, pool: list[str], log: dict[str, Any]
) -> None:
    audit = json.loads((manifests_dir(root) / "ingest_pool.json").read_text())
    first_month = audit["first_month_in_top60"]
    man = Manifest(root, "spot_daily")
    done = {Path(p).stem for p in man.paths()}
    freeze_ms = int(log["freeze_end_ms"])
    n_new, n_empty = 0, []
    for sym in pool:
        if sym in done:
            continue
        fm = first_month.get(sym)
        start = pd.Timestamp(fm + "-01", tz="UTC") if fm else pd.Timestamp("2017-08-01", tz="UTC")
        rows = fetch_klines_paged(
            client,
            SPOT_BASE,
            "/api/v3/klines",
            sym,
            "1d",
            int(start.timestamp() * 1000),
            freeze_ms,
        )
        if not rows:
            n_empty.append(sym)
            continue
        df = klines_frame(rows, sym, "1d")
        out = raw_dir(root) / "spot_daily" / f"{sym}.parquet"
        _to_parquet(df, out)
        man.add_file(
            out,
            rows=len(df),
            source=f"{SPOT_BASE}/api/v3/klines",
            params={"symbol": sym, "interval": "1d"},
        )
        n_new += 1
    log["daily"] = {"downloaded_now": n_new, "empty": n_empty}


def phase_futures(client: BinancePublicClient, root: Path, log: dict[str, Any]) -> None:
    man = Manifest(root, "futures_daily")
    done = {Path(p).stem for p in man.paths()}
    freeze_ms = int(log["freeze_end_ms"])
    for sym in ("BTCUSDT", "ETHUSDT"):
        if sym in done:
            continue
        rows = fetch_klines_paged(
            client,
            FAPI_BASE,
            "/fapi/v1/klines",
            sym,
            "1d",
            to_ms(1567900800000),  # 2019-09-08: primera vela verificada
            freeze_ms,
        )
        df = klines_frame(rows, sym, "1d")
        out = raw_dir(root) / "futures_daily" / f"{sym}.parquet"
        _to_parquet(df, out)
        man.add_file(
            out,
            rows=len(df),
            source=f"{FAPI_BASE}/fapi/v1/klines",
            params={"symbol": sym, "interval": "1d"},
        )
    log["futures"] = "ok"


def phase_funding(client: BinancePublicClient, root: Path, log: dict[str, Any]) -> None:
    man = Manifest(root, "funding")
    done = {Path(p).stem for p in man.paths()}
    freeze_ms = int(log["freeze_end_ms"])
    for sym in ("BTCUSDT", "ETHUSDT"):
        if sym in done:
            continue
        rows = fetch_funding_paged(client, sym, to_ms(1567209600000), freeze_ms)  # 2019-08-31
        df = funding_frame(rows, sym)
        out = raw_dir(root) / "funding" / f"{sym}.parquet"
        _to_parquet(df, out)
        man.add_file(
            out, rows=len(df), source=f"{FAPI_BASE}/fapi/v1/fundingRate", params={"symbol": sym}
        )
    # cross-check contra dump mensual de vision (BTCUSDT 2020-01)
    cc_rel = "data/raw/funding/crosscheck_BTCUSDT_2020-01.json"
    if not (root / cc_rel).exists():
        key = "data/futures/um/monthly/fundingRate/BTCUSDT/BTCUSDT-fundingRate-2020-01.zip"
        content = client.get_bytes(
            f"https://s3-ap-northeast-1.amazonaws.com/data.binance.vision/{key}"
        )
        vrows = parse_csv_zip(content)
        # Esquema del dump mensual (verificado 2026-10-26):
        #   (calc_time, funding_interval_hours, last_funding_rate)  -> 3 columnas
        # Formato antiguo de funding (otros datasets): (symbol, fundingTime,
        #   fundingRate, markPrice) -> 4 columnas. Soportamos ambos.
        if vrows and len(vrows[0]) >= 4:
            vmap = {int(r[1]): float(r[2]) for r in vrows}
            schema = "symbol,fundingTime,fundingRate,markPrice"
        else:
            vmap = {int(r[0]): float(r[2]) for r in vrows}
            schema = "calc_time,funding_interval_hours,last_funding_rate"
        api = pd.read_parquet(raw_dir(root) / "funding" / "BTCUSDT.parquet")
        api_map = {
            int(t.timestamp() * 1000): float(x)
            for t, x in zip(api["funding_time"], api["funding_rate"], strict=True)
        }
        common = sorted(set(vmap) & set(api_map))
        mismatched = [t for t in common if abs(vmap[t] - api_map[t]) > 1e-12]
        write_json(
            root,
            cc_rel,
            {
                "vision_key": key,
                "vision_schema": schema,
                "vision_rows": len(vmap),
                "api_rows_in_month": sum(1 for t in api_map if 1577836800000 <= t < 1580515200000),
                "common": len(common),
                "mismatched": len(mismatched),
                "sha256_zip": hashlib.sha256(content).hexdigest(),
            },
        )
    log["funding"] = "ok+crosscheck"


# ---------------------------------------------------------------------------
def run_sync(root: Path | None = None, phases: str = "all") -> dict[str, Any]:
    root = root or Path.cwd()
    t0 = time.time()
    freeze_end = compute_freeze_end()
    log: dict[str, Any] = {
        "started_utc": datetime.now(UTC).isoformat(timespec="seconds"),
        "freeze_end_utc": freeze_end.isoformat(),
        "freeze_end_ms": int(freeze_end.timestamp() * 1000) // 1000 * 1000 + 999,
        "phases_requested": phases,
    }
    want = (
        set(phases.split(","))
        if phases != "all"
        else {"meta", "monthly", "pool", "daily", "futures", "funding"}
    )
    config_dir(root).mkdir(parents=True, exist_ok=True)
    with BinancePublicClient() as client:
        if "meta" in want:
            phase_meta(client, root, log)
        if "monthly" in want:
            phase_monthly(client, root, log)
        pool: list[str] = []
        if "pool" in want:
            pool = phase_pool(root, log)
        if "daily" in want:
            if not pool:
                pool = phase_pool(root, log) if (raw_dir(root) / "spot_monthly").exists() else []
            phase_daily(client, root, pool, log)
        if "futures" in want:
            phase_futures(client, root, log)
        if "funding" in want:
            phase_funding(client, root, log)
        log["api_requests"] = client.n_requests
        log["last_used_weight_1m"] = client.used_weight_1m
    log["elapsed_s"] = round(time.time() - t0, 1)
    log["finished_utc"] = datetime.now(UTC).isoformat(timespec="seconds")
    write_json(root, "data/manifests/sync_log.json", log)
    return log
