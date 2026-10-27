"""Informe de calidad de datos M1 (DuckDB + pandas).

PROHIBIDO en M1: metricas de estrategia (retorno/Sharpe/drawdown de reglas).
Los unicos retornos que se computan aqui son log-retornos entre velas
consecutivas de UN mismo simbolo, exclusivamente para deteccion de outliers
(z robusto) — auditoria de datos, tal y como exige la especificacion de M1
("huecos, duplicados, outliers (z robusto), cobertura por simbolo").
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import duckdb
import numpy as np
import pandas as pd

from qa.data.manifest import Manifest, read_json_gz
from qa.data.paths import curated_dir, holdout_sealed_dir, manifests_dir, raw_dir, reports_dir

ROBUST_Z_THRESHOLD = 8.0


def _robust_z_outliers(spot: pd.DataFrame) -> dict[str, Any]:
    out = spot.sort_values(["symbol", "open_time"]).copy()
    out["lr"] = np.log(out["close"]).groupby(out["symbol"]).diff()
    med = out.groupby("symbol")["lr"].transform("median")
    mad = (out["lr"] - med).abs().groupby(out["symbol"]).transform("median")
    scale = 1.4826 * mad.replace(0.0, np.nan)
    out["z"] = (out["lr"] - med) / scale
    flagged = out[out["z"].abs() > ROBUST_Z_THRESHOLD]
    top = (
        flagged.reindex(flagged["z"].abs().sort_values(ascending=False).index)
        .head(10)[["symbol", "open_time", "lr", "z"]]
        .astype({"open_time": str, "lr": float, "z": float})
        .to_dict(orient="records")
    )
    return {"n_flagged": int(len(flagged)), "top10": top}


def _coverage(spot: pd.DataFrame) -> pd.DataFrame:
    rows = []
    for sym, g in spot.groupby("symbol", sort=True):
        g = g.sort_values("open_time")
        n = len(g)
        span_days = int((g["open_time"].max() - g["open_time"].min()).days) + 1
        gaps = g["open_time"].diff().dt.days.dropna()
        rows.append(
            {
                "symbol": sym,
                "first": str(g["open_time"].min().date()),
                "last": str(g["open_time"].max().date()),
                "rows": n,
                "expected_days": span_days,
                "missing_days": max(0, span_days - n),
                "missing_pct": round(100.0 * max(0, span_days - n) / span_days, 3),
                "max_gap_days": int(gaps.max()) if len(gaps) else 0,
                "zero_quote_volume_days": int((g["quote_volume"] <= 0).sum()),
            }
        )
    return pd.DataFrame(rows)


def run_quality(root: Path) -> dict[str, Any]:
    con = duckdb.connect()
    meta = json.loads((manifests_dir(root) / "dataset_meta.json").read_text())
    pool_audit = json.loads((manifests_dir(root) / "ingest_pool.json").read_text())
    from qa.backtest.seal import is_sealed

    sealed = is_sealed(root)
    spot_in = pd.read_parquet(curated_dir(root) / "spot_daily_in_sample.parquet")
    spot_ho_path = holdout_sealed_dir(root) / "spot_daily_holdout.parquet"
    if sealed:
        spot_ho = spot_in.iloc[:0]  # holdout cifrado: no se lee en QA (por diseno)
        fund_ho = spot_in.iloc[:0]
    else:
        spot_ho = pd.read_parquet(spot_ho_path) if spot_ho_path.exists() else spot_in.iloc[:0]
    fut_in = pd.read_parquet(curated_dir(root) / "futures_daily_in_sample.parquet")
    fund_in = pd.read_parquet(curated_dir(root) / "funding_in_sample.parquet")
    if not sealed:
        fund_ho = pd.read_parquet(holdout_sealed_dir(root) / "funding_holdout.parquet")
    pit = pd.read_parquet(curated_dir(root) / "pit_universe.parquet")

    con.register("spot_in", spot_in)
    con.register("fund_in", fund_in)
    con.register("pit", pit)

    dup_check = con.execute(
        "SELECT count(*) FROM (SELECT symbol, open_time, count(*) c FROM spot_in "
        "GROUP BY 1,2 HAVING c > 1)"
    ).fetchone()
    dup_groups = int(dup_check[0]) if dup_check else 0

    zero_or_neg = con.execute(
        "SELECT count(*) FROM spot_in WHERE close <= 0 OR low <= 0 OR high < low"
    ).fetchone()
    bad_prices = int(zero_or_neg[0]) if zero_or_neg else 0

    coverage = _coverage(spot_in)
    outliers = _robust_z_outliers(spot_in)

    # funding: cobertura y huecos frente al intervalo de 8 h
    funding_stats: list[dict[str, Any]] = []
    for sym in sorted(fund_in["symbol"].unique()):
        g = fund_in[fund_in["symbol"] == sym].sort_values("funding_time")
        gt = pd.concat([g, fund_ho[fund_ho["symbol"] == sym]], ignore_index=True).sort_values(
            "funding_time"
        )
        gaps_h = gt["funding_time"].diff().dt.total_seconds().dropna() / 3600.0
        expected = (
            int((gt["funding_time"].max() - gt["funding_time"].min()).total_seconds() // 3600 // 8)
            + 1
        )
        funding_stats.append(
            {
                "symbol": sym,
                "records_in_sample": int(len(g)),
                "records_total": int(len(gt)),
                "first": str(gt["funding_time"].min()),
                "last": str(gt["funding_time"].max()),
                "expected_at_8h": expected,
                "missing": max(0, expected - int(len(gt))),
                "gaps_over_8_5h": int((gaps_h > 8.5).sum()),
                "max_gap_hours": float(gaps_h.max()) if len(gaps_h) else 0.0,
                "mean_rate": float(gt["funding_rate"].mean()),
                "min_rate": float(gt["funding_rate"].min()),
                "max_rate": float(gt["funding_rate"].max()),
            }
        )

    cc_path = raw_dir(root) / "funding" / "crosscheck_BTCUSDT_2020-01.json"
    crosscheck = json.loads(cc_path.read_text()) if cc_path.exists() else None

    # PIT: candidatos por mes
    pit_monthly = (
        pit.groupby("month")
        .agg(n_candidates=("symbol", "count"))
        .reset_index()
        .sort_values("month")
    )
    pit_summary = {
        "months": int(len(pit_monthly)),
        "first_month": str(pit_monthly["month"].min()),
        "last_month": str(pit_monthly["month"].max()),
        "n_candidates_min": int(pit_monthly["n_candidates"].min()),
        "n_candidates_median": float(pit_monthly["n_candidates"].median()),
        "first_month_with_20": str(
            pit_monthly.loc[pit_monthly["n_candidates"] >= 20, "month"].min()
        ),
        "first_month_with_40": str(
            pit_monthly.loc[pit_monthly["n_candidates"] >= 40, "month"].min()
        ),
        "symbols_ever_in_top20": int(pit.loc[pit["in_top20"], "symbol"].nunique()),
    }

    # deslistados incluidos (status BREAK en la foto de exchangeInfo)
    info = read_json_gz(raw_dir(root) / "meta" / "exchangeinfo_spot.json.gz")
    status_by_symbol = {s["symbol"]: s.get("status") for s in info.get("symbols", [])}
    pool = pool_audit["pool"]
    delisted_in_pool = sorted(
        [s for s in pool if status_by_symbol.get(s) == "BREAK"]
        + [s for s in pool if s not in status_by_symbol]
    )

    failures: list[str] = []
    for name in ("spot_daily", "futures_daily", "funding", "curated", "meta"):
        failures.extend(Manifest(root, name).verify())

    result: dict[str, Any] = {
        "dataset_meta": meta,
        "spot": {
            "symbols_in_sample": int(spot_in["symbol"].nunique()),
            "rows_in_sample": int(len(spot_in)),
            "rows_holdout": "SELLADO (AES256; sha256 en ledger/holdout_seal.log)"
            if sealed
            else int(len(spot_ho)),
            "duplicate_symbol_day_groups": dup_groups,
            "bad_price_rows": bad_prices,
            "tz_all_utc": bool(spot_in["open_time"].dt.tz is not None),
            "first_day": str(spot_in["open_time"].min()),
            "last_day_in_sample": str(spot_in["open_time"].max()),
            "coverage_worst_missing_pct": coverage.nlargest(5, "missing_pct")[
                ["symbol", "missing_pct", "max_gap_days"]
            ].to_dict(orient="records"),
            "coverage_complete_symbols": int((coverage["missing_days"] == 0).sum()),
        },
        "outliers_logret_robust_z": outliers,
        "funding": funding_stats,
        "funding_crosscheck_vs_vision_dump": crosscheck,
        "pit_universe": pit_summary,
        "pool": {
            "n_pool": pool_audit["n_pool"],
            "monthly_universe_symbols": pool_audit["n_symbols_monthly_universe"],
            "delisted_or_absent_in_pool": delisted_in_pool,
            "n_delisted_or_absent": len(delisted_in_pool),
        },
        "manifest_failures": failures,
        "futures": {
            "rows_in_sample": int(len(fut_in)),
            "symbols": sorted(fut_in["symbol"].unique().tolist()),
            "first_day": str(fut_in["open_time"].min()),
        },
    }
    reports_dir(root).mkdir(parents=True, exist_ok=True)
    (reports_dir(root) / "M1_data_quality.json").write_text(
        json.dumps(result, indent=2, default=str), encoding="utf-8"
    )
    coverage.to_csv(reports_dir(root) / "M1_coverage_by_symbol.csv", index=False)
    con.close()
    return result


def render_quality_md(result: dict[str, Any]) -> str:
    dm = result["dataset_meta"]
    sp = result["spot"]
    fu = result["funding"]
    pit = result["pit_universe"]
    pool = result["pool"]
    lines = [
        "# Informe de calidad de datos — M1",
        "",
        f"- Freeze de datos (ultimo dia UTC completo): **{dm['data_freeze_end_utc']}**",
        f"- Holdout sellado: **{dm['holdout_start_utc']} → {dm['holdout_end_utc']}** "
        f"({dm['holdout_days']} dias, ficheros `*_holdout.parquet` fisicamente separados)",
        f"- Duplicados (symbol, ts) eliminados en curacion: {dm['duplicates_removed']}",
        f"- Fallos de manifiestos SHA256: {len(result['manifest_failures'])}",
        "",
        "## Spot diario (in-sample)",
        f"- Simbolos: **{sp['symbols_in_sample']}** · filas: {sp['rows_in_sample']} "
        f"(holdout: {sp['rows_holdout']})",
        f"- Rango: {sp['first_day']} → {sp['last_day_in_sample']} · tz UTC: {sp['tz_all_utc']}",
        f"- Grupos duplicados residuales: {sp['duplicate_symbol_day_groups']} · "
        f"filas con precios imposibles (close<=0 o high<low): {sp['bad_price_rows']}",
        f"- Simbolos sin ningun hueco: {sp['coverage_complete_symbols']} "
        "(detalle completo: `reports/M1_coverage_by_symbol.csv`)",
        f"- Peores coberturas: {sp['coverage_worst_missing_pct']}",
        "",
        "## Outliers (z robusto sobre log-retornos, |z|>8 — QA de datos, no metrica de estrategia)",
        f"- Filas marcadas: {result['outliers_logret_robust_z']['n_flagged']}",
        f"- Top 10: {result['outliers_logret_robust_z']['top10'][:5]}",
        "",
        "## Funding (perp USDT-M, historico real)",
    ]
    for f in fu:
        lines.append(
            f"- **{f['symbol']}**: {f['records_total']} registros "
            f"({f['first']} → {f['last']}), esperados@8h {f['expected_at_8h']}, "
            f"faltan {f['missing']}, huecos>8.5h: {f['gaps_over_8_5h']} "
            f"(max {f['max_gap_hours']:.1f}h), rate medio {f['mean_rate']:.6f} "
            f"[min {f['min_rate']:.4f}, max {f['max_rate']:.4f}]"
        )
    cc = result["funding_crosscheck_vs_vision_dump"]
    if cc:
        lines.append(
            f"- Cross-check API vs dump mensual vision (BTCUSDT 2020-01): "
            f"{cc['common']} registros comunes, **{cc['mismatched']} discrepancias** "
            f"(sha256 del zip: {cc['sha256_zip'][:16]}…)"
        )
    lines += [
        "",
        "## Universo PIT (top-N mensual)",
        f"- Meses: {pit['months']} ({pit['first_month']} → {pit['last_month']})",
        f"- Candidatos por mes: min {pit['n_candidates_min']}, "
        f"mediana {pit['n_candidates_median']}",
        f"- Primer mes con >=20 candidatos: {pit['first_month_with_20']}",
        f"- Primer mes con >=40 candidatos: {pit['first_month_with_40']}",
        f"- Simbolos distintos que alguna vez estuvieron en top-20: {pit['symbols_ever_in_top20']}",
        "",
        "## Pool de ingesta y deslistados",
        f"- Pool (union top-60 mensual + BTC/ETH): {pool['n_pool']} simbolos "
        f"(universo mensual: {pool['monthly_universe_symbols']})",
        f"- Deslistados/ausentes del exchangeInfo actual incluidos: "
        f"{pool['n_delisted_or_absent']} → {pool['delisted_or_absent_in_pool'][:12]}",
        "",
        "## Futures diario (perp USDT-M)",
        f"- {result['futures']['symbols']} · filas in-sample: "
        f"{result['futures']['rows_in_sample']} · desde {result['futures']['first_day']}",
        "",
        "## Limitaciones y sesgos declarados",
        "1. **Supervivencia del venue:** solo existe lo que Binance listo. Los dumps "
        "conservan deslistados (incluidos en el pool cuando fueron top-60 mensual), pero "
        "monedas muertas que nunca cotizaron en Binance son invisibles.",
        "2. **Pool top-60 mensual como filtro de ingesta:** el ranking diario top-20 se "
        "reconstruye dentro del pool. Riesgo residual: un simbolo top-20 diario que nunca "
        "fuese top-60 mensual quedaria fuera (margen 3x; auditado mes a mes en el JSON).",
        "3. **Regimen 2017-18:** liquidez y spreads de la microestructura temprana; los "
        "costes verificados en 2026 la subestiman (protegido por stress x2, PRERREGISTRO s3).",
        "4. **PIT fino pre-2019:** meses con <20 candidatos existen; H2 arranca cuando "
        "first_month_with_20 lo permita (reportado arriba).",
        "5. **NBTUSDT** (unico simbolo USDT con dumps y sin entrada en exchangeInfo actual) "
        "se ingirio via vision monthly si sus dumps existen; en otro caso queda documentado.",
        "6. El funding anterior a 2019-09 no existe (perps USD-M lanzados en 2019): H3 "
        "empieza ahi. ETHUSDT puede empezar despues que BTCUSDT: aplicar regla P4 "
        "(MDE por activo; ETH INCONTRASTABLE si MDE_ETH > 2x MDE_BTC).",
        "",
        "**Ninguna metrica de estrategia (retorno/Sharpe/drawdown de reglas) fue calculada "
        "en M1**, segun la prohibicion del gate M0b.",
        "",
    ]
    return "\n".join(lines) + "\n"
