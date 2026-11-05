"""Motor de Investigación y Backtesting Multi-Horizonte (M6.4).

Evalúa tres estrategias diferenciadas por horizonte temporal sobre la Cesta Elite:
- Activos: BTCUSDT, ETHUSDT, SOLUSDT, SUIUSDT.
- Período: 2024-01-01 a 2026-11-02 (Era moderna post-ETFs).

Estrategias:
1. SPRINT (1H): Momentum intradía, breakout RVOL > 1.5x, TP fijo +2.5R, Trailing 1.2x ATR.
2. CRUISE (4H): Swing tendencial, pullback EMA21, SL Swing Low (8 velas) con regla Anti-Wick.
3. MARATHON (1D/1W): Macro Wave de ciclo, régimen BTC SMA200, SL 15%, salida por SMA50/SMA20w.
"""

from __future__ import annotations

import json
import math
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

from qa.agent.capital import load_costs
from qa.backtest.trials import TrialLedger
from qa.data.client import SPOT_BASE, BinancePublicClient
from qa.data.klines import fetch_klines_paged, klines_frame
from qa.data.paths import get_root
from qa.stats.metrics import max_drawdown, sharpe_ann, sortino_ann

ELITE_BASKET = ["BTCUSDT", "ETHUSDT", "SOLUSDT", "SUIUSDT"]


def get_cache_dir() -> Path:
    d = get_root() / "data" / "cache"
    d.mkdir(parents=True, exist_ok=True)
    return d


def fetch_or_load_klines(
    symbols: list[str],
    interval: str,
    start_year: int = 2024,
) -> dict[str, pd.DataFrame]:
    """Carga de cache local parquet o descarga de Binance público si no existe."""
    cache_dir = get_cache_dir()
    dataset: dict[str, pd.DataFrame] = {}

    start_ms = int(datetime(start_year, 1, 1, tzinfo=UTC).timestamp() * 1000)
    end_ms = int(datetime(2026, 11, 2, tzinfo=UTC).timestamp() * 1000)

    with BinancePublicClient() as client:
        for sym in symbols:
            cache_file = cache_dir / f"{sym}_{interval}_{start_year}_2026.parquet"
            if cache_file.exists():
                try:
                    df = pd.read_parquet(cache_file)
                    dataset[sym] = df
                    continue
                except Exception:
                    pass

            # Descargar paginado
            print(f"Descargando {sym} ({interval}) desde {start_year}...")
            # SUI listado en mayo 2023
            sym_start = start_ms
            max_p = 35 if interval == "1h" else (10 if interval == "4h" else 5)
            rows = fetch_klines_paged(
                client=client,
                base_url=SPOT_BASE,
                path="/api/v3/klines",
                symbol=sym,
                interval=interval,
                start_ms=sym_start,
                end_ms=end_ms,
                limit=1000,
                max_pages=max_p,
            )
            if rows:
                df = klines_frame(rows, sym, interval)
                df = df.sort_values("open_time").reset_index(drop=True)
                df.to_parquet(cache_file, index=False)
                dataset[sym] = df

    return dataset


