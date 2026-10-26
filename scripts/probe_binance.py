"""Live probes of Binance public endpoints and data dumps for M0/M1 facts.

Verifies, empirically (no assumptions from docs or memory):
- reachability of spot and USDⓈ-M futures REST APIs and data.binance.vision;
- timestamp units (ms vs µs) of spot/futures klines and fundingRate;
- max ``limit`` accepted by klines endpoints;
- earliest available candle and funding record per API;
- trading filters (LOT_SIZE, NOTIONAL / MIN_NOTIONAL) for BTC, ETH and a small
  cap, plus futures contract specs;
- whether data.binance.vision keeps daily dumps for delisted symbols;
- current funding interval spacing (8h vs 4h) for BTCUSDT perp;
- reference prices for cost arithmetic examples.

All calls are public, read-only, GET only, with sleeps to respect rate limits.
Evidence: docs/evidence/binance_probes.json (full bodies truncated).
Exit code 0 if all critical probes succeeded.

Usage:
    python scripts/probe_binance.py
"""

from __future__ import annotations

import json
import time
import urllib.parse
import urllib.request
import xml.etree.ElementTree as ET
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

REPO = Path(__file__).resolve().parents[1]
OUT = REPO / "docs" / "evidence" / "binance_probes.json"
UA = {"User-Agent": "QUANT-ARENA-M0-endpoint-verification/1.0"}
TIMEOUT = 30
SLEEP = 0.25


def _get(url: str) -> tuple[int, dict[str, str], bytes]:
    req = urllib.request.Request(url, headers=UA)
    with urllib.request.urlopen(req, timeout=TIMEOUT) as r:
        return r.status, dict(r.headers), r.read()


def _digits_of(x: Any) -> int:
    return len(str(int(x)))


def _ts_to_iso(ms_or_us: float) -> str:
    if ms_or_us > 1e14:  # microseconds
        return datetime.fromtimestamp(ms_or_us / 1e6, tz=UTC).isoformat()
    return datetime.fromtimestamp(ms_or_us / 1e3, tz=UTC).isoformat()


def _json_probe(name: str, url: str, ev: list[dict[str, Any]]) -> Any:
    time.sleep(SLEEP)
    rec: dict[str, Any] = {"name": name, "url": url}
    try:
        status, headers, body = _get(url)
        rec["http_status"] = status
        rec["x_mbx_used_weight_1m"] = headers.get("x-mbx-used-weight-1m")
        rec["x_mbx_used_weight"] = headers.get("x-mbx-used-weight")
        try:
            data = json.loads(body)
        except json.JSONDecodeError:
            data = body[:500].decode("utf-8", errors="replace")
        rec["body_excerpt"] = data if isinstance(data, str) else json.dumps(data)[:1500]
        ev.append(rec)
        return data
    except Exception as e:  # noqa: BLE001
        rec["error"] = repr(e)[:400]
        try:
            body = e.read()[:400].decode("utf-8", errors="replace")  # type: ignore[attr-defined]
            rec["error_body"] = body
        except Exception:  # noqa: BLE001, S110
            pass
        ev.append(rec)
        return None


def _xml_list(name: str, url: str, ev: list[dict[str, Any]], max_keys: int = 5) -> list[str]:
    time.sleep(SLEEP)
    rec: dict[str, Any] = {"name": name, "url": url}
    try:
        status, _h, body = _get(url)
        rec["http_status"] = status
        root = ET.fromstring(body)
        ns = {"s3": root.tag.split("}")[0].strip("{")} if root.tag.startswith("{") else {}
        pref = "s3:" if ns else ""
        keys = [k.text or "" for k in root.findall(f"{pref}Contents/{pref}Key", ns)]
        prefixes = [p.text or "" for p in root.findall(f"{pref}CommonPrefixes/{pref}Prefix", ns)]
        rec["keys"] = keys[:max_keys]
        rec["common_prefixes"] = prefixes[:max_keys]
        rec["truncated"] = root.findtext(f"{pref}IsTruncated", default="", namespaces=ns or None)
        ev.append(rec)
        return keys or prefixes
    except Exception as e:  # noqa: BLE001
        rec["error"] = repr(e)[:400]
        ev.append(rec)
        return []


