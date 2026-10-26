"""Manifiestos SHA256 append-only por dataset (M1).

Cada fichero crudo descargado se registra con su hash, tamanno, filas, instante
de descarga, endpoint y parametros. ``qa data verify`` recalcula y falla si
cualquier fichero cambia o desaparece.
"""

from __future__ import annotations

import gzip
import hashlib
import json
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from pydantic import BaseModel, Field


class ManifestEntry(BaseModel):
    path: str  # relativo a la raiz del repo
    sha256: str
    bytes: int
    rows: int | None = None
    retrieved_at_utc: str
    source: str
    params: dict[str, Any] = Field(default_factory=dict)


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


class Manifest:
    def __init__(self, root: Path, name: str) -> None:
        self.root = root
        self.path = root / "data" / "manifests" / f"{name}.jsonl"
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._entries: dict[str, ManifestEntry] = {}
        if self.path.exists():
            for line in self.path.read_text(encoding="utf-8").splitlines():
                if line.strip():
                    e = ManifestEntry.model_validate_json(line)
                    self._entries[e.path] = e

    def paths(self) -> set[str]:
        return set(self._entries)

    def add_file(
        self,
        abs_path: Path,
        rows: int | None,
        source: str,
        params: dict[str, Any] | None = None,
    ) -> ManifestEntry:
        rel = abs_path.relative_to(self.root).as_posix()
        entry = ManifestEntry(
            path=rel,
            sha256=sha256_file(abs_path),
            bytes=abs_path.stat().st_size,
            rows=rows,
            retrieved_at_utc=datetime.now(UTC).isoformat(timespec="seconds"),
            source=source,
            params=params or {},
        )
        self._entries[rel] = entry
        with self.path.open("a", encoding="utf-8") as f:
            f.write(entry.model_dump_json() + "\n")
        return entry

    def verify(self) -> list[str]:
        """Lista de fallos (vacia = OK). No modifica nada."""
        failures: list[str] = []
        for rel, e in sorted(self._entries.items()):
            p = self.root / rel
            if not p.exists():
                failures.append(f"FALTA {rel}")
                continue
            actual = sha256_file(p)
            if actual != e.sha256:
                failures.append(
                    f"HASH DISTINTO {rel}: esperado {e.sha256[:12]}…, actual {actual[:12]}…"
                )
        return failures

    def __len__(self) -> int:
        return len(self._entries)


def write_json(root: Path, rel: str, payload: Any) -> Path:
    """Escribe un JSON determinista (sort_keys) y devuelve la ruta absoluta."""
    p = root / rel
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(payload, indent=2, sort_keys=True, default=str), encoding="utf-8")
    return p


def write_json_gz(root: Path, rel: str, payload: Any) -> Path:
    """JSON determinista comprimido (evidencias grandes, p. ej. exchangeInfo)."""
    p = root / rel
    p.parent.mkdir(parents=True, exist_ok=True)
    data = json.dumps(payload, indent=2, sort_keys=True, default=str).encode("utf-8")
    with open(p, "wb") as fh, gzip.GzipFile(fileobj=fh, mode="wb", mtime=0) as gz:
        gz.write(data)  # mtime=0: bytes reproducibles
    return p


def read_json_gz(path: Path) -> Any:
    with gzip.open(path, "rb") as f:
        return json.loads(f.read().decode("utf-8"))
