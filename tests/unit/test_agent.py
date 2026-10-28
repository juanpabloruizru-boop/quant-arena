"""Agente M4/M5: tracker (cadena), criba de noticias, choques, señales y
guard de lenguaje del dashboard. Todo offline (fixtures sintéticos)."""

from __future__ import annotations

from dataclasses import asdict
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd
import pytest

from qa.agent.news import NewsItem, detect_shocks, screen_title
from qa.agent.signals import band_positions, h1_state, h3_state
from qa.agent.tracker import close_trade, diagnose, load_trades, open_trade, verify_chain
from qa.forward.paper import append_forward_record, verify_forward_chain
from qa.report.dashboard import PROHIBIDOS, render_dashboard


# ---------------- tracker ----------------
def test_trade_chain_and_diagnose(tmp_path: Path) -> None:
    t = open_trade(
        tmp_path,
        "BTCUSDT",
        "spot",
        "1d",
        80_000.0,
        1_000.0,
        74_000.0,
        95_000.0,
        note="prueba",
        example=True,
    )
    ok, n, _ = verify_chain(tmp_path)
    assert ok and n == 1
    d = diagnose(t, 82_000.0, "1D por encima de SMA50", [])
    assert d["pnl_pct"] == pytest.approx(2.5)
    assert d["pnl_usd"] == pytest.approx(25.0)
    assert d["dist_sl_pct"] == pytest.approx(round((82_000 - 74_000) / 82_000 * 100, 2))
    assert "SIN ALERTAS" in d["estado_seguimiento"]
    d2 = diagnose(t, 82_000.0, "ctx", ["choque 4h: -6%"])
    assert d2["estado_seguimiento"].startswith("REVISAR (hechos observados, no es una orden)")
    close_trade(tmp_path, t["id"], 83_000.0)
    trades = load_trades(tmp_path)
    assert trades[0]["status"] == "closed"
    # tampering rompe la cadena
    p = tmp_path / "ledger" / "user_trades.jsonl"
    lines = p.read_text().splitlines()
    lines[0] = lines[0].replace("prueba", "TRUCADO")
    p.write_text("\n".join(lines) + "\n")
    ok2, _, msg = verify_chain(tmp_path)
    assert not ok2 and "rota" in msg


# ---------------- noticias / choques ----------------
def test_screen_title() -> None:
    kws, bases = screen_title(
        "Binance to delist FTT after insolvency fears", ["delist", "insolven"], ["ftt", "btc"]
    )
    assert "delist" in kws and "insolven" in kws
    assert "ftt" in bases
    k2, b2 = screen_title("Bitcoin ETF inflows hit record", ["hack"], ["btc"])
    assert k2 == [] and b2 == ["btc"]


def _klines(n: int, crash: bool) -> pd.DataFrame:
    rng = np.random.default_rng(0)
    base = 100 + np.cumsum(rng.normal(0, 0.5, n))
    if crash:
        base[-7:] -= np.linspace(0, 18, 7)
    df = pd.DataFrame(
        {
            "open_time": pd.date_range("2026-01-01", periods=n, freq="4h", tz="UTC"),
            "open": base,
            "high": base + 1.0,
            "low": base - 1.0,
            "close": base,
            "quote_volume": np.full(n, 1e6),
        }
    )
    if crash:
        df.loc[df.index[-1], "quote_volume"] = 9e6
    return df


def test_detect_shocks() -> None:
    calm = _klines(60, crash=False)
    crash = _klines(60, crash=True)
    kl = {
        "AAAUSDT": {"4h": calm, "1h": calm},
        "BBBUSDT": {"4h": crash, "1h": crash},
    }
    prem = {"BBBUSDT": {"last_funding_rate": -0.0009}}
    out = detect_shocks(
        kl,
        prem,
        {
            "atr_window": 14,
            "umbral_4h_atr": 2.5,
            "umbral_1h_atr": 3.0,
            "umbral_volumen": 3.0,
            "umbral_funding_abs": 0.0005,
        },
    )
    tipos = {(o["symbol"], o["tipo"]) for o in out}
    assert ("BBBUSDT", "choque_4h") in tipos
    assert ("BBBUSDT", "spike_volumen_4h") in tipos
    assert ("BBBUSDT", "funding_extremo") in tipos
    assert all(o["symbol"] != "AAAUSDT" for o in out)


