"""H2 — Momentum transversal semanal en universo PIT (rejilla v1.4).

Mecanica pre-registrada:
- Universo del rebalanceo: top-N PIT vigente (ultimo mes-start <= inicio de la
  semana de decision), N en {10, 20}.
- Formacion: retorno de L semanas EXCLUYENDO la ultima semana completada:
  f[w] = close[w-2]/close[w-2-L] - 1 (feature testeada por truncamiento).
- Cartera: long del tercil superior por f, equiponderado, sin cortos;
  rebalanceo semanal; decision al cierre de la semana w-1, vigente semana w.
- Higiene (v1.3): toda ventana de formacion que cruce una ruptura
  corporate_action invalida al simbolo en ese rebalanceo.
- Deslistado: ultimo precio observado (el panel semanal usa el ultimo cierre
  disponible; si el simbolo no cotiza nada en la semana, retorno 0 y sale en
  el siguiente rebalanceo).
- Costes: por nombre, fee taker spot + slippage por tramos de participacion
  (notional del nombre / volumen quote diario medio de la semana).
- Benchmark: universo top-N equiponderado con el mismo modelo de costes.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field
from typing import Any

import numpy as np
import pandas as pd

from qa.backtest.costs import CostModel
from qa.data.pit import membership_at
from qa.features.indicators import formation_return_weekly


@dataclass(frozen=True)
class H2Cell:
    L_weeks: int  # 4 | 12 | 26
    N: int  # 10 | 20

    @property
    def cell_id(self) -> str:
        return f"L{self.L_weeks}_N{self.N}"

    @property
    def config(self) -> dict[str, object]:
        return {"family": "H2", "L_weeks": self.L_weeks, "N": self.N}


H2_GRID: list[H2Cell] = [H2Cell(L, N) for L in (4, 12, 26) for N in (10, 20)]
assert len(H2_GRID) == 6


@dataclass
class WeeklyPanel:
    close: pd.DataFrame  # index: week-start (lunes), columns: symbol; ultimo cierre de la semana
    daily_vol: pd.DataFrame  # volumen quote diario medio por symbol-week
    weeks: pd.DatetimeIndex


def build_weekly_panel(daily: pd.DataFrame) -> WeeklyPanel:
    d = daily[["symbol", "open_time", "close", "quote_volume"]].copy()
    d["week"] = d["open_time"].dt.to_period("W-SUN").dt.start_time.dt.tz_localize("UTC")
    g = d.groupby(["week", "symbol"], sort=True)
    close = g["close"].last().unstack("symbol").sort_index()
    vol_sum = g["quote_volume"].sum().unstack("symbol").sort_index()
    ndays = g["quote_volume"].size().unstack("symbol").sort_index().replace(0, np.nan)
    daily_vol = (vol_sum / ndays).reindex(close.index)
    return WeeklyPanel(close=close, daily_vol=daily_vol, weeks=pd.DatetimeIndex(close.index))


@dataclass
class H2Result:
    strat_ret: pd.Series  # retornos semanales NETOS de la cartera
    bench_ret: pd.Series  # retornos semanales NETOS del universo EW
    weeks_used: int
    first_week: str
    last_week: str
    mean_eligible: float
    turnover_per_year: float
    last_basket: list[str] = field(default_factory=list)
    diagnostics: dict[str, Any] = field(default_factory=dict)


def build_h2(
    panel: WeeklyPanel,
    pit: pd.DataFrame,
    adjudications: pd.DataFrame,
    cell: H2Cell,
    cost_model: CostModel,
    capital_usdt: float,
) -> H2Result:
    close = panel.close
    weeks = panel.weeks
    L, N = cell.L_weeks, cell.N

    # formacion por simbolo (causal, salta la ultima semana)
    form = pd.DataFrame(
        {s: formation_return_weekly(close[s].to_numpy(), L) for s in close.columns},
        index=weeks,
    )
    ret_w = close.pct_change()  # retorno semanal close-to-close

    corp: dict[str, list[pd.Timestamp]] = {}
    if adjudications is not None and len(adjudications):
        ca = adjudications[adjudications["classification"] == "corporate_action"]
        for sym, grp in ca.groupby("symbol"):
            corp[str(sym)] = [pd.Timestamp(t) for t in grp["event_date_utc"]]

    strat_rets: dict[pd.Timestamp, float] = {}
    bench_rets: dict[pd.Timestamp, float] = {}
    prev_w: dict[str, float] = {}
    prev_b: dict[str, float] = {}
    elig_counts: list[int] = []
    turnovers: list[float] = []
    last_basket: list[str] = []

    for i in range(L + 2, len(weeks)):
        w_ts = weeks[i]
        members = membership_at(pit, w_ts, N)
        if len(members) < N:
            continue  # PIT fino: meses con <N candidatos quedan excluidos (v1.1/P2)
        w_prev_ts = weeks[i - 1]
        form_end = w_prev_ts - pd.Timedelta(days=1)  # cierre de la semana w-2 = fin formacion
        form_start = weeks[i - 2 - L]

        cand: list[tuple[str, float]] = []
        for s in members:
            if s not in form.columns:
                continue
            f = form.iloc[i].get(s, np.nan)
            if not np.isfinite(f):
                continue
            # entrada valorable: cierre de w-1 presente
            if not np.isfinite(close.iloc[i - 1].get(s, np.nan)):
                continue
            blocked = False
            for e in corp.get(s, ()):
                if form_start <= e <= form_end + pd.Timedelta(days=1):
                    blocked = True
                    break
            if blocked:
                continue
            cand.append((s, float(f)))
        if len(cand) < 3:
            continue
        elig_counts.append(len(cand))
        cand.sort(key=lambda x: -x[1])
        n_sel = max(1, math.ceil(len(cand) / 3))
        basket = [s for s, _ in cand[:n_sel]]

        # retorno de la semana w (close-to-close desde w-1); deslistados: el
        # panel ya usa el ultimo cierre observado; sin datos en w => 0 (flat)
        row_ret = ret_w.iloc[i]

        def _ret(s: str, _row: pd.Series = row_ret) -> float:
            r = _row.get(s, np.nan)
            return float(r) if np.isfinite(r) else 0.0

        w_new = {s: 1.0 / n_sel for s in basket}
        # costes de rebalanceo (entrada/salida) por nombre
        cost = 0.0
        turnover = 0.0
        for s in set(w_new) | set(prev_w):
            dw = abs(w_new.get(s, 0.0) - prev_w.get(s, 0.0))
            if dw <= 1e-12:
                continue
            turnover += dw
            notional = dw * capital_usdt
            dv = panel.daily_vol.iloc[i].get(s, np.nan)
            participation = notional / float(dv) if np.isfinite(dv) and dv > 0 else np.inf
            rate = cost_model.side_cost_rate(participation)
            cost += dw * (rate if rate is not None else 0.10)  # sin liquidez: penalizado
        strat_rets[w_ts] = sum(w_new[s] * _ret(s) for s in basket) - cost
        turnovers.append(turnover)

        # benchmark: universo top-N equiponderado (los valorables)
        bmembers = [
            s
            for s in members
            if s in close.columns and np.isfinite(close.iloc[i - 1].get(s, np.nan))
        ]
        if bmembers:
            bw_new = {s: 1.0 / len(bmembers) for s in bmembers}
            bcost = 0.0
            for s in set(bw_new) | set(prev_b):
                dw = abs(bw_new.get(s, 0.0) - prev_b.get(s, 0.0))
                if dw <= 1e-12:
                    continue
                notional = dw * capital_usdt
                dv = panel.daily_vol.iloc[i].get(s, np.nan)
                part = notional / float(dv) if np.isfinite(dv) and dv > 0 else np.inf
                rate = cost_model.side_cost_rate(part)
                bcost += dw * (rate if rate is not None else 0.10)
            bench_rets[w_ts] = sum(bw_new[s] * _ret(s) for s in bmembers) - bcost
            prev_b = bw_new
        prev_w = w_new
        last_basket = basket

    idx = sorted(strat_rets)
    strat = pd.Series(strat_rets, dtype=float).reindex(idx)
    bench = pd.Series(bench_rets, dtype=float).reindex(idx).fillna(0.0)
    n_weeks = len(strat)
    return H2Result(
        strat_ret=strat,
        bench_ret=bench,
        weeks_used=n_weeks,
        first_week=str(idx[0].date()) if n_weeks else "",
        last_week=str(idx[-1].date()) if n_weeks else "",
        mean_eligible=float(np.mean(elig_counts)) if elig_counts else 0.0,
        turnover_per_year=float(np.sum(turnovers) / max(1, n_weeks) * 52.0),
        last_basket=last_basket,
        diagnostics={"n_weeks_skipped_thin": 0},
    )
