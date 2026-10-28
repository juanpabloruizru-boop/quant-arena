"""Cadena de hashes append-only compartida (M5b).

Mismo esquema que el tracker de operaciones de M4: cada línea JSON firma a la
anterior con SHA-256, de modo que editar o borrar historia ROMPE la cadena y
se detecta con `verify_chain_file`. `rewrite_chain` es la única mutación
permitida y la usa exclusivamente `qa capital reset-examples` (solo registros
marcados `example: true`, siempre con copia de seguridad previa).
"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any


def sha_line(line: str) -> str:
    return hashlib.sha256(line.encode("utf-8")).hexdigest()


def _last_hash(path: Path) -> str:
    if not path.exists():
        return ""
    lines = [ln for ln in path.read_text(encoding="utf-8").splitlines() if ln.strip()]
    return sha_line(lines[-1]) if lines else ""


def append_chained(path: Path, record: dict[str, Any]) -> dict[str, Any]:
    """Añade un registro al final, encadenándolo al hash de la línea previa."""
    path.parent.mkdir(parents=True, exist_ok=True)
    record = dict(record)
    record["prev_hash"] = _last_hash(path)
    line = json.dumps(record, sort_keys=True, default=str)
    with path.open("a", encoding="utf-8") as f:
        f.write(line + "\n")
    return record


def verify_chain_file(path: Path) -> tuple[bool, int, str]:
    if not path.exists():
        return True, 0, "sin registros"
    lines = [ln for ln in path.read_text(encoding="utf-8").splitlines() if ln.strip()]
    prev = ""
    for i, ln in enumerate(lines):
        rec = json.loads(ln)
        if rec.get("prev_hash", "") != prev:
            return False, len(lines), f"cadena rota en la linea {i + 1}"
        prev = sha_line(ln)
    return True, len(lines), "cadena valida"


def read_records(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    out: list[dict[str, Any]] = []
    for ln in path.read_text(encoding="utf-8").splitlines():
        if ln.strip():
            rec = json.loads(ln)
            assert isinstance(rec, dict)
            out.append(rec)
    return out


def rewrite_chain(path: Path, records: list[dict[str, Any]]) -> int:
    """Reescribe el fichero con `records` recalculando la cadena de hashes.

    Uso exclusivo: `reset-examples` (registros EJEMPLO, con backup previo).
    Devuelve el número de líneas escritas.
    """
    path.parent.mkdir(parents=True, exist_ok=True)
    prev = ""
    lines: list[str] = []
    for rec in records:
        rec = dict(rec)
        rec["prev_hash"] = prev
        line = json.dumps(rec, sort_keys=True, default=str)
        lines.append(line)
        prev = sha_line(line)
    path.write_text("\n".join(lines) + ("\n" if lines else ""), encoding="utf-8")
    return len(lines)
