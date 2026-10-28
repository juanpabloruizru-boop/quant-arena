"""Forward paper minimo (M4 v0): registro diario de ESTADOS con cadena de hashes.

v0 (este hito): cada ejecucion (manual `qa forward run` o GitHub Actions,
ADR-007) anade UNA linea a ledger/forward.jsonl con el estado de las 5 celdas
congeladas (posicion objetivo H1, cesta H2, senal H3) + hashes de datos + git
SHA + prev_hash. El motor de fills t+1 con P&L paper completo se activa al
congelar la etiqueta `forward-v1` (gate M4 del orquestador).
"""

from __future__ import annotations

import hashlib
import json
import subprocess
from datetime import UTC, datetime
from pathlib import Path
from typing import Any


def _git_sha(root: Path) -> str:
    try:
        out = subprocess.run(
            ["git", "rev-parse", "HEAD"], cwd=root, capture_output=True, text=True, timeout=10
        )
        return out.stdout.strip() or "unknown"
    except (OSError, subprocess.TimeoutExpired):
        return "unknown"


def _sha(line: str) -> str:
    return hashlib.sha256(line.encode("utf-8")).hexdigest()


def append_forward_record(root: Path, states: dict[str, Any]) -> dict[str, Any]:
    p = root / "ledger" / "forward.jsonl"
    p.parent.mkdir(parents=True, exist_ok=True)
    prev = ""
    if p.exists():
        lines = [ln for ln in p.read_text(encoding="utf-8").splitlines() if ln.strip()]
        if lines:
            prev = _sha(lines[-1])
    cells = states.get("cells", {})
    rec = {
        "ts_utc": datetime.now(UTC).isoformat(timespec="seconds"),
        "git_sha": _git_sha(root),
        "data_fetched_at": states.get("fetched_at_utc"),
        "h1": {
            a: {
                "estado": cells.get(f"H1_{a}", {}).get("estado"),
                "posicion_regla": cells.get(f"H1_{a}", {}).get("posicion_regla"),
            }
            for a in ("BTCUSDT", "ETHUSDT")
        },
        "h2_cesta": cells.get("H2_L26_N10", {}).get("cesta_teoretica"),
        "h3": {
            a: {
                "senal_activa": cells.get(f"H3_{a}", {}).get("senal_activa"),
                "funding_ma30_ann": cells.get(f"H3_{a}", {}).get("funding_ma30_ann"),
            }
            for a in ("BTCUSDT", "ETHUSDT")
        },
        "prev_hash": prev,
    }
    line = json.dumps(rec, sort_keys=True, default=str)
    with p.open("a", encoding="utf-8") as f:
        f.write(line + "\n")
    return rec


def verify_forward_chain(root: Path) -> tuple[bool, int, str]:
    p = root / "ledger" / "forward.jsonl"
    if not p.exists():
        return True, 0, "sin registros forward"
    lines = [ln for ln in p.read_text(encoding="utf-8").splitlines() if ln.strip()]
    prev = ""
    for i, ln in enumerate(lines):
        rec = json.loads(ln)
        if rec.get("prev_hash", "") != prev:
            return False, len(lines), f"cadena forward rota en linea {i + 1}"
        prev = _sha(ln)
    return True, len(lines), "cadena forward valida"