# ---------------- señales ----------------
def test_band_positions_flips_always_trade() -> None:
    target = np.array([0.0, 0.8, 0.75, 0.72, 0.0, 0.5])
    pos = band_positions(target, band=0.10)
    assert pos[1] == 0.8  # flip entra
    assert pos[2] == 0.8  # -5pp < banda: no toca
    assert pos[3] == 0.8  # -8pp acumulado desde 0.8? |0.72-0.8|=0.08 < 0.10: no toca
    assert pos[4] == 0.0  # flip a flat siempre opera
    assert pos[5] == 0.5


def test_h1_state_long_when_above_sma() -> None:
    n = 120
    close = np.linspace(100, 160, n)  # tendencia alcista limpia
    df = pd.DataFrame(
        {
            "open_time": pd.date_range("2026-01-01", periods=n, freq="D", tz="UTC"),
            "close": close,
        }
    )
    st = h1_state(df)
    assert st["estado"] == "LONG"
    assert st["close_vs_sma50_pct"] > 0
    assert 0.0 < st["posicion_regla"] <= 1.0
    assert "SIN VENTAJA DEMOSTRADA" in st["veredicto"]


def test_h3_state_threshold() -> None:
    days = pd.date_range("2026-08-01", periods=40, freq="D", tz="UTC")
    times = [d + pd.Timedelta(hours=h) for d in days for h in (0, 8, 16)]
    f = pd.DataFrame({"funding_time": times, "funding_rate": [0.0002] * len(times)})
    st = h3_state(f)
    assert st["senal_activa"] is True  # 0.0002*3*365 = 21.9% > 5%
    f2 = pd.DataFrame({"funding_time": times, "funding_rate": [0.00001] * len(times)})
    assert h3_state(f2)["senal_activa"] is False


# ---------------- forward chain ----------------
def test_forward_chain(tmp_path: Path) -> None:
    states = {
        "fetched_at_utc": "x",
        "cells": {"H1_BTCUSDT": {"estado": "FLAT", "posicion_regla": 0.0}},
    }
    append_forward_record(tmp_path, states)
    append_forward_record(tmp_path, states)
    ok, n, _ = verify_forward_chain(tmp_path)
    assert ok and n == 2


# ---------------- guard de lenguaje del dashboard ----------------
def _fixture_dashboard_inputs() -> dict[str, Any]:
    states = {
        "fetched_at_utc": "2026-10-28T00:00:00Z",
        "cells": {
            "H1_BTCUSDT": {
                "veredicto": "SIN VENTAJA DEMOSTRADA (INCONTRASTABLE)",
                "nota": "n",
                "estado": "FLAT",
                "posicion_regla": 0.0,
                "objetivo_actual": 0.0,
                "close": 80000.0,
                "sma50": 85000.0,
                "close_vs_sma50_pct": -5.9,
                "vol_realizada_20d_ann": 0.42,
                "last_candle_utc": "2026-10-27",
            },
            "H1_ETHUSDT": {
                "veredicto": "SIN VENTAJA DEMOSTRADA (INCONTRASTABLE)",
                "nota": "n",
                "estado": "FLAT",
                "posicion_regla": 0.0,
                "objetivo_actual": 0.0,
                "close": 2300.0,
                "sma50": 2600.0,
                "close_vs_sma50_pct": -11.5,
                "vol_realizada_20d_ann": 0.55,
                "last_candle_utc": "2026-10-27",
            },
            "H2_L26_N10": {
                "veredicto": "SIN VENTAJA DEMOSTRADA (INCONTRASTABLE)",
                "nota": "n",
                "universo_top10_actual": ["BTCUSDT"],
                "formacion_26w": {},
                "cesta_teoretica": ["BTCUSDT"],
                "n_eligibles": 1,
            },
            "H3_BTCUSDT": {
                "veredicto": "VALIDADA (PASA in-sample + holdout signo)",
                "nota": "a nivel de signo; con costes x2 el edge es ~0",
                "funding_ma30_ann": 0.033,
                "funding_ma7_ann": 0.031,
                "umbral": 0.05,
                "senal_activa": False,
                "estado": "INACTIVA (MA30 <= 5% anual)",
                "last_funding_rate": 0.00008,
                "next_funding_utc": "2026-10-28T16:00",
            },
            "H3_ETHUSDT": {
                "veredicto": "NO PASA (holdout)",
                "nota": "n",
                "funding_ma30_ann": 0.036,
                "funding_ma7_ann": 0.03,
                "umbral": 0.05,
                "senal_activa": False,
                "estado": "INACTIVA (MA30 <= 5% anual)",
                "last_funding_rate": 0.0001,
                "next_funding_utc": "2026-10-28T16:00",
            },
        },
    }
    trades = [
        {
            "id": "ex1",
            "asset": "BTCUSDT",
            "kind": "spot",
            "pnl_pct": -2.0,
            "pnl_usd": -20.0,
            "dist_sl_pct": 3.1,
            "dist_tp_pct": 12.0,
            "contexto_tendencia": "1D por debajo de SMA50",
            "estado_seguimiento": "SIN ALERTAS — contexto: 1D por debajo de SMA50",
            "example": True,
        }
    ]
    news = [
        asdict(
            NewsItem(
                "X", "BTC hack rumor denied", "http://x", "2026-10-27T10:00", ["hack"], ["btc"]
            )
        )
    ]
    shocks = [{"symbol": "ETHUSDT", "tipo": "choque_4h", "detalle": "-6% en 24h"}]
    meta = {"git_sha": "abc1234", "evidencia": {"filas": [["H1", "a", "b", "INCONTRASTABLE"]]}}
    return {"states": states, "trades": trades, "news": news, "shocks": shocks, "meta": meta}


