"""Sellado cifrado del holdout (condicion E, gate M2).

- ``seal_holdout``: cifra cada ``holdout_sealed/*.parquet`` con gpg simetrico
  AES256 y una clave aleatoria de 32 bytes (64 hex). La clave se devuelve UNA
  sola vez (para mostrarla en el informe) y NO se persiste en ningun fichero
  del sandbox. Registra sha256 del plaintext en ``ledger/holdout_seal.log``
  (append-only) y un marcador ``holdout_sealed/SEALED.json`` con huella de la
  clave (sha256(key)[:16], no reveladora) para validar la clave del usuario
  sin descifrar.
- ``open_holdout_file``: exige clave correcta (huella), descifra a un temporal,
  verifica sha256 contra el registro y lo devuelve.
- Si la clave se pierde: regenerar datos con ``qa data sync``/``qa data curate``
  (QA_FREEZE_END=2026-10-25 para fijar el mismo freeze) y verificar los sha256
  del plaintext contra ``ledger/holdout_seal.log``.
"""

from __future__ import annotations

import hashlib
import json
import os
import secrets
import shutil
import subprocess
import tempfile
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from qa.data.paths import holdout_sealed_dir

CIPHER = "gpg-symmetric-AES256"


def _require_gpg() -> str:
    gpg = shutil.which("gpg")
    if gpg is None:
        raise RuntimeError(
            "gpg no disponible en el entorno (apt-get install -y gnupg); "
            "necesario para el sellado/desellado del holdout"
        )
    return gpg


def _gpg_symmetric(gpg: str, key: str, src: Path, dst: Path, decrypt: bool) -> None:
    cmd = [
        gpg,
        "--batch",
        "--yes",
        "--pinentry-mode",
        "loopback",
        "--passphrase-fd",
        "0",
        "--cipher-algo",
        "AES256",
    ]
    cmd.append("--decrypt" if decrypt else "--symmetric")
    cmd += ["--output", str(dst), str(src)]
    proc = subprocess.run(  # noqa: S603 - binario del sistema, args fijos
        cmd, input=key.encode(), capture_output=True, timeout=300
    )
    if proc.returncode != 0:
        raise RuntimeError(f"gpg fallo ({proc.returncode}): {proc.stderr.decode()[:200]}")


def key_fingerprint(key: str) -> str:
    return hashlib.sha256(key.encode()).hexdigest()[:16]


def seal_holdout(root: Path) -> str:
    """Cifra el holdout y devuelve la clave (unica vez que existe en memoria)."""
    gpg = _require_gpg()
    hdir = holdout_sealed_dir(root)
    marker_path = hdir / "SEALED.json"
    if marker_path.exists():
        raise RuntimeError("holdout ya sellado (SEALED.json existe)")
    key = secrets.token_hex(32)  # 32 bytes aleatorios
    files_meta: dict[str, Any] = {}
    seal_log = root / "ledger" / "holdout_seal.log"
    seal_log.parent.mkdir(parents=True, exist_ok=True)
    entries = []
    for p in sorted(hdir.glob("*.parquet")):
        sha = hashlib.sha256(p.read_bytes()).hexdigest()
        gpg_path = p.with_suffix(".parquet.gpg")
        _gpg_symmetric(gpg, key, p, gpg_path, decrypt=False)
        files_meta[p.name] = {
            "sha256_plaintext": sha,
            "bytes_plaintext": p.stat().st_size,
            "gpg": gpg_path.name,
            "sha256_gpg": hashlib.sha256(gpg_path.read_bytes()).hexdigest(),
        }
        entries.append(
            {
                "ts_utc": datetime.now(UTC).isoformat(timespec="seconds"),
                "action": "seal",
                "file": f"holdout_sealed/{p.name}",
                "sha256_plaintext": sha,
                "cipher": CIPHER,
                "key_fingerprint": key_fingerprint(key),
            }
        )
        p.unlink()  # el plaintext deja de existir
    marker = {
        "sealed_at_utc": datetime.now(UTC).isoformat(timespec="seconds"),
        "cipher": CIPHER,
        "key_fingerprint": key_fingerprint(key),
        "files": files_meta,
        "recovery": (
            "Si la clave se pierde: regenerar con qa data sync + qa data curate "
            "(QA_FREEZE_END=2026-10-25) y verificar sha256 contra ledger/holdout_seal.log"
        ),
    }
    marker_path.write_text(json.dumps(marker, indent=2, sort_keys=True), encoding="utf-8")
    with seal_log.open("a", encoding="utf-8") as f:
        for e in entries:
            f.write(json.dumps(e, sort_keys=True) + "\n")
    return key


def open_holdout_file(root: Path, name: str, key: str, purpose: str) -> Path:
    """Descifra a un temporal verificado; el llamador lo lee y lo borra."""
    gpg = _require_gpg()
    hdir = holdout_sealed_dir(root)
    marker = json.loads((hdir / "SEALED.json").read_text(encoding="utf-8"))
    if key_fingerprint(key) != marker["key_fingerprint"]:
        raise PermissionError("clave de holdout incorrecta (huella no coincide)")
    fname = f"{name}_holdout.parquet"
    meta = marker["files"][fname]
    src = hdir / meta["gpg"]
    tmp = Path(tempfile.mkstemp(prefix="qa_holdout_", suffix=".parquet")[1])
    _gpg_symmetric(gpg, key, src, tmp, decrypt=True)
    sha = hashlib.sha256(tmp.read_bytes()).hexdigest()
    if sha != meta["sha256_plaintext"]:
        tmp.unlink(missing_ok=True)
        raise RuntimeError(
            f"holdout descifrado NO coincide con el sha256 sellado ({sha[:12]}… "
            f"vs {meta['sha256_plaintext'][:12]}…)"
        )
    seal_log = root / "ledger" / "holdout_seal.log"
    with seal_log.open("a", encoding="utf-8") as f:
        f.write(
            json.dumps(
                {
                    "ts_utc": datetime.now(UTC).isoformat(timespec="seconds"),
                    "action": "open",
                    "file": f"holdout_sealed/{fname}",
                    "sha256_plaintext": sha,
                    "purpose": purpose,
                    "key_fingerprint": key_fingerprint(key),
                },
                sort_keys=True,
            )
            + "\n"
        )
    return tmp


def is_sealed(root: Path) -> bool:
    return (holdout_sealed_dir(root) / "SEALED.json").exists()


def clear_key_from_env() -> None:
    os.environ.pop("QA_HOLDOUT_KEY", None)
