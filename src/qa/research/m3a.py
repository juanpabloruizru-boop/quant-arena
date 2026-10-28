"""Investigacion M3 (una sola pasada): orquestadores por familia.

Modo M3a: SOLO in-sample. El holdout no se carga ni se toca (data_access lo
impide sin unlock+clave; este modulo solo usa load_in_sample).

Parametros de produccion v1.4: n_perm = 10 000 (H1), RC con B = 2 000,
CPCV(10, 2) = 45 trayectorias, PBO-CSCV(16 splits, 1000 combinaciones,
semilla fija), bootstrap por bloques (20 d diario / 8 sem semanal, 10 000),
costes costs.yaml + stress x2. Capital de investigacion: 10 000 USDT
(participacion en tier 1 para BTC/ETH; se documenta en el informe).

Cada celda se registra en el ledger ANTES de devolver metricas (principio 3).
Reanudable: si la celda ya existe en el ledger, se reutilizan sus metricas
(las series se recalculan, que es barato; las permutaciones no).
"""

from __future__ import annotations

import math
import time
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd
from numpy.typing import NDArray

from qa.backtest.costs import CostModel
from qa.backtest.data_access import load_in_sample
from qa.backtest.engine import run_carry, run_positions, simple_returns
from qa.backtest.trials import TrialLedger
from qa.data.pit import load_adjudications
from qa.stats.benchmarks import timing_permutation_pvalue
from qa.stats.bootstrap import newey_west_se, stationary_bootstrap_indices
from qa.stats.cpcv import cpcv_splits
from qa.stats.dsr import deflated_sharpe
from qa.stats.metrics import (
    calmar,
    max_drawdown,
    metrics_summary,
    sharpe_ann,
    sortino_ann,
    trades_from_positions,
    ulcer_index,
)
from qa.stats.spa import cscv_pbo, reality_check_pvalue
from qa.strategies.h1 import BAND_FROZEN, H1_GRID, H1Cell, h1_desired_weights
from qa.strategies.h2 import H2_GRID, H2Cell, build_h2, build_weekly_panel
from qa.strategies.h3 import H3_GRID, H3Cell, h3_signal

CAPITAL = 10_000.0
N_PERM = 10_000
RC_B = 2_000
BOOT_B = 10_000
SEED = 20261027
T_STAR = 0.025
H2_START = pd.Timestamp("2019-04-01", tz="UTC")  # pre-registrado (M1: primer mes con >=20)
SP1_END = pd.Timestamp("2020-01-01", tz="UTC")  # frontera SP1/SP2 (exclusiva)
SP2_END = pd.Timestamp("2023-01-01", tz="UTC")  # frontera SP2/SP3 (exclusiva)
ASSETS_H1H3 = ("BTCUSDT", "ETHUSDT")
F64 = NDArray[np.float64]


def _norm_cdf(x: float) -> float:
    from statistics import NormalDist

    return NormalDist().cdf(x)


def load_all(root: Path) -> dict[str, Any]:
    spot = load_in_sample("spot_daily", root)
    funding = load_in_sample("funding", root)
    futures = load_in_sample("futures_daily", root)
    pit = pd.read_parquet(root / "data" / "curated" / "pit_universe.parquet")
    adj = load_adjudications(root)
    cm = CostModel.from_yaml(root / "config" / "costs.yaml")
    cm2 = CostModel.from_yaml(root / "config" / "costs.yaml", stress=True)
    return {
        "spot": spot,
        "funding": funding,
        "futures": futures,
        "pit": pit,
        "adj": adj,
        "cm": cm,
        "cm2": cm2,
    }


def _trade_wr(net_returns: F64, positions: F64) -> float:
    pnls = [
        float(np.prod(1.0 + net_returns[a:b]) - 1.0) for a, b in trades_from_positions(positions)
    ]
    return float(np.mean([p > 0 for p in pnls])) if pnls else 0.0