# ==============================================================================
# 1. ESTRATEGIA 1: SPRINT (Momentum Intradía — 1H)
# ==============================================================================
def simulate_sprint(
    df: pd.DataFrame,
    symbol: str,
    costs: dict[str, Any],
    initial_capital: float = 1000.0,
    risk_pct: float = 0.02,
) -> dict[str, Any]:
    """Simulación SPRINT: Breakout RVOL > 1.5x, TP fijo +2.5R, trailing 1.2x ATR desde +1R."""
    # Taker fee ida y vuelta = 0.10%
    fee_rt = float(costs["perp_usdm"]["taker_fee"]) * 2.0
    c = df["close"].astype(float)
    h = df["high"].astype(float)
    low_px = df["low"].astype(float)
    v = df["volume"].astype(float)

    ema9 = c.ewm(span=9, adjust=False).mean()
    ema21 = c.ewm(span=21, adjust=False).mean()

    # RVOL
    v_sma20 = v.rolling(20).mean()
    rvol = v / (v_sma20 + 1e-9)

    # ATR14
    tr = np.maximum(
        h - low_px, np.maximum(np.abs(h - c.shift(1)), np.abs(low_px - c.shift(1)))
    )
    atr = tr.rolling(14).mean()

    capital = initial_capital
    peak_cap = initial_capital
    max_dd_val = 0.0
    dd_start_idx: int | None = None
    max_dd_dur = 0

    trades: list[dict[str, Any]] = []
    daily_returns: list[float] = []

    active_trade: dict[str, Any] | None = None
    min_bars = 40
    n = len(df)

    last_day: str | None = None
    day_open_cap = capital

    for t in range(min_bars, n):
        row = df.iloc[t]
        high_val = float(h.iloc[t])
        low_val = float(low_px.iloc[t])
        close_val = float(c.iloc[t])
        atr_val = float(atr.iloc[t]) if not math.isnan(atr.iloc[t]) else close_val * 0.02
        cur_day = str(row["open_time"])[:10]

        # Tracking diario
        if last_day is None:
            last_day = cur_day
            day_open_cap = capital
        elif cur_day != last_day:
            day_ret = (capital / day_open_cap - 1.0) if day_open_cap > 0 else 0.0
            daily_returns.append(day_ret)
            last_day = cur_day
            day_open_cap = capital

        # Gestionar trade activo
        if active_trade is not None:
            entry_px = active_trade["entry_price"]
            sl = active_trade["sl"]
            tp = active_trade["tp"]
            size_usd = active_trade["size_usd"]
            dist_sl = active_trade["dist_sl"]
            reached_1r = active_trade["reached_1r"]

            # Comprobar si tocó TP fijo (+2.5R)
            if high_val >= tp:
                pnl_gross = size_usd * (tp / entry_px - 1.0)
                fee = size_usd * fee_rt
                pnl_net = pnl_gross - fee
                capital += pnl_net
                active_trade["realized_pnl"] = pnl_net
                active_trade["exit_price"] = tp
                active_trade["exit_reason"] = "TP_2.5R"
                active_trade["duration_hours"] = t - active_trade["opened_idx"]
                trades.append(active_trade)
                active_trade = None

            # Comprobar si tocó SL
            elif low_val <= sl:
                pnl_gross = size_usd * (sl / entry_px - 1.0)
                fee = size_usd * fee_rt
                pnl_net = pnl_gross - fee
                capital += pnl_net
                active_trade["realized_pnl"] = pnl_net
                active_trade["exit_price"] = sl
                active_trade["exit_reason"] = "TRAILING_SL" if reached_1r else "INITIAL_SL"
                active_trade["duration_hours"] = t - active_trade["opened_idx"]
                trades.append(active_trade)
                active_trade = None

            # Trailing Stop rápido de protección a partir de +1.0R
            else:
                if not reached_1r and high_val >= (entry_px + 1.0 * dist_sl):
                    active_trade["reached_1r"] = True
                    # Subir SL a Break-Even o High - 1.2 * ATR
                    new_sl = max(entry_px, high_val - 1.2 * atr_val)
                    active_trade["sl"] = max(sl, new_sl)
                elif reached_1r:
                    new_sl = high_val - 1.2 * atr_val
                    if new_sl > sl:
                        active_trade["sl"] = new_sl

        # Evaluar apertura si no hay posición activa
        if active_trade is None and t >= 25:
            # Entrada: RVOL > 1.5, EMA9 > EMA21, Close > EMA9 y Ruptura de rango (15 barras)
            c_now = close_val
            e9 = float(ema9.iloc[t])
            e21 = float(ema21.iloc[t])
            rv = float(rvol.iloc[t])
            recent_high = float(h.iloc[t - 15 : t].max())

            if rv > 1.5 and e9 > e21 and c_now > e9 and c_now >= recent_high:
                dist_sl = max(1.5 * atr_val, 0.015 * c_now)
                sl = c_now - dist_sl
                tp = c_now + 2.5 * dist_sl  # TP agresivo +2.5R
                risk_usd = capital * risk_pct
                dist_sl_pct = dist_sl / c_now
                size_usd = round(risk_usd / max(0.005, dist_sl_pct), 2)
                size_usd = min(size_usd, capital * 4.0)

                active_trade = {
                    "strategy": "SPRINT",
                    "symbol": symbol,
                    "direction": "LONG",
                    "entry_price": c_now,
                    "size_usd": size_usd,
                    "dist_sl": dist_sl,
                    "sl": sl,
                    "tp": tp,
                    "risk_usd": risk_usd,
                    "reached_1r": False,
                    "opened_idx": t,
                    "realized_pnl": 0.0,
                }

        # Drawdown tracking
        if capital > peak_cap:
            peak_cap = capital
            if dd_start_idx is not None:
                cur_dur = (t - dd_start_idx) // 24
                if cur_dur > max_dd_dur:
                    max_dd_dur = cur_dur
                dd_start_idx = None
        else:
            if dd_start_idx is None:
                dd_start_idx = t
            dd = (peak_cap - capital) / peak_cap
            if dd > max_dd_val:
                max_dd_val = dd

    # Cerrar trade remanente al final del período
    if active_trade is not None:
        exit_px = float(c.iloc[-1])
        entry_px = active_trade["entry_price"]
        size_usd = active_trade["size_usd"]
        pnl_gross = size_usd * (exit_px / entry_px - 1.0)
        fee = size_usd * fee_rt
        pnl_net = pnl_gross - fee
        capital += pnl_net
        active_trade["realized_pnl"] = pnl_net
        active_trade["exit_price"] = exit_px
        active_trade["exit_reason"] = "TERMINAL_CLOSE"
        active_trade["duration_hours"] = n - 1 - active_trade["opened_idx"]
        trades.append(active_trade)
        active_trade = None

    # Finalizar último día
    if day_open_cap > 0:
        daily_returns.append(capital / day_open_cap - 1.0)

    return _compute_metrics(
        "SPRINT", symbol, initial_capital, capital, max_dd_val, max_dd_dur, trades, daily_returns
    )


