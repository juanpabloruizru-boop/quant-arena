"""Analisis de potencia v1.2 para el pre-registro de QUANT-ARENA v2 (M0c/M1).

Responde, por hipotesis: cuantos anios de datos o cuantas senales/observaciones
hacen falta para detectar el efecto objetivo con potencia 80% (alpha 5%
una cola). Si el efecto tipico NO es detectable en el horizonte disponible, se
declara "INCONTRASTABLE en el horizonte".

CAMBIOS v1.2 (correccion del defecto 1 del gate M0b):
- El benchmark primario de H1 pasa a ser el **vol-matched B&H**
  (f = sigma_estrategia / sigma_BH por periodo). El exposure-matched (fraccion
  constante e_bar) queda como DIAGNOSTICO: por Jensen (E[w^2] >= e_bar^2) esta
  sesgado en contra de cualquier regla de exposicion variable bajo el nulo; las
  tablas v1.1 que lo usaban como criterio quedan retiradas.
- Criterio de H1 basado en la **distribucion permutada** del propio vector de
  exposicion (bloques circulares de 20 d): p-valor y regla de subperiodos con
  el mismo estadistico Delta maxDD vol-matched.
- Tests de identidad/calibracion (ver tests/unit/test_benchmark_identities.py y
  tests/synthetic/test_null_calibration.py): exposicion constante => Delta = 0;
  bajo nulo E[Delta vol-matched] ~ 0 y p uniformes; signo: Delta > 0 = peor.
- **Mundo con habilidad plantada**: drift latente AR(1) persistente calibrado
  para que el DeltaSharpe verdadero de la regla de tendencia (neto, vs B&H
  crudo) valga {0.1, 0.3, 0.5}. Se reporta potencia REAL por tamanno de efecto.
- Tabla de sensibilidad de la banda de rebalanceo {0, 2, 5, 10, 20} pp
  (soporte del grado de libertad congelado en PRERREGISTRO s4).

Metodos analiticos (sin cambios): SE del Sharpe (Lo 2002), DSR (Bailey &
Lopez de Prado 2014), MDE de media con AR(1) (Newey-West aprox.), n para
discriminar tasas de acierto.

Salidas (trackeadas en git):
  reports/M0_power_analysis.md
  reports/M0_power_analysis.json

Uso:  python scripts/power_analysis.py   (determinista; ~2-5 min)
"""

from __future__ import annotations

import json
import math
from dataclasses import asdict, dataclass
from datetime import UTC, datetime
from pathlib import Path
from statistics import NormalDist
from typing import Any

import numpy as np
from numpy.typing import NDArray

from qa.stats.benchmarks import (
    circular_block_permutations,
    permutation_delta_stats,
    permutation_pvalue,
    random_rotations,
)

SEED = 20261026
CAL_SEED = SEED + 500_000
PERM_SEED = SEED + 900_000
NORM = NormalDist()
Z_ALPHA = NORM.inv_cdf(0.95)  # 1.6449 (una cola, 5%)
Z_BETA = NORM.inv_cdf(0.80)  # 0.8416 (potencia 80%)
K_POWER = Z_ALPHA + Z_BETA  # 2.4866
DAYS_PER_YEAR = 365.0
WEEKS_PER_YEAR = 52.0
GAMMA_EM = 0.5772156649015329

REPO = Path(__file__).resolve().parents[1]
OUT_MD = REPO / "reports" / "M0_power_analysis.md"
OUT_JSON = REPO / "reports" / "M0_power_analysis.json"

H1_YEARS = (datetime(2025, 10, 25) - datetime(2017, 8, 17)).days / DAYS_PER_YEAR
H2_YEARS = (datetime(2025, 10, 25) - datetime(2019, 1, 1)).days / DAYS_PER_YEAR
H3_YEARS = (datetime(2025, 10, 25) - datetime(2019, 9, 10)).days / DAYS_PER_YEAR

SUB_B1 = (datetime(2020, 1, 1) - datetime(2017, 8, 17)).days  # fin SP1
SUB_B2 = (datetime(2023, 1, 1) - datetime(2017, 8, 17)).days  # fin SP2
COST_PER_SIDE = 0.0013  # taker 0.10% (verificado) + slippage 3 pb (asuncion)
BAND_FROZEN = 0.10
PERM_BLOCK = 20
PERM_THRESH = 0.025  # t* calibrado en el nulo sintetico (5000 sims, FPR 4.36%<=5%)
AR1_PHI = 0.995  # media-vida ~139 dias: regimenes persistentes de drift


F64 = NDArray[np.float64]


