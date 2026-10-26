"""Ledger de trials: registro obligatorio, idempotencia, n_trials (M2)."""

from __future__ import annotations

import json
from collections.abc import Iterator
from pathlib import Path

import numpy as np
import pytest

from qa.backtest.costs import CostModel
from qa.backtest.engine import evaluate, run_positions
from qa.backtest.trials import TrialLedger


@pytest.fixture()
def ledger(tmp_path: Path) -> Iterator[TrialLedger]:
    led = TrialLedger(tmp_path)
    yield led
    led.close()


def test_trial_context_records(ledger: TrialLedger) -> None:
    with ledger.trial("TEST", "cell-A", "BTCUSDT", {"window": 200}) as ctx:
        ctx.set_metrics({"sharpe_ann": 1.23})
    rows = ledger.all_trials()
    assert len(rows) == 1
    r = rows[0]
    assert r["hypothesis"] == "TEST" and r["cell_id"] == "cell-A"
    assert json.loads(r["metrics"])["sharpe_ann"] == 1.23
    assert len(r["git_sha"]) >= 7


def test_trial_idempotent_rerun(ledger: TrialLedger) -> None:
    for _ in range(3):
        with ledger.trial("TEST", "cell-A", "BTCUSDT", {"window": 200}) as ctx:
            ctx.set_metrics({"sharpe_ann": 1.23})
    assert ledger.n_trials(hypothesis="TEST") == 1  # mismo run_id, sin duplicados


def test_failed_trial_still_recorded(ledger: TrialLedger) -> None:
    with pytest.raises(ValueError), ledger.trial("TEST", "cell-B", "ETHUSDT", {}) as ctx:
        ctx.error = "boom"
        raise ValueError("boom")
    rows = [r for r in ledger.all_trials() if r["cell_id"] == "cell-B"]
    assert len(rows) == 1  # el fallo tambien queda registrado


def test_n_trials_counts_only_strategy_kind(ledger: TrialLedger) -> None:
    with ledger.trial("TEST", "c1", "BTCUSDT", {}, kind="strategy") as c:
        c.set_metrics({})
    with ledger.trial("TEST", "c1", "BTCUSDT", {}, kind="null_permutation") as c:
        c.set_metrics({})
    assert ledger.n_trials("TEST", kind="strategy") == 1
    assert ledger.n_trials("TEST", kind="null_permutation") == 1


def test_evaluate_requires_trial_context() -> None:
    cm = CostModel(
        spot_taker_fee=0.001,
        perp_taker_fee=0.0005,
        slippage_tiers=((0.05, 5.0),),
        max_participation=0.05,
        min_notional_usdt=5.0,
    )
    close = 100.0 * np.cumprod(1 + np.array([0.0] + list(np.full(49, 0.001))))
    res = run_positions(close, np.ones(50), np.full(50, 1e9), cm, 10_000.0)
    with pytest.raises(RuntimeError, match="REGISTRO OBLIGATORIO"):
        evaluate(None, res)
