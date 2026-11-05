"""Motor Cuantitativo y de Backtesting CRUISE PRO (M6.5).

Evalúa las optimizaciones de frontera sobre el motor CRUISE (4H) y MARATHON (1D):
1. Regla 1: Rotación Dinámica de Capital por Momentum (40% Top 1, 25% Top 2/3, 10% Top 4).
2. Regla 2: Piramidación Protectora a Riesgo Cero (Add-on de 25% con SL blindado a >= +0.5R).

Período de Evaluación: 2024-01-01 a 2026-11-02 (Cesta Elite: BTC, ETH, SOL, SUI).
"""

from __future__ import annotations

import json
import math
from datetime import UTC
from typing import Any

import numpy as np
import pandas as pd

from qa.agent.capital import load_costs
from qa.backtest.trials import TrialLedger
from qa.data.paths import get_root
from qa.research.multi_horizon_runner import (
    ELITE_BASKET,
    _compute_metrics,
    fetch_or_load_klines,
    simulate_marathon,
)
from qa.stats.metrics import max_drawdown, sharpe_ann, sortino_ann


def compute_30d_momentum_weights(
    klines_1d: dict[str, pd.DataFrame],
    symbols: list[str] = ELITE_BASKET,
    window_days: int = 30,
) -> pd.DataFrame:
    """Calcula la serie causal de ponderaciones según el retorno rodante de 30 días.

    Ranking:
    - Top 1: 40% (0.40)
    - Top 2 & 3: 25% (0.25)
    - Top 4: 10% (0.10)
    """
    closes = {s: klines_1d[s].set_index("open_time")["close"].astype(float) for s in symbols}
    df_close = pd.DataFrame(closes).sort_index()

    # Retorno relativo rodante de 30 días: Close(t) / Close(t - 30)
    df_score = df_close / df_close.shift(window_days)
    df_score = df_score.bfill().fillna(1.0)

    # Filtrar desde 2024 en adelante
    start_ts = pd.Timestamp("2024-01-01", tz=UTC)
    df_score_active = df_score[df_score.index >= start_ts]

    def _rank_row(row: pd.Series) -> pd.Series:
        ranks = row.rank(ascending=False, method="first")
        w: dict[str, float] = {}
        for sym, r in ranks.items():
            if r == 1:
                w[sym] = 0.40
            elif r in (2, 3):
                w[sym] = 0.25
            else:
                w[sym] = 0.10
        return pd.Series(w)

    df_weights = df_score_active.apply(_rank_row, axis=1)
    return df_weights


