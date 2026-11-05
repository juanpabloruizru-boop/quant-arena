"""Pruebas unitarias para las optimizaciones cuantitativas y operativas (M6.3 Modo Carrera).

Verifica:
1. Descorrelación del scoring y penalización simétrica de RSI en extremos.
2. Detección de compresión de volatilidad (ATR percentile) y bonificación de convicción.
3. Filtro direccional de funding rate para futuros USD-M.
4. Indicador causal ADX/DMI y filtro de régimen lateral vs confirmación tendencial.
5. Filtro de Fuerza Relativa frente a Bitcoin (RS Spread vs BTC) y veto de debilidad.
6. Veto definitivo de activos zombi en lista negra (ZECUSDT blacklist).
7. Trailing stop dinámico protector tendencial Anti-Wick (2.2x ATR).
8. Dimensionamiento adaptativo Modo Carrera acotado en [2.0%, 5.0%].
9. Cierre parcial real del 25% en TP1 y captura de colas gruesas con el 75% restante.
10. Preferencia Maker Swing (retroceso a EMA21 / límite) vs entrada inmediata Taker.
11. Conector seguro y desacoplado de notificaciones (Telegram / Discord).
"""

from __future__ import annotations

from pathlib import Path

import numpy as np
import pytest

from qa.agent.autopilot import (
    BLACKLIST,
    UNIVERSO,
    calcular_niveles_rr,
    compute_indicators,
    score_symbol,
)
from qa.agent.capital import compute_status, realized_pnl_usd
from qa.agent.geometry import adaptive_risk_pct, anti_wick_trailing_sl
from qa.agent.notifications import notify_event, send_discord_alert, send_telegram_alert
from qa.agent.tracker import close_trade, load_trades, open_trade, update_trade
from qa.features.indicators import adx, relative_strength_ratio, rs_is_above_sma


# ---------------- 1. Descorrelación y Filtros de Señal ----------------
def test_rsi_extreme_penalties() -> None:
    ind_overbought = {
        "4h": {
            "close": 100.0,
            "ema9": 102.0,
            "ema21": 98.0,
            "sma50": 90.0,
            "rsi": 82.0,  # Sobrecompra extrema > 75
            "macd_hist": 1.5,
            "macd_accel": 0.2,
            "atr14": 2.0,
            "atr_mean": 2.0,
            "atr_pctl": 0.50,
            "atr_compression": False,
            "atr_extended": False,
            "adx14": 28.0,
            "adx_slope": 1.0,
            "rvol": 1.0,
        },
        "1d": {"close": 100.0, "sma50": 90.0},
    }
    sc_ob = score_symbol("BTCUSDT", ind_overbought, "4h")
    assert "Penalización sobrecompra" in sc_ob["reason"]
    # El score long debe estar fuertemente castigado a pesar de la tendencia alcista
    assert sc_ob["score_long"] < 60

    ind_oversold = {
        "4h": {
            "close": 50.0,
            "ema9": 48.0,
            "ema21": 52.0,
            "sma50": 60.0,
            "rsi": 18.0,  # Sobreventa extrema < 25
            "macd_hist": -1.5,
            "macd_accel": -0.2,
            "atr14": 2.0,
            "atr_mean": 2.0,
            "atr_pctl": 0.50,
            "atr_compression": False,
            "atr_extended": False,
            "adx14": 28.0,
            "adx_slope": 1.0,
            "rvol": 1.0,
        },
        "1d": {"close": 50.0, "sma50": 60.0},
    }
    sc_os = score_symbol("ETHUSDT", ind_oversold, "4h")
    assert "Penalización sobreventa" in sc_os["reason"]
    assert sc_os["score_short"] < 60