def test_dashboard_language_guard() -> None:
    fx = _fixture_dashboard_inputs()
    tele = {
        "BTCUSDT": {
            "cambio_24h_pct": -1.2,
            "4h": {
                "disponible": True,
                "precio": 80000.0,
                "sma50": 79000.0,
                "dist_sma50_pct": 1.3,
                "lado_sma50": "por encima",
                "atr14_pct": 0.8,
            },
            "1d": {
                "disponible": True,
                "precio": 80000.0,
                "sma50": 85000.0,
                "dist_sma50_pct": -5.9,
                "lado_sma50": "por debajo",
                "atr14_pct": 2.4,
            },
            "1w": {"disponible": False},
        }
    }
    h1_lv = {
        "BTCUSDT": {
            "precio": 80000.0,
            "nivel_sma50": 85000.0,
            "distancia_a_sma50_pct": -5.9,
            "atr14_usd": 1900.0,
            "atr14_pct": 2.4,
            "banda_inf_c_menos_2atr": 76200.0,
            "banda_sup_c_mas_3atr": 85700.0,
            "exposicion_regla": 0.6,
            "escala_usd_sobre_capital_ref": 600.0,
            "capital_ref_usd": 1000.0,
        }
    }
    html_out = render_dashboard(
        fx["states"],
        fx["trades"],
        fx["news"],
        {"X": "ok"},
        fx["shocks"],
        {"BTCUSDT": [1.0, 2.0, 3.0]},
        fx["meta"],
        telemetry=tele,
        h1_levels=h1_lv,
        capital_ref=1000.0,
    )
    up = html_out.upper()
    for bad in PROHIBIDOS:
        assert bad not in up, f"lenguaje prohibido: {bad}"
    assert "SIN VENTAJA DEMOSTRADA" in up
    assert "NO PASA" in up
    assert "VALIDADA" in up
    assert "EJEMPLO" in up
    assert "NO ES ASESORAMIENTO DE INVERSIÓN" in up or "NO ES ASESORAMIENTO" in up
    assert "COSTES ×2" in up or "COSTES X2" in up
    # paneles de telemetria descriptiva con sus avisos obligatorios
    assert "TELEMETRÍA DESCRIPTIVA DE PRECIOS" in up
    assert "NO CONSTITUYE HIPÓTESIS EVALUADA NI SEÑAL DE TRADING" in up
    assert "ESCALA TEÓRICA" in up
    assert "NIVELES OBSERVABLES DE H1" in up
    assert "GLOSARIO PARA JP" in up
    assert "600.0 USD" in html_out  # escala aritmetica: 60% x 1000 USD