# ---------------------------------------------------------------------------
# Analiticos (sin cambios desde v1.0)
# ---------------------------------------------------------------------------
def se_sharpe_ann(years: float, sr_ann: float = 0.0) -> float:
    t_obs = years * DAYS_PER_YEAR
    sr_d = sr_ann / math.sqrt(DAYS_PER_YEAR)
    se_d = math.sqrt((1.0 + 0.5 * sr_d**2) / t_obs)
    return se_d * math.sqrt(DAYS_PER_YEAR)


def mde_sharpe_diff_unpaired(years: float, sr_ann: float = 0.0) -> float:
    return K_POWER * math.sqrt(2.0) * se_sharpe_ann(years, sr_ann)


def years_for_sharpe_mde(delta: float, sr_ann: float = 0.0) -> float:
    lo, hi = 0.01, 10_000.0
    for _ in range(200):
        mid = 0.5 * (lo + hi)
        if mde_sharpe_diff_unpaired(mid, sr_ann) > delta:
            lo = mid
        else:
            hi = mid
    return 0.5 * (lo + hi)


def expected_max_sr_under_null(n_trials: int, sd_trials_ann: float) -> float:
    n = max(2, int(n_trials))
    e_max_std = (1.0 - GAMMA_EM) * NORM.inv_cdf(1.0 - 1.0 / n) + GAMMA_EM * NORM.inv_cdf(
        1.0 - 1.0 / (n * math.e)
    )
    return sd_trials_ann * e_max_std


def dsr(
    sr_ann: float, years: float, n_trials: int, sd_trials_ann: float, skew: float, kurt: float
) -> float:
    t_obs = max(3.0, years * DAYS_PER_YEAR)
    sr_obs = sr_ann / math.sqrt(DAYS_PER_YEAR)
    sr0_obs = expected_max_sr_under_null(n_trials, sd_trials_ann) / math.sqrt(DAYS_PER_YEAR)
    denom = math.sqrt(max(1e-12, 1.0 - skew * sr_obs + ((kurt - 1.0) / 4.0) * sr_obs**2))
    return NORM.cdf((sr_obs - sr0_obs) * math.sqrt(t_obs - 1.0) / denom)


def sr_required_for_dsr(
    years: float,
    n_trials: int,
    sd_trials_ann: float,
    skew: float,
    kurt: float,
    target: float = 0.95,
) -> float:
    lo, hi = 0.0, 10.0
    if dsr(hi, years, n_trials, sd_trials_ann, skew, kurt) < target:
        return float("inf")
    for _ in range(100):
        mid = 0.5 * (lo + hi)
        if dsr(mid, years, n_trials, sd_trials_ann, skew, kurt) < target:
            lo = mid
        else:
            hi = mid
    return 0.5 * (lo + hi)


def mde_mean(n_obs: float, sigma: float, rho: float = 0.0) -> float:
    lr_factor = (1.0 + rho) / (1.0 - rho)
    return K_POWER * sigma * math.sqrt(lr_factor / n_obs)


def n_obs_for_mean(target_mu: float, sigma: float, rho: float = 0.0) -> float:
    lr_factor = (1.0 + rho) / (1.0 - rho)
    return lr_factor * (K_POWER * sigma / target_mu) ** 2


def n_for_winrate(p0: float, p1: float) -> float:
    num = Z_ALPHA * math.sqrt(p0 * (1.0 - p0)) + Z_BETA * math.sqrt(p1 * (1.0 - p1))
    return (num / (p1 - p0)) ** 2


# ---------------------------------------------------------------------------
# Mecanica de la estrategia H1 (vectorizada en simulaciones)
# ---------------------------------------------------------------------------
def _f64(a: Any) -> F64:
    return np.asarray(a, dtype=np.float64)


def _rolling_mean(x: F64, w: int) -> F64:
    c = np.cumsum(x, axis=1)
    out = np.full(x.shape, np.nan, dtype=np.float64)
    pad = np.concatenate([np.zeros((x.shape[0], 1)), c[:, :-w]], axis=1)
    out[:, w - 1 :] = (c[:, w - 1 :] - pad) / w
    return out


def _maxdd_rows(returns: F64) -> F64:
    wealth = np.cumprod(1.0 + returns, axis=1)
    peak = np.maximum.accumulate(wealth, axis=1)
    return _f64(np.max(1.0 - wealth / peak, axis=1))


def _sharpe_rows(r: F64) -> F64:
    mu = np.mean(r, axis=1)
    sd = np.std(r, axis=1, ddof=1)
    sd = np.where(sd < 1e-12, np.nan, sd)
    return _f64(mu / sd * math.sqrt(DAYS_PER_YEAR))


def _markov_states(rng: np.random.Generator, n_sims: int, t_len: int, p_stay: float) -> Any:
    u = rng.random((n_sims, t_len))
    state = np.zeros((n_sims, t_len), dtype=bool)
    state[:, 0] = rng.random(n_sims) < 0.5
    for t in range(1, t_len):
        stay = u[:, t] < p_stay
        state[:, t] = np.where(stay, state[:, t - 1], ~state[:, t - 1])
    return state


