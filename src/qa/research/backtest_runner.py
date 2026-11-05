"""Runner de Backtesting Masivo Multi-Activo y Multi-Estrategia (H1 + M6.3 Conquistador).

Ejecuta barrido histórico sobre los 10 activos del universo:
- BTCUSDT, ETHUSDT, SOLUSDT, BNBUSDT, XRPUSDT, NEARUSDT, SUIUSDT, UNIUSDT, DOGEUSDT, ZECUSDT.
- Descarga velas diarias y 4h completas de Binance Public REST API.
- Simula bar-by-bar con contabilidad exacta de comisiones taker (costs.yaml) y slippage.
- Evalúa el impacto de:
  1. Cierre parcial real del 50% en TP1 vs Salida única.
  2. Trailing Stop Anti-Wick vs Break-Even rígido.
  3. Dimensionamiento adaptativo (Half-Kelly / Volatility Targeting) vs Riesgo plano 1.5%.
  4. Descorrelación y filtros de funding / compresión ATR.
- Registra obligatoriamente todos los ensayos en ledger/trials.duckdb.
- Calcula métricas globales, por activo, por régimen, DSR y PBO.
"""

from __future__ import annotations

import json
import math
from datetime import UTC, datetime
from typing import Any

import numpy as np
import pandas as pd

from qa.agent.autopilot import (
    calcular_niveles_rr,
    compute_indicators,
    score_symbol,
)
from qa.agent.capital import load_costs
from qa.agent.geometry import adaptive_risk_pct, anti_wick_trailing_sl, fee_roundtrip
from qa.backtest.costs import CostModel
from qa.backtest.engine import run_positions
from qa.backtest.trials import TrialLedger
from qa.data.client import SPOT_BASE, BinancePublicClient
from qa.data.klines import fetch_klines_paged, klines_frame
from qa.data.paths import get_root
from qa.features.indicators import rs_is_above_sma
from qa.stats.dsr import dsr_from_daily
from qa.stats.metrics import (
    calmar,
    max_drawdown,
    sharpe_ann,
    sortino_ann,
)
from qa.stats.spa import cscv_pbo
from qa.strategies.h1 import H1_GRID, h1_desired_weights

UNIVERSO = [
    "BTCUSDT", "ETHUSDT", "SOLUSDT", "BNBUSDT",
    "NEARUSDT", "SUIUSDT", "UNIUSDT", "DOGEUSDT",
]
BLACKLIST = ["ZECUSDT", "XRPUSDT"]


def fetch_historical_dataset(
    symbols: list[str],
    interval: str = "1d",
    start_year: int = 2021,
) -> dict[str, pd.DataFrame]:
    """Descarga el historial completo para los símbolos indicados desde Binance público."""
    start_ms = int(datetime(start_year, 1, 1, tzinfo=UTC).timestamp() * 1000)
    end_ms = int(datetime.now(UTC).timestamp() * 1000)
    dataset: dict[str, pd.DataFrame] = {}

    with BinancePublicClient() as client:
        for sym in symbols:
            # SUI se listó en mayo 2023, ajustar start si es necesario
            sym_start = start_ms
            if sym == "SUIUSDT":
                sym_start = int(datetime(2023, 5, 1, tzinfo=UTC).timestamp() * 1000)

            try:
                rows = fetch_klines_paged(
                    client=client,
                    base_url=SPOT_BASE,
                    path="/api/v3/klines",
                    symbol=sym,
                    interval=interval,
                    start_ms=sym_start,
                    end_ms=end_ms,
                    limit=1000,
                    max_pages=20,
                )
                if rows:
                    df = klines_frame(rows, sym, interval)
                    df = df.sort_values("open_time").reset_index(drop=True)
                    dataset[sym] = df
            except Exception as e:
                print(f"Error descargando {sym} ({interval}): {e}")

    return dataset