def simulate_cruise_pro(
    df_4h: pd.DataFrame,
    df_1d: pd.DataFrame,
    btc_1d: pd.DataFrame,
    symbol: str,
    costs: dict[str, Any],
    initial_capital: float = 1000.0,
    risk_pct: float = 0.035,
    enable_pyramiding: bool = True,
    weight_series: pd.Series | None = None,
) -> dict[str, Any]:
    """Simulación CRUISE PRO con Trailing Anti-Mecha y Piramidación a Riesgo Cero."""
    fee_rt = float(costs["perp_usdm"]["maker_fee"]) + float(costs["perp_usdm"]["taker_fee"])

    c_4h = df_4h["close"].astype(float)
    l_4h = df_4h["low"].astype(float)
    o_4h = df_4h["open"].astype(float)
    ema21_4h = c_4h.ewm(span=21, adjust=False).mean()

    c_1d = df_1d["close"].astype(float)
    sma50_1d = c_1d.rolling(50).mean()

    c_btc = btc_1d["close"].astype(float)
    sma200_btc = c_btc.rolling(200).mean()

    capital = initial_capital
    peak_cap = initial_capital
    max_dd_val = 0.0
    dd_start_idx: int | None = None
    max_dd_dur = 0

    trades: list[dict[str, Any]] = []
    daily_returns: list[float] = []

    active_trade: dict[str, Any] | None = None
    min_bars = 40
    n = len(df_4h)

    last_day: str | None = None
    day_open_cap = capital

    for t in range(min_bars, n):
        row = df_4h.iloc[t]
        open_val = float(o_4h.iloc[t])
        close_val = float(c_4h.iloc[t])
        low_val = float(l_4h.iloc[t])
        cur_day = str(row["open_time"])[:10]

        # Tracking diario de retornos
        if last_day is None:
            last_day = cur_day
            day_open_cap = capital
        elif cur_day != last_day:
            day_ret = (capital / day_open_cap - 1.0) if day_open_cap > 0 else 0.0
            daily_returns.append(day_ret)
            last_day = cur_day
            day_open_cap = capital

        # 1. Gestionar posición activa si existe
        if active_trade is not None:
            entry_px = active_trade["entry_price"]
            sl = active_trade["sl"]
            size_usd = active_trade["size_usd"]
            dist_sl = active_trade["dist_sl"]
            risk_usd = active_trade["risk_usd"]

            # Regla Anti-Wick: Solo se liquida si la vela de 4H CIERRA por debajo del SL
            if close_val < sl:
                exit_px = close_val
                if not active_trade.get("pyramided", False):
                    pnl_gross = size_usd * (exit_px / entry_px - 1.0)
                    fee = size_usd * fee_rt
                    pnl_net = pnl_gross - fee
                else:
                    add_px = active_trade["add_entry_price"]
                    add_sz = active_trade["add_size_usd"]
                    pnl_init = size_usd * (exit_px / entry_px - 1.0) - size_usd * fee_rt
                    pnl_add = add_sz * (exit_px / add_px - 1.0) - add_sz * fee_rt
                    pnl_net = pnl_init + pnl_add

                capital += pnl_net
                active_trade["realized_pnl"] = pnl_net
                active_trade["exit_price"] = exit_px
                active_trade["exit_reason"] = (
                    "PYRAMID_SL_CLOSE" if active_trade.get("pyramided") else "STRUCTURAL_SL_CLOSE"
                )
                active_trade["duration_hours"] = (t - active_trade["opened_idx"]) * 4
                trades.append(active_trade)
                active_trade = None

            else:
                # Actualizar Trailing estructural: mínimo de las últimas 8 velas de 4H
                recent_swing_low = float(l_4h.iloc[max(0, t - 8) : t].min())
                active_trade["sl"] = max(sl, recent_swing_low)

                # Tracking del máximo R no realizado
                unrealized_r = (close_val - entry_px) / dist_sl
                if unrealized_r > active_trade.get("peak_r", 0.0):
                    active_trade["peak_r"] = unrealized_r

                # Piramidación Protectora a Riesgo Cero
                if enable_pyramiding and not active_trade.get("pyramided", False):
                    # Condición 1: Ganancia no realizada histórica o actual >= +4.0R
                    reached_4r = active_trade.get("peak_r", 0.0) >= 4.0
                    # Condición 2: Trailing Stop actual ya asegura beneficio >= +1.5R
                    sl_locked_r = (active_trade["sl"] - entry_px) / dist_sl
                    secured_1_5r = sl_locked_r >= 1.5

                    if reached_4r and secured_1_5r:
                        e21_val = float(ema21_4h.iloc[t])
                        # Toque a EMA21(4H) con tolerancia de 0.6%
                        pullback_ema = low_val <= (e21_val * 1.006)
                        # Rechazo alcista en vela cerrada (Close > Open y Close >= EMA21)
                        bullish_reject = (close_val > open_val) and (close_val >= e21_val)

                        if pullback_ema and bullish_reject:
                            add_size_usd = round(0.25 * size_usd, 2)
                            add_entry_price = close_val

                            # Blindaje de Riesgo Cero:
                            # Requerimos que ante desplome inmediato a sl_new:
                            # PnL_net(sl_new) >= 0.5 * risk_usd
                            total_fees = (size_usd + add_size_usd) * fee_rt
                            target_profit = 0.5 * risk_usd + total_fees
                            target_val = size_usd + add_size_usd + target_profit
                            denom = (size_usd / entry_px) + (add_size_usd / add_entry_price)
                            sl_zero_risk = target_val / denom

                            active_trade["sl"] = max(active_trade["sl"], sl_zero_risk)
                            active_trade["pyramided"] = True
                            active_trade["add_size_usd"] = add_size_usd
                            active_trade["add_entry_price"] = add_entry_price
                            active_trade["pyramid_idx"] = t

        # 2. Evaluar apertura de nueva posición si no hay trade activo
        if active_trade is None and t >= 10:
            cur_time = row["open_time"]
            d1_sub = df_1d[df_1d["open_time"] <= cur_time]
            btc_sub = btc_1d[btc_1d["open_time"] <= cur_time]

            macro_bull = True
            if len(btc_sub) >= 50:
                last_btc_c = float(btc_sub["close"].iloc[-1])
                btc_sma200_val = (
                    float(sma200_btc.loc[btc_sub.index[-1]])
                    if not math.isnan(sma200_btc.loc[btc_sub.index[-1]])
                    else last_btc_c
                )
                macro_bull = last_btc_c >= btc_sma200_val

            asset_trend_bull = True
            if len(d1_sub) >= 20:
                last_d1_c = float(d1_sub["close"].iloc[-1])
                d1_sma50_val = (
                    float(sma50_1d.loc[d1_sub.index[-1]])
                    if not math.isnan(sma50_1d.loc[d1_sub.index[-1]])
                    else last_d1_c
                )
                asset_trend_bull = last_d1_c >= d1_sma50_val

            e21_val = float(ema21_4h.iloc[t])
            pullback_hit = low_val <= (e21_val * 1.006)
            bullish_turn = close_val > open_val and close_val > e21_val

            if macro_bull and asset_trend_bull and pullback_hit and bullish_turn:
                swing_low_8 = float(l_4h.iloc[max(0, t - 8) : t + 1].min())
                dist_sl = max(close_val - swing_low_8, close_val * 0.02)
                sl = close_val - dist_sl

                # Escalado por momentum si weight_series está activo
                w_factor = 1.0
                if weight_series is not None:
                    # Encontrar el peso a la fecha actual
                    cur_ts = pd.Timestamp(cur_day, tz=UTC)
                    matching_ts = weight_series.index[weight_series.index <= cur_ts]
                    if len(matching_ts) > 0:
                        w_val = float(weight_series.loc[matching_ts[-1]])
                        w_factor = w_val / 0.25

                risk_usd = capital * risk_pct * w_factor
                dist_sl_pct = dist_sl / close_val
                size_usd = round(risk_usd / max(0.005, dist_sl_pct), 2)
                size_usd = min(size_usd, capital * 3.5 * w_factor)

                active_trade = {
                    "strategy": "CRUISE_PRO",
                    "symbol": symbol,
                    "direction": "LONG",
                    "entry_price": close_val,
                    "size_usd": size_usd,
                    "dist_sl": dist_sl,
                    "sl": sl,
                    "tp": 0.0,
                    "risk_usd": risk_usd,
                    "opened_idx": t,
                    "pyramided": False,
                    "peak_r": 0.0,
                    "realized_pnl": 0.0,
                }

        # Drawdown tracking
        if capital > peak_cap:
            peak_cap = capital
            if dd_start_idx is not None:
                cur_dur = (t - dd_start_idx) * 4 // 24
                if cur_dur > max_dd_dur:
                    max_dd_dur = cur_dur
                dd_start_idx = None
        else:
            if dd_start_idx is None:
                dd_start_idx = t
            dd = (peak_cap - capital) / peak_cap
            if dd > max_dd_val:
                max_dd_val = dd

    # Cerrar trade remanente
    if active_trade is not None:
        exit_px = float(c_4h.iloc[-1])
        entry_px = active_trade["entry_price"]
        size_usd = active_trade["size_usd"]
        if not active_trade.get("pyramided", False):
            pnl_gross = size_usd * (exit_px / entry_px - 1.0)
            fee = size_usd * fee_rt
            pnl_net = pnl_gross - fee
        else:
            add_px = active_trade["add_entry_price"]
            add_sz = active_trade["add_size_usd"]
            pnl_init = size_usd * (exit_px / entry_px - 1.0) - size_usd * fee_rt
            pnl_add = add_sz * (exit_px / add_px - 1.0) - add_sz * fee_rt
            pnl_net = pnl_init + pnl_add

        capital += pnl_net
        active_trade["realized_pnl"] = pnl_net
        active_trade["exit_price"] = exit_px
        active_trade["exit_reason"] = "TERMINAL_CLOSE"
        active_trade["duration_hours"] = (n - 1 - active_trade["opened_idx"]) * 4
        trades.append(active_trade)
        active_trade = None

    if day_open_cap > 0:
        daily_returns.append(capital / day_open_cap - 1.0)

    strat_label = "CRUISE_PRO" if enable_pyramiding else "CRUISE"
    return _compute_metrics(
        strat_label,
        symbol,
        initial_capital,
        capital,
        max_dd_val,
        max_dd_dur,
        trades,
        daily_returns,
    )