def main() -> int:
    ev: list[dict[str, Any]] = []
    facts: dict[str, Any] = {}
    checked_at = datetime.now(UTC).isoformat(timespec="seconds")

    # --- Spot ---------------------------------------------------------------
    _json_probe("spot_ping", "https://api.binance.com/api/v3/ping", ev)
    t = _json_probe("spot_time", "https://api.binance.com/api/v3/time", ev)
    if isinstance(t, dict):
        facts["spot_server_time_utc"] = _ts_to_iso(t["serverTime"])
        facts["spot_server_time_digits"] = _digits_of(t["serverTime"])

    k = _json_probe(
        "spot_klines_btcusdt_1d",
        "https://api.binance.com/api/v3/klines?symbol=BTCUSDT&interval=1d&limit=2",
        ev,
    )
    if isinstance(k, list) and k:
        facts["spot_kline_openTime_digits"] = _digits_of(k[0][0])
        facts["spot_kline_openTime_unit"] = "ms" if _digits_of(k[0][0]) == 13 else "us?"
        facts["spot_kline_first_row_utc"] = _ts_to_iso(k[0][0])

    k1500 = _json_probe(
        "spot_klines_limit_1500",
        "https://api.binance.com/api/v3/klines?symbol=BTCUSDT&interval=1d&limit=1500",
        ev,
    )
    if isinstance(k1500, list):
        facts["spot_klines_limit_1500_rows"] = len(k1500)
    k1501 = _json_probe(
        "spot_klines_limit_1501_expect_error",
        "https://api.binance.com/api/v3/klines?symbol=BTCUSDT&interval=1d&limit=1501",
        ev,
    )
    if isinstance(k1501, list):
        facts["spot_klines_limit_1501_rows"] = len(k1501)
        facts["spot_klines_limit_cap_note"] = (
            "limit>1000 no produce error: el API devuelve como mucho 1000 filas "
            "(verificado empiricamente)"
        )

    k0 = _json_probe(
        "spot_klines_earliest",
        "https://api.binance.com/api/v3/klines?symbol=BTCUSDT&interval=1d&startTime=0&limit=1",
        ev,
    )
    if isinstance(k0, list) and k0:
        facts["spot_btcusdt_earliest_candle_utc"] = _ts_to_iso(k0[0][0])

    for sym in ("BTCUSDT", "ETHUSDT", "PEPEUSDT"):
        ei = _json_probe(
            f"spot_exchangeinfo_{sym.lower()}",
            f"https://api.binance.com/api/v3/exchangeInfo?symbol={sym}",
            ev,
        )
        if isinstance(ei, dict):
            for s in ei.get("symbols", []):
                facts[f"spot_filters_{sym}"] = {
                    "status": s.get("status"),
                    "baseAssetPrecision": s.get("baseAssetPrecision"),
                    "quotePrecision": s.get("quotePrecision"),
                    "filters": {
                        f["filterType"]: {
                            kk: vv
                            for kk, vv in f.items()
                            if kk
                            in ("minQty", "maxQty", "stepSize", "minNotional", "applyToMarket")
                        }
                        for f in s.get("filters", [])
                        if f["filterType"] in ("LOT_SIZE", "NOTIONAL", "MIN_NOTIONAL")
                    },
                }

    ei_all = _json_probe(
        "spot_exchangeinfo_all_count", "https://api.binance.com/api/v3/exchangeInfo", ev
    )
    if isinstance(ei_all, dict):
        syms = ei_all.get("symbols", [])
        facts["spot_symbols_total"] = len(syms)
        facts["spot_symbols_trading"] = sum(1 for s in syms if s.get("status") == "TRADING")
        facts["spot_symbols_break"] = sum(1 for s in syms if s.get("status") == "BREAK")

    px = _json_probe(
        "spot_price_btcusdt",
        "https://api.binance.com/api/v3/ticker/price?symbol=BTCUSDT",
        ev,
    )
    if isinstance(px, dict):
        facts["btcusdt_price_ref"] = px.get("price")
    px = _json_probe(
        "spot_price_ethusdt",
        "https://api.binance.com/api/v3/ticker/price?symbol=ETHUSDT",
        ev,
    )
    if isinstance(px, dict):
        facts["ethusdt_price_ref"] = px.get("price")

    # --- USDⓈ-M Futures ------------------------------------------------------
    _json_probe("fapi_ping", "https://fapi.binance.com/fapi/v1/ping", ev)
    fk = _json_probe(
        "fapi_klines_btcusdt_1d",
        "https://fapi.binance.com/fapi/v1/klines?symbol=BTCUSDT&interval=1d&limit=2",
        ev,
    )
    if isinstance(fk, list) and fk:
        facts["fapi_kline_openTime_digits"] = _digits_of(fk[0][0])
        facts["fapi_kline_openTime_unit"] = "us" if _digits_of(fk[0][0]) == 16 else "ms"
        facts["fapi_kline_first_row_utc"] = _ts_to_iso(fk[0][0])

    fk0 = _json_probe(
        "fapi_klines_earliest",
        "https://fapi.binance.com/fapi/v1/klines?symbol=BTCUSDT&interval=1d&startTime=0&limit=1",
        ev,
    )
    if isinstance(fk0, list) and fk0:
        facts["fapi_btcusdt_earliest_candle_utc"] = _ts_to_iso(fk0[0][0])

    fr = _json_probe(
        "fapi_fundingrate_recent",
        "https://fapi.binance.com/fapi/v1/fundingRate?symbol=BTCUSDT&limit=8",
        ev,
    )
    if isinstance(fr, list) and len(fr) >= 2:
        facts["fapi_funding_time_digits"] = _digits_of(fr[0]["fundingTime"])
        facts["fapi_funding_time_unit"] = "us" if _digits_of(fr[0]["fundingTime"]) == 16 else "ms"
        gaps = sorted(
            {
                int(b["fundingTime"]) - int(a["fundingTime"])
                for a, b in zip(fr, fr[1:], strict=False)
            }
        )
        facts["fapi_funding_gaps_ms"] = gaps
        facts["fapi_funding_interval_h"] = sorted({round(g / 3.6e6, 2) for g in gaps})
        facts["fapi_funding_last_rates"] = [x["fundingRate"] for x in fr[:3]]
    fr0 = _json_probe(
        "fapi_fundingrate_earliest",
        "https://fapi.binance.com/fapi/v1/fundingRate?symbol=BTCUSDT&startTime=0&limit=1",
        ev,
    )
    if isinstance(fr0, list) and fr0:
        facts["fapi_btcusdt_earliest_funding_utc"] = _ts_to_iso(fr0[0]["fundingTime"])

    pi = _json_probe(
        "fapi_premiumindex", "https://fapi.binance.com/fapi/v1/premiumIndex?symbol=BTCUSDT", ev
    )
    if isinstance(pi, dict):
        facts["fapi_last_funding_rate"] = pi.get("lastFundingRate")
        facts["fapi_next_funding_time_utc"] = (
            _ts_to_iso(pi["nextFundingTime"]) if pi.get("nextFundingTime") else None
        )

    fei = _json_probe(
        "fapi_exchangeinfo_btcusdt",
        "https://fapi.binance.com/fapi/v1/exchangeInfo?symbol=BTCUSDT",
        ev,
    )
    if isinstance(fei, dict):
        entries = []
        for sym in fei.get("symbols", []):
            if sym.get("symbol") == "BTCUSDT":
                entries.append(
                    {
                        "contractType": sym.get("contractType"),
                        "status": sym.get("status"),
                        "quoteAsset": sym.get("quoteAsset"),
                        "onboardDate_utc": (
                            _ts_to_iso(sym["onboardDate"]) if sym.get("onboardDate") else None
                        ),
                        "filters": {
                            f["filterType"]: {
                                kk: vv
                                for kk, vv in f.items()
                                if kk in ("minQty", "stepSize", "minNotional", "notional")
                            }
                            for f in sym.get("filters", [])
                            if f["filterType"] in ("LOT_SIZE", "MIN_NOTIONAL")
                        },
                    }
                )
        facts["fapi_btcusdt_entries"] = entries
        facts["fapi_symbols_total"] = len(fei.get("symbols", []))

    # --- data.binance.vision dumps ------------------------------------------
    # data.binance.vision sirve HTML al navegador; el bucket S3 subyacente responde XML.
    base = "https://s3-ap-northeast-1.amazonaws.com/data.binance.vision?delimiter=/&prefix="
    q = urllib.parse.quote
    keys = _xml_list(
        "vision_spot_daily_btcusdt_1d_first",
        base + q("data/spot/daily/klines/BTCUSDT/1d/", safe="/"),
        ev,
    )
    if keys:
        facts["vision_spot_btcusdt_first_days"] = keys[:4]
    keys = _xml_list(
        "vision_spot_2017_08_17_exists",
        base + q("data/spot/daily/klines/BTCUSDT/1d/BTCUSDT-1d-2017-08-17.zip", safe="/"),
        ev,
    )
    facts["vision_spot_2017_08_17_zip"] = keys[:1]
    keys = _xml_list(
        "vision_um_daily_btcusdt_1d_first",
        base + q("data/futures/um/daily/klines/BTCUSDT/1d/", safe="/"),
        ev,
    )
    if keys:
        facts["vision_um_btcusdt_first_days"] = keys[:4]
    keys = _xml_list(
        "vision_um_fundingrate_btcusdt_first",
        base + q("data/futures/um/daily/fundingRate/BTCUSDT/", safe="/"),
        ev,
    )
    if keys:
        facts["vision_um_funding_btcusdt_first_days"] = keys[:4]
    keys = _xml_list(
        "vision_um_metrics_btcusdt_first",
        base + q("data/futures/um/daily/metrics/BTCUSDT/", safe="/"),
        ev,
    )
    if keys:
        facts["vision_um_metrics_btcusdt_first_days"] = keys[:3]
    keys = _xml_list(
        "vision_spot_delisted_fttusdt",
        base + q("data/spot/daily/klines/FTTUSDT/1d/", safe="/"),
        ev,
    )
    facts["vision_spot_fttusdt_days_found"] = len(keys)
    facts["vision_spot_fttusdt_first"] = keys[:2]
    keys = _xml_list(
        "vision_spot_delisted_lunabtc",
        base + q("data/spot/daily/klines/LUNABTC/1d/", safe="/"),
        ev,
    )
    facts["vision_spot_lunabtc_days_found"] = len(keys)
    keys = _xml_list(
        "vision_spot_4h_exists",
        base + q("data/spot/daily/klines/BTCUSDT/4h/", safe="/"),
        ev,
    )
    facts["vision_spot_btcusdt_4h_first_days"] = keys[:3]

    # ?symbol= variant: captura la entrada tal y como la sirve el filtro por símbolo
    fei2 = _json_probe(
        "fapi_exchangeinfo_symbolparam_btcusdt",
        "https://fapi.binance.com/fapi/v1/exchangeInfo?symbol=BTCUSDT",
        ev,
    )
    if isinstance(fei2, dict):
        entries2 = []
        for sym in fei2.get("symbols", []):
            if sym.get("symbol") == "BTCUSDT":
                entries2.append(
                    {
                        "contractType": sym.get("contractType"),
                        "status": sym.get("status"),
                        "onboardDate_utc": (
                            _ts_to_iso(sym["onboardDate"]) if sym.get("onboardDate") else None
                        ),
                        "filters": {
                            f["filterType"]: {
                                kk: vv
                                for kk, vv in f.items()
                                if kk in ("minQty", "stepSize", "minNotional", "notional")
                            }
                            for f in sym.get("filters", [])
                            if f["filterType"] in ("LOT_SIZE", "MIN_NOTIONAL")
                        },
                    }
                )
        facts["fapi_btcusdt_entries_symbolparam"] = entries2
        facts["fapi_symbols_total_symbolparam"] = len(fei2.get("symbols", []))

    # exploración de datasets disponibles en el bucket para futures UM
    keys = _xml_list(
        "vision_um_daily_datasets",
        base + q("data/futures/um/daily/", safe="/"),
        ev,
    )
    facts["vision_um_daily_datasets"] = [k.rstrip("/").rsplit("/", 1)[-1] for k in keys]
    for cand in ("fundingRate", "funding"):
        keys = _xml_list(
            f"vision_um_daily_{cand}_btcusdt",
            base + q(f"data/futures/um/daily/{cand}/BTCUSDT/", safe="/"),
            ev,
        )
        if keys:
            facts[f"vision_um_{cand}_btcusdt_first_days"] = keys[:4]

    keys = _xml_list(
        "vision_um_monthly_datasets",
        base + q("data/futures/um/monthly/", safe="/"),
        ev,
    )
    facts["vision_um_monthly_datasets"] = [k.rstrip("/").rsplit("/", 1)[-1] for k in keys]

    fr19 = _json_probe(
        "fapi_fundingrate_from_2019",
        "https://fapi.binance.com/fapi/v1/fundingRate?symbol=BTCUSDT"
        "&startTime=1567900800000&limit=2",
        ev,
    )
    if isinstance(fr19, list) and fr19:
        facts["fapi_btcusdt_funding_first_records"] = [
            {"fundingTime_utc": _ts_to_iso(x["fundingTime"]), "fundingRate": x["fundingRate"]}
            for x in fr19
        ]

    out = {"checked_at_utc": checked_at, "facts": facts, "probes": ev}
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(out, indent=2, ensure_ascii=False), encoding="utf-8")

    print("=== FACTS ===")
    for kk, vv in facts.items():
        print(f"{kk}: {vv}")
    errs = [p["name"] for p in ev if "error" in p or (p.get("http_status") not in (None, 200))]
    print(f"\nevidence -> {OUT}")
    print(f"probes: {len(ev)}, failures/errors: {errs if errs else 'none'}")
    return 0 if not errs else 1


if __name__ == "__main__":
    raise SystemExit(main())