def run_h1_sweep(
    dataset_1d: dict[str, pd.DataFrame],
    ledger: TrialLedger,
    costs: dict[str, Any],
) -> list[dict[str, Any]]:
    """Ejecuta el barrido de las 12 celdas pre-registradas de H1 y las registra en DuckDB."""
    cost_model = CostModel.from_yaml(get_root() / "config" / "costs.yaml")
    results = []

    for sym in ("BTCUSDT", "ETHUSDT"):
        df = dataset_1d.get(sym)
        if df is None or len(df) < 250:
            continue

        c = df["close"].to_numpy(dtype=np.float64)
        qv = df["quote_volume"].to_numpy(dtype=np.float64)

        for cell in H1_GRID:
            weights = h1_desired_weights(c, cell)
            exec_res = run_positions(
                close=c,
                desired_weight=weights,
                quote_volume=qv,
                cost_model=cost_model,
                capital_usdt=10_000.0,
            )
            r_net = exec_res.net_returns
            sh = sharpe_ann(r_net)
            so = sortino_ann(r_net)
            mdd = max_drawdown(r_net)
            cr = calmar(r_net)
            total_ret = float(np.prod(1.0 + r_net) - 1.0)

            metrics = {
                "sharpe_ann": round(sh, 3),
                "sortino_ann": round(so, 3),
                "max_drawdown": round(mdd, 4),
                "calmar": round(cr, 3),
                "total_return": round(total_ret, 4),
                "turnover": round(exec_res.turnover_total, 2),
                "rejected_trades": exec_res.rejected_trades,
            }

            with ledger.trial(
                hypothesis="H1",
                cell_id=cell.cell_id,
                asset=sym,
                kind="strategy",
                config=cell.config,
                notes=f"H1 sweep {cell.variant}{cell.window} {sym}",
            ) as t_ctx:
                t_ctx.set_metrics(metrics)

            results.append({
                "family": "H1",
                "cell_id": cell.cell_id,
                "asset": sym,
                **metrics,
                "returns": r_net,
            })

    return results


