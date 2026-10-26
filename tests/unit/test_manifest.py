"""Manifiestos SHA256: registro, verificacion y fallo ante tampering."""

from __future__ import annotations

from pathlib import Path

from qa.data.manifest import Manifest


def _make_file(root: Path, rel: str, content: bytes) -> Path:
    p = root / rel
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_bytes(content)
    return p


def test_manifest_roundtrip_and_verify(tmp_path: Path) -> None:
    f = _make_file(tmp_path, "data/raw/x/test.bin", b"hola")
    man = Manifest(tmp_path, "test")
    entry = man.add_file(f, rows=1, source="unit-test")
    assert len(entry.sha256) == 64
    assert Manifest(tmp_path, "test").verify() == []


def test_manifest_detects_tampering(tmp_path: Path) -> None:
    f = _make_file(tmp_path, "data/raw/x/test.bin", b"hola")
    man = Manifest(tmp_path, "test")
    man.add_file(f, rows=1, source="unit-test")
    f.write_bytes(b"hola modificado a traicion")
    failures = Manifest(tmp_path, "test").verify()
    assert len(failures) == 1
    assert "HASH DISTINTO" in failures[0]


def test_manifest_detects_missing_file(tmp_path: Path) -> None:
    f = _make_file(tmp_path, "data/raw/x/test.bin", b"hola")
    Manifest(tmp_path, "test").add_file(f, rows=1, source="unit-test")
    f.unlink()
    failures = Manifest(tmp_path, "test").verify()
    assert failures == [f"FALTA {f.relative_to(tmp_path).as_posix()}"]