# ==============================================================================
# 2. ESTRATEGIA 2: CRUISE (Swing Tendencial — 4H / 1D)
# ==============================================================================
def simulate_cruise(
    df_4h: pd.DataFrame,
    df_1d: pd.DataFrame,
    btc_1d: pd.DataFrame,
    symbol: str,
    costs: dict[str, Any],
    initial_capital: float = 1000.0,
    risk_pct: float = 0.035,
) -> dict[str, Any]:
    """Simulación CRUISE: Pullback EMA21(4H) / SMA50(1D), SL Swing Low 8 velas, Regla Anti-Wick."""
    # Maker entry (0.02%) + Taker exit (0.05%) = 0.07%
    fee_rt = float(costs["perp_usdm"]["maker_fee"]) + float(costs["perp_usdm"]["taker_fee"])

    c_4h = df_4h["close"].astype(float)
    l_4h = df_4h["low"].astype(float)
    o_4h = df_4h["open"].astype(float)
    ema21_4h = c_4h.ewm(span=21, adjust=False).mean()

    # Contexto 1D
    c_1d = df_1d["close"].astype(float)
    sma50_1d = c_1d.rolling(50).mean()

    # Contexto BTC 1D
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

        # Tracking diario
        if last_day is None:
            last_day = cur_day
            day_open_cap = capital
        elif cur_day != last_day:
            day_ret = (capital / day_open_cap - 1.0) if day_open_cap > 0 else 0.0
            daily_returns.append(day_ret)
            last_day = cur_day
            day_open_cap = capital

        # 1. Gestionar trade activo
        if active_trade is not None:
            entry_px = active_trade["entry_price"]
            sl = active_trade["sl"]
            size_usd = active_trade["size_usd"]

            # Regla Anti-Wick: Solo se liquida si la vela de 4H CIERRA por debajo del SL
            # Las mechas intradiarias (low_val < sl pero close_val >= sl) NO expulsan la posición
            if close_val < sl:
                # Salida al precio de cierre de la vela de 4H
                exit_px = close_val
                pnl_gross = size_usd * (exit_px / entry_px - 1.0)
                fee = size_usd * fee_rt
                pnl_net = pnl_gross - fee
                capital += pnl_net
                active_trade["realized_pnl"] = pnl_net
                active_trade["exit_price"] = exit_px
                active_trade["exit_reason"] = "STRUCTURAL_SL_CLOSE"
                active_trade["duration_hours"] = (t - active_trade["opened_idx"]) * 4
                trades.append(active_trade)
                active_trade = None

            else:
                # Trailing estructural: mínimo de las últimas 8 velas de 4H
                recent_swing_low = float(l_4h.iloc[max(0, t - 8) : t].min())
                active_trade["sl"] = max(sl, recent_swing_low)

        # 2. Evaluar apertura si no hay posición
        if active_trade is None and t >= 10:
            # Buscar contexto diario a la fecha
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

            # Condiciones de entrada CRUISE:
            # Macro alcista + Tendencia 1D alcista + Pullback a EMA21(4H) + Giro alcista en vela 4H
            e21_val = float(ema21_4h.iloc[t])
            pullback_hit = low_val <= (e21_val * 1.006)
            bullish_turn = close_val > open_val and close_val > e21_val

            if macro_bull and asset_trend_bull and pullback_hit and bullish_turn:
                # SL anclado al Swing Low estructural de 8 velas
                swing_low_8 = float(l_4h.iloc[max(0, t - 8) : t + 1].min())
                dist_sl = max(close_val - swing_low_8, close_val * 0.02)
                sl = close_val - dist_sl
                risk_usd = capital * risk_pct
                dist_sl_pct = dist_sl / close_val
                size_usd = round(risk_usd / max(0.005, dist_sl_pct), 2)
                size_usd = min(size_usd, capital * 3.5)

                active_trade = {
                    "strategy": "CRUISE",
                    "symbol": symbol,
                    "direction": "LONG",
                    "entry_price": close_val,
                    "size_usd": size_usd,
                    "dist_sl": dist_sl,
                    "sl": sl,
                    "tp": 0.0,  # Sin TP estático
                    "risk_usd": risk_usd,
                    "opened_idx": t,
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

    # Cerrar trade remanente al final del período
    if active_trade is not None:
        exit_px = float(c_4h.iloc[-1])
        entry_px = active_trade["entry_price"]
        size_usd = active_trade["size_usd"]
        pnl_gross = size_usd * (exit_px / entry_px - 1.0)
        fee = size_usd * fee_rt
        pnl_net = pnl_gross - fee
        capital += pnl_net
        active_trade["realized_pnl"] = pnl_net
        active_trade["exit_price"] = exit_px
        active_trade["exit_reason"] = "TERMINAL_CLOSE"
        active_trade["duration_hours"] = (n - 1 - active_trade["opened_idx"]) * 4
        trades.append(active_trade)
        active_trade = None

    if day_open_cap > 0:
        daily_returns.append(capital / day_open_cap - 1.0)

    return _compute_metrics(
        "CRUISE", symbol, initial_capital, capital, max_dd_val, max_dd_dur, trades, daily_returns
    )


# ==============================================================================
# 3. ESTRATEGIA 3: MARATHON (Posicional de Ciclo / Macro Wave — 1D / 1W)
# ==============================================================================
def simulate_marathon(
    df_1d: pd.DataFrame,
    btc_1d: pd.DataFrame,
    symbol: str,
    costs: dict[str, Any],
    initial_capital: float = 1000.0,
    risk_pct: float = 0.04,
) -> dict[str, Any]:
    """Simulación MARATHON: Ciclo macro post-ETF, SL 15%, salida por cambio macro o SMA50(1D)."""
    # Maker entry (0.02%) + Taker exit (0.05%) = 0.07%
    fee_rt = float(costs["perp_usdm"]["maker_fee"]) + float(costs["perp_usdm"]["taker_fee"])

    c = df_1d["close"].astype(float)
    sma50 = c.rolling(50).mean()
    ema9 = c.ewm(span=9, adjust=False).mean()
    ema21 = c.ewm(span=21, adjust=False).mean()

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
    n = len(df_1d)

    for t in range(min_bars, n):
        row = df_1d.iloc[t]
        close_val = float(c.iloc[t])
        prev_cap = capital

        # 1. Gestionar posición activa si existe
        if active_trade is not None:
            entry_px = active_trade["entry_price"]
            size_usd = active_trade["size_usd"]
            sl_macro = active_trade["sl"]

            # Comprobar ruptura de estructura macro:
            # 1. Cierre diario confirmado por debajo de SMA50(1D) x 0.97 (3% de holgura)
            sma50_val = float(sma50.iloc[t]) if not math.isnan(sma50.iloc[t]) else entry_px * 0.90
            broke_sma50 = close_val < (sma50_val * 0.97)

            # 2. Ruptura de régimen macro Bitcoin (BTC < SMA200)
            btc_cur_time = row["open_time"]
            btc_sub = btc_1d[btc_1d["open_time"] <= btc_cur_time]
            btc_macro_bear = False
            if len(btc_sub) >= 50:
                btc_c_last = float(btc_sub["close"].iloc[-1])
                btc_sma200_val = (
                    float(sma200_btc.loc[btc_sub.index[-1]])
                    if not math.isnan(sma200_btc.loc[btc_sub.index[-1]])
                    else btc_c_last
                )
                btc_macro_bear = btc_c_last < btc_sma200_val

            # 3. Stop loss de catástrofe amplio (15%)
            hit_catastrophe_sl = close_val <= sl_macro

            if broke_sma50 or btc_macro_bear or hit_catastrophe_sl:
                exit_reason = (
                    "MACRO_BTC_BEAR"
                    if btc_macro_bear
                    else ("SMA50_BROKEN" if broke_sma50 else "CATASTROPHE_SL")
                )
                exit_px = close_val
                pnl_gross = size_usd * (exit_px / entry_px - 1.0)
                fee = size_usd * fee_rt
                pnl_net = pnl_gross - fee
                capital += pnl_net
                active_trade["realized_pnl"] = pnl_net
                active_trade["exit_price"] = exit_px
                active_trade["exit_reason"] = exit_reason
                active_trade["duration_days"] = t - active_trade["opened_idx"]
                active_trade["duration_hours"] = (t - active_trade["opened_idx"]) * 24
                trades.append(active_trade)
                active_trade = None

        # 2. Evaluar apertura posicional de ciclo si no hay posición
        if active_trade is None and t >= 30:
            btc_cur_time = row["open_time"]
            btc_sub = btc_1d[btc_1d["open_time"] <= btc_cur_time]
            btc_macro_bull = True
            if len(btc_sub) >= 50:
                btc_c_last = float(btc_sub["close"].iloc[-1])
                btc_sma200_val = (
                    float(sma200_btc.loc[btc_sub.index[-1]])
                    if not math.isnan(sma200_btc.loc[btc_sub.index[-1]])
                    else btc_c_last
                )
                btc_macro_bull = btc_c_last >= btc_sma200_val

            sma50_val = float(sma50.iloc[t]) if not math.isnan(sma50.iloc[t]) else close_val
            e9_val = float(ema9.iloc[t])
            e21_val = float(ema21.iloc[t])

            # Entrada MARATHON: Régimen Macro Alcista + Close > SMA50(1D) + EMA9 > EMA21
            if btc_macro_bull and close_val > sma50_val and e9_val > e21_val:
                # Stop loss amplio de ciclo del 15% (absorbe volatilidad sin sacarnos)
                dist_sl = close_val * 0.15
                sl = close_val - dist_sl
                risk_usd = capital * risk_pct
                size_usd = round(risk_usd / 0.15, 2)
                # Apalancamiento bajo (típico 1.5x a 2.5x)
                size_usd = min(size_usd, capital * 2.2)

                active_trade = {
                    "strategy": "MARATHON",
                    "symbol": symbol,
                    "direction": "LONG",
                    "entry_price": close_val,
                    "size_usd": size_usd,
                    "dist_sl": dist_sl,
                    "sl": sl,
                    "tp": 0.0,  # Sin TP estático: dejar correr hasta que termine el ciclo
                    "risk_usd": risk_usd,
                    "opened_idx": t,
                    "realized_pnl": 0.0,
                }

        ret_day = (capital / prev_cap - 1.0) if prev_cap > 0 else 0.0
        daily_returns.append(ret_day)

        if capital > peak_cap:
            peak_cap = capital
            if dd_start_idx is not None:
                cur_dur = t - dd_start_idx
                if cur_dur > max_dd_dur:
                    max_dd_dur = cur_dur
                dd_start_idx = None
        else:
            if dd_start_idx is None:
                dd_start_idx = t
            dd = (peak_cap - capital) / peak_cap
            if dd > max_dd_val:
                max_dd_val = dd

    # Cerrar trade remanente al final del período
    if active_trade is not None:
        exit_px = float(c.iloc[-1])
        entry_px = active_trade["entry_price"]
        size_usd = active_trade["size_usd"]
        pnl_gross = size_usd * (exit_px / entry_px - 1.0)
        fee = size_usd * fee_rt
        pnl_net = pnl_gross - fee
        capital += pnl_net
        active_trade["realized_pnl"] = pnl_net
        active_trade["exit_price"] = exit_px
        active_trade["exit_reason"] = "TERMINAL_CLOSE"
        active_trade["duration_days"] = n - 1 - active_trade["opened_idx"]
        active_trade["duration_hours"] = (n - 1 - active_trade["opened_idx"]) * 24
        trades.append(active_trade)
        active_trade = None

    return _compute_metrics(
        "MARATHON", symbol, initial_capital, capital, max_dd_val, max_dd_dur, trades, daily_returns
    )


def _compute_metrics(
    strategy_name: str,
    symbol: str,
    initial_cap: float,
    final_cap: float,
    max_dd: float,
    max_dd_days: int,
    trades: list[dict[str, Any]],
    daily_returns: list[float],
) -> dict[str, Any]:
    ret_arr = np.array(daily_returns, dtype=np.float64) if daily_returns else np.zeros(1)
    total_ret = float(final_cap / initial_cap - 1.0)
    n_days = max(1, len(daily_returns))
    years = max(0.1, n_days / 365.0)
    cagr = float((1.0 + total_ret) ** (1.0 / years) - 1.0) if total_ret > -1.0 else -1.0

    sh = sharpe_ann(ret_arr)
    so = sortino_ann(ret_arr)

    wins = [tr for tr in trades if tr["realized_pnl"] > 0]
    losses = [tr for tr in trades if tr["realized_pnl"] <= 0]
    win_rate = len(wins) / len(trades) * 100.0 if trades else 0.0

    sum_win = sum(tr["realized_pnl"] for tr in wins)
    sum_loss = abs(sum(tr["realized_pnl"] for tr in losses))
    pf = round(sum_win / sum_loss, 2) if sum_loss > 0 else (99.0 if sum_win > 0 else 0.0)

    # R multiplos
    r_mults = [
        tr["realized_pnl"] / max(1.0, tr.get("risk_usd", 1.0))
        for tr in trades
        if tr.get("risk_usd")
    ]
    max_r = max(r_mults) if r_mults else 0.0
    avg_r = float(np.mean(r_mults)) if r_mults else 0.0

    pct_gains = [
        (tr["exit_price"] / tr["entry_price"] - 1.0) * 100.0
        for tr in trades
        if tr.get("entry_price") and tr.get("exit_price")
    ]
    max_pct_gain = max(pct_gains) if pct_gains else 0.0

    durations = [tr.get("duration_hours", 0) for tr in trades]
    avg_dur_h = float(np.mean(durations)) if durations else 0.0

    return {
        "strategy": strategy_name,
        "symbol": symbol,
        "initial_capital": initial_cap,
        "final_capital": round(final_cap, 2),
        "total_return_pct": round(total_ret * 100.0, 2),
        "cagr_pct": round(cagr * 100.0, 2),
        "sharpe_ann": round(sh, 3),
        "sortino_ann": round(so, 3),
        "max_drawdown_pct": round(max_dd * 100.0, 2),
        "max_dd_days": max_dd_days,
        "total_trades": len(trades),
        "win_rate_pct": round(win_rate, 1),
        "profit_factor": pf,
        "expectancy_r": round(avg_r, 2),
        "max_r_trade": round(max_r, 2),
        "max_pct_gain": round(max_pct_gain, 2),
        "avg_duration_hours": round(avg_dur_h, 1),
        "daily_returns": ret_arr,
        "trades": trades,
    }


def run_multi_horizon_evaluation() -> dict[str, Any]:
    """Ejecuta la evaluación simultánea de Sprint, Cruise y Marathon sobre la Cesta Elite."""
    root = get_root()
    ledger = TrialLedger(root)
    costs = load_costs(root)

    print("=================================================================")
    print(" [1/3] Descargando y Cargando Datos 2024-2026 (1H, 4H, 1D)")
    print("=================================================================")
    # 1D cargado desde 2023 para calentamiento perfecto de SMA200 y SMA50
    dataset_1d = fetch_or_load_klines(
        ELITE_BASKET, interval="1d", start_year=2023
    )
    dataset_4h = fetch_or_load_klines(
        ELITE_BASKET, interval="4h", start_year=2024
    )
    dataset_1h = fetch_or_load_klines(
        ELITE_BASKET, interval="1h", start_year=2024
    )

    btc_1d = dataset_1d["BTCUSDT"]

    results_sprint: dict[str, Any] = {}
    results_cruise: dict[str, Any] = {}
    results_marathon: dict[str, Any] = {}

    print("\n=================================================================")
    print(" [2/3] Simulando las 3 Estrategias sobre la Cesta Elite")
    print("=================================================================")
    for sym in ELITE_BASKET:
        print(f"\n--- Evaluando {sym} ---")
        df_1h = dataset_1h.get(sym)
        df_4h = dataset_4h.get(sym)
        df_1d = dataset_1d.get(sym)

        if df_1h is not None and not df_1h.empty:
            print(f"  [1] SPRINT (1H)... ({len(df_1h)} velas)")
            res_sp = simulate_sprint(df_1h, sym, costs)
            results_sprint[sym] = res_sp
            with ledger.trial(
                hypothesis="SPRINT_1H",
                cell_id="MOMENTUM_1H",
                asset=sym,
                kind="sprint_momentum",
                config={"tp_r": 2.5, "trail_atr": 1.2, "rvol_min": 1.5},
                notes=f"Sprint 1H {sym} 2024-2026",
            ) as t_ctx:
                t_ctx.set_metrics({
                    "cagr": res_sp["cagr_pct"],
                    "sharpe_ann": res_sp["sharpe_ann"],
                    "max_drawdown": res_sp["max_drawdown_pct"],
                    "win_rate": res_sp["win_rate_pct"],
                    "profit_factor": res_sp["profit_factor"],
                    "max_r": res_sp["max_r_trade"],
                })

        if df_4h is not None and df_1d is not None:
            print(f"  [2] CRUISE (4H Swing Anti-Mecha)... ({len(df_4h)} velas)")
            res_cr = simulate_cruise(df_4h, df_1d, btc_1d, sym, costs)
            results_cruise[sym] = res_cr
            with ledger.trial(
                hypothesis="CRUISE_4H",
                cell_id="SWING_ANTI_WICK",
                asset=sym,
                kind="cruise_swing",
                config={"pullback_ema21": True, "anti_wick_sl": True},
                notes=f"Cruise 4H {sym} 2024-2026",
            ) as t_ctx:
                t_ctx.set_metrics({
                    "cagr": res_cr["cagr_pct"],
                    "sharpe_ann": res_cr["sharpe_ann"],
                    "max_drawdown": res_cr["max_drawdown_pct"],
                    "win_rate": res_cr["win_rate_pct"],
                    "profit_factor": res_cr["profit_factor"],
                    "max_r": res_cr["max_r_trade"],
                })

        if df_1d is not None:
            # Filtrar 1D a partir de 2024 para simulación
            df_1d_2024 = df_1d[df_1d["open_time"] >= "2024-01-01"].reset_index(drop=True)
            print(f"  [3] MARATHON (1D/1W Macro Wave)... ({len(df_1d_2024)} velas)")
            res_ma = simulate_marathon(df_1d_2024, btc_1d, sym, costs)
            results_marathon[sym] = res_ma
            with ledger.trial(
                hypothesis="MARATHON_MACRO",
                cell_id="MACRO_WAVE_CYCLE",
                asset=sym,
                kind="marathon_cycle",
                config={"btc_sma200": True, "sl_macro_pct": 0.15},
                notes=f"Marathon Macro {sym} 2024-2026",
            ) as t_ctx:
                t_ctx.set_metrics({
                    "cagr": res_ma["cagr_pct"],
                    "sharpe_ann": res_ma["sharpe_ann"],
                    "max_drawdown": res_ma["max_drawdown_pct"],
                    "win_rate": res_ma["win_rate_pct"],
                    "profit_factor": res_ma["profit_factor"],
                    "max_r": res_ma["max_r_trade"],
                })

    ledger.close()

    print("\n=================================================================")
    print(" [3/3] Consolidando Métricas Comparativas")
    print("=================================================================")

    def _portfolio_agg(res_dict: dict[str, Any], name: str) -> dict[str, Any]:
        min_l = min(len(r["daily_returns"]) for r in res_dict.values())
        mat = np.column_stack([r["daily_returns"][-min_l:] for r in res_dict.values()])
        port_ret = mat.mean(axis=1)
        tot_ret = float(np.prod(1.0 + port_ret) - 1.0)
        n_d = len(port_ret)
        y = n_d / 365.0
        cagr = float((1.0 + tot_ret) ** (1.0 / y) - 1.0)
        sh = sharpe_ann(port_ret)
        so = sortino_ann(port_ret)
        mdd = max_drawdown(port_ret)

        tot_trades = sum(r["total_trades"] for r in res_dict.values())
        tot_wins = sum(
            len([t for t in r["trades"] if t["realized_pnl"] > 0])
            for r in res_dict.values()
        )
        wr = round(tot_wins / tot_trades * 100.0, 1) if tot_trades > 0 else 0.0

        all_r = [
            t["realized_pnl"] / max(1.0, t.get("risk_usd", 1.0))
            for r in res_dict.values()
            for t in r["trades"]
        ]
        max_r_global = max(all_r) if all_r else 0.0
        avg_r_global = float(np.mean(all_r)) if all_r else 0.0

        tot_w_pnl = sum(
            sum(t["realized_pnl"] for t in r["trades"] if t["realized_pnl"] > 0)
            for r in res_dict.values()
        )
        tot_l_pnl = abs(
            sum(
                sum(t["realized_pnl"] for t in r["trades"] if t["realized_pnl"] <= 0)
                for r in res_dict.values()
            )
        )
        pf = round(tot_w_pnl / tot_l_pnl, 2) if tot_l_pnl > 0 else 0.0

        all_pcts = [
            (t["exit_price"] / t["entry_price"] - 1.0) * 100.0
            for r in res_dict.values()
            for t in r["trades"]
            if t.get("entry_price") and t.get("exit_price")
        ]
        max_gain_pct = max(all_pcts) if all_pcts else 0.0

        all_dur = [t.get("duration_hours", 0) for r in res_dict.values() for t in r["trades"]]
        avg_dur_d = round(float(np.mean(all_dur)) / 24.0, 1) if all_dur else 0.0

        return {
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
        }

    summary = {
        "portfolio_comparison": {
            "sprint": _portfolio_agg(results_sprint, "SPRINT (1H)"),
            "cruise": _portfolio_agg(results_cruise, "CRUISE (4H)"),
            "marathon": _portfolio_agg(results_marathon, "MARATHON (1D)"),
        },
        "per_asset": {
            "sprint": results_sprint,
            "cruise": results_cruise,
            "marathon": results_marathon,
        },
    }

    out_json = root / "reports" / "multi_horizon_summary.json"
    out_json.parent.mkdir(parents=True, exist_ok=True)
    # Sanitizar arrays para json
    clean_summary = dict(summary)
    for strat in ("sprint", "cruise", "marathon"):
        clean_summary["per_asset"][strat] = {
            k: {sk: sv for sk, sv in v.items() if sk not in ("daily_returns", "trades")}
            for k, v in summary["per_asset"][strat].items()
        }
    out_json.write_text(json.dumps(clean_summary, indent=2, default=str), encoding="utf-8")
    print(f"\nResumen JSON guardado en {out_json}")
    return summary


if __name__ == "__main__":
    run_multi_horizon_evaluation()