def test_volatility_compression_and_extension_filter() -> None:
    ind_comp = {
        "4h": {
            "close": 100.0,
            "ema9": 102.0,
            "ema21": 98.0,
            "sma50": 90.0,
            "rsi": 55.0,  # Zona óptima de aceleración
            "macd_hist": 1.0,
            "macd_accel": 0.5,
            "atr14": 1.0,
            "atr_mean": 2.5,
            "atr_pctl": 0.15,  # Compresión de volatilidad
            "atr_compression": True,
            "atr_extended": False,
            "adx14": 28.0,
            "adx_slope": 1.2,
            "rvol": 1.3,
        },
        "1d": {"close": 100.0, "sma50": 90.0},
    }
    sc_c = score_symbol("SOLUSDT", ind_comp, "4h")
    assert "Compresión ATR" in sc_c["reason"]
    assert sc_c["score"] >= 80  # Setup de muy alta convicción

    ind_ext = {
        "4h": {
            "close": 100.0,
            "ema9": 102.0,
            "ema21": 98.0,
            "sma50": 90.0,
            "rsi": 55.0,
            "macd_hist": 1.0,
            "macd_accel": 0.5,
            "atr14": 5.0,
            "atr_mean": 2.0,
            "atr_pctl": 0.95,  # Sobre-extensión de volatilidad
            "atr_compression": False,
            "atr_extended": True,
            "adx14": 28.0,
            "adx_slope": 1.2,
            "rvol": 1.3,
        },
        "1d": {"close": 100.0, "sma50": 90.0},
    }
    sc_e = score_symbol("SOLUSDT", ind_ext, "4h")
    assert "Penalización ATR sobre-extendido" in sc_e["reason"]
    assert sc_e["score"] < sc_c["score"]


def test_funding_rate_directional_filter() -> None:
    ind_neutral = {
        "4h": {
            "close": 100.0,
            "ema9": 102.0,
            "ema21": 98.0,
            "sma50": 90.0,
            "rsi": 58.0,
            "macd_hist": 1.0,
            "macd_accel": 0.2,
            "atr14": 2.0,
            "atr_mean": 2.0,
            "atr_pctl": 0.50,
            "atr_compression": False,
            "atr_extended": False,
            "adx14": 26.0,
            "adx_slope": 0.5,
            "rvol": 1.0,
        },
        "1d": {"close": 100.0, "sma50": 90.0},
    }
    # Funding normal (5 pb)
    sc_normal = score_symbol("BNBUSDT", ind_neutral, "4h", funding_rate=0.00005)
    # Funding hiper alcista (euforia compradora, > 0.03% / 8h)
    sc_high_fund = score_symbol("BNBUSDT", ind_neutral, "4h", funding_rate=0.00045)
    assert "Funding alcista extremo" in sc_high_fund["reason"]
    assert sc_high_fund["score_long"] <= sc_normal["score_long"] - 25

    # Para probar penalización en SHORT, usamos un setup con sesgo bajista
    ind_bearish = {
        "4h": {
            "close": 90.0,
            "ema9": 88.0,
            "ema21": 92.0,
            "sma50": 100.0,
            "rsi": 40.0,
            "macd_hist": -1.0,
            "macd_accel": -0.2,
            "atr14": 2.0,
            "atr_mean": 2.0,
            "atr_pctl": 0.50,
            "atr_compression": False,
            "atr_extended": False,
            "adx14": 26.0,
            "adx_slope": 0.5,
            "rvol": 1.0,
        },
        "1d": {"close": 90.0, "sma50": 100.0},
    }
    sc_bear_normal = score_symbol("BNBUSDT", ind_bearish, "4h", funding_rate=0.00005)
    # Funding muy negativo (pánico vendedor, < -0.02% / 8h)
    sc_neg_fund = score_symbol("BNBUSDT", ind_bearish, "4h", funding_rate=-0.00035)
    assert "Funding bajista extremo" in sc_neg_fund["reason"]
    assert sc_neg_fund["score_short"] <= sc_bear_normal["score_short"] - 25


# ---------------- 2. ADX / DMI y Régimen Lateral ----------------
def test_adx_causal_truncation() -> None:
    rng = np.random.default_rng(42)
    n = 100
    h = 100.0 + np.cumsum(rng.normal(0.2, 1.0, n))
    l_arr = h - rng.uniform(0.5, 2.0, n)
    c = (h + l_arr) / 2.0

    adx_full, p_full, m_full = adx(h, l_arr, c, n=14)
    # Invarianza por truncamiento: en cualquier t valido, el calculo truncado es identico
    for t in (40, 60, 80, 99):
        adx_part, p_part, m_part = adx(h[: t + 1], l_arr[: t + 1], c[: t + 1], n=14)
        assert np.isclose(adx_full[t], adx_part[t], rtol=1e-10, atol=1e-10)
        assert np.isclose(p_full[t], p_part[t], rtol=1e-10, atol=1e-10)
        assert np.isclose(m_full[t], m_part[t], rtol=1e-10, atol=1e-10)