def _ar1_drift_returns(
    rng: np.random.Generator, n_sims: int, n_steps: int, s_mu: float, sig_d: float
) -> F64:
    """Drift latente AR(1) persistente + ruido. Habilidad plantada calibrable."""
    burn = 400
    total = n_steps + burn
    mu = np.zeros((n_sims, total))
    eps = rng.normal(0.0, s_mu, size=(n_sims, total))
    for t in range(1, total):
        mu[:, t] = AR1_PHI * mu[:, t - 1] + eps[:, t]
    return _f64(mu[:, burn:] + rng.normal(0.0, sig_d, size=(n_sims, n_steps)))


def _gen_returns(
    dgp: str,
    rng: np.random.Generator,
    n_sims: int,
    n_steps: int,
    mu_ann: float,
    sigma_ann: float,
    s_mu: float,
) -> F64:
    mu_d = math.log1p(mu_ann) / DAYS_PER_YEAR
    sig_d = sigma_ann / math.sqrt(DAYS_PER_YEAR)
    if dgp == "gbm":
        return _f64(rng.normal(mu_d, sig_d, size=(n_sims, n_steps)))
    if dgp == "ar1_drift":
        return _ar1_drift_returns(rng, n_sims, n_steps, s_mu, sig_d)
    if dgp == "ms_vol_jump":
        p_stay = 0.99
        sig_low = 0.35 / math.sqrt(DAYS_PER_YEAR)
        sig_high = 1.00 / math.sqrt(DAYS_PER_YEAR)
        state = _markov_states(rng, n_sims, n_steps, p_stay)
        sig_path = np.where(state, sig_high, sig_low)
        r = rng.normal(mu_d, sig_path)
        lam_day = np.where(state, 2.0 / DAYS_PER_YEAR, 0.2 / DAYS_PER_YEAR)
        n_jumps = rng.poisson(lam_day)
        r = r + n_jumps * rng.normal(-0.15, 0.08, size=(n_sims, n_steps))
        return _f64(r)
    raise ValueError(f"dgp desconocido: {dgp}")


def _positions(r: F64, window: int, sigma_obj: float, band: float) -> F64:
    """pos[:, t] = posicion vigente durante r[:, t] (decision en cierre t-1)."""
    n_sims, n_steps = r.shape
    close = _f64(np.exp(np.cumsum(np.log1p(r), axis=1)))
    pad_close = np.concatenate([np.ones((n_sims, 1)), close[:, :-1]], axis=1)
    sma = _rolling_mean(pad_close, window)
    long_sig = _f64(np.nan_to_num(pad_close > sma))

    m1 = _rolling_mean(r, 20)
    m2 = _rolling_mean(r * r, 20)
    vol20 = np.sqrt(np.maximum(m2 - m1 * m1, 0.0)) * math.sqrt(DAYS_PER_YEAR)
    with np.errstate(divide="ignore", invalid="ignore"):
        scale = np.minimum(1.0, sigma_obj / vol20)
    scale = _f64(np.nan_to_num(scale, nan=0.0))
    target = long_sig * scale  # objetivo decidido al cierre de t

    pos = np.zeros_like(target)
    last = np.zeros(n_sims)
    for t in range(n_steps):
        tgt = target[:, t - 1] if t >= 1 else np.zeros(n_sims)
        flip = (tgt > 0.0) != (last > 0.0)
        trade = flip | (np.abs(tgt - last) >= band) if band > 0 else np.ones(n_sims, dtype=bool)
        last = np.where(trade, tgt, last)
        pos[:, t] = last
    return pos


@dataclass
class H1Agg:
    dgp: str
    years: float
    window: int
    target_d_sharpe: float | None
    s_mu: float | None
    n_sims: int
    n_perm: int
    mean_d_sharpe_raw: float
    mean_d_maxdd_raw_pp: float
    power_dd_raw_z: float
    mean_d_maxdd_expmatched_pp: float  # diagnostico (sesgo Jensen)
    mean_d_maxdd_volmatched_pp: float  # estadistico primario v1.2
    sd_d_maxdd_volmatched_pp: float
    power_dd_vm_z: float
    mean_p_perm: float | None
    fpr_perm_p05: float | None  # P(p<t*) - bajo nulo es el FPR; bajo habilidad, potencia
    power_perm_signed: float | None  # P(p<0.05 y Delta_vm<0)
    frac_subperiods_ge2of3: float | None
    power_composite: float | None  # P(p<0.05 y Delta_vm<0 y >=2/3 subperiodos)
    turnover_per_year: float
    cost_drag_pct_year: float
    null_scheme: str = "block20"