# ---------------------------------------------------------------------------
# H1
# ---------------------------------------------------------------------------
def run_h1(root: Path, ledger: TrialLedger, data: dict[str, Any]) -> dict[str, Any]:
    t0 = time.time()
    perm_cost = data["cm"].side_cost_rate(1e-9) or 0.0011
    out: dict[str, Any] = {"perm_cost_per_side": perm_cost, "assets": {}}
    for ai, asset in enumerate(ASSETS_H1H3):
        d = data["spot"][data["spot"]["symbol"] == asset].sort_values("open_time")
        close = np.asarray(d["close"].to_numpy(), dtype=np.float64)
        qv = np.asarray(d["quote_volume"].to_numpy(), dtype=np.float64)
        times_r = pd.DatetimeIndex(d["open_time"].to_numpy()[1:])
        r = simple_returns(close)
        excess_cols: list[F64] = []
        ret_cols: list[F64] = []
        cells: dict[str, Any] = {}
        for ci, cell in enumerate(H1_GRID):
            desired = h1_desired_weights(close, cell)
            res = run_positions(close, desired, qv, data["cm"], CAPITAL, band=BAND_FROZEN)
            strat = res.net_returns
            cached = ledger.find("H1", cell.cell_id, asset)
            if cached is None:
                m = _h1_cell_metrics(
                    cell,
                    res,
                    r,
                    times_r,
                    data["cm2"],
                    close,
                    qv,
                    perm_cost,
                    seed=SEED + 1000 * ci + ai,
                )
                with ledger.trial("H1", cell.cell_id, asset, cell.config) as ctx:
                    ctx.set_metrics(m)
            else:
                m = cached
            f_vm = float(np.std(strat, ddof=1) / np.std(r, ddof=1))
            excess_cols.append(strat - f_vm * r)
            ret_cols.append(strat)
            cells[cell.cell_id] = m
        rc = reality_check_pvalue(
            np.stack(excess_cols, axis=1), mean_block=20, n_boot=RC_B, seed=SEED + ai
        )
        pbo = cscv_pbo(np.stack(ret_cols, axis=1), n_splits=16, n_combos=1000, seed=SEED + ai)
        out["assets"][asset] = {"cells": cells, "rc": rc, "pbo": round(float(pbo), 4)}
    out["elapsed_s"] = round(time.time() - t0, 1)
    return out