def evaluate_cruise_pro_suite() -> dict[str, Any]:
    """Evalúa las 4 configuraciones comparativas más el blend con Marathon."""
    root = get_root()
    ledger = TrialLedger(root)
    costs = load_costs(root)

    print("=================================================================")
    print(" [1/3] Cargando Datos de la Cesta Elite (1D y 4H)")
    print("=================================================================")
    k_1d = fetch_or_load_klines(ELITE_BASKET, "1d", 2023)
    k_4h = fetch_or_load_klines(ELITE_BASKET, "4h", 2024)
    btc_1d = k_1d["BTCUSDT"]

    print("=================================================================")
    print(" [2/3] Calculando Ponderaciones Dinámicas de Momentum (30 Días)")
    print("=================================================================")
    df_weights = compute_30d_momentum_weights(k_1d, ELITE_BASKET, window_days=30)
    print("Promedios de peso en el ciclo 2024-2026:")
    print(df_weights.mean())

    def _simulate_basket(
        enable_pyr: bool,
        use_dyn_weight: bool,
        name: str,
    ) -> dict[str, Any]:
        asset_res: dict[str, Any] = {}
        for sym in ELITE_BASKET:
            res = simulate_cruise_pro(
                df_4h=k_4h[sym],
                df_1d=k_1d[sym],
                btc_1d=btc_1d,
                symbol=sym,
                costs=costs,
                initial_capital=1000.0,
                risk_pct=0.035,
                enable_pyramiding=enable_pyr,
                weight_series=None,
            )
            asset_res[sym] = res

        # Agregación de cartera
        min_l = min(len(r["daily_returns"]) for r in asset_res.values())
        mat = np.column_stack([r["daily_returns"][-min_l:] for r in asset_res.values()])

        if use_dyn_weight:
            w_mat = df_weights.iloc[-min_l:][ELITE_BASKET].values
            w_mat = w_mat / w_mat.sum(axis=1, keepdims=True)
            port_ret = (mat * w_mat).sum(axis=1)
        else:
            port_ret = mat.mean(axis=1)

        tot_ret = float(np.prod(1.0 + port_ret) - 1.0)
        n_days = len(port_ret)
        y = n_days / 365.0
        cagr = float((1.0 + tot_ret) ** (1.0 / y) - 1.0)
        sh = sharpe_ann(port_ret)
        so = sortino_ann(port_ret)
        mdd = max_drawdown(port_ret)

        tot_trades = sum(r["total_trades"] for r in asset_res.values())
        tot_wins = sum(
            len([t for t in r["trades"] if t["realized_pnl"] > 0])
            for r in asset_res.values()
        )
        wr = round(tot_wins / tot_trades * 100.0, 1) if tot_trades > 0 else 0.0

        all_r = [
            t["realized_pnl"] / max(1.0, t.get("risk_usd", 1.0))
            for r in asset_res.values()
            for t in r["trades"]
        ]
        max_r_global = max(all_r) if all_r else 0.0
        avg_r_global = float(np.mean(all_r)) if all_r else 0.0

        tot_w_pnl = sum(
            sum(t["realized_pnl"] for t in r["trades"] if t["realized_pnl"] > 0)
            for r in asset_res.values()
        )
        tot_l_pnl = abs(
            sum(
                sum(t["realized_pnl"] for t in r["trades"] if t["realized_pnl"] <= 0)
                for r in asset_res.values()
            )
        )
        pf = round(tot_w_pnl / tot_l_pnl, 2) if tot_l_pnl > 0 else 0.0

        all_pcts = [
            (t["exit_price"] / t["entry_price"] - 1.0) * 100.0
            for r in asset_res.values()
            for t in r["trades"]
            if t.get("entry_price") and t.get("exit_price")
        ]
        max_gain_pct = max(all_pcts) if all_pcts else 0.0

        all_dur = [t.get("duration_hours", 0) for r in asset_res.values() for t in r["trades"]]
        avg_dur_d = round(float(np.mean(all_dur)) / 24.0, 1) if all_dur else 0.0

        tot_pyr = sum(
            len([t for t in r["trades"] if t.get("pyramided")])
            for r in asset_res.values()
        )

        return {
            "name": name,
            "portfolio": {
                "strategy": name,
                "total_return_pct": round(tot_ret * 100.0, 2),
                "cagr_pct": round(cagr * 100.0, 2),
                "sharpe_ann": round(sh, 3),
                "sortino_ann": round(so, 3),
                "max_drawdown_pct": round(mdd * 100.0, 2),
                "total_trades": tot_trades,
                "win_rate_pct": wr,
                "profit_factor": pf,
                "expectancy_r": round(avg_r_global, 2),
                "max_r_trade": round(max_r_global, 2),
                "max_pct_gain": round(max_gain_pct, 2),
                "avg_duration_days": avg_dur_d,
                "pyramided_trades": tot_pyr,
            },
            "per_asset": asset_res,
            "port_returns": port_ret,
        }

    print("\n=================================================================")
    print(" [3/3] Simulando Configuraciones Comparativas")
    print("=================================================================")

    # 1. Baseline Cruise
    res_base = _simulate_basket(False, False, "CRUISE_BASELINE")
    print(f" -> Baseline: Ret={res_base['portfolio']['total_return_pct']}%")

    # 2. Cruise + Piramidación Protectora
    res_pyr = _simulate_basket(True, False, "CRUISE_PYRAMIDING")
    print(f" -> Con Piramidación: Ret={res_pyr['portfolio']['total_return_pct']}%")

    # 3. Cruise + Rotación Dinámica Momentum
    res_dyn = _simulate_basket(False, True, "CRUISE_DYNAMIC_MOMENTUM")
    print(f" -> Con Rotación Momentum: Ret={res_dyn['portfolio']['total_return_pct']}%")

    # 4. Cruise PRO (Combinada)
    res_pro = _simulate_basket(True, True, "CRUISE_PRO_COMBINED")
    print(f" -> CRUISE PRO Combinada: Ret={res_pro['portfolio']['total_return_pct']}%")

    # Simular Marathon para el blend de cartera
    marathon_res: dict[str, Any] = {}
    for sym in ELITE_BASKET:
        marathon_res[sym] = simulate_marathon(
            df_1d=k_1d[sym],
            btc_1d=btc_1d,
            symbol=sym,
            costs=costs,
            initial_capital=1000.0,
            risk_pct=0.04,
        )
    min_m = min(len(r["daily_returns"]) for r in marathon_res.values())
    mat_m = np.column_stack([r["daily_returns"][-min_m:] for r in marathon_res.values()])
    marathon_port_ret = mat_m.mean(axis=1)

    # 5. Cartera Híbrida Institucional: 70% Cruise PRO + 30% Marathon Macro
    min_hybrid = min(len(res_pro["port_returns"]), len(marathon_port_ret))
    r_pro_tail = res_pro["port_returns"][-min_hybrid:]
    r_mar_tail = marathon_port_ret[-min_hybrid:]
    port_hybrid = 0.70 * r_pro_tail + 0.30 * r_mar_tail
    tot_hyb = float(np.prod(1.0 + port_hybrid) - 1.0)
    cagr_hyb = float((1.0 + tot_hyb) ** (1.0 / (min_hybrid / 365.0)) - 1.0)
    sh_hyb = sharpe_ann(port_hybrid)
    so_hyb = sortino_ann(port_hybrid)
    mdd_hyb = max_drawdown(port_hybrid)

    hybrid_metrics = {
        "strategy": "HYBRID_CRUISE_PRO_MARATHON",
        "total_return_pct": round(tot_hyb * 100.0, 2),
        "cagr_pct": round(cagr_hyb * 100.0, 2),
        "sharpe_ann": round(sh_hyb, 3),
        "sortino_ann": round(so_hyb, 3),
        "max_drawdown_pct": round(mdd_hyb * 100.0, 2),
    }
    print(
        f" -> Cartera Híbrida (70% Cruise PRO / 30% Marathon): "
        f"Ret={hybrid_metrics['total_return_pct']}%, MDD={hybrid_metrics['max_drawdown_pct']}%"
    )

    # Registrar en Ledger DuckDB
    for suite_name, obj in [
        ("CRUISE_BASELINE", res_base["portfolio"]),
        ("CRUISE_PYRAMIDING", res_pyr["portfolio"]),
        ("CRUISE_DYNAMIC_MOMENTUM", res_dyn["portfolio"]),
        ("CRUISE_PRO_COMBINED", res_pro["portfolio"]),
        ("HYBRID_CRUISE_PRO_MARATHON", hybrid_metrics),
    ]:
        with ledger.trial(
            hypothesis="CRUISE_PRO",
            cell_id="FRONTIER_OPTIMIZATION",
            asset="PORTFOLIO_ELITE",
            kind="frontier_optimization",
            config={"suite": suite_name},
            notes=f"Evaluación {suite_name} 2024-2026",
        ) as t_ctx:
            t_ctx.set_metrics({
                "cagr": obj["cagr_pct"],
                "sharpe_ann": obj["sharpe_ann"],
                "max_drawdown": obj["max_drawdown_pct"],
                "total_return": obj["total_return_pct"],
            })
    ledger.close()

    # Consolidar JSON de resumen
    summary_out = {
        "portfolio_comparison": {
            "baseline": res_base["portfolio"],
            "pyramiding_only": res_pyr["portfolio"],
            "dynamic_momentum_only": res_dyn["portfolio"],
            "cruise_pro_combined": res_pro["portfolio"],
            "hybrid_marathon": hybrid_metrics,
        },
        "per_asset_cruise_pro": {
            sym: {
                k: v
                for k, v in res_pro["per_asset"][sym].items()
                if k not in ("daily_returns", "trades")
            }
            for sym in ELITE_BASKET
        },
    }

    out_file = root / "reports" / "cruise_pro_summary.json"
    out_file.parent.mkdir(parents=True, exist_ok=True)
    out_file.write_text(json.dumps(summary_out, indent=2, default=str), encoding="utf-8")
    print(f"\nResumen cuantitativo exportado a: {out_file}")

    return summary_out


if __name__ == "__main__":
    evaluate_cruise_pro_suite()