def test_adx_lateral_regime_and_trend_bonus() -> None:
    ind_chop = {
        "4h": {
            "close": 100.0,
            "ema9": 101.0,
            "ema21": 99.0,
            "sma50": 95.0,
            "rsi": 52.0,
            "macd_hist": 0.2,
            "macd_accel": 0.05,
            "atr14": 1.5,
            "atr_mean": 1.5,
            "atr_pctl": 0.5,
            "adx14": 18.5,  # Mercado lateral / compresión sucia < 22
            "adx_slope": -0.5,
            "rvol": 1.0,
        },
        "1d": {"close": 100.0, "sma50": 95.0},
    }
    sc_chop = score_symbol("BTCUSDT", ind_chop, "4h")
    assert "Bloqueo Régimen Lateral ADX" in sc_chop["reason"]
    # Debe bloquear apertura direccional limitando el score por debajo de 40
    assert sc_chop["score"] <= 35

    ind_trend = {
        "4h": {
            "close": 100.0,
            "ema9": 101.0,
            "ema21": 99.0,
            "sma50": 95.0,
            "rsi": 58.0,
            "macd_hist": 0.8,
            "macd_accel": 0.2,
            "atr14": 1.5,
            "atr_mean": 1.5,
            "atr_pctl": 0.5,
            "adx14": 28.5,  # Tendencia fuerte >= 22
            "adx_slope": 1.5,  # Pendiente positiva
            "rvol": 1.2,
        },
        "1d": {"close": 100.0, "sma50": 95.0},
    }
    sc_trend = score_symbol("BTCUSDT", ind_trend, "4h")
    assert "Fuerza Tendencial ADX" in sc_trend["reason"]
    assert sc_trend["score"] >= 75


# ---------------- 3. Filtro RS vs BTC y Blacklist ----------------
def test_rs_vs_btc_calculation_and_filter() -> None:
    import pandas as pd

    # Probar cálculo directo de relative_strength_ratio y rs_is_above_sma
    c_alt = np.array([10.0, 11.0, 12.0, 13.0, 14.0] * 5)
    c_btc = np.array([100.0, 100.0, 100.0, 100.0, 100.0] * 5)
    rs_arr = relative_strength_ratio(c_alt, c_btc)
    assert len(rs_arr) == len(c_alt)
    assert rs_is_above_sma(c_alt, c_btc, window=5) is True

    # Verificar que compute_indicators calcula ADX y campos asociados
    df_sample = pd.DataFrame({
        "open": np.linspace(100, 150, 40),
        "high": np.linspace(102, 155, 40),
        "low": np.linspace(98, 148, 40),
        "close": np.linspace(101, 153, 40),
        "volume": np.full(40, 1000.0),
    })
    ind_computed = compute_indicators({"4h": df_sample})
    assert "adx14" in ind_computed["4h"]
    assert "adx_slope" in ind_computed["4h"]

    ind_alt = {
        "4h": {
            "close": 100.0,
            "ema9": 102.0,
            "ema21": 98.0,
            "sma50": 90.0,
            "rsi": 58.0,
            "macd_hist": 1.0,
            "macd_accel": 0.2,
            "atr14": 2.0,
            "atr_mean": 2.0,
            "atr_pctl": 0.50,
            "adx14": 27.0,
            "adx_slope": 0.5,
            "rvol": 1.1,
        },
        "1d": {"close": 100.0, "sma50": 90.0},
    }
    # Altcoin con debilidad relativa frente a BTC (RS < SMA20(RS))
    sc_weak = score_symbol("ETHUSDT", ind_alt, "4h", rs_ratio_above_sma=False)
    assert "Veto RS vs BTC < SMA20" in sc_weak["reason"]
    # Los LONGs deben quedar totalmente vetados (score_long = 0)
    assert sc_weak["score_long"] == 0

    # Altcoin con fortaleza relativa frente a BTC (RS > SMA20(RS))
    sc_strong = score_symbol("SOLUSDT", ind_alt, "4h", rs_ratio_above_sma=True)
    assert "Fuerza Relativa RS vs BTC > SMA20" in sc_strong["reason"]
    assert sc_strong["score_long"] >= 75