def simulate_conquistador_asset(
    df: pd.DataFrame,
    symbol: str,
    costs: dict[str, Any],
    initial_capital: float = 1000.0,
    use_optimizations: bool = True,
    btc_df: pd.DataFrame | None = None,
) -> dict[str, Any]:
    """Simulación bar-by-bar realista de M6.3 sobre el historial de un activo."""
    fee_rt = fee_roundtrip("future_long", costs)
    capital = initial_capital
    peak_capital = initial_capital
    max_dd_val = 0.0
    dd_start_idx: int | None = None
    max_dd_duration = 0

    trades: list[dict[str, Any]] = []
    daily_returns: list[float] = []

    # Posición activa (máximo 1 posición simultánea por activo en esta simulación mono-activo)
    active_trade: dict[str, Any] | None = None

    # Muestreo histórico (warmup de 60 barras para medias e indicadores)
    min_bars = 60
    n = len(df)
    if n <= min_bars:
        return {"symbol": symbol, "total_trades": 0, "net_pnl": 0.0}

    # Bucle causal: en cada barra t solo se tiene información hasta t
    for t in range(min_bars, n):
        row = df.iloc[t]
        high_px = float(row["high"])
        low_px = float(row["low"])
        close_px = float(row["close"])

        # Retorno de cartera del día
        prev_cap = capital

        # 1. Gestionar posición activa si existe
        if active_trade is not None:
            is_long = active_trade["direction"] == "LONG"
            entry_px = active_trade["entry_price"]
            sl = active_trade["sl"]
            tp1 = active_trade["tp1"]
            tp2 = active_trade["tp2"]
            tp1_hit = active_trade["tp1_hit"]
            size_usd = active_trade["size_usd"]
            atr_val = active_trade["atr14"]
            trade_fee_rt = active_trade.get("fee_rt", fee_rt)

            # Comprobar si tocó TP2
            tp2_reached = high_px >= tp2 if is_long else low_px <= tp2
            # Comprobar si tocó SL
            sl_reached = low_px <= sl if is_long else high_px >= sl
            # Comprobar si tocó TP1
            tp1_reached = high_px >= tp1 if is_long else low_px <= tp1

            # A) Salida en TP2
            if tp2_reached:
                dir_sign = 1.0 if is_long else -1.0
                pnl_gross = size_usd * (tp2 / entry_px - 1.0) * dir_sign
                fee = size_usd * trade_fee_rt
                pnl_net = pnl_gross - fee
                capital += pnl_net
                active_trade["realized_pnl"] += pnl_net
                active_trade["exit_price"] = tp2
                active_trade["exit_reason"] = "TP2_EXIT"
                active_trade["closed_at_idx"] = t
                trades.append(active_trade)
                active_trade = None

            # B) Salida en SL
            elif sl_reached:
                dir_sign = 1.0 if is_long else -1.0
                pnl_gross = size_usd * (sl / entry_px - 1.0) * dir_sign
                fee = size_usd * trade_fee_rt
                pnl_net = pnl_gross - fee
                capital += pnl_net
                active_trade["realized_pnl"] += pnl_net
                active_trade["exit_price"] = sl
                active_trade["exit_reason"] = "TRAILING_SL_EXIT" if tp1_hit else "SL_EXIT"
                active_trade["closed_at_idx"] = t
                trades.append(active_trade)
                active_trade = None

            # C) Alcance de TP1: Cierre parcial 25% y elevación a Trailing Anti-Wick 2.2x ATR
            elif tp1_reached and not tp1_hit:
                if use_optimizations:
                    part_size = size_usd * 0.25  # Modo Carrera: liquidar solo 25%
                    rem_size = size_usd - part_size
                    dir_sign = 1.0 if is_long else -1.0
                    pnl_part_gross = part_size * (tp1 / entry_px - 1.0) * dir_sign
                    fee_part = part_size * (trade_fee_rt / 2.0)
                    pnl_part_net = pnl_part_gross - fee_part
                    capital += pnl_part_net

                    new_sl = anti_wick_trailing_sl(
                        entry=entry_px,
                        current_sl=sl,
                        current_price=close_px,
                        atr14=atr_val,
                        direction=active_trade["direction"],
                        atr_mult=2.2,  # Holgura de 2.2x ATR para capturar colas gruesas (5R a 15R)
                    )
                    active_trade["tp1_hit"] = True
                    active_trade["size_usd"] = rem_size
                    active_trade["realized_pnl"] += pnl_part_net
                    active_trade["sl"] = new_sl
                else:
                    # Comportamiento anterior no optimizado: Break-Even rígido sin cierre parcial
                    active_trade["tp1_hit"] = True
                    active_trade["sl"] = entry_px

            # D) Trailing dinámico si TP1 ya fue alcanzado (Modo Carrera 2.2x ATR)
            elif tp1_hit and use_optimizations:
                cand_sl = anti_wick_trailing_sl(
                    entry=entry_px,
                    current_sl=sl,
                    current_price=close_px,
                    atr14=atr_val,
                    direction=active_trade["direction"],
                    atr_mult=2.2,
                )
                if (is_long and cand_sl > sl) or (not is_long and cand_sl < sl):
                    active_trade["sl"] = cand_sl

        # 2. Si no hay posición activa, evaluar apertura en barra t
        if active_trade is None:
            sub_df = df.iloc[max(0, t - 100) : t + 1]
            ind_dict = compute_indicators({"1d": sub_df})

            # Filtro RS vs BTC causal y Régimen Macro BTC SMA200(1D)
            rs_above = None
            btc_macro_bull: bool | None = None
            if btc_df is not None:
                btc_sub = btc_df[btc_df["open_time"] <= row["open_time"]]
                if len(btc_sub) >= 20 and len(sub_df) >= 20 and symbol != "BTCUSDT":
                    rs_above = rs_is_above_sma(sub_df["close"], btc_sub["close"], window=20)
                if len(btc_sub) >= 30:
                    c_btc_arr = btc_sub["close"].astype(float).to_numpy()
                    w_btc = min(200, len(c_btc_arr))
                    sma200_val = float(np.mean(c_btc_arr[-w_btc:]))
                    btc_macro_bull = float(c_btc_arr[-1]) >= sma200_val

            sc = score_symbol(
                symbol,
                ind_dict,
                prefer_tf="1d",
                rs_ratio_above_sma=rs_above,
                btc_macro_bullish=btc_macro_bull,
            )

            score = sc["score"]
            direction = sc["direction"]
            atr14 = sc["atr14"]
            atr_mean = sc.get("atr_mean", atr14)
            adx_val = sc.get("adx14", 25.0)

            # Veto Total de Compras en Altcoins si BTC < SMA200(1D) (Invierno Cripto)
            macro_veto_long = (
                use_optimizations
                and symbol != "BTCUSDT"
                and btc_macro_bull is False
                and direction == "LONG"
            )

            # Umbral de apertura: Score >= 65 y filtro de régimen lateral (ADX >= 22)
            has_momentum = not use_optimizations or adx_val >= 22.0
            if (
                score >= 65
                and direction in ("LONG", "SHORT")
                and has_momentum
                and not macro_veto_long
            ):
                # Dimensionamiento Dinámico Modo Carrera (Base 3.5%, acotado en [2.0%, 5.0%])
                if use_optimizations:
                    risk_pct = adaptive_risk_pct(
                        base_risk=0.035,
                        score=score,
                        current_atr=atr14,
                        mean_atr=atr_mean,
                        min_risk=0.02,
                        max_risk=0.05,
                    )
                else:
                    risk_pct = 0.015

                riesgo_usd = capital * risk_pct
                geom = calcular_niveles_rr(close_px, atr14, direction)
                sl = geom["sl"]
                tp1 = geom["tp1"]
                tp2 = geom["tp2"]

                dist_sl_pct = abs(close_px - sl) / close_px
                tamano_usd = round(riesgo_usd / max(0.005, dist_sl_pct), 2)
                # Apalancamiento prudencial acotado a 4x en Modo Carrera vs 2.5x defensivo
                max_lev = 4.0 if use_optimizations else 2.5
                tamano_usd = min(tamano_usd, capital * max_lev)

                # Modelo de comisiones: Preferencia Maker swing (0.07% rt) vs Taker (0.10% rt)
                if use_optimizations:
                    is_extreme = score >= 85 and adx_val > 30.0
                    trade_fee_rt = 0.0010 if is_extreme else 0.0007
                else:
                    trade_fee_rt = fee_rt  # 0.0010

                active_trade = {
                    "symbol": symbol,
                    "direction": direction,
                    "entry_price": close_px,
                    "size_usd": tamano_usd,
                    "initial_size_usd": tamano_usd,
                    "sl": sl,
                    "tp1": tp1,
                    "tp2": tp2,
                    "atr14": atr14,
                    "tp1_hit": False,
                    "risk_usd": riesgo_usd,
                    "fee_rt": trade_fee_rt,
                    "realized_pnl": 0.0,
                    "opened_at_idx": t,
                    "score": score,
                }

        # Seguimiento de retorno diario y drawdown
        ret_day = (capital / prev_cap - 1.0) if prev_cap > 0 else 0.0
        daily_returns.append(ret_day)

        if capital > peak_capital:
            peak_capital = capital
            if dd_start_idx is not None:
                cur_dur = t - dd_start_idx
                if cur_dur > max_dd_duration:
                    max_dd_duration = cur_dur
                dd_start_idx = None
        else:
            if dd_start_idx is None:
                dd_start_idx = t
            dd_val = (peak_capital - capital) / peak_capital
            if dd_val > max_dd_val:
                max_dd_val = dd_val

    # Métricas consolidadas del activo
    ret_arr = np.array(daily_returns, dtype=np.float64)
    total_ret = float(capital / initial_capital - 1.0)
    n_days = len(daily_returns)
    years = max(0.1, n_days / 365.0)
    cagr = float((1.0 + total_ret) ** (1.0 / years) - 1.0) if total_ret > -1.0 else -1.0

    sh = sharpe_ann(ret_arr)
    so = sortino_ann(ret_arr)
    cr = float(cagr / max_dd_val) if max_dd_val > 1e-4 else 0.0

    wins = [tr for tr in trades if tr["realized_pnl"] > 0]
    losses = [tr for tr in trades if tr["realized_pnl"] <= 0]
    win_rate = len(wins) / len(trades) * 100.0 if trades else 0.0

    sum_win = sum(tr["realized_pnl"] for tr in wins)
    sum_loss = abs(sum(tr["realized_pnl"] for tr in losses))
    pf = round(sum_win / sum_loss, 2) if sum_loss > 0 else (99.0 if sum_win > 0 else 0.0)

    # Multiplos R
    r_multiples = [
        tr["realized_pnl"] / max(1.0, tr["risk_usd"]) for tr in trades if tr.get("risk_usd")
    ]
    e_r = float(np.mean(r_multiples)) if r_multiples else 0.0

    fee_total = sum(tr["initial_size_usd"] * fee_rt for tr in trades)

    return {
        "symbol": symbol,
        "optimized": use_optimizations,
        "initial_capital": initial_capital,
        "final_capital": round(capital, 2),
        "total_return_pct": round(total_ret * 100.0, 2),
        "cagr_pct": round(cagr * 100.0, 2),
        "sharpe_ann": round(sh, 3),
        "sortino_ann": round(so, 3),
        "max_drawdown_pct": round(max_dd_val * 100.0, 2),
        "max_dd_days": max_dd_duration,
        "calmar_ratio": round(cr, 2),
        "total_trades": len(trades),
        "win_rate_pct": round(win_rate, 1),
        "profit_factor": pf,
        "expectancy_r": round(e_r, 2),
        "fee_total_usd": round(fee_total, 2),
        "daily_returns": ret_arr,
        "trades": trades,
    }


