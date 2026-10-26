"""Analisis de potencia para el pre-registro de QUANT-ARENA v2 (M0).

Responde, por hipotesis: cuantos anios de datos o cuantas senales/observaciones
hacen falta para detectar el efecto objetivo con potencia 80% (alpha 5%
una cola). Si el efecto tipico NO es detectable en el horizonte disponible, se
declara explicitamente ("INCONTRASTABLE en el horizonte") y el criterio de exito
del preregistro se formula sobre la metrica que si tiene potencia.

Metodos:
1. Analiticos:
   - SE del Sharpe anualizado (Lo, 2002): SE(SR_d) = sqrt((1 + SR_d^2/2)/T).
   - DSR (Bailey & Lopez de Prado, 2014): SR0 = E[max SR bajo nulo] dado
     n_trials y la dispersion entre celdas; DSR = Phi((SR-SR0)sqrt(T-1)/
     sqrt(1 - g3*SR + (g4-1)/4*SR^2)), con SR por observacion.
   - MDE de una media con autocorrelacion AR(1) (aprox. Newey-West):
     SE = sigma*sqrt(((1+rho)/(1-rho))/n).
   - n para discriminar tasas de acierto (test de proporcion una cola).
2. Monte Carlo (semilla fija) del montaje concreto de H1 (long/flat SMA +
   vol targeting sobre el mismo activo), que estima la potencia del test
   PAREADO de diferencia de Sharpe y de diferencia de max drawdown.

Supuestos de planificacion (NO son predicciones de mercado): estan marcados
como ASSUMPTION y se exploran en tablas de sensibilidad.

Salidas (trackeadas en git):
  reports/M0_power_analysis.md
  reports/M0_power_analysis.json

Uso:  python scripts/power_analysis.py   (determinista; ~30-60 s)
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

SEED = 20261026
NORM = NormalDist()
Z_ALPHA = NORM.inv_cdf(0.95)  # 1.6449 (una cola, 5%)
Z_BETA = NORM.inv_cdf(0.80)  # 0.8416 (potencia 80%)
K_POWER = Z_ALPHA + Z_BETA  # 2.4866
DAYS_PER_YEAR = 365.0  # cripto opera todos los dias
WEEKS_PER_YEAR = 52.0
GAMMA_EM = 0.5772156649015329  # Euler-Mascheroni

REPO = Path(__file__).resolve().parents[1]
OUT_MD = REPO / "reports" / "M0_power_analysis.md"
OUT_JSON = REPO / "reports" / "M0_power_analysis.json"

# Horizontes in-sample esperados segun disponibilidad verificada (2026-10-26):
# H1: spot diario BTCUSDT desde 2017-08-17; congelacion ~2026-10-25; holdout 365d.
H1_YEARS = (datetime(2025, 10, 25) - datetime(2017, 8, 17)).days / DAYS_PER_YEAR
# H2: profundidad de altcoins liquidas asumida desde 2019-01-01.
H2_YEARS = (datetime(2025, 10, 25) - datetime(2019, 1, 1)).days / DAYS_PER_YEAR
# H3: funding BTCUSDT perp desde 2019-09-10 (verificado por API).
H3_YEARS = (datetime(2025, 10, 25) - datetime(2019, 9, 10)).days / DAYS_PER_YEAR


# ---------------------------------------------------------------------------
# Analiticos
# ---------------------------------------------------------------------------
def se_sharpe_ann(years: float, sr_ann: float = 0.0) -> float:
    """SE del Sharpe anualizado (Lo 2002), T en observaciones diarias."""
    t_obs = years * DAYS_PER_YEAR
    sr_d = sr_ann / math.sqrt(DAYS_PER_YEAR)
    se_d = math.sqrt((1.0 + 0.5 * sr_d**2) / t_obs)
    return se_d * math.sqrt(DAYS_PER_YEAR)


def mde_sharpe_diff_unpaired(years: float, sr_ann: float = 0.0) -> float:
    """MDE (potencia 80%, alpha 5% una cola) para diferencia de Sharpe NO pareada."""
    return K_POWER * math.sqrt(2.0) * se_sharpe_ann(years, sr_ann)


def years_for_sharpe_mde(delta: float, sr_ann: float = 0.0) -> float:
    """Anios necesarios para detectar una diferencia de Sharpe `delta` (no pareada)."""
    lo, hi = 0.01, 10_000.0
    for _ in range(200):
        mid = 0.5 * (lo + hi)
        if mde_sharpe_diff_unpaired(mid, sr_ann) > delta:
            lo = mid
        else:
            hi = mid
    return 0.5 * (lo + hi)


def expected_max_sr_under_null(n_trials: int, sd_trials_ann: float) -> float:
    """SR0 (anualizado) = esperanza del maximo de n_trials Sharpe bajo el nulo."""
    n = max(2, int(n_trials))
    e_max_std = (1.0 - GAMMA_EM) * NORM.inv_cdf(1.0 - 1.0 / n) + GAMMA_EM * NORM.inv_cdf(
        1.0 - 1.0 / (n * math.e)
    )
    return sd_trials_ann * e_max_std


def dsr(
    sr_ann: float, years: float, n_trials: int, sd_trials_ann: float, skew: float, kurt: float
) -> float:
    """Deflated Sharpe Ratio (Bailey & Lopez de Prado 2014), SR en terminos diarios."""
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
    """Sharpe anualizado minimo observado para alcanzar DSR >= target (biseccion)."""
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
    """MDE para la media con varianza de largo plazo AR(1) (aprox. Newey-West)."""
    lr_factor = (1.0 + rho) / (1.0 - rho)
    return K_POWER * sigma * math.sqrt(lr_factor / n_obs)


def n_obs_for_mean(target_mu: float, sigma: float, rho: float = 0.0) -> float:
    lr_factor = (1.0 + rho) / (1.0 - rho)
    return lr_factor * (K_POWER * sigma / target_mu) ** 2


def n_for_winrate(p0: float, p1: float) -> float:
    """n de trades para discriminar WR=p1 frente a nulo WR=p0 (una cola, 80%)."""
    num = Z_ALPHA * math.sqrt(p0 * (1.0 - p0)) + Z_BETA * math.sqrt(p1 * (1.0 - p1))
    return (num / (p1 - p0)) ** 2


# ---------------------------------------------------------------------------
# Monte Carlo de H1 (test pareado Delta-Sharpe y Delta-maxDD)
# ---------------------------------------------------------------------------
@dataclass
class MCResult:
    years: float
    mu_ann: float
    sigma_ann: float
    window: int
    sigma_obj: float
    n_sims: int
    mean_d_sharpe: float
    sd_d_sharpe: float
    power_d_sharpe_gt0: float
    mean_d_maxdd_pp: float  # strat - B&H, negativo = mejora, en puntos porcentuales
    sd_d_maxdd_pp: float
    power_d_maxdd_improves: float


def _f64(a: Any) -> NDArray[np.float64]:
    """Convierte cualquier array-like a NDArray[float64] (amigable para mypy)."""
    return np.asarray(a, dtype=np.float64)


def _rolling_mean(x: NDArray[np.float64], w: int) -> NDArray[np.float64]:
    c = np.cumsum(x, axis=1)
    out = np.full(x.shape, np.nan, dtype=np.float64)
    pad = np.concatenate([np.zeros((x.shape[0], 1)), c[:, :-w]], axis=1)
    out[:, w - 1 :] = (c[:, w - 1 :] - pad) / w
    return out


def _max_drawdown(wealth: NDArray[np.float64]) -> NDArray[np.float64]:
    peak = np.maximum.accumulate(wealth, axis=1)
    dd = 1.0 - wealth / peak
    return _f64(dd.max(axis=1))


def _sharpe_ann(r: NDArray[np.float64]) -> NDArray[np.float64]:
    mu = r.mean(axis=1)
    sd = r.std(axis=1, ddof=1)
    sd = np.where(sd < 1e-12, np.nan, sd)
    return _f64(mu / sd * math.sqrt(DAYS_PER_YEAR))


def simulate_h1(
    *,
    years: float,
    mu_ann: float,
    sigma_ann: float,
    window: int,
    sigma_obj: float,
    n_sims: int,
    cost_per_side: float,
    seed: int,
) -> MCResult:
    rng = np.random.default_rng(seed)
    t_days = int(round(years * DAYS_PER_YEAR))
    mu_d = math.log1p(mu_ann) / DAYS_PER_YEAR  # deriva log-normal equivalente
    sig_d = sigma_ann / math.sqrt(DAYS_PER_YEAR)
    r = rng.normal(mu_d, sig_d, size=(n_sims, t_days + 1))

    close = _f64(np.exp(np.cumsum(np.log1p(r), axis=1)))
    sma = _rolling_mean(close, window)
    long_sig = _f64(np.nan_to_num(close > sma))  # durante warmup: flat

    # volatilidad realizada 20d sobre r[t] (datos hasta t inclusive)
    m1 = _rolling_mean(r, 20)
    m2 = _rolling_mean(r * r, 20)
    var20 = np.maximum(m2 - m1 * m1, 0.0)
    vol20 = np.sqrt(var20) * math.sqrt(DAYS_PER_YEAR)
    with np.errstate(divide="ignore", invalid="ignore"):
        scale_raw = np.minimum(1.0, (sigma_obj / vol20))
    scale = _f64(np.nan_to_num(scale_raw, nan=0.0))

    pos_desired = long_sig * scale
    pos = np.zeros_like(pos_desired)
    pos[:, 1:] = pos_desired[:, :-1]  # decision en cierre de t, posicion desde t+1

    strat_r = pos[:, :-1] * r[:, 1:]
    turnover = np.abs(np.diff(pos, axis=1, prepend=np.zeros((n_sims, 1))))[:, :-1]
    strat_r = strat_r - turnover * cost_per_side

    bh_r = r[:, 1:]
    d_sharpe = _sharpe_ann(strat_r) - _sharpe_ann(bh_r)
    w_strat = _f64(np.cumprod(1.0 + strat_r, axis=1))
    w_bh = _f64(np.cumprod(1.0 + bh_r, axis=1))
    d_maxdd = _max_drawdown(w_strat) - _max_drawdown(w_bh)  # negativo = mejora

    d_sharpe = d_sharpe[np.isfinite(d_sharpe)]
    m_sr, s_sr = float(d_sharpe.mean()), float(d_sharpe.std(ddof=1))
    m_dd, s_dd = float(d_maxdd.mean()), float(d_maxdd.std(ddof=1))
    power_sr = NORM.cdf(m_sr / s_sr - Z_ALPHA) if s_sr > 0 else 0.0
    power_dd = NORM.cdf(-Z_ALPHA - m_dd / s_dd) if s_dd > 0 else 0.0
    return MCResult(
        years=years,
        mu_ann=mu_ann,
        sigma_ann=sigma_ann,
        window=window,
        sigma_obj=sigma_obj,
        n_sims=n_sims,
        mean_d_sharpe=round(m_sr, 4),
        sd_d_sharpe=round(s_sr, 4),
        power_d_sharpe_gt0=round(power_sr, 4),
        mean_d_maxdd_pp=round(m_dd * 100.0, 2),
        sd_d_maxdd_pp=round(s_dd * 100.0, 2),
        power_d_maxdd_improves=round(power_dd, 4),
    )


# ---------------------------------------------------------------------------
# Composicion de tablas
# ---------------------------------------------------------------------------
def build_results() -> dict[str, Any]:
    res: dict[str, Any] = {
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
    }

    # T1: MDE de diferencia de Sharpe (no pareada, cota conservadora)
    res["T1_sharpe_mde_unpaired"] = [
        {"years": y, "mde_d_sharpe_ann": round(mde_sharpe_diff_unpaired(y), 3)}
        for y in (3.3, 5.0, 8.2, 10.0, 15.0, 20.0, 30.0, 50.0)
    ]
    res["T1b_years_for_delta_sharpe"] = [
        {"delta_sharpe": d, "years_needed": round(years_for_sharpe_mde(d), 1)}
        for d in (0.2, 0.3, 0.5, 1.0, 1.5)
    ]

    # T2: Sharpe minimo para DSR>=0.95
    rows: list[dict[str, Any]] = []
    for years in (3.3, round(H1_YEARS, 1)):
        for n_trials in (38, 60):
            for sd_trials in (0.5, 0.75):
                for skew, kurt in ((0.0, 3.0), (-0.5, 6.0)):
                    sr_req = sr_required_for_dsr(years, n_trials, sd_trials, skew, kurt)
                    rows.append(
                        {
                            "years": years,
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
    res["T2_dsr_required_sharpe"] = rows

    # T3: Monte Carlo H1
    cost_per_side = 0.0013  # taker 0.10% (verificado) + slippage 3 bps (asuncion tier 1)
    mc: list[MCResult] = []
    i = 0
    for years in (3.3, round(H1_YEARS, 1)):
        for window in (100, 200):
            for mu_ann in (0.15, 0.40):
                mc.append(
                    simulate_h1(
                        years=years,
                        mu_ann=mu_ann,
                        sigma_ann=0.60,  # ASSUMPTION: vol anualizada cripto large-cap
                        window=window,
                        sigma_obj=0.25,
                        n_sims=1200,
                        cost_per_side=cost_per_side,
                        seed=SEED + i,
                    )
                )
                i += 1
    res["T3_mc_h1"] = [asdict(m) for m in mc]
    res["T3_assumptions"] = {
        "sigma_ann": 0.60,
        "cost_per_side": cost_per_side,
        "n_sims": 1200,
        "note": "MBG log-normal; el test real usara bootstrap por bloques sobre datos reales.",
    }

    # T4: H2 momentum transversal semanal
    n_weeks = H2_YEARS * WEEKS_PER_YEAR
    t4: list[dict[str, Any]] = []
    for sigma_w in (0.03, 0.04, 0.05):
        for rho in (0.0, 0.15):
            m = mde_mean(n_weeks, sigma_w, rho)
            t4.append(
                {
                    "n_weeks": int(n_weeks),
                    "sigma_weekly": sigma_w,
                    "rho_ar1": rho,
                    "mde_mu_weekly": round(m, 5),
                    "mde_mu_annualized": round(m * WEEKS_PER_YEAR, 4),
                }
            )
    res["T4_h2_weekly_mde"] = t4
    res["T4b_h2_years_for_targets"] = [
        {
            "target_mu_weekly": mu,
            "sigma_weekly": 0.04,
            "rho_ar1": 0.15,
            "years_needed": round(n_obs_for_mean(mu, 0.04, 0.15) / WEEKS_PER_YEAR, 1),
        }
        for mu in (0.001, 0.002, 0.004)
    ]

    # T5: H3 carry diario neto
    n_days = H3_YEARS * DAYS_PER_YEAR
    t5: list[dict[str, Any]] = []
    for sigma_d in (0.0005, 0.001, 0.002):
        for rho in (0.0, 0.10):
            m = mde_mean(n_days, sigma_d, rho)
            t5.append(
                {
                    "n_days": int(n_days),
                    "sigma_daily": sigma_d,
                    "rho_ar1": rho,
                    "mde_mu_daily": round(m, 7),
                    "mde_mu_annualized": round(m * DAYS_PER_YEAR, 4),
                }
            )
    res["T5_h3_daily_mde"] = t5
    res["T5b_h3_years_for_targets"] = [
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

    # T6: tasas de acierto
    res["T6_winrate_n"] = [
        {"p0": 0.40, "p1": p1, "n_trades_needed": int(math.ceil(n_for_winrate(0.40, p1)))}
        for p1 in (0.42, 0.45, 0.50)
    ]
    return res


def render_md(res: dict[str, Any]) -> str:
    lines: list[str] = []
    a = lines.append
    a("# Analisis de potencia - M0 (QUANT-ARENA v2)")
    a("")
    a(
        f"- Generado: {res['generated_at_utc']} | semilla: {res['seed']} | "
        f"alpha una cola: {res['alpha_one_sided']} | potencia objetivo: {res['power_target']}"
    )
    h = res["horizons_years"]
    a(
        f"- Horizontes in-sample asumidos (segun disponibilidad verificada): "
        f"H1 {h['H1_in_sample']} anios, H2 {h['H2_in_sample']} anios, H3 {h['H3_in_sample']} anios."
    )
    a("- Formula clave: MDE = (z_95 + z_80) x SE = 2.4866 x SE. Cripto = 365 dias/anio.")
    a("")
    a("## T1. Diferencia de Sharpe anualizado (no pareada; cota conservadora)")
    a("| anios de datos | MDE DeltaSharpe |")
    a("|---|---|")
    for r in res["T1_sharpe_mde_unpaired"]:
        a(f"| {r['years']} | {r['mde_d_sharpe_ann']} |")
    a("")
    a("## T1b. Anios necesarios segun efecto objetivo")
    a("| DeltaSharpe objetivo | anios necesarios |")
    a("|---|---|")
    for r in res["T1b_years_for_delta_sharpe"]:
        a(f"| {r['delta_sharpe']} | {r['years_needed']} |")
    a("")
    a("## T2. Sharpe minimo observado para DSR >= 0.95")
    a("| anios | n_trials | sd celdas | skew | kurt | SR0 | Sharpe min |")
    a("|---|---|---|---|---|---|---|")
    for r in res["T2_dsr_required_sharpe"]:
        sr = r["min_sharpe_ann_for_dsr95"]
        a(
            f"| {r['years']} | {r['n_trials']} | {r['sd_trials_ann']} | {r['skew']} | "
            f"{r['kurtosis']} | {r['sr0_ann']} | {'INF' if sr is None else sr} |"
        )
    a("")
    a("## T3. Monte Carlo H1 (pareado: misma ruta para estrategia y B&H)")
    a(
        "| anios | ventana | mu_ann | E[DSR] | sd(DSR) | potencia(DSharpe>0) | "
        "E[DmaxDD] pp | sd pp | potencia(mejora DD) |"
    )
    a("|---|---|---|---|---|---|---|---|---|")
    for r in res["T3_mc_h1"]:
        a(
            f"| {r['years']} | {r['window']} | {r['mu_ann']} | {r['mean_d_sharpe']} | "
            f"{r['sd_d_sharpe']} | {r['power_d_sharpe_gt0']} | {r['mean_d_maxdd_pp']} | "
            f"{r['sd_d_maxdd_pp']} | {r['power_d_maxdd_improves']} |"
        )
    a("")
    a("## T4. H2 momentum transversal (spread semanal)")
    a("| n semanas | sigma semanal | rho | MDE semanal | MDE anualizado |")
    a("|---|---|---|---|---|")
    for r in res["T4_h2_weekly_mde"]:
        a(
            f"| {r['n_weeks']} | {r['sigma_weekly']} | {r['rho_ar1']} | "
            f"{r['mde_mu_weekly']} | {r['mde_mu_annualized']} |"
        )
    a("")
    a("### T4b. Anios necesarios (sigma 4%/sem, rho 0.15)")
    a("| mu semanal objetivo | anios |")
    a("|---|---|")
    for r in res["T4b_h2_years_for_targets"]:
        a(f"| {r['target_mu_weekly']} | {r['years_needed']} |")
    a("")
    a("## T5. H3 carry delta-neutral (P&L neto diario)")
    a("| n dias | sigma diario | rho | MDE diario | MDE anualizado |")
    a("|---|---|---|---|---|")
    for r in res["T5_h3_daily_mde"]:
        a(
            f"| {r['n_days']} | {r['sigma_daily']} | {r['rho_ar1']} | "
            f"{r['mde_mu_daily']} | {r['mde_mu_annualized']} |"
        )
    a("")
    a("### T5b. Anios necesarios (sigma 10 bps/dia, rho 0.10)")
    a("| mu anualizado objetivo | anios |")
    a("|---|---|")
    for r in res["T5b_h3_years_for_targets"]:
        a(f"| {r['target_mu_annualized']} | {r['years_needed']} |")
    a("")
    a("## T6. Discriminar tasas de acierto (WR)")
    a("| WR nulo | WR alternativo | n trades necesario |")
    a("|---|---|---|")
    for r in res["T6_winrate_n"]:
        a(f"| {r['p0']} | {r['p1']} | {r['n_trades_needed']} |")
    a("")
    return "\n".join(lines) + "\n"


def main() -> None:
    res = build_results()
    OUT_MD.parent.mkdir(parents=True, exist_ok=True)
    OUT_MD.write_text(render_md(res), encoding="utf-8")
    OUT_JSON.write_text(json.dumps(res, indent=2, ensure_ascii=False), encoding="utf-8")
    print(f"power analysis -> {OUT_MD}")
    print(f"                -> {OUT_JSON}")


if __name__ == "__main__":
    main()
