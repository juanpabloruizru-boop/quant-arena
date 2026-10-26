"""Rutas canonicas del proyecto (M1).

``QA_ROOT`` permite apuntar a otro directorio en tests; por defecto, la raiz
del repo (tres niveles por encima de este fichero: src/qa/data/paths.py).
"""

from __future__ import annotations

import os
from pathlib import Path


def get_root() -> Path:
    env = os.environ.get("QA_ROOT")
    if env:
        return Path(env).resolve()
    return Path(__file__).resolve().parents[3]


def raw_dir(root: Path | None = None) -> Path:
    return (root or get_root()) / "data" / "raw"


def curated_dir(root: Path | None = None) -> Path:
    return (root or get_root()) / "data" / "curated"


def holdout_sealed_dir(root: Path | None = None) -> Path:
    """Holdout sellado: FUERA de data/ por defecto (condicion gate M1/M2)."""
    return (root or get_root()) / "holdout_sealed"


def manifests_dir(root: Path | None = None) -> Path:
    return (root or get_root()) / "data" / "manifests"


def reports_dir(root: Path | None = None) -> Path:
    return (root or get_root()) / "reports"


def config_dir(root: Path | None = None) -> Path:
    return (root or get_root()) / "config"