def _h1_cell_metrics(
    cell: H1Cell,
    res: Any,
    r: F64,
    times_r: pd.DatetimeIndex,
    cm2: CostModel,
    close: F64,
    qv: F64,
    perm_cost: float,
    seed: int,
) -> dict[str, Any]:
    strat: F64 = res.net_returns
    pos: F64 = res.positions
    m: dict[str, Any] = dict(metrics_summary(strat, pos))
    total = float(np.prod(1.0 + strat) - 1.0)
    m["cagr_net"] = round((1.0 + total) ** (365.0 / len(strat)) - 1.0, 5) if total > -1 else -1.0
    m["exposure_mean"] = round(float(pos.mean()), 4)
    m["time_in_market_pct"] = round(float((pos > 0).mean()) * 100, 2)
    m["trades_per_year"] = round(m.get("n_trades", 0) / (len(strat) / 365.0), 2)
    m["win_rate_trades"] = round(_trade_wr(strat, pos), 4)
    mu_ = float(strat.mean())
    sd_ = float(strat.std(ddof=1))
    m["skew"] = round(float(((strat - mu_) ** 3).mean()) / sd_**3, 4)
    m["kurt"] = round(float(((strat - mu_) ** 4).mean()) / sd_**4, 4)
    m["d_sharpe_vs_bh"] = round(sharpe_ann(strat) - sharpe_ann(r), 4)
    m["d_maxdd_raw_pp"] = round((max_drawdown(strat) - max_drawdown(r)) * 100, 2)
    # permutacion de produccion (10 000, bloques 20 d)
    p_val, d_vm, p_adv = timing_permutation_pvalue(
        pos, r, perm_cost, n_perm=N_PERM, block=20, seed=seed, chunk=1000
    )
    m["perm_p"] = round(p_val, 5)
    m["perm_p_adverso"] = round(p_adv, 5)
    m["d_vm_pp"] = round(d_vm * 100, 2)
    # subperiodos (mismo estadistico, f dentro del subperiodo)
    masks = {
        "SP1": times_r < SP1_END,
        "SP2": (times_r >= SP1_END) & (times_r < SP2_END),
        "SP3": times_r >= SP2_END,
    }
    subs: dict[str, float] = {}
    for k, mask in masks.items():
        sd_b = float(np.std(r[mask], ddof=1))
        sd_s = float(np.std(strat[mask], ddof=1))
        f_sp = sd_s / sd_b if sd_b > 1e-15 else 1.0
        subs[k] = round((max_drawdown(strat[mask]) - max_drawdown(f_sp * r[mask])) * 100, 2)
    m["subperiod_d_vm_pp"] = subs
    m["subperiod_improve_count"] = int(sum(1 for v in subs.values() if v < 0))
    # CPCV(10,2) con purga/embargo: mediana del criterio primario
    splits = cpcv_splits(len(r), n_splits=10, n_test=2, formation=cell.window, embargo=20)
    d_paths: list[float] = []
    for _tr_idx, te_idx in splits:
        sd_b = float(np.std(r[te_idx], ddof=1))
        sd_s = float(np.std(strat[te_idx], ddof=1))
        f_p = sd_s / sd_b if sd_b > 1e-15 else 1.0
        d_paths.append(max_drawdown(strat[te_idx]) - max_drawdown(f_p * r[te_idx]))
    m["cpcv_median_dvm_pp"] = round(float(np.median(d_paths)) * 100, 2)
    m["cpcv_frac_improve"] = round(float(np.mean([d < 0 for d in d_paths])), 4)
    # stress x2
    desired = h1_desired_weights(close, cell)
    res2 = run_positions(close, desired, qv, cm2, CAPITAL, band=BAND_FROZEN)
    strat2: F64 = res2.net_returns
    f2 = float(np.std(strat2, ddof=1) / np.std(r, ddof=1))
    m["stress_d_sharpe_vs_bh"] = round(sharpe_ann(strat2) - sharpe_ann(r), 4)
    m["stress_d_vm_pp"] = round((max_drawdown(strat2) - max_drawdown(f2 * r)) * 100, 2)
    m["stress_sharpe_ann"] = round(sharpe_ann(strat2), 4)
    # estado "hoy" (ultimo dia in-sample)
    m["last_day"] = str(times_r[-1].date())
    m["current_position"] = round(float(pos[-1]), 4)
    m["current_target_weight"] = round(float(desired[-1]), 4)
    return m


# ---------------------------------------------------------------------------
# H2
# ---------------------------------------------------------------------------
def _weekly_metrics(x: NDArray[np.floating[Any]]) -> dict[str, float]:
    xa = np.asarray(x, dtype=np.float64)
    return {
        "sharpe_ann": round(sharpe_ann(xa, periods=52.0), 4),
        "sortino_ann": round(sortino_ann(xa, periods=52.0), 4),
        "max_drawdown": round(max_drawdown(xa), 4),
        "calmar": round(calmar(xa, periods=52.0), 4),
        "ulcer_index": round(ulcer_index(xa), 6),
        "total_return": round(float(np.prod(1.0 + xa) - 1.0), 5),
        "n_obs": int(xa.size),
    }