def _simulate_chunk(
    *,
    dgp: str,
    t_days: int,
    window: int,
    sigma_obj: float,
    band: float,
    cost_per_side: float,
    n_sims: int,
    seed: int,
    perm_offset: int,
    mu_ann: float,
    sigma_ann: float,
    s_mu: float,
    n_perm: int,
    null_scheme: str,
) -> dict[str, Any]:
    rng = np.random.default_rng(seed)
    r = _gen_returns(dgp, rng, n_sims, t_days + 1, mu_ann, sigma_ann, s_mu)
    pos = _positions(r[:, 1:], window, sigma_obj, band)

    bh = r[:, 1:]
    gross = pos * bh
    turnover = np.abs(np.diff(pos, axis=1, prepend=np.zeros((n_sims, 1))))
    strat = gross - turnover * cost_per_side

    d_sharpe_raw = np.nan_to_num(_sharpe_rows(strat) - _sharpe_rows(bh))
    dd_strat = _maxdd_rows(strat)
    d_raw = dd_strat - _maxdd_rows(bh)

    sd_bh = np.std(bh, axis=1, ddof=1)
    sd_strat = np.std(strat, axis=1, ddof=1)
    f_vm = np.where(sd_bh > 1e-15, sd_strat / sd_bh, 1.0)
    d_vm = dd_strat - _maxdd_rows(f_vm[:, None] * bh)
    e_bar = np.mean(pos, axis=1)
    d_em = dd_strat - _maxdd_rows(e_bar[:, None] * bh)

    sub_ok: NDArray[np.bool_] | None = None
    if t_days >= SUB_B2 + 120:
        sub_ok = np.zeros((n_sims, 3), dtype=bool)
        for j, (a, b) in enumerate(((0, SUB_B1), (SUB_B1, SUB_B2), (SUB_B2, t_days))):
            sd_b = np.std(bh[:, a:b], axis=1, ddof=1)
            sd_s = np.std(strat[:, a:b], axis=1, ddof=1)
            f_sp = np.where(sd_b > 1e-15, sd_s / sd_b, 1.0)
            sub_ok[:, j] = (
                _maxdd_rows(strat[:, a:b]) - _maxdd_rows(f_sp[:, None] * bh[:, a:b])
            ) < 0

    p_perm: F64 | None = None
    if n_perm > 0:
        p_perm = np.empty(n_sims)
        for i in range(n_sims):
            if null_scheme == "rotation":
                perms = random_rotations(pos[i], n_perm, seed=PERM_SEED + perm_offset + i)
            else:
                perms = circular_block_permutations(
                    pos[i], PERM_BLOCK, n_perm, seed=PERM_SEED + perm_offset + i
                )
            d_p, _ = permutation_delta_stats(perms, bh[i], cost_per_side)
            p_perm[i] = permutation_pvalue(d_vm[i], d_p)

    return {
        "d_sharpe_raw": d_sharpe_raw,
        "d_raw": d_raw,
        "d_vm": d_vm,
        "d_em": d_em,
        "sub_ok": sub_ok,
        "p_perm": p_perm,
        "turnover_sum": turnover.sum(axis=1),
        "cost_sum": (turnover * cost_per_side).sum(axis=1),
    }


