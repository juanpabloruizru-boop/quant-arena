"""Motor de backtest vectorizado (M2).

Convenciones (pre-registradas):
- Temporal: la senal se decide al CIERRE del dia t; la posicion rige desde el
  dia t+1 (nunca opera con el cierre que la genera: cero look-ahead).
- Ejecucion y costes: el trade del dia t+1 usa el quote_volume de t+1 para la
  participacion (el trade forma parte del volumen de ese dia). Fee taker por
  lado + slippage por tramos (config/costs.yaml). Participacion por encima del
  ultimo tramo => trade RECHAZADO (se mantiene la posicion anterior y se
  registra). Orden por debajo del minNotional => RECHAZADA, salvo cierre total
  a 0 (liquidacion de posicion, permitida).
- Carry (H3): entrada a las 00:00 UTC del dia siguiente a la senal; el
  position captura los eventos de funding con ``entry_ts < fundingTime <
  exit_ts`` (estricto en ambos extremos => convencion CONSERVADORA: se pierde
  el evento de las 00:00 del dia de entrada y el del instante exacto de
  salida). Short perp recibe +rate cuando rate > 0.
- Registro obligatorio: ``evaluate`` exige un contexto de trial abierto
  (principio 3: ejecutar sin registrar es imposible).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

import numpy as np
import pandas as pd
from numpy.typing import NDArray

from qa.backtest.costs import CostModel
from qa.backtest.trials import _TrialContext
from qa.stats.metrics import metrics_summary

F64 = NDArray[np.float64]


@dataclass
class ExecutionResult:
    positions: F64  # posicion vigente por dia (alineada con net_returns)
    gross_returns: F64
    net_returns: F64
    turnover_total: float
    cost_total: float
    rejected_trades: int
    rejected_min_notional: int
    funding_collected: float = 0.0
    metrics: dict[str, Any] = field(default_factory=dict)


def simple_returns(close: NDArray[np.floating[Any]]) -> F64:
    c = np.asarray(close, dtype=np.float64)
    return c[1:] / c[:-1] - 1.0


def run_positions(
    close: NDArray[np.floating[Any]],
    desired_weight: NDArray[np.floating[Any]],
    quote_volume: NDArray[np.floating[Any]],
    cost_model: CostModel,
    capital_usdt: float,
    band: float = 0.10,
    perp: bool = False,
) -> ExecutionResult:
    """Ejecuta pesos deseados (decididos al cierre de t) sobre retornos de t+1.

    ``desired_weight[i]`` corresponde al cierre del dia i (misma longitud que
    ``close``). El retorno del dia j es close[j]/close[j-1]-1; la posicion que
    lo captura es la decidida al cierre de j-1.
    """
    c = np.asarray(close, dtype=np.float64)
    dw = np.asarray(desired_weight, dtype=np.float64)
    qv = np.asarray(quote_volume, dtype=np.float64)
    n = c.shape[0]
    r = simple_returns(c)  # longitud n-1, r[j-1] = retorno del dia j
    m = r.shape[0]

    pos = np.zeros(m)  # pos[j-1] = posicion vigente durante el dia j
    costs = np.zeros(m)
    rejected = 0
    rejected_min = 0
    current = 0.0
    for j in range(1, n):
        target = float(dw[j - 1])
        delta = target - current
        need_trade = (target > 0.0) != (current > 0.0) or abs(delta) >= (
            band if band > 0 else 1e-12
        )
        if need_trade and abs(delta) > 1e-12:
            notional = abs(delta) * capital_usdt
            day_volume = qv[j] if j < qv.shape[0] else qv[-1]
            participation = notional / day_volume if day_volume > 0 else np.inf
            if notional < cost_model.min_notional_usdt and target != 0.0:
                rejected_min += 1  # orden por debajo del minimo => no se ejecuta
            elif cost_model.slippage_bps(participation) is None:
                rejected += 1  # participacion excesiva => trade inviable
            else:
                rate = cost_model.side_cost_rate(participation, perp=perp)
                assert rate is not None
                costs[j - 1] += abs(delta) * rate
                current = target
        pos[j - 1] = current

    gross = pos * r
    net = gross - costs
    turnover_total = float(np.abs(np.diff(pos, prepend=0.0)).sum())
    result = ExecutionResult(
        positions=pos,
        gross_returns=gross,
        net_returns=net,
        turnover_total=round(turnover_total, 4),
        cost_total=round(float(costs.sum()), 6),
        rejected_trades=rejected,
        rejected_min_notional=rejected_min,
    )
    result.metrics = metrics_summary(net, pos)
    result.metrics["turnover_total"] = round(turnover_total, 4)
    result.metrics["cost_total"] = result.cost_total
    result.metrics["rejected_trades"] = rejected
    result.metrics["rejected_min_notional"] = rejected_min
    return result


def run_carry(
    days: pd.DatetimeIndex,
    funding: pd.DataFrame,
    signal_active: NDArray[np.bool_],
    quote_volume: NDArray[np.floating[Any]],
    cost_model: CostModel,
    capital_usdt: float,
    spot_close: NDArray[np.floating[Any]],
    perp_close: NDArray[np.floating[Any]],
) -> ExecutionResult:
    """Carry delta-neutral: long spot + short perp, funding real + P&L de basis.

    P&L diario mientras la posicion esta activa (por unidad de capital):
      r_spot[d] - r_perp[d]  (convergencia de la prima basis; el short de perp
      gana cuando el perp cae relativo al spot) + eventos de funding del dia.
    NUNCA debe reportarse carry neto sin la pierna de basis.

    ``signal_active[i]``: decidido al cierre del dia i; la posicion queda activa
    desde las 00:00 UTC del dia i+1 hasta las 00:00 del primer dia inactivo.
    ``days``: indice diario UTC del periodo simulado (misma longitud que
    ``signal_active`` + 1 dia de cierre final).
    """
    act = np.asarray(signal_active, dtype=bool)
    n = act.shape[0]
    # active[d] = posicion vigente durante el dia d (d=1..n-1 respecto a days)
    active = np.concatenate(([False], act[:-1]))[:n]
    pnl = np.zeros(n)
    # pierna de basis: long spot / short perp a igual nocional
    sp = np.asarray(spot_close, dtype=np.float64)
    pp = np.asarray(perp_close, dtype=np.float64)
    r_spot = np.concatenate(([0.0], sp[1:] / sp[:-1] - 1.0))[:n]
    r_perp = np.concatenate(([0.0], pp[1:] / pp[:-1] - 1.0))[:n]
    pnl += active * (r_spot - r_perp)
    funding_total = 0.0
    entry_day = active & ~np.concatenate(([False], active[:-1]))[:n]
    exit_day = ~active & np.concatenate(([False], active[:-1]))[:n]

    f = funding.copy()
    f["ft"] = pd.to_datetime(f["funding_time"])
    f["day_key"] = f["ft"].dt.strftime("%Y-%m-%d")
    f["is_midnight"] = f["ft"].dt.hour == 0

    day_index = {
        pd.Timestamp(d).strftime("%Y-%m-%d"): i
        for i, d in enumerate(pd.DatetimeIndex(days.floor("D")))
    }
    for day_key, grp in f.groupby("day_key"):
        i = day_index.get(str(day_key))
        if i is None or not active[i]:
            continue
        for _, ev in grp.iterrows():
            at_midnight = bool(ev["is_midnight"])
            entered_today = bool(entry_day[i])
            # convencion estricta: entry_ts < fundingTime < exit_ts
            if at_midnight and entered_today:
                continue  # evento 00:00 del dia de entrada: NO capturado
            rate = float(ev["funding_rate"])
            pnl[i] += rate  # short perp recibe rate>0
            funding_total += rate

    # costes: entrada y salida, dos piernas (spot taker + perp taker + slippage)
    for k in np.nonzero(entry_day | exit_day)[0]:
        day_volume = float(quote_volume[k]) if quote_volume[k] > 0 else np.inf
        participation = capital_usdt / day_volume
        spot_rate = cost_model.side_cost_rate(participation, perp=False)
        perp_rate = cost_model.side_cost_rate(participation, perp=True)
        if spot_rate is None or perp_rate is None:
            # sin liquidez para abrir/cerrar: la senal no se ejecuta ese dia
            continue
        pnl[k] -= spot_rate + perp_rate

    pos_float = active.astype(float)
    result = ExecutionResult(
        positions=pos_float,
        gross_returns=pnl.copy(),
        net_returns=pnl,
        turnover_total=round(float(pos_float.sum()), 4),
        cost_total=0.0,
        rejected_trades=0,
        rejected_min_notional=0,
        funding_collected=round(funding_total, 8),
    )
    result.metrics = metrics_summary(pnl, pos_float)
    result.metrics["funding_collected"] = result.funding_collected
    result.metrics["active_days"] = int(active.sum())
    return result


def evaluate(ctx: _TrialContext | None, result: ExecutionResult) -> dict[str, Any]:
    """Cierra la evaluacion registrando metricas en el ledger (OBLIGATORIO).

    Sin contexto de trial abierto => RuntimeError (principio 3: no existe
    backtest sin registro).
    """
    if ctx is None:
        raise RuntimeError(
            "REGISTRO OBLIGATORIO: todo backtest debe ejecutarse dentro de "
            "ledger.trial(...) (principio 3; el DSR lee n_trials de ahi)."
        )
    ctx.set_metrics(result.metrics)
    return result.metrics