def run_h2(root: Path, ledger: TrialLedger, data: dict[str, Any]) -> dict[str, Any]:
    t0 = time.time()
    panel = build_weekly_panel(data["spot"])
    cells: dict[str, Any] = {}
    series: dict[str, tuple[pd.Series, pd.Series]] = {}
    for cell in H2_GRID:
        res = build_h2(panel, data["pit"], data["adj"], cell, data["cm"], CAPITAL)
        res2 = build_h2(panel, data["pit"], data["adj"], cell, data["cm2"], CAPITAL)
        strat = res.strat_ret.to_numpy(dtype=np.float64)
        bench = res.bench_ret.to_numpy(dtype=np.float64)
        strat = res.strat_ret.loc[res.strat_ret.index >= H2_START].to_numpy(dtype=np.float64)
        bench = res.bench_ret.loc[res.bench_ret.index >= H2_START].to_numpy(dtype=np.float64)
        strat2 = res2.strat_ret.loc[res2.strat_ret.index >= H2_START].to_numpy(dtype=np.float64)
        series[cell.cell_id] = (
            res.strat_ret.loc[res.strat_ret.index >= H2_START],
            res.bench_ret.loc[res.bench_ret.index >= H2_START],
        )
        cached = ledger.find("H2", cell.cell_id, "UNIVERSE")
        if cached is None:
            m = _h2_cell_metrics(cell, strat, bench, strat2, res)
            with ledger.trial("H2", cell.cell_id, "UNIVERSE", cell.config) as ctx:
                ctx.set_metrics(m)
        else:
            m = cached
        cells[cell.cell_id] = m
    # estadisticos familiares sobre semanas comunes
    common_idx: pd.Index | None = None
    for pair in series.values():
        idx_ = pair[0].index
        common_idx = idx_ if common_idx is None else common_idx.intersection(idx_)
    assert common_idx is not None
    common = common_idx
    mat_excess = np.stack(
        [
            (series[c][0].loc[common] - series[c][1].loc[common]).to_numpy(dtype=np.float64)
            for c in series
        ],
        axis=1,
    )
    mat_ret = np.stack(
        [series[c][0].loc[common].to_numpy(dtype=np.float64) for c in series], axis=1
    )
    rc = reality_check_pvalue(mat_excess, mean_block=8, n_boot=RC_B, seed=SEED + 2)
    pbo = cscv_pbo(mat_ret, n_splits=16, n_combos=1000, seed=SEED + 2)
    out = {
        "cells": cells,
        "rc": rc,
        "pbo": round(float(pbo), 4),
        "common_weeks": int(len(common)),
        "elapsed_s": round(time.time() - t0, 1),
    }
    return out


def _h2_cell_metrics(cell: H2Cell, strat: F64, bench: F64, strat2: F64, res: Any) -> dict[str, Any]:
    m: dict[str, Any] = _weekly_metrics(strat)
    m["bench_sharpe_ann"] = round(sharpe_ann(bench, periods=52.0), 4)
    mu_ = float(strat.mean())
    sd_ = float(strat.std(ddof=1))
    m["skew"] = round(float(((strat - mu_) ** 3).mean()) / sd_**3, 4)
    m["kurt"] = round(float(((strat - mu_) ** 4).mean()) / sd_**4, 4)
    m["d_sharpe_vs_ew"] = round(m["sharpe_ann"] - m["bench_sharpe_ann"], 4)
    m["exposure_mean"] = 1.0
    m["time_in_market_pct"] = 100.0
    m["trades_per_year"] = round(res.turnover_per_year / 2.0, 1)
    m["win_rate_weeks"] = round(float((strat > 0).mean()), 4)
    m["mean_eligible"] = round(res.mean_eligible, 1)
    m["first_week"] = res.first_week
    m["last_week"] = res.last_week
    m["last_basket"] = res.last_basket
    # IC bootstrap del DeltaSharpe semanal (bloques de 8 semanas)
    n = strat.size
    idx = stationary_bootstrap_indices(n, 8, BOOT_B, SEED + 3)
    ds = np.empty(BOOT_B)
    for b in range(BOOT_B):
        j = idx[b]
        ds[b] = sharpe_ann(strat[j], periods=52.0) - sharpe_ann(bench[j], periods=52.0)
    lo, hi = np.quantile(ds, [0.025, 0.975])
    m["d_sharpe_ci95"] = [round(float(lo), 4), round(float(hi), 4)]
    # MDE semanal (AR1)
    d_ser = strat - bench
    rho = float(np.corrcoef(d_ser[:-1], d_ser[1:])[0, 1]) if n > 2 else 0.0
    rho = min(max(rho, -0.9), 0.9)
    sigma = float(d_ser.std(ddof=1))
    k_power = 2.4866
    mde_w = k_power * sigma * math.sqrt(((1 + rho) / (1 - rho)) / n)
    m["mde_weekly"] = round(mde_w, 5)
    m["mde_annualized"] = round(mde_w * 52.0, 4)
    m["d_mean_weekly"] = round(float(d_ser.mean()), 5)
    # CPCV(10,2)
    splits = cpcv_splits(n, n_splits=10, n_test=2, formation=cell.L_weeks + 2, embargo=2)
    d_paths = [
        sharpe_ann(strat[te], periods=52.0) - sharpe_ann(bench[te], periods=52.0)
        for _tr, te in splits
    ]
    m["cpcv_median_d_sharpe"] = round(float(np.median(d_paths)), 4)
    m["cpcv_frac_positive"] = round(float(np.mean([x > 0 for x in d_paths])), 4)
    # stress x2
    m["stress_sharpe_ann"] = round(sharpe_ann(strat2, periods=52.0), 4)
    cagr = (1.0 + float(np.prod(1.0 + strat) - 1.0)) ** (52.0 / n) - 1.0
    m["cagr_net"] = round(float(cagr), 5)
    return m


