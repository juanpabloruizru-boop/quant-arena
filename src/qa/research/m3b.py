"""M3b — evaluacion UNICA del holdout sellado (v1.4 s7.9, puerta 2).

Reglas de este modulo (congeladas antes de la apertura):
- Solo las 5 celdas de reports/M3a_selected_cells.json. Cero re-ajustes.
- Warmup de indicadores con cola in-sample (300 dias naturales); la ventana
  de evaluacion es EXCLUSIVAMENTE [ho_start, ho_end] (holdout).
- **Fresh-start:** ninguna posicion antes de ho_start; los costes de entrada
  iniciales se cargan dentro del holdout (conservador).
- El holdout se descifra UNA vez por fichero (spot/futures/funding) y todo se
  evalua en memoria en la misma corrida (incluido el apendice de escalado de
  capital), minimizando las entradas del log de acceso a las estrictamente
  necesarias (3).
- C7 (v1.4 s8): coherencia de signo del criterio primario; en H1 ambos activos
  con signo opuesto al in-sample => NO_PASA. n=1 ano: no se exige significacion.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

from qa.backtest.costs import CostModel
from qa.backtest.engine import run_carry, run_positions, simple_returns
from qa.backtest.trials import TrialLedger
from qa.data.pit import load_adjudications
from qa.stats.benchmarks import timing_permutation_pvalue
from qa.stats.bootstrap import newey_west_se
from qa.stats.metrics import (
    max_drawdown,
    metrics_summary,
    sharpe_ann,
    trades_from_positions,
)
from qa.strategies.h1 import BAND_FROZEN, H1Cell
from qa.strategies.h2 import H2Cell, build_h2, build_weekly_panel
from qa.strategies.h3 import H3Cell, h3_signal

WARMUP_DAYS = 300
HOLDOUT_START = pd.Timestamp("2025-10-26", tz="UTC")
CAPITAL_DEFAULT = 10_000.0
CAPITAL_LEVELS = (100.0, 500.0, 1_000.0, 10_000.0)
SEED = 20261028


def _norm_cdf(x: float) -> float:
    from statistics import NormalDist

    return NormalDist().cdf(x)


@dataclass
class M3bFrames:
    """Datos necesarios, cargados UNA sola vez por el driver."""

    spot_full: pd.DataFrame  # in-sample + holdout (todos los simbolos)
    futures_full: pd.DataFrame  # in-sample + holdout (BTC/ETH)
    funding_full: pd.DataFrame  # in-sample + holdout (BTC/ETH)
    pit: pd.DataFrame
    ho_start: pd.Timestamp


def _h1_asset_frame(frames: M3bFrames, asset: str) -> tuple[pd.DatetimeIndex, Any, Any]:
    d = frames.spot_full[frames.spot_full["symbol"] == asset].sort_values("open_time")
    d = d[d["open_time"] >= frames.ho_start - pd.Timedelta(days=WARMUP_DAYS)]
    return (
        pd.DatetimeIndex(d["open_time"]),
        np.asarray(d["close"].to_numpy(), dtype=np.float64),
        np.asarray(d["quote_volume"].to_numpy(), dtype=np.float64),
    )


def eval_h1(
    frames: M3bFrames, asset: str, cell: H1Cell, cm: CostModel, capital: float
) -> dict[str, Any]:
    times, close, qv = _h1_asset_frame(frames, asset)
    desired_full = None
    from qa.strategies.h1 import h1_desired_weights

    desired_full = h1_desired_weights(close, cell)
    desired = np.where(times >= frames.ho_start, desired_full, 0.0)  # fresh-start
    res = run_positions(close, desired, qv, cm, capital, band=BAND_FROZEN)
    times_r = times[1:]
    r_all = simple_returns(close)
    mask = times_r >= frames.ho_start
    strat = res.net_returns[mask]
    pos = res.positions[mask]
    r_ho = r_all[mask]

    m: dict[str, Any] = dict(metrics_summary(strat, pos))
    total = float(np.prod(1.0 + strat) - 1.0)
    n_days = int(mask.sum())
    m["total_return_net"] = round(total, 5)
    m["cagr_net"] = round((1.0 + total) ** (365.0 / n_days) - 1.0, 5) if total > -1 else -1.0
    m["bh_return_same_window"] = round(float(np.prod(1.0 + r_ho) - 1.0), 5)
    m["d_sharpe_vs_bh"] = round(sharpe_ann(strat) - sharpe_ann(r_ho), 4)
    m["d_maxdd_raw_pp"] = round((max_drawdown(strat) - max_drawdown(r_ho)) * 100, 2)
    sd_b = float(np.std(r_ho, ddof=1))
    sd_s = float(np.std(strat, ddof=1))
    f_vm = sd_s / sd_b if sd_b > 1e-15 else 1.0
    m["d_vm_pp"] = round((max_drawdown(strat) - max_drawdown(f_vm * r_ho)) * 100, 2)
    perm_cost = cm.side_cost_rate(1e-9) or 0.0011
    p_val, d_obs, p_adv = timing_permutation_pvalue(
        pos, r_ho, perm_cost, n_perm=10_000, block=20, seed=SEED + 1, chunk=1000
    )
    m["perm_p_descriptivo"] = round(p_val, 5)
    m["perm_p_adverso"] = round(p_adv, 5)
    m["n_trades"] = len(trades_from_positions(pos))
    m["trades_per_year"] = round(m["n_trades"] / (n_days / 365.0), 2)
    m["exposure_mean"] = round(float(pos.mean()), 4)
    m["time_in_market_pct"] = round(float((pos > 0).mean()) * 100, 2)
    m["rejected_min_notional"] = int(res.rejected_min_notional)
    m["rejected_liquidity"] = int(res.rejected_trades)
    m["last_day"] = str(times_r[-1].date())
    m["position_last_day"] = round(float(pos[-1]), 4)
    m["target_weight_last_day"] = round(float(desired[-1]), 4)
    m["n_days"] = n_days
    return m


def eval_h2(
    frames: M3bFrames, cell: H2Cell, cm: CostModel, capital: float, root: Path
) -> dict[str, Any]:
    daily = frames.spot_full[
        frames.spot_full["open_time"] >= frames.ho_start - pd.Timedelta(days=WARMUP_DAYS)
    ]
    panel = build_weekly_panel(daily)
    adj = load_adjudications(root)
    res = build_h2(panel, frames.pit, adj, cell, cm, capital)
    strat = res.strat_ret.loc[res.strat_ret.index >= frames.ho_start]
    bench = res.bench_ret.loc[res.bench_ret.index >= frames.ho_start]
    s = strat.to_numpy(dtype=np.float64)
    b = bench.to_numpy(dtype=np.float64)
    m: dict[str, Any] = {}
    m["n_weeks"] = int(len(s))
    m["total_return_net"] = round(float(np.prod(1.0 + s) - 1.0), 5)
    m["bench_total_return"] = round(float(np.prod(1.0 + b) - 1.0), 5)
    m["sharpe_ann"] = round(sharpe_ann(s, periods=52.0), 4)
    m["bench_sharpe_ann"] = round(sharpe_ann(b, periods=52.0), 4)
    m["d_sharpe_vs_ew"] = round(m["sharpe_ann"] - m["bench_sharpe_ann"], 4)
    m["max_drawdown"] = round(max_drawdown(s), 4)
    m["win_rate_weeks"] = round(float((s > 0).mean()), 4) if len(s) else 0.0
    m["mean_eligible"] = round(res.mean_eligible, 1)
    m["last_basket"] = res.last_basket
    m["first_week"] = str(strat.index[0].date()) if len(strat) else ""
    m["last_week"] = str(strat.index[-1].date()) if len(strat) else ""
    return m


def _h3_asset_frames(
    frames: M3bFrames, asset: str
) -> tuple[pd.DatetimeIndex, pd.DataFrame, Any, Any, Any]:
    spot = frames.spot_full[frames.spot_full["symbol"] == asset].sort_values("open_time")
    perp = frames.futures_full[frames.futures_full["symbol"] == asset].sort_values("open_time")
    fund = frames.funding_full[frames.funding_full["symbol"] == asset].sort_values("funding_time")
    lo = frames.ho_start - pd.Timedelta(days=WARMUP_DAYS)
    sp = spot.set_index(spot["open_time"].dt.floor("D"))
    pp = perp.set_index(perp["open_time"].dt.floor("D"))
    idx0 = sp.index.intersection(pp.index)
    idx = pd.DatetimeIndex(idx0[idx0 >= lo])
    return (
        idx,
        fund,
        sp.loc[idx, "close"].to_numpy(dtype=np.float64),
        pp.loc[idx, "close"].to_numpy(dtype=np.float64),
        sp.loc[idx, "quote_volume"].to_numpy(dtype=np.float64),
    )


def eval_h3(
    frames: M3bFrames, asset: str, cell: H3Cell, cm: CostModel, capital: float
) -> dict[str, Any]:
    days, fund, spot_close, perp_close, qv = _h3_asset_frames(frames, asset)
    sig_full, fma = h3_signal(days, fund, cell)
    allowed = np.asarray(days >= frames.ho_start)
    sig = np.asarray(sig_full & allowed)  # fresh-start: flat antes del holdout
    res = run_carry(days, fund, sig, qv, cm, capital, spot_close, perp_close)
    net_all = res.net_returns
    net = net_all[allowed]
    n = int(net.size)
    mean_d = float(net.mean())
    se = newey_west_se(net, lag=cell.window_days)
    t_stat = mean_d / se if se > 0 else 0.0
    total = float(np.prod(1.0 + net) - 1.0)
    m: dict[str, Any] = dict(metrics_summary(net, res.positions[allowed]))
    m["n_days"] = n
    m["total_return_net"] = round(total, 5)
    m["cagr_net"] = round((1.0 + total) ** (365.0 / n) - 1.0, 5) if total > -1 else -1.0
    m["mean_daily_net_bp"] = round(mean_d * 10_000, 4)
    m["hac_t"] = round(float(t_stat), 4)
    m["hac_p_one_sided"] = (
        round(1.0 - _norm_cdf(t_stat), 5) if mean_d > 0 else round(_norm_cdf(t_stat), 5)
    )
    fund_ho = float(fund[(fund["funding_time"] >= frames.ho_start)]["funding_rate"].sum())
    m["funding_total_period"] = round(fund_ho, 6)
    m["funding_collected"] = res.funding_collected
    m["time_in_market_pct"] = round(float(res.positions[allowed].mean()) * 100, 2)
    entries = int(np.sum(np.diff(res.positions[allowed].astype(bool), prepend=False) > 0))
    m["episodes"] = entries
    m["episodes_per_year"] = round(entries / (n / 365.0), 2)
    m["last_day"] = str(days[-1].date())
    m["signal_active_last_day"] = bool(sig_full[-1])
    m["funding_ma_ann_last_day"] = round(float(fma[-1]), 5) if np.isfinite(fma[-1]) else None
    return m


def verdicts_from_results(results: dict[str, Any]) -> dict[str, Any]:
    """Reglas de veredicto final (v1.4 s8 C7 + politica), mecanicas."""
    out: dict[str, Any] = {}
    h1 = results["H1"]
    is_signs = {"BTCUSDT": -1.0, "ETHUSDT": -1.0}  # IS: mejora (d_vm<0) en ambos
    # signo OPUESTO al IS <=> producto de signos negativo (CORREGIDO: la primera
    # version marcaba erronneamente el signo coherente como opuesto)
    opp = [h1[a]["d_vm_pp"] * is_signs[a] < 0 for a in ("BTCUSDT", "ETHUSDT")]
    out["H1"] = {
        "per_asset": {
            a: ("NO_PASA" if opp[i] else "INCONTRASTABLE")
            for i, a in enumerate(("BTCUSDT", "ETHUSDT"))
        },
        "family": "NO_PASA" if all(opp) else "INCONTRASTABLE",
        "regla": "IS fue INCONTRASTABLE; C7: signo opuesto en AMBOS activos => NO_PASA",
    }
    out["H2"] = {
        "family": "INCONTRASTABLE",
        "regla": "IS INCONTRASTABLE (CI incluia 0); holdout descriptivo, n=1 ano no concluyente",
    }
    h3 = results["H3"]
    per_asset = {}
    for a in ("BTCUSDT", "ETHUSDT"):
        mean_bp = h3[a]["mean_daily_net_bp"]
        per_asset[a] = "PASA" if mean_bp > 0 else "NO_PASA"
    vals = list(per_asset.values())
    out["H3"] = {
        "per_asset": per_asset,
        "family": (
            "PASA"
            if all(v == "PASA" for v in vals)
            else "NO_PASA"
            if all(v == "NO_PASA" for v in vals)
            else "PASA_PARCIAL"
        ),
        "regla": (
            "IS PASA_IS + C7: signo del carry neto diario en holdout "
            "(no exige significacion, n=1 ano)"
        ),
    }
    return out


def evaluate_all(
    frames: M3bFrames,
    cm: CostModel,
    cm2: CostModel,
    root: Path,
    capital: float = CAPITAL_DEFAULT,
) -> dict[str, Any]:
    """Evalua las 5 celdas congeladas + benchmarks + escalado de capital."""
    sel = json.loads((root / "reports" / "M3a_selected_cells.json").read_text())["selected_cells"]
    out: dict[str, Any] = {
        "mode_official": frames.ho_start == HOLDOUT_START,
        "ho_start": str(frames.ho_start.date()),
        "selected": sel,
        "capital_default": capital,
    }
    out["H1"] = {
        a: eval_h1(frames, a, H1Cell("sma", 50, 0.25), cm, capital) for a in ("BTCUSDT", "ETHUSDT")
    }
    for a in ("BTCUSDT", "ETHUSDT"):
        s2 = eval_h1(frames, a, H1Cell("sma", 50, 0.25), cm2, capital)
        out["H1"][a]["stress_d_vm_pp"] = s2["d_vm_pp"]
        out["H1"][a]["stress_total_return_net"] = s2["total_return_net"]
    out["H2"] = eval_h2(frames, H2Cell(26, 10), cm, capital, root)
    out["H2"]["stress"] = eval_h2(frames, H2Cell(26, 10), cm2, capital, root)
    out["H3"] = {
        a: eval_h3(frames, a, H3Cell(30, 0.05), cm, capital) for a in ("BTCUSDT", "ETHUSDT")
    }
    for a in ("BTCUSDT", "ETHUSDT"):
        s2 = eval_h3(frames, a, H3Cell(30, 0.05), cm2, capital)
        out["H3"][a]["stress_mean_daily_net_bp"] = s2["mean_daily_net_bp"]
        out["H3"][a]["stress_total_return_net"] = s2["total_return_net"]

    # benchmarks del periodo (para la tabla JP)
    bench: dict[str, Any] = {}
    for a in ("BTCUSDT", "ETHUSDT"):
        d = frames.spot_full[frames.spot_full["symbol"] == a].sort_values("open_time")
        dh = d[d["open_time"] >= frames.ho_start]
        c0 = float(dh["close"].iloc[0])
        c1 = float(dh["close"].iloc[-1])
        bench[f"bh_{a}"] = round(c1 / c0 - 1.0, 5)
    out["benchmarks_bh_holdout"] = bench

    # apendice: escalado de capital (misma corrida, mismos datos en memoria)
    scaling: dict[str, Any] = {}
    for cap in CAPITAL_LEVELS:
        row: dict[str, Any] = {}
        for a in ("BTCUSDT", "ETHUSDT"):
            h1m = eval_h1(frames, a, H1Cell("sma", 50, 0.25), cm, cap)
            row[f"H1_{a}"] = {
                "total_return_net": h1m["total_return_net"],
                "max_drawdown": h1m["max_drawdown"],
                "n_trades": h1m["n_trades"],
                "rejected_min_notional": h1m["rejected_min_notional"],
                "rejected_liquidity": h1m["rejected_liquidity"],
            }
            h3m = eval_h3(frames, a, H3Cell(30, 0.05), cm, cap)
            row[f"H3_{a}"] = {
                "total_return_net": h3m["total_return_net"],
                "mean_daily_net_bp": h3m["mean_daily_net_bp"],
                "episodes": h3m["episodes"],
            }
        h2m = eval_h2(frames, H2Cell(26, 10), cm, cap, root)
        row["H2"] = {
            "total_return_net": h2m["total_return_net"],
            "max_drawdown": h2m["max_drawdown"],
            "sharpe_ann": h2m["sharpe_ann"],
        }
        scaling[str(int(cap))] = row
    out["capital_scaling"] = scaling
    out["generated_at_utc"] = datetime.now(UTC).isoformat(timespec="seconds")
    return out


def record_trials(root: Path, ledger: TrialLedger, results: dict[str, Any]) -> int:
    """Registra las 5 evaluaciones como kind='holdout_evaluation' (no suman a n_trials)."""
    sel_sha = (
        __import__("hashlib")
        .sha256((root / "reports" / "M3a_selected_cells.json").read_bytes())
        .hexdigest()[:16]
    )
    n = 0
    plan = [
        ("H1", "sma50_s25", "BTCUSDT", results["H1"]["BTCUSDT"]),
        ("H1", "sma50_s25", "ETHUSDT", results["H1"]["ETHUSDT"]),
        ("H2", "L26_N10", "UNIVERSE", results["H2"]),
        ("H3", "w30_t5", "BTCUSDT", results["H3"]["BTCUSDT"]),
        ("H3", "w30_t5", "ETHUSDT", results["H3"]["ETHUSDT"]),
    ]
    for hyp, cell_id, asset, metrics in plan:
        cfg = {"selection_file_sha256": sel_sha, "cell": cell_id, "mode": "M3b_holdout_unico"}
        with ledger.trial(
            hyp,
            cell_id,
            asset,
            cfg,
            kind="holdout_evaluation",
            notes="apertura unica autorizada por orquestador (gate M3a)",
        ) as ctx:
            keep = {k: v for k, v in metrics.items() if not isinstance(v, (list, dict))}
            ctx.set_metrics(keep)
        n += 1
    return n