def simulate_h1_v12(
    *,
    dgp: str,
    years: float,
    window: int,
    sigma_obj: float = 0.25,
    band: float = BAND_FROZEN,
    cost_per_side: float = COST_PER_SIDE,
    n_sims: int,
    seed: int,
    mu_ann: float = 0.15,
    sigma_ann: float = 0.60,
    s_mu: float = 0.0,
    n_perm: int = 0,
    null_scheme: str = "block20",
    target_d_sharpe: float | None = None,
    max_chunk: int = 500,
) -> H1Agg:
    """Simula H1 por chunks de memoria acotada; semillas por simulacion globales."""
    t_days = int(round(years * DAYS_PER_YEAR))
    acc: dict[str, list[Any]] = {
        k: []
        for k in (
            "d_sharpe_raw",
            "d_raw",
            "d_vm",
            "d_em",
            "sub_ok",
            "p_perm",
            "turnover_sum",
            "cost_sum",
        )
    }
    done = 0
    chunk_idx = 0
    while done < n_sims:
        m = min(max_chunk, n_sims - done)
        part = _simulate_chunk(
            dgp=dgp,
            t_days=t_days,
            window=window,
            sigma_obj=sigma_obj,
            band=band,
            cost_per_side=cost_per_side,
            n_sims=m,
            seed=seed + 10_007 * chunk_idx,
            perm_offset=done,
            mu_ann=mu_ann,
            sigma_ann=sigma_ann,
            s_mu=s_mu,
            n_perm=n_perm,
            null_scheme=null_scheme,
        )
        for k, v in part.items():
            if v is not None:
                acc[k].append(v)
        done += m
        chunk_idx += 1

    d_sharpe_raw = np.concatenate(acc["d_sharpe_raw"])
    d_raw = np.concatenate(acc["d_raw"])
    d_vm = np.concatenate(acc["d_vm"])
    d_em = np.concatenate(acc["d_em"])
    turnover_sum = np.concatenate(acc["turnover_sum"])
    cost_sum = np.concatenate(acc["cost_sum"])
    sub_ok = np.concatenate(acc["sub_ok"]) if acc["sub_ok"] else None
    p_perm = np.concatenate(acc["p_perm"]) if acc["p_perm"] else None

    m_sr = float(d_sharpe_raw.mean())
    m_raw, s_raw = float(d_raw.mean()), float(d_raw.std(ddof=1))
    m_vm, s_vm = float(d_vm.mean()), float(d_vm.std(ddof=1))
    power_raw = NORM.cdf(-Z_ALPHA - m_raw / s_raw) if s_raw > 0 else 0.0
    power_vm = NORM.cdf(-Z_ALPHA - m_vm / s_vm) if s_vm > 0 else 0.0

    frac_sub23: float | None = None
    if sub_ok is not None:
        frac_sub23 = round(float((sub_ok.sum(axis=1) >= 2).mean()), 4)
    composite: NDArray[np.bool_] | None = None
    if p_perm is not None and sub_ok is not None:
        composite = (p_perm < PERM_THRESH) & (d_vm < 0) & (sub_ok.sum(axis=1) >= 2)

    def _rnd(x: float, nd: int) -> float | None:
        return None if math.isnan(x) else round(x, nd)

    return H1Agg(
        dgp=dgp,
        years=years,
        window=window,
        target_d_sharpe=target_d_sharpe,
        s_mu=None if s_mu == 0 else round(s_mu, 8),
        n_sims=n_sims,
        n_perm=n_perm,
        mean_d_sharpe_raw=round(m_sr, 4),
        mean_d_maxdd_raw_pp=round(m_raw * 100, 2),
        power_dd_raw_z=round(power_raw, 4),
        mean_d_maxdd_expmatched_pp=round(float(d_em.mean()) * 100, 2),
        mean_d_maxdd_volmatched_pp=round(m_vm * 100, 2),
        sd_d_maxdd_volmatched_pp=round(s_vm * 100, 2),
        power_dd_vm_z=round(power_vm, 4),
        mean_p_perm=None if p_perm is None else round(float(p_perm.mean()), 4),
        fpr_perm_p05=None if p_perm is None else round(float((p_perm < PERM_THRESH).mean()), 4),
        power_perm_signed=(
            None
            if p_perm is None
            else round(float(((p_perm < PERM_THRESH) & (d_vm < 0)).mean()), 4)
        ),
        frac_subperiods_ge2of3=frac_sub23,
        power_composite=None if composite is None else round(float(composite.mean()), 4),
        turnover_per_year=round(float(turnover_sum.mean()) / years, 2),
        cost_drag_pct_year=round(float(cost_sum.mean()) / years * 100, 3),
        null_scheme=null_scheme,
    )


def calibrate_ar1(
    target: float, window: int, years: float, n_sims: int, seed: int
) -> tuple[float, float]:
    """Biseccion sobre s_mu para que E[DeltaSharpe neto vs B&H crudo] == target."""
    lo, hi = 1e-6, 6e-3
    best = lo
    for k in range(11):
        mid = math.sqrt(lo * hi)  # biseccion geometrica
        agg = simulate_h1_v12(
            dgp="ar1_drift",
            years=years,
            window=window,
            n_sims=n_sims,
            seed=seed + k,
            s_mu=mid,
            n_perm=0,
        )
        achieved = agg.mean_d_sharpe_raw
        if achieved < target:
            lo = mid
        else:
            hi = mid
        best = mid
    final = simulate_h1_v12(
        dgp="ar1_drift",
        years=years,
        window=window,
        n_sims=n_sims,
        seed=seed + 99,
        s_mu=best,
        n_perm=0,
    )
    return best, final.mean_d_sharpe_raw