def test_btc_macro_regime_and_altcoin_veto() -> None:
    import pandas as pd

    from qa.agent.signals import btc_macro_regime

    # Probar btc_macro_regime
    days = pd.date_range("2022-01-01", periods=250, freq="D", tz="UTC")
    df_bear = pd.DataFrame({
        "open_time": days,
        "close": np.linspace(60000.0, 20000.0, 250),  # Bear Market
    })
    reg_bear = btc_macro_regime(df_bear, window=200)
    assert reg_bear["is_bullish"] is False
    assert reg_bear["regimen"] == "BAJISTA_INVIERNO"
    assert reg_bear["veto_altcoin_longs"] is True

    # Probar que en régimen bajista macro se vetan los LONGs en altcoins
    ind_alt = {
        "4h": {
            "close": 100.0,
            "ema9": 102.0,
            "ema21": 98.0,
            "sma50": 90.0,
            "rsi": 58.0,
            "macd_hist": 1.0,
            "macd_accel": 0.2,
            "atr14": 2.0,
            "atr_mean": 2.0,
            "atr_pctl": 0.50,
            "adx14": 28.0,
            "adx_slope": 0.5,
            "rvol": 1.1,
        },
        "1d": {"close": 100.0, "sma50": 90.0},
    }
    sc_alt_macro = score_symbol(
        "SOLUSDT", ind_alt, "4h", btc_macro_bullish=False
    )
    assert "BTC < SMA200(1D)" in sc_alt_macro["reason"]
    assert sc_alt_macro["score_long"] == 0

    # En régimen alcista, altcoins tienen compras habilitadas
    sc_alt_bull = score_symbol(
        "SOLUSDT", ind_alt, "4h", btc_macro_bullish=True
    )
    assert "Macro Alcista" in sc_alt_bull["reason"]
    assert sc_alt_bull["score_long"] >= 75


def test_zec_and_xrp_blacklist_veto() -> None:
    ind_dummy = {"4h": {"close": 50.0, "atr14": 1.0}}
    sc_zec = score_symbol("ZECUSDT", ind_dummy, "4h")
    assert sc_zec["score"] == 0
    assert sc_zec["direction"] == "NEUTRAL"
    assert "Veto Definitivo Blacklist" in sc_zec["reason"]
    assert "ZECUSDT" in BLACKLIST
    assert "ZECUSDT" not in UNIVERSO

    sc_xrp = score_symbol("XRPUSDT", ind_dummy, "4h")
    assert sc_xrp["score"] == 0
    assert sc_xrp["direction"] == "NEUTRAL"
    assert "Veto Definitivo Blacklist" in sc_xrp["reason"]
    assert "XRPUSDT" in BLACKLIST
    assert "XRPUSDT" not in UNIVERSO


# ---------------- 4. Trailing Stop Protector Anti-Wick 2.2x ATR ----------------
def test_anti_wick_trailing_sl_fat_tails_long() -> None:
    entry = 100.0
    current_sl = 95.0
    atr14 = 2.0

    # Con holgura 2.2x ATR: candidate = 104 - 2.2*2 = 99.6. max(95, 99.6) = 99.6
    sl_1 = anti_wick_trailing_sl(entry, current_sl, 104.0, atr14, direction="LONG", atr_mult=2.2)
    assert sl_1 == 99.6

    # Mecha de retroceso a 101.0 -> SL nunca retrocede
    sl_2 = anti_wick_trailing_sl(entry, sl_1, 101.0, atr14, direction="LONG", atr_mult=2.2)
    assert sl_2 == 99.6

    # Expansión parabólica a 115.0 -> SL avanza a 115 - 4.4 = 110.6 (captura de colas gruesas)
    sl_3 = anti_wick_trailing_sl(entry, sl_2, 115.0, atr14, direction="LONG", atr_mult=2.2)
    assert sl_3 == 110.6


def test_anti_wick_trailing_sl_fat_tails_short() -> None:
    entry = 100.0
    current_sl = 105.0
    atr14 = 2.0

    # Caída a 96.0 -> candidate = 96 + 4.4 = 100.4. min(105, 100.4) = 100.4
    sl_1 = anti_wick_trailing_sl(entry, current_sl, 96.0, atr14, direction="SHORT", atr_mult=2.2)
    assert sl_1 == 100.4

    # Mecha alcista a 98.0 -> SL se mantiene firme en 100.4
    sl_2 = anti_wick_trailing_sl(entry, sl_1, 98.0, atr14, direction="SHORT", atr_mult=2.2)
    assert sl_2 == 100.4


# ---------------- 5. Dimensionamiento Adaptativo Modo Carrera ----------------
def test_adaptive_risk_pct_modo_carrera() -> None:
    # Setup promedio (score 70, atr normal) -> 3.5%
    r_med = adaptive_risk_pct(base_risk=0.035, score=70, current_atr=2.0, mean_atr=2.0)
    assert r_med == pytest.approx(0.035, abs=1e-4)

    # Setup de muy alta convicción (score 90) en compresión ATR -> escala al tope 5.0%
    r_high = adaptive_risk_pct(base_risk=0.035, score=90, current_atr=1.0, mean_atr=2.0)
    assert r_high == 0.05

    # Setup de baja convicción (score 35) en alta volatilidad -> limitado al mínimo 2.0%
    r_low = adaptive_risk_pct(base_risk=0.035, score=35, current_atr=5.0, mean_atr=2.0)
    assert r_low == 0.02


