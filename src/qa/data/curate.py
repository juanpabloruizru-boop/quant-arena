"""Curacion de datos crudos -> Parquet inmutable + holdout sellado (M1).

- Deduplica por (symbol, open_time), ordena y valida tipos.
- **Holdout sellado:** los ultimos 365 dias ([freeze_end-364d, freeze_end]) se
  separan FISICAMENTE en ficheros ``*_holdout.parquet``. El codigo de
  investigacion (M3) no debe leerlos hasta la evaluacion unica pre-registrada.
- ``dataset_meta.json``: fronteras exactas, filas y SHA256 por fichero.
"""

from __future__ import annotations

import json
from datetime import timedelta
from pathlib import Path
from typing import Any

import pandas as pd

from qa.data.manifest import Manifest, write_json
from qa.data.paths import curated_dir, manifests_dir, raw_dir


def _load_dir(d: Path) -> pd.DataFrame:
    files = sorted(d.glob("*.parquet"))
    if not files:
        return pd.DataFrame()
    return pd.concat([pd.read_parquet(f) for f in files], ignore_index=True)


def _write_split(
    df: pd.DataFrame,
    time_col: str,
    holdout_start: pd.Timestamp,
    root: Path,
    name: str,
    meta: dict[str, Any],
    man: Manifest,
) -> None:
    for tag, part in (
        ("in_sample", df[df[time_col] < holdout_start]),
        ("holdout", df[df[time_col] >= holdout_start]),
    ):
        p = curated_dir(root) / f"{name}_{tag}.parquet"
        p.parent.mkdir(parents=True, exist_ok=True)
        part.to_parquet(p, index=False, engine="pyarrow")
        entry = man.add_file(p, rows=len(part), source=f"curated:{name}")
        meta["files"][p.relative_to(root).as_posix()] = {
            "rows": len(part),
            "sha256": entry.sha256,
            "bytes": entry.bytes,
        }


def run_curate(root: Path) -> dict[str, Any]:
    sync_log = json.loads((manifests_dir(root) / "sync_log.json").read_text())
    freeze_end = pd.Timestamp(sync_log["freeze_end_utc"])
    holdout_start = freeze_end.normalize() - timedelta(days=364)
    man = Manifest(root, "curated")
    meta: dict[str, Any] = {
        "data_freeze_end_utc": str(freeze_end),
        "holdout_start_utc": str(holdout_start),
        "holdout_end_utc": str(freeze_end),
        "holdout_days": 365,
        "files": {},
    }
    dups: dict[str, int] = {}
    for name, time_col in (
        ("spot_daily", "open_time"),
        ("futures_daily", "open_time"),
        ("funding", "funding_time"),
    ):
        df = _load_dir(raw_dir(root) / name)
        if df.empty:
            dups[name] = 0
            continue
        key = ["symbol", time_col]
        dups[name] = int(len(df) - len(df.drop_duplicates(subset=key)))
        df = df.drop_duplicates(subset=key, keep="last").sort_values(key)
        _write_split(df, time_col, holdout_start, root, name, meta, man)
    meta["duplicates_removed"] = dups
    write_json(root, "data/manifests/dataset_meta.json", meta)
    return meta