# ---------------------------------------------------------------------------
# Composicion
# ---------------------------------------------------------------------------
def build_results() -> dict[str, Any]:
    res: dict[str, Any] = {
        "version": "1.3",
        "perm_threshold": PERM_THRESH,
        "generated_at_utc": datetime.now(UTC).isoformat(timespec="seconds"),
        "seed": SEED,
        "alpha_one_sided": 0.05,
        "power_target": 0.80,
        "k_power": round(K_POWER, 4),
        "horizons_years": {
            "H1_in_sample": round(H1_YEARS, 2),
            "H2_in_sample": round(H2_YEARS, 2),
            "H3_in_sample": round(H3_YEARS, 2),
        },
        "v12_note": (
            "Tablas v1.1 de exposure-matched como criterio RETIRADAS (defecto 1 gate M0b: "
            "sesgo de Jensen E[w^2]>=ebar^2 contra exposicion variable bajo el nulo). "
            "Benchmark primario: vol-matched. Criterio: permutacion del vector de exposicion."
        ),
    }
    years = round(H1_YEARS, 1)

    # S1/S2 analiticos (sin cambios)
    res["S1_sharpe_mde_unpaired"] = [
        {"years": y, "mde_d_sharpe_ann": round(mde_sharpe_diff_unpaired(y), 3)}
        for y in (3.3, 5.0, 8.2, 10.0, 15.0, 20.0, 30.0, 50.0)
    ]
    res["S1b_years_for_delta_sharpe"] = [
        {"delta_sharpe": d, "years_needed": round(years_for_sharpe_mde(d), 1)}
        for d in (0.2, 0.3, 0.5, 1.0, 1.5)
    ]
    rows: list[dict[str, Any]] = []
    for yr in (3.3, years):
        for n_trials in (38, 60):
            for sd_trials in (0.5, 0.75):
                for skew, kurt in ((0.0, 3.0), (-0.5, 6.0)):
                    sr_req = sr_required_for_dsr(yr, n_trials, sd_trials, skew, kurt)
                    rows.append(
                        {
                            "years": yr,
                            "n_trials": n_trials,
                            "sd_trials_ann": sd_trials,
                            "skew": skew,
                            "kurtosis": kurt,
                            "sr0_ann": round(expected_max_sr_under_null(n_trials, sd_trials), 3),
                            "min_sharpe_ann_for_dsr95": (
                                None if math.isinf(sr_req) else round(sr_req, 3)
                            ),
                        }
                    )
    res["S2_dsr_required_sharpe"] = rows

    # S3: calibracion del nulo (GBM, sin habilidad) con el criterio v1.2 completo
    null_agg = simulate_h1_v12(
        dgp="gbm",
        years=years,
        window=200,
        n_sims=500,
        seed=SEED + 1,
        n_perm=199,
    )
    res["S3_null_calibration"] = asdict(null_agg)

    # S4: mundo con habilidad plantada (AR1 drift calibrado), potencia por tamanno
    planted: list[dict[str, Any]] = []
    calib: list[dict[str, Any]] = []
    for window in (100, 200):
        for target in (0.1, 0.3, 0.5):
            s_mu, achieved = calibrate_ar1(
                target, window, years, n_sims=250, seed=CAL_SEED + 17 * window + int(target * 100)
            )
            calib.append(
                {
                    "window": window,
                    "target_d_sharpe": target,
                    "s_mu_daily": round(s_mu, 8),
                    "achieved_d_sharpe_cal": achieved,
                    "phi": AR1_PHI,
                }
            )
            agg = simulate_h1_v12(
                dgp="ar1_drift",
                years=years,
                window=window,
                n_sims=400,
                seed=SEED + 2,
                s_mu=s_mu,
                n_perm=199,
                target_d_sharpe=target,
            )
            planted.append(asdict(agg))
    res["S4_calibration"] = calib
    res["S4_planted_skill_power"] = planted

    # S6: sensibilidad de la banda de rebalanceo (soporte s4 PRERREGISTRO)
    band_rows: list[dict[str, Any]] = []
    for dgp_band in ("gbm", "ms_vol_jump"):
        for band in (0.0, 0.02, 0.05, 0.10, 0.20):
            agg = simulate_h1_v12(
                dgp=dgp_band,
                years=years,
                window=200,
                band=band,
                n_sims=300,
                seed=SEED + 3,
                n_perm=0,
            )
            band_rows.append(
                {
                    "dgp": dgp_band,
                    "band": band,
                    "turnover_per_year": agg.turnover_per_year,
                    "cost_drag_pct_year": agg.cost_drag_pct_year,
                    "mean_d_maxdd_volmatched_pp": agg.mean_d_maxdd_volmatched_pp,
                    "mean_d_sharpe_raw": agg.mean_d_sharpe_raw,
                }
            )
    res["S6_band_sensitivity"] = band_rows

    # S7: H2 semanal (analitico, sin cambios)
    n_weeks = H2_YEARS * WEEKS_PER_YEAR
    res["S7_h2_weekly_mde"] = [
        {
            "n_weeks": int(n_weeks),
            "sigma_weekly": sw,
            "rho_ar1": rho,
            "mde_mu_weekly": round(mde_mean(n_weeks, sw, rho), 5),
            "mde_mu_annualized": round(mde_mean(n_weeks, sw, rho) * WEEKS_PER_YEAR, 4),
        }
        for sw in (0.03, 0.04, 0.05)
        for rho in (0.0, 0.15)
    ]
    res["S7b_h2_years_for_targets"] = [
        {
            "target_mu_weekly": mu,
            "sigma_weekly": 0.04,
            "rho_ar1": 0.15,
            "years_needed": round(n_obs_for_mean(mu, 0.04, 0.15) / WEEKS_PER_YEAR, 1),
        }
        for mu in (0.001, 0.002, 0.004)
    ]

    # S8: H3 carry diario (analitico, sin cambios)
    n_days = H3_YEARS * DAYS_PER_YEAR
    res["S8_h3_daily_mde"] = [
        {
            "n_days": int(n_days),
            "sigma_daily": sd,
            "rho_ar1": rho,
            "mde_mu_daily": round(mde_mean(n_days, sd, rho), 7),
            "mde_mu_annualized": round(mde_mean(n_days, sd, rho) * DAYS_PER_YEAR, 4),
        }
        for sd in (0.0005, 0.001, 0.002)
        for rho in (0.0, 0.10)
    ]
    res["S8b_h3_years_for_targets"] = [
        {
            "target_mu_annualized": mu,
            "sigma_daily": 0.001,
            "rho_ar1": 0.10,
            "years_needed": round(
                n_obs_for_mean(mu / DAYS_PER_YEAR, 0.001, 0.10) / DAYS_PER_YEAR, 2
            ),
        }
        for mu in (0.01, 0.02, 0.04)
    ]

    # S9: tasas de acierto (sin cambios)
    res["S9_winrate_n"] = [
        {"p0": 0.40, "p1": p1, "n_trades_needed": int(math.ceil(n_for_winrate(0.40, p1)))}
        for p1 in (0.42, 0.45, 0.50)
    ]
    return res