# ---------------------------------------------------------------------------
# H3
# ---------------------------------------------------------------------------
def _h3_asset_frames(
    data: dict[str, Any], asset: str
) -> tuple[pd.DatetimeIndex, Any, Any, Any, Any]:
    spot = data["spot"][data["spot"]["symbol"] == asset].sort_values("open_time")
    perp = data["futures"][data["futures"]["symbol"] == asset].sort_values("open_time")
    fund = data["funding"][data["funding"]["symbol"] == asset].sort_values("funding_time")
    first_f = fund["funding_time"].min().floor("D")
    sp = spot.set_index(spot["open_time"].dt.floor("D"))
    pp = perp.set_index(perp["open_time"].dt.floor("D"))
    idx = sp.index.intersection(pp.index)
    idx = idx[idx >= first_f]
    return (
        idx,
        fund,
        sp.loc[idx, "close"].to_numpy(dtype=np.float64),
        pp.loc[idx, "close"].to_numpy(dtype=np.float64),
        sp.loc[idx, "quote_volume"].to_numpy(dtype=np.float64),
    )


def run_h3(root: Path, ledger: TrialLedger, data: dict[str, Any]) -> dict[str, Any]:
    t0 = time.time()
    out: dict[str, Any] = {"assets": {}}
    nets: dict[str, pd.Series] = {}
    for asset in ASSETS_H1H3:
        days, fund, spot_close, perp_close, qv = _h3_asset_frames(data, asset)
        cells: dict[str, Any] = {}
        for cell in H3_GRID:
            cached = ledger.find("H3", cell.cell_id, asset)
            sig, fma = h3_signal(days, fund, cell)
            res = run_carry(days, fund, sig, qv, data["cm"], CAPITAL, spot_close, perp_close)
            net = res.net_returns
            nets[f"{asset}:{cell.cell_id}"] = pd.Series(net, index=days)
            if cached is None:
                m = _h3_cell_metrics(
                    cell, res, sig, fma, days, data["cm2"], fund, qv, spot_close, perp_close
                )
                with ledger.trial("H3", cell.cell_id, asset, cell.config) as ctx:
                    ctx.set_metrics(m)
            else:
                m = cached
            cells[cell.cell_id] = m
        out["assets"][asset] = {
            "cells": cells,
            "n_days": int(len(days)),
            "first_day": str(days[0].date()),
            "last_day": str(days[-1].date()),
        }
    # familiares: RC y PBO sobre timeline comun (8 celdas)
    common = None
    for s_ in nets.values():
        common = s_.index if common is None else common.intersection(s_.index)
    assert common is not None
    mat = np.stack([nets[k].loc[common].to_numpy(dtype=np.float64) for k in nets], axis=1)
    rc = reality_check_pvalue(mat, mean_block=20, n_boot=RC_B, seed=SEED + 4)
    pbo = cscv_pbo(mat, n_splits=16, n_combos=1000, seed=SEED + 4)
    out["rc"] = rc
    out["pbo"] = round(float(pbo), 4)
    out["common_days"] = int(len(common))
    out["elapsed_s"] = round(time.time() - t0, 1)
    return out


