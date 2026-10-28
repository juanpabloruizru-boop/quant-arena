"""Ledger append-only de trials (DuckDB) — M2.

Principio 3: TODO backtest se registra solo. El motor (qa.backtest.engine)
exige un TrialLedger abierto dentro de un contexto ``trial(...)``; ejecutar un
backtest sin registro es imposible por construccion (RuntimeError).

- n_trials para DSR/SPA se lee de esta tabla (nunca manual).
- run_id determinista = sha256(hypothesis|cell|asset|kind|config_hash|data_hash).
- Solo INSERT (ON CONFLICT DO NOTHING). Ninguna API de UPDATE/DELETE existe.
"""

from __future__ import annotations

import contextlib
import hashlib
import json
import subprocess
from collections.abc import Iterator
from contextlib import contextmanager
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import duckdb


def _git_sha(root: Path) -> str:
    try:
        out = subprocess.run(
            ["git", "rev-parse", "HEAD"], cwd=root, capture_output=True, text=True, timeout=10
        )
        return out.stdout.strip() or "unknown"
    except (OSError, subprocess.TimeoutExpired):
        return "unknown"


def config_hash(config: dict[str, Any]) -> str:
    blob = json.dumps(config, sort_keys=True, default=str).encode("utf-8")
    return hashlib.sha256(blob).hexdigest()[:16]


class TrialLedger:
    def __init__(self, root: Path) -> None:
        self.root = root
        ledger_dir = root / "ledger"
        ledger_dir.mkdir(parents=True, exist_ok=True)
        self.path = ledger_dir / "trials.duckdb"
        self.con = duckdb.connect(str(self.path))
        self.con.execute(
            """
            CREATE TABLE IF NOT EXISTS trials (
                run_id VARCHAR PRIMARY KEY,
                ts_utc TIMESTAMP,
                hypothesis VARCHAR,
                cell_id VARCHAR,
                asset VARCHAR,
                kind VARCHAR,
                config_hash VARCHAR,
                data_hash VARCHAR,
                git_sha VARCHAR,
                metrics VARCHAR,
                notes VARCHAR
            )
            """
        )

    def data_hash(self) -> str:
        from qa.data.paths import manifests_dir

        meta = manifests_dir(self.root) / "dataset_meta.json"
        if not meta.exists():
            return "no-dataset"
        return hashlib.sha256(meta.read_bytes()).hexdigest()[:16]

    @contextmanager
    def trial(
        self,
        hypothesis: str,
        cell_id: str,
        asset: str,
        config: dict[str, Any],
        kind: str = "strategy",
        notes: str = "",
    ) -> Iterator[_TrialContext]:
        ctx = _TrialContext(
            ledger=self,
            hypothesis=hypothesis,
            cell_id=cell_id,
            asset=asset,
            kind=kind,
            cfg_hash=config_hash(config),
            notes=notes,
        )
        try:
            yield ctx
        except BaseException as e:
            if ctx.error is None:
                ctx.error = repr(e)[:500]
            raise
        finally:
            # el registro ocurre SIEMPRE al salir del contexto (exito o excepcion)
            self._insert(ctx, ctx.metrics, ctx.error)
            ctx._committed = True

    def _insert(
        self, ctx: _TrialContext, metrics: dict[str, Any] | None, error: str | None
    ) -> None:
        key = (
            f"{ctx.hypothesis}|{ctx.cell_id}|{ctx.asset}|{ctx.kind}|"
            f"{ctx.cfg_hash}|{self.data_hash()}"
        )
        run_id = hashlib.sha256(key.encode()).hexdigest()[:16]
        payload = dict(metrics or {})
        if error:
            payload["_error"] = error[:500]
        self.con.execute(
            "INSERT INTO trials VALUES (?,?,?,?,?,?,?,?,?,?,?) ON CONFLICT (run_id) DO NOTHING",
            [
                run_id,
                datetime.now(UTC).replace(tzinfo=None),
                ctx.hypothesis,
                ctx.cell_id,
                ctx.asset,
                ctx.kind,
                ctx.cfg_hash,
                self.data_hash(),
                _git_sha(self.root),
                json.dumps(payload, default=str),
                ctx.notes,
            ],
        )

    def find(
        self, hypothesis: str, cell_id: str, asset: str, kind: str = "strategy"
    ) -> dict[str, Any] | None:
        """Metrics de un trial ya registrado (checkpoint/resume), o None."""
        rows = self.con.execute(
            "SELECT metrics FROM trials WHERE hypothesis=? AND cell_id=? AND asset=? AND kind=? "
            "ORDER BY ts_utc DESC LIMIT 1",
            [hypothesis, cell_id, asset, kind],
        ).fetchall()
        if not rows or not rows[0][0]:
            return None
        loaded = json.loads(rows[0][0])
        return dict(loaded)

    def family_sharpes(self, hypothesis: str, kind: str = "strategy") -> list[float]:
        """Sharpe anualizados de todos los trials de una familia (para sd del DSR)."""
        rows = self.con.execute(
            "SELECT metrics FROM trials WHERE hypothesis=? AND kind=?", [hypothesis, kind]
        ).fetchall()
        out: list[float] = []
        for (m,) in rows:
            if m:
                d = json.loads(m)
                if "sharpe_ann" in d:
                    out.append(float(d["sharpe_ann"]))
        return out

    def n_trials(self, hypothesis: str | None = None, kind: str = "strategy") -> int:
        q = "SELECT count(*) FROM trials WHERE kind = ?"
        args: list[Any] = [kind]
        if hypothesis is not None:
            q += " AND hypothesis = ?"
            args.append(hypothesis)
        row = self.con.execute(q, args).fetchone()
        return int(row[0]) if row else 0

    def all_trials(self) -> list[dict[str, Any]]:
        rows = self.con.execute(
            "SELECT run_id, ts_utc, hypothesis, cell_id, asset, kind, config_hash, "
            "data_hash, git_sha, metrics, notes FROM trials ORDER BY ts_utc"
        ).fetchall()
        cols = [
            "run_id",
            "ts_utc",
            "hypothesis",
            "cell_id",
            "asset",
            "kind",
            "config_hash",
            "data_hash",
            "git_sha",
            "metrics",
            "notes",
        ]
        return [dict(zip(cols, r, strict=True)) for r in rows]

    def close(self) -> None:
        self.con.close()


class _TrialContext:
    def __init__(
        self,
        ledger: TrialLedger,
        hypothesis: str,
        cell_id: str,
        asset: str,
        kind: str,
        cfg_hash: str,
        notes: str,
    ) -> None:
        self.ledger = ledger
        self.hypothesis = hypothesis
        self.cell_id = cell_id
        self.asset = asset
        self.kind = kind
        self.cfg_hash = cfg_hash
        self.notes = notes
        self.metrics: dict[str, Any] | None = None
        self.error: str | None = None
        self._committed = False

    def set_metrics(self, metrics: dict[str, Any]) -> None:
        self.metrics = metrics

    def __del__(self) -> None:
        # red de seguridad: si el contexto murio sin registrar, hacerlo ya
        if not self._committed:
            with contextlib.suppress(Exception):  # ultimo recurso
                self.ledger._insert(self, self.metrics, self.error or "context-exited-early")