# ---------------- 6. Cierre Parcial del 25% en TP1 y Runner del 75% ----------------
def test_partial_close_tp1_25_pct_accounting(tmp_path: Path) -> None:
    costs = {
        "spot": {"taker_fee": 0.001, "maker_fee": 0.001},
        "perp_usdm": {"taker_fee": 0.0005, "maker_fee": 0.0002},
    }
    # Abrir operación de futuros de $100 USD nocional
    t = open_trade(
        tmp_path,
        asset="BTCUSDT",
        kind="future_long",
        timeframe="4h",
        entry_price=100.0,
        size_usd=100.0,
        sl=95.0,
        tp=130.0,
        tp1=115.0,
        tp2=130.0,
        risk_usd=5.0,
    )
    tid = t["id"]

    # Simular ejecución de TP1 con cierre del 25% (Modo Carrera):
    # 25 USD cerrados a 115.0: Bruto = +3.75 USD. Fees = 25 * 0.001 = 0.025. Neto = +3.725 USD.
    pnl_net_part = 3.73
    fees_part = 0.03
    new_sl = 104.0
    update_trade(
        tmp_path,
        tid,
        updates={
            "tp1_hit": True,
            "size_usd": 75.0,  # 75% runner restante
            "partial_closed_size_usd": 25.0,
            "partial_realized_pnl_usd": pnl_net_part,
            "partial_fees_usd": fees_part,
            "sl": new_sl,
        },
        note="TP1 Alcanzado con cierre parcial 25% Modo Carrera",
    )

    trades = load_trades(tmp_path)
    tr = trades[0]
    assert tr["tp1_hit"] is True
    assert tr["size_usd"] == 75.0  # 75% de la posición se deja correr
    assert tr["partial_realized_pnl_usd"] == 3.73
    assert tr["sl"] == 104.0

    # Verificar que compute_status computa el PnL parcial en tiempo real
    status = compute_status(
        capital_records=[{"action": "set", "amount": 1000.0}],
        trades=trades,
        prices={"BTCUSDT": 116.0},
        costs=costs,
    )
    assert status["pnl_realizado_usd"] == 3.73

    # Cerrar el 75% restante en TP2 (130.0):
    # 75 USD cerrados a 130.0: Bruto = +22.50 USD. Fees = 0.075. Neto = +22.425 USD.
    close_trade(tmp_path, tid, exit_price=130.0, tag="TP2_EXIT")
    trades_closed = load_trades(tmp_path)
    res_final = realized_pnl_usd(trades_closed[0], costs)
    # Total Neto = 3.73 + 22.42 = 26.15 USD (+26% sobre nocional)
    assert res_final["pnl_neto_usd"] == pytest.approx(26.15, abs=0.10)


# ---------------- 7. Niveles R:R Asimétricos (TP1 3.0x y TP2 6.0x) ----------------
def test_calcular_niveles_rr_asymmetric() -> None:
    entry = 100.0
    atr14 = 2.0
    geom = calcular_niveles_rr(entry, atr14, "LONG")
    # dist_sl = max(1.5 * 2.0, 0.015 * 100) = 3.0
    assert geom["dist_sl"] == 3.0
    assert geom["sl"] == 97.0
    # TP1 = 100 + 3.0 * 3.0 = 109.0
    assert geom["tp1"] == 109.0
    # TP2 = 100 + 6.0 * 3.0 = 118.0
    assert geom["tp2"] == 118.0
    assert geom["rr_neto"] == 6.0


# ---------------- 8. Telemetría y Notificaciones ----------------
def test_notifications_silent_and_safe() -> None:
    assert send_discord_alert("Prueba") is False
    assert send_telegram_alert("Prueba") is False

    notify_event(
        "ORDER_OPEN",
        {
            "asset": "BTCUSDT",
            "timeframe": "4h",
            "kind": "future_long",
            "entry_price": 70000.0,
            "sl": 67000.0,
            "tp1": 79000.0,
            "tp2": 88000.0,
            "score": 90,
            "risk_usd": 35.0,
            "risk_pct": 0.035,
        },
    )
    notify_event("HEAT_WARNING", {"heat_usd": 220.0, "heat_pct": 22.0})