def _h3_cell_metrics(
    cell: H3Cell,
    res: Any,
    sig: NDArray[np.bool_],
    fma: F64,
    days: pd.DatetimeIndex,
    cm2: CostModel,
    fund: pd.DataFrame,
    qv: F64,
    spot_close: F64,
    perp_close: F64,
) -> dict[str, Any]:
    net: F64 = res.net_returns
    m: dict[str, Any] = dict(metrics_summary(net, res.positions))
    n = net.size
    total = float(np.prod(1.0 + net) - 1.0)
    m["cagr_net"] = round((1.0 + total) ** (365.0 / n) - 1.0, 5) if total > -1 else -1.0
    se = newey_west_se(net, lag=cell.window_days)
    mean_d = float(net.mean())
    t_stat = mean_d / se if se > 0 else 0.0
    mu_ = float(net.mean())
    sd_ = float(net.std(ddof=1))
    if sd_ > 1e-15:
        m["skew"] = round(float(((net - mu_) ** 3).mean()) / sd_**3, 4)
        m["kurt"] = round(float(((net - mu_) ** 4).mean()) / sd_**4, 4)
    m["hac_t"] = round(float(t_stat), 4)
    m["hac_p_one_sided"] = (
        round(1.0 - _norm_cdf(t_stat), 5) if mean_d > 0 else round(_norm_cdf(t_stat), 5)
    )
    m["mean_daily_net_bp"] = round(mean_d * 10_000, 4)
    m["funding_collected"] = res.funding_collected
    m["active_days"] = m.get("n_trades") or int(sig.sum())
    m["time_in_market_pct"] = round(float(res.positions.mean()) * 100, 2)
    m["episodes_per_year"] = round(
        float((res.positions > 0).astype(int).sum()) / n * 365.0 / max(1.0, n / 365.0), 2
    )
    # CPCV(10,2)
    splits = cpcv_splits(n, n_splits=10, n_test=2, formation=cell.window_days, embargo=7)
    sh_paths = [sharpe_ann(net[te]) for _tr, te in splits]
    m["cpcv_median_sharpe"] = round(float(np.median(sh_paths)), 4)
    m["cpcv_frac_positive"] = round(float(np.mean([x > 0 for x in sh_paths])), 4)
    # MDE (P4): sigma realizada diaria de la celda
    rho = float(np.corrcoef(net[:-1], net[1:])[0, 1]) if n > 2 else 0.0
    rho = min(max(rho, -0.9), 0.9)
    sigma = float(net.std(ddof=1))
    mde_d = 2.4866 * sigma * math.sqrt(((1 + rho) / (1 - rho)) / n)
    m["mde_daily"] = round(mde_d, 7)
    m["mde_annualized"] = round(mde_d * 365.0, 4)
    # stress x2
    res2 = run_carry(days, fund, sig, qv, cm2, CAPITAL, spot_close, perp_close)
    m["stress_mean_daily_net_bp"] = round(float(res2.net_returns.mean()) * 10_000, 4)
    # estado "hoy"
    m["last_day"] = str(days[-1].date())
    m["current_signal_active"] = bool(sig[-1])
    m["current_funding_ma_ann"] = round(float(fma[-1]), 5) if np.isfinite(fma[-1]) else None
    return m


# ---------------------------------------------------------------------------
# Seleccion (mediana CPCV, una celda por familia y activo) y veredictos IS
# ---------------------------------------------------------------------------
def _dsr_for(m: dict[str, Any], sd_trials_ann: float, n_trials: int, periods: float) -> float:
    sr_obs = float(m["sharpe_ann"]) / math.sqrt(periods)
    return deflated_sharpe(
        sr_per_obs=sr_obs,
        n_obs=int(m["n_obs"]),
        n_trials=n_trials,
        sd_trials_per_obs=sd_trials_ann / math.sqrt(periods),
        skew=float(m.get("skew", 0.0)),
        kurtosis=float(m.get("kurt", 3.0)),
    )