def render_md(res: dict[str, Any]) -> str:
    out: list[str] = []
    a = out.append
    a("# Analisis de potencia v1.3 - (QUANT-ARENA v2)")
    a("")
    a(
        f"- Generado: {res['generated_at_utc']} | semilla: {res['seed']} | "
        f"alpha una cola 5% | potencia objetivo 80% | K = {res['k_power']}"
    )
    h = res["horizons_years"]
    a(
        f"- Horizontes in-sample: H1 {h['H1_in_sample']} a, H2 {h['H2_in_sample']} a, "
        f"H3 {h['H3_in_sample']} a. Coste por lado: 13 pb. Banda: 10 pp."
    )
    a(f"- **Nota v1.2:** {res['v12_note']}")
    a("")
    a("## S1. MDE de diferencia de Sharpe (no pareada; cota conservadora)")
    a("| anios | MDE DSharpe |")
    a("|---|---|")
    for r in res["S1_sharpe_mde_unpaired"]:
        a(f"| {r['years']} | {r['mde_d_sharpe_ann']} |")
    a("")
    a("## S1b. Anios necesarios por efecto objetivo")
    a("| DSharpe | anios |")
    a("|---|---|")
    for r in res["S1b_years_for_delta_sharpe"]:
        a(f"| {r['delta_sharpe']} | {r['years_needed']} |")
    a("")
    a("## S2. Sharpe minimo para DSR >= 0.95 (gate de H2/H3; informativo en H1)")
    a("| anios | n_trials | sd celdas | skew | kurt | SR0 | Sharpe min |")
    a("|---|---|---|---|---|---|---|")
    for r in res["S2_dsr_required_sharpe"]:
        sr = r["min_sharpe_ann_for_dsr95"]
        a(
            f"| {r['years']} | {r['n_trials']} | {r['sd_trials_ann']} | {r['skew']} | "
            f"{r['kurtosis']} | {r['sr0_ann']} | {'INF' if sr is None else sr} |"
        )
    a("")
    n = res["S3_null_calibration"]
    a("## S3. Calibracion del nulo (GBM sin habilidad) - criterio v1.2 completo")
    a("| metrica | valor | lectura |")
    a("|---|---|---|")
    a(f"| E[DmaxDD vol-matched] | {n['mean_d_maxdd_volmatched_pp']} pp | debe ser ~0 (identidad) |")
    a(
        f"| E[DmaxDD exposure-matched] (diagnostico) | {n['mean_d_maxdd_expmatched_pp']} pp "
        "| sesgo de Jensen: NO es criterio |"
    )
    a(f"| E[DmaxDD vs B&H crudo] | {n['mean_d_maxdd_raw_pp']} pp | efecto exposicion, no skill |")
    a(f"| p medio de permutacion | {n['mean_p_perm']} | ~0.5 = uniforme |")
    a(f"| FPR P(p<t*=0.025) | {n['fpr_perm_p05']} | nivel calibrado: FPR sintetico <=5% |")
    a(f"| FPR regla compuesta | {n['power_composite']} | <= 0.05 nominal |")
    a(
        f"| turnover/ano, sangria costes | {n['turnover_per_year']}x, "
        f"{n['cost_drag_pct_year']} %/ano | con banda 10 pp |"
    )
    a("")
    a("## S4. Habilidad plantada (drift AR(1) calibrado) - potencia REAL por efecto")
    a("### S4a. Calibracion")
    a("| ventana | objetivo DSharpe | s_mu diario | logrado (cal) |")
    a("|---|---|---|---|")
    for r in res["S4_calibration"]:
        a(
            f"| {r['window']} | {r['target_d_sharpe']} | {r['s_mu_daily']} | "
            f"{r['achieved_d_sharpe_cal']} |"
        )
    a("")
    a("### S4b. Potencia del criterio v1.2 (permutacion + subperiodos)")
    a(
        "| ventana | DSharpe obj | DSharpe logrado | pot. perm p<t* | pot. (p<t* y D<0) | "
        "P(>=2/3 subp.) | pot. REGLA COMPUESTA | E[DmaxDD_vm] pp |"
    )
    a("|---|---|---|---|---|---|---|---|")
    for r in res["S4_planted_skill_power"]:
        a(
            f"| {r['window']} | {r['target_d_sharpe']} | {r['mean_d_sharpe_raw']} | "
            f"{r['fpr_perm_p05']} | {r['power_perm_signed']} | "
            f"{r['frac_subperiods_ge2of3']} | {r['power_composite']} | "
            f"{r['mean_d_maxdd_volmatched_pp']} |"
        )
    a("")
    a("## S6. Sensibilidad de la banda de rebalanceo (ventana 200)")
    a("| dgp | banda | turnover/ano | sangria %/ano | E[DmaxDD_vm] pp | E[DSharpe] |")
    a("|---|---|---|---|---|---|")
    for r in res["S6_band_sensitivity"]:
        a(
            f"| {r['dgp']} | {r['band']} | {r['turnover_per_year']} | {r['cost_drag_pct_year']} | "
            f"{r['mean_d_maxdd_volmatched_pp']} | {r['mean_d_sharpe_raw']} |"
        )
    a("")
    a("## S7. H2 momentum transversal (spread semanal)")
    a("| n sem | sigma sem | rho | MDE sem | MDE anual |")
    a("|---|---|---|---|---|")
    for r in res["S7_h2_weekly_mde"]:
        a(
            f"| {r['n_weeks']} | {r['sigma_weekly']} | {r['rho_ar1']} | "
            f"{r['mde_mu_weekly']} | {r['mde_mu_annualized']} |"
        )
    a("")
    a("### S7b. Anios necesarios (sigma 4%/sem, rho 0.15)")
    a("| mu semanal | anios |")
    a("|---|---|")
    for r in res["S7b_h2_years_for_targets"]:
        a(f"| {r['target_mu_weekly']} | {r['years_needed']} |")
    a("")
    a("## S8. H3 carry delta-neutral (neto diario)")
    a("| n dias | sigma dia | rho | MDE diario | MDE anual |")
    a("|---|---|---|---|---|")
    for r in res["S8_h3_daily_mde"]:
        a(
            f"| {r['n_days']} | {r['sigma_daily']} | {r['rho_ar1']} | "
            f"{r['mde_mu_daily']} | {r['mde_mu_annualized']} |"
        )
    a("")
    a("### S8b. Anios necesarios (sigma 10 pb/dia, rho 0.10)")
    a("| mu anual | anios |")
    a("|---|---|")
    for r in res["S8b_h3_years_for_targets"]:
        a(f"| {r['target_mu_annualized']} | {r['years_needed']} |")
    a("")
    a("## S9. Discriminar tasas de acierto")
    a("| WR nulo | WR alt | n trades |")
    a("|---|---|---|")
    for r in res["S9_winrate_n"]:
        a(f"| {r['p0']} | {r['p1']} | {r['n_trades_needed']} |")
    a("")
    return "\n".join(out) + "\n"


def main() -> None:
    res = build_results()
    OUT_MD.parent.mkdir(parents=True, exist_ok=True)
    OUT_MD.write_text(render_md(res), encoding="utf-8")
    OUT_JSON.write_text(json.dumps(res, indent=2, ensure_ascii=False), encoding="utf-8")
    print(f"power analysis v1.3 -> {OUT_MD}")
    print(f"                    -> {OUT_JSON}")


if __name__ == "__main__":
    main()