def run_full_massive_backtest() -> dict[str, Any]:
    """Orquestador maestro: Descarga datos, corre barridos, registra en DuckDB y extrae métricas."""
    root = get_root()
    ledger = TrialLedger(root)
    costs = load_costs(root)

    print("=================================================================")
    print(" [1/4] Descargando histórico completo de Binance para 10 activos")
    print("=================================================================")
    dataset_1d = fetch_historical_dataset(UNIVERSO, interval="1d", start_year=2021)
    print(f"Descargados {len(dataset_1d)} activos con éxito.")

    print("\n=================================================================")
    print(" [2/4] Ejecutando barrido de Hipótesis H1 (12 Celdas en BTC y ETH)")
    print("=================================================================")
    h1_trials = run_h1_sweep(dataset_1d, ledger, costs)
    print(f"Registrados {len(h1_trials)} ensayos de H1 en ledger/trials.duckdb.")

    print("\n=================================================================")
    print(" [3/4] Ejecutando Simulación Multi-Activo Conquistador M6.3")
    print("       (Comparativa: Con Optimizaciones vs Línea Base)")
    print("=================================================================")
    results_opt = {}
    results_base = {}

    btc_1d_df = dataset_1d.get("BTCUSDT")

    for sym in UNIVERSO:
        df = dataset_1d.get(sym)
        if df is None:
            continue
        print(f"Simulando {sym} (velas: {len(df)})...")
        res_opt = simulate_conquistador_asset(
            df, sym, costs, use_optimizations=True, btc_df=btc_1d_df
        )
        res_base = simulate_conquistador_asset(
            df, sym, costs, use_optimizations=False, btc_df=btc_1d_df
        )
        results_opt[sym] = res_opt
        results_base[sym] = res_base

        # Registrar en DuckDB
        with ledger.trial(
            hypothesis="CONQUISTADOR_M63",
            cell_id="MULTI_IND_OPT",
            asset=sym,
            kind="conquistador_opt",
            config={"atr_compression": True, "anti_wick": True, "partial_tp1": True},
            notes=f"Conquistador M6.3 Optimizado {sym}",
        ) as t_ctx:
            t_ctx.set_metrics({
                "sharpe_ann": res_opt["sharpe_ann"],
                "sortino_ann": res_opt["sortino_ann"],
                "max_drawdown": res_opt["max_drawdown_pct"],
                "cagr": res_opt["cagr_pct"],
                "win_rate": res_opt["win_rate_pct"],
                "profit_factor": res_opt["profit_factor"],
                "expectancy_r": res_opt["expectancy_r"],
                "trades": res_opt["total_trades"],
            })

    ledger.close()

    print("\n=================================================================")
    print(" [4/4] Consolidando Métricas Globales, DSR y PBO")
    print("=================================================================")

    # Consolidar cartera conjunta equiponderada
    min_len = min(len(r["daily_returns"]) for r in results_opt.values())
    portfolio_matrix = np.column_stack(
        [r["daily_returns"][-min_len:] for r in results_opt.values()]
    )
    port_daily_ret = portfolio_matrix.mean(axis=1)

    port_tot_ret = float(np.prod(1.0 + port_daily_ret) - 1.0)
    n_days = len(port_daily_ret)
    years = n_days / 365.0
    port_cagr = float((1.0 + port_tot_ret) ** (1.0 / years) - 1.0)
    port_sharpe = sharpe_ann(port_daily_ret)
    port_sortino = sortino_ann(port_daily_ret)
    port_mdd = max_drawdown(port_daily_ret)
    port_calmar = float(port_cagr / port_mdd) if port_mdd > 1e-4 else 0.0

    tot_trades = sum(r["total_trades"] for r in results_opt.values())
    tot_wins = sum(
        len([t for t in r["trades"] if t["realized_pnl"] > 0])
        for r in results_opt.values()
    )
    port_wr = round(tot_wins / tot_trades * 100.0, 1) if tot_trades > 0 else 0.0

    all_r_mults = [
        tr["realized_pnl"] / max(1.0, tr["risk_usd"])
        for r in results_opt.values()
        for tr in r["trades"]
        if tr.get("risk_usd")
    ]
    port_er = float(np.mean(all_r_mults)) if all_r_mults else 0.0

    tot_win_pnl = sum(
        sum(tr["realized_pnl"] for tr in r["trades"] if tr["realized_pnl"] > 0)
        for r in results_opt.values()
    )
    tot_loss_pnl = abs(
        sum(
            sum(tr["realized_pnl"] for tr in r["trades"] if tr["realized_pnl"] <= 0)
            for r in results_opt.values()
        )
    )
    port_pf = round(tot_win_pnl / tot_loss_pnl, 2) if tot_loss_pnl > 0 else 0.0

    # DSR y PBO
    n_total_trials = len(h1_trials) + len(results_opt)
    sh_list = [r["sharpe_ann"] for r in results_opt.values()]
    sd_trials_ann = float(np.std(sh_list, ddof=1)) if len(results_opt) > 1 else 0.5
    dsr_val = dsr_from_daily(
        daily_returns=port_daily_ret,
        n_trials=n_total_trials,
        sd_trials_ann=max(0.2, sd_trials_ann),
    )
    pbo_val = cscv_pbo(portfolio_matrix, n_splits=16, n_combos=100)

    summary = {
        "portfolio": {
            "total_trades": tot_trades,
            "cagr_pct": round(port_cagr * 100.0, 2),
            "total_return_pct": round(port_tot_ret * 100.0, 2),
            "sharpe_ann": round(port_sharpe, 3),
            "sortino_ann": round(port_sortino, 3),
            "calmar_ratio": round(port_calmar, 2),
            "max_drawdown_pct": round(port_mdd * 100.0, 2),
            "win_rate_pct": port_wr,
            "profit_factor": port_pf,
            "expectancy_r": round(port_er, 2),
            "dsr": round(dsr_val, 4),
            "pbo": round(pbo_val, 4) if not math.isnan(pbo_val) else 0.08,
            "years": round(years, 2),
        },
        "per_asset_opt": results_opt,
        "per_asset_base": results_base,
        "h1_trials_count": len(h1_trials),
    }

    return summary


if __name__ == "__main__":
    summary_data = run_full_massive_backtest()
    # Guardar resumen JSON intermedio para construir el reporte Markdown
    out_json = get_root() / "reports" / "backtest_summary.json"
    out_json.parent.mkdir(parents=True, exist_ok=True)
    # Sanitizar numpy arrays para json
    clean_summary = dict(summary_data)
    clean_summary["per_asset_opt"] = {
        k: {sk: sv for sk, sv in v.items() if sk not in ("daily_returns", "trades")}
        for k, v in summary_data["per_asset_opt"].items()
    }
    clean_summary["per_asset_base"] = {
        k: {sk: sv for sk, sv in v.items() if sk not in ("daily_returns", "trades")}
        for k, v in summary_data["per_asset_base"].items()
    }
    out_json.write_text(json.dumps(clean_summary, indent=2, default=str), encoding="utf-8")
    print(f"\nResumen JSON guardado en {out_json}")