def select_and_verdict(ledger: TrialLedger, results: dict[str, Any]) -> dict[str, Any]:
    out: dict[str, Any] = {}

    # ---- H1 (por activo; familia PASA si ambos activos pasan) ----
    sh1 = ledger.family_sharpes("H1")
    sd1 = float(np.std(sh1, ddof=1)) if len(sh1) > 1 else 0.5
    h1: dict[str, Any] = {"n_trials_ledger": len(sh1), "sd_trials_ann": round(sd1, 4), "assets": {}}
    for asset, blk in results["H1"]["assets"].items():
        cells = blk["cells"]
        best = min(cells, key=lambda c: cells[c]["cpcv_median_dvm_pp"])
        m = cells[best]
        checks = {
            "C1a_perm_p<=t*_y_mejora": bool(m["perm_p"] <= T_STAR and m["d_vm_pp"] < 0),
            "C1b_subperiodos>=2de3": bool(m["subperiod_improve_count"] >= 2),
            "C2_rc_familiar_p<0.05": bool(blk["rc"]["p_value"] < 0.05),
            "C3_pbo<0.20": bool(blk["pbo"] < 0.20),
            "C4_stress_mantiene": bool(
                m["stress_d_vm_pp"] < 0 and m["stress_d_sharpe_vs_bh"] >= -0.10
            ),
            "C5_folds>=60%": bool(m["cpcv_frac_improve"] >= 0.60),
        }
        all_pass = all(checks.values())
        adverse = bool(m.get("perm_p_adverso", 1.0) <= T_STAR)
        verdict = "PASA_IS" if all_pass else ("NO_PASA_IS" if adverse else "INCONTRASTABLE")
        dsr_val = _dsr_for(m, sd1, max(len(sh1), 24), 365.0)
        h1["assets"][asset] = {
            "selected_cell": best,
            "checks": checks,
            "verdict": verdict,
            "dsr_informativo": round(dsr_val, 4),
            "metrics": {
                k: m[k]
                for k in (
                    "sharpe_ann",
                    "max_drawdown",
                    "calmar",
                    "ulcer_index",
                    "cagr_net",
                    "d_sharpe_vs_bh",
                    "d_vm_pp",
                    "perm_p",
                    "perm_p_adverso",
                    "subperiod_d_vm_pp",
                    "subperiod_improve_count",
                    "cpcv_median_dvm_pp",
                    "cpcv_frac_improve",
                    "stress_d_vm_pp",
                    "stress_d_sharpe_vs_bh",
                    "exposure_mean",
                    "time_in_market_pct",
                    "trades_per_year",
                    "win_rate_trades",
                    "n_trades",
                    "cost_total",
                    "turnover_total",
                    "current_position",
                    "current_target_weight",
                    "last_day",
                    "n_obs",
                )
                if k in m
            },
        }
    verts = [a["verdict"] for a in h1["assets"].values()]
    h1["family_verdict"] = (
        "PASA_IS"
        if all(v == "PASA_IS" for v in verts)
        else "NO_PASA_IS"
        if any(v == "NO_PASA_IS" for v in verts)
        else "INCONTRASTABLE"
    )
    out["H1"] = h1

    # ---- H2 ----
    sh2 = ledger.family_sharpes("H2")
    sd2 = float(np.std(sh2, ddof=1)) if len(sh2) > 1 else 0.5
    cells2 = results["H2"]["cells"]
    best2 = max(cells2, key=lambda c: cells2[c]["cpcv_median_d_sharpe"])
    m2 = cells2[best2]
    ci_lo, ci_hi = m2["d_sharpe_ci95"]
    checks2 = {
        "C1_dsharpe_CI_excluye_0": bool(ci_lo > 0),
        "C2_dsr>0.95": bool(_dsr_for(m2, sd2, max(len(sh2), 6), 52.0) > 0.95),
        "C3_pbo<0.20": bool(results["H2"]["pbo"] < 0.20),
        "C4_stress_sharpe>0": bool(m2["stress_sharpe_ann"] > 0),
        "C5_folds>=60%": bool(m2["cpcv_frac_positive"] >= 0.60),
        "C6_rc_p<0.05": bool(results["H2"]["rc"]["p_value"] < 0.05),
    }
    verdict2 = (
        "PASA_IS" if all(checks2.values()) else "NO_PASA_IS" if ci_hi < 0 else "INCONTRASTABLE"
    )
    out["H2"] = {
        "n_trials_ledger": len(sh2),
        "sd_trials_ann": round(sd2, 4),
        "selected_cell": best2,
        "checks": checks2,
        "verdict": verdict2,
        "dsr": round(_dsr_for(m2, sd2, max(len(sh2), 6), 52.0), 4),
        "mde_annualized": m2["mde_annualized"],
        "metrics": {
            k: m2[k]
            for k in (
                "sharpe_ann",
                "bench_sharpe_ann",
                "d_sharpe_vs_ew",
                "d_sharpe_ci95",
                "max_drawdown",
                "calmar",
                "ulcer_index",
                "cagr_net",
                "first_week",
                "last_week",
                "weeks_used" if "weeks_used" in m2 else "n_obs",
                "win_rate_weeks",
                "trades_per_year",
                "mean_eligible",
                "mde_weekly",
                "mde_annualized",
                "d_mean_weekly",
                "cpcv_median_d_sharpe",
                "cpcv_frac_positive",
                "stress_sharpe_ann",
                "last_basket",
                "n_obs",
            )
            if k in m2
        },
    }

    # ---- H3 (por activo; familia PASA si algun activo pasa, nota FWER programa) ----
    sh3 = ledger.family_sharpes("H3")
    sd3 = float(np.std(sh3, ddof=1)) if len(sh3) > 1 else 0.5
    h3: dict[str, Any] = {"n_trials_ledger": len(sh3), "sd_trials_ann": round(sd3, 4), "assets": {}}
    for asset, blk in results["H3"]["assets"].items():
        cells = blk["cells"]
        best = max(cells, key=lambda c: cells[c]["cpcv_median_sharpe"])
        m = cells[best]
        dsr_val = _dsr_for(m, sd3, max(len(sh3), 8), 365.0)
        checks = {
            "C1_media>0_HAC_p<0.05": bool(
                m["mean_daily_net_bp"] > 0 and m["hac_p_one_sided"] < 0.05
            ),
            "C2_dsr>0.95": bool(dsr_val > 0.95),
            "C3_pbo<0.20": bool(results["H3"]["pbo"] < 0.20),
            "C4_stress_media>0": bool(m["stress_mean_daily_net_bp"] > 0),
            "C5_folds>=60%": bool(m["cpcv_frac_positive"] >= 0.60),
            "C6_rc_p<0.05": bool(results["H3"]["rc"]["p_value"] < 0.05),
        }
        all_pass = all(checks.values())
        adverse = bool(m["mean_daily_net_bp"] < 0 and m["hac_p_one_sided"] < 0.05)
        verdict = "PASA_IS" if all_pass else ("NO_PASA_IS" if adverse else "INCONTRASTABLE")
        h3["assets"][asset] = {
            "selected_cell": best,
            "checks": checks,
            "verdict": verdict,
            "dsr": round(dsr_val, 4),
            "mde_annualized": m["mde_annualized"],
            "metrics": {
                k: m[k]
                for k in (
                    "sharpe_ann",
                    "max_drawdown",
                    "calmar",
                    "cagr_net",
                    "mean_daily_net_bp",
                    "hac_t",
                    "hac_p_one_sided",
                    "funding_collected",
                    "time_in_market_pct",
                    "episodes_per_year",
                    "mde_daily",
                    "mde_annualized",
                    "cpcv_median_sharpe",
                    "cpcv_frac_positive",
                    "stress_mean_daily_net_bp",
                    "current_signal_active",
                    "current_funding_ma_ann",
                    "last_day",
                    "n_obs",
                    "skew",
                    "kurt",
                )
                if k in m
            },
        }
    verts3 = [a["verdict"] for a in h3["assets"].values()]
    h3["family_verdict"] = (
        "PASA_IS"
        if any(v == "PASA_IS" for v in verts3)
        else "NO_PASA_IS"
        if any(v == "NO_PASA_IS" for v in verts3)
        else "INCONTRASTABLE"
    )
    mdes = [a["mde_annualized"] for a in h3["assets"].values()]
    if len(mdes) == 2 and min(mdes) > 0:
        h3["mde_ratio_max_min"] = round(max(mdes) / min(mdes), 3)
    out["H3"] = h3
    out["program_fwer_note"] = (
        "FWER de programa <= ~3x el FWER familiar (union bound, 3 familias "
        "independientes); FWER familiar medido bajo nulo: H1 0.5% (M2b)."
    )
    return out
