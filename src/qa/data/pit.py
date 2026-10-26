"""Universo point-in-time: top-N mensual por volumen en dolares (M1).

Para cada mes m (frontera = primer instante UTC del mes) se usa SOLO datos
estrictamente anteriores a m:
- media diaria de quote_volume en los 30 dias naturales previos [m-30d, m);
- edad minima de listado: primera vela <= m-60d;
- al menos 15 dias con datos en la ventana;
- volumen medio > 0.
Se publican los 40 primeros con flags in_top10/in_top20 (N del grid de H2).

Invariante por truncamiento (test obligatorio): para cualquier mes m, el
resultado construido con ``daily[open_time < m]`` es IDENTICO al construido
con la serie completa. La funcion pura ``build_pit_from_frame`` solo mira hacia
atras por construccion.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import pandas as pd

from qa.data.manifest import Manifest, write_json
from qa.data.paths import curated_dir, holdout_sealed_dir

PIT_COLS = ["month", "rank", "symbol", "trailing_mean", "n_days", "in_top10", "in_top20"]


def load_adjudications(root: Path) -> pd.DataFrame:
    """Tabla sellada de adjudicacion (config/adjudications.csv)."""
    p = root / "config" / "adjudications.csv"
    if not p.exists():
        return pd.DataFrame(columns=["symbol", "event_date_utc", "log_return", "classification"])
    adj = pd.read_csv(p)
    adj["event_date_utc"] = pd.to_datetime(adj["event_date_utc"], utc=True)
    return adj


def build_pit_from_frame(
    daily: pd.DataFrame,
    top_k: int = 40,
    window_days: int = 30,
    min_age_days: int = 60,
    min_days: int = 15,
    adjudications: pd.DataFrame | None = None,
    corporate_exclusion_days: int = 30,
) -> pd.DataFrame:
    df = daily.loc[:, ["symbol", "open_time", "quote_volume"]].copy()
    if df.empty:
        return pd.DataFrame(columns=PIT_COLS)
    corp = (
        adjudications[adjudications["classification"] == "corporate_action"]
        if adjudications is not None and len(adjudications)
        else pd.DataFrame(columns=["symbol", "event_date_utc"])
    )
    first_trade = df.groupby("symbol")["open_time"].min()
    t_min = df["open_time"].min()
    t_max = df["open_time"].max()
    m_min = pd.Period(t_min.strftime("%Y-%m"), freq="M") + 1
    m_max = pd.Period(t_max.strftime("%Y-%m"), freq="M") + 1
    recs: list[pd.DataFrame] = []
    for m in pd.period_range(m_min, m_max, freq="M"):
        m_start = m.to_timestamp().tz_localize("UTC")
        win_start = m_start - pd.Timedelta(days=window_days)
        sub = df[(df["open_time"] >= win_start) & (df["open_time"] < m_start)]
        if sub.empty:
            continue
        stats = sub.groupby("symbol").agg(
            n_days=("quote_volume", "size"), trailing_mean=("quote_volume", "mean")
        )
        age_ok = first_trade[first_trade <= m_start - pd.Timedelta(days=min_age_days)].index
        stats = stats[stats.index.isin(age_ok)]
        # v1.3: excluir del ranking los simbolos en ventana de ruptura (corporate_action)
        if len(corp):
            win_start_excl = m_start - pd.Timedelta(days=corporate_exclusion_days)
            blocked = set(
                corp.loc[
                    (corp["event_date_utc"] >= win_start_excl) & (corp["event_date_utc"] < m_start),
                    "symbol",
                ]
            )
            if blocked:
                stats = stats[~stats.index.isin(blocked)]
        stats = stats[(stats["n_days"] >= min_days) & (stats["trailing_mean"] > 0)]
        if stats.empty:
            continue
        stats = stats.sort_values("trailing_mean", ascending=False).head(top_k)
        stats = stats.reset_index().rename(columns={"index": "symbol"})
        stats["month"] = m_start
        stats["rank"] = stats.index + 1
        stats["in_top10"] = stats["rank"] <= 10
        stats["in_top20"] = stats["rank"] <= 20
        recs.append(stats[PIT_COLS])
    if not recs:
        return pd.DataFrame(columns=PIT_COLS)
    return pd.concat(recs, ignore_index=True)


def run_pit(root: Path) -> dict[str, Any]:
    frames = []
    for p in (
        curated_dir(root) / "spot_daily_in_sample.parquet",
        holdout_sealed_dir(root) / "spot_daily_holdout.parquet",
    ):
        if p.exists():
            frames.append(pd.read_parquet(p, columns=["symbol", "open_time", "quote_volume"]))
    daily = pd.concat(frames, ignore_index=True)
    pit = build_pit_from_frame(daily, adjudications=load_adjudications(root))
    out = curated_dir(root) / "pit_universe.parquet"
    out.parent.mkdir(parents=True, exist_ok=True)
    pit.to_parquet(out, index=False, engine="pyarrow")
    man = Manifest(root, "curated")
    entry = man.add_file(out, rows=len(pit), source="pit_universe")
    meta = {
        "months": int(pit["month"].nunique()),
        "symbols_ever": int(pit["symbol"].nunique()),
        "first_month_full_top20": (
            str(pit.loc[pit["in_top20"], "month"].min()) if pit["in_top20"].any() else None
        ),
        "sha256": entry.sha256,
    }
    write_json(root, "data/manifests/pit_universe_meta.json", meta)
    return meta
