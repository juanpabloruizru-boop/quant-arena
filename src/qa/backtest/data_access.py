"""Acceso a datos con HOLDOUT SELLADO en runtime (condicion del gate M1).

- ``load_in_sample``: unico camino permitido para investigacion (M3).
- ``load_holdout``: exige ``QA_HOLDOUT_UNLOCK=1`` en el entorno Y escribe una
  fila append-only en ``ledger/holdout_access.log`` con sha256 del fichero,
  git SHA, proposito e instante UTC. Sin ambos: RuntimeError.
- El holdout vive FUERA de data/ (directorio ``holdout_sealed/``).
"""

from __future__ import annotations

import hashlib
import json
import os
import subprocess
from datetime import UTC, datetime
from pathlib import Path

import pandas as pd

from qa.data.paths import curated_dir, holdout_sealed_dir

IN_SAMPLE_FILES = {
    "spot_daily",
    "futures_daily",
    "funding",
    "pit_universe",
}
HOLDOUT_FILES = {"spot_daily", "futures_daily", "funding"}


class HoldoutSealedError(RuntimeError):
    """Se intento leer el holdout sin QA_HOLDOUT_UNLOCK=1."""


def _git_sha(root: Path) -> str:
    try:
        out = subprocess.run(
            ["git", "rev-parse", "HEAD"], cwd=root, capture_output=True, text=True, timeout=10
        )
        return out.stdout.strip() or "unknown"
    except (OSError, subprocess.TimeoutExpired):
        return "unknown"


def load_in_sample(name: str, root: Path) -> pd.DataFrame:
    if name == "pit_universe":
        p = curated_dir(root) / "pit_universe.parquet"
    else:
        p = curated_dir(root) / f"{name}_in_sample.parquet"
    if not p.exists():
        raise FileNotFoundError(f"dataset in-sample no encontrado: {p}")
    return pd.read_parquet(p)


def load_holdout(name: str, root: Path, purpose: str) -> pd.DataFrame:
    """Solo con QA_HOLDOUT_UNLOCK=1 (+ QA_HOLDOUT_KEY si esta cifrado).

    Dos modos:
    - SELLADO (SEALED.json presente, ficheros .gpg): exige la clave del
      usuario (QA_HOLDOUT_KEY); valida su huella, descifra a temporal,
      verifica sha256 contra el registro del sellado y loguea el acceso.
    - plaintext (pre-sellado): exige solo QA_HOLDOUT_UNLOCK=1 y loguea.
    """
    if name not in HOLDOUT_FILES:
        raise ValueError(f"dataset holdout desconocido: {name}")
    if os.environ.get("QA_HOLDOUT_UNLOCK") != "1":
        raise HoldoutSealedError(
            "HOLDOUT SELLADO: el motor se niega a cargar "
            f"{name}_holdout sin QA_HOLDOUT_UNLOCK=1 (una sola evaluacion al "
            "final de M3, segun PRERREGISTRO)."
        )
    log_dir = root / "ledger"
    log_dir.mkdir(parents=True, exist_ok=True)

    from qa.backtest import seal

    if seal.is_sealed(root):
        key = os.environ.get("QA_HOLDOUT_KEY")
        if not key:
            raise HoldoutSealedError(
                "HOLDOUT CIFRADO: falta QA_HOLDOUT_KEY (la clave de 32 bytes "
                "entregada una unica vez en el informe M2b)."
            )
        tmp = seal.open_holdout_file(root, name, key, purpose)
        try:
            df = pd.read_parquet(tmp)
            sha = hashlib.sha256(tmp.read_bytes()).hexdigest()
        finally:
            tmp.unlink(missing_ok=True)
        source = f"holdout_sealed/{name}_holdout.parquet.gpg (descifrado)"
    else:
        p = holdout_sealed_dir(root) / f"{name}_holdout.parquet"
        if not p.exists():
            raise FileNotFoundError(f"holdout no encontrado: {p}")
        sha = hashlib.sha256(p.read_bytes()).hexdigest()
        df = pd.read_parquet(p)
        source = str(p.relative_to(root))

    entry = {
        "ts_utc": datetime.now(UTC).isoformat(timespec="seconds"),
        "file": source,
        "sha256": sha,
        "git_sha": _git_sha(root),
        "purpose": purpose,
    }
    with (log_dir / "holdout_access.log").open("a", encoding="utf-8") as f:
        f.write(json.dumps(entry, sort_keys=True) + "\n")
    return df
