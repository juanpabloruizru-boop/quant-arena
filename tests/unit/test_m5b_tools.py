"""Herramientas M5b: contabilidad de capital, filtro R:R, calculadora, auditoría.

Todo offline (fixtures sintéticos + config del repo copiada a tmp_path para los
tests de CLI). Verifica la aritmética documentada en el informe M5b y el guard
de lenguaje del dashboard con los nuevos paneles.
"""

from __future__ import annotations

import json
import shutil
from pathlib import Path
from typing import Any

import pytest
from typer.testing import CliRunner

from qa.agent.audit import closed_rows, max_drawdown_realizado_usd, run_audit
from qa.agent.capital import (
    add_capital,
    compute_status,
    load_capital,
    net_contributed,
    open_risk_usd,
    reset_examples,
    set_capital,
    verify_capital_chain,
)
from qa.agent.geometry import (
    breakeven_neto,
    check_rr_discipline,
    position_calc,
    rr_neto_trade,
    rr_tendencia,
    tp_minimo_para_rr,
    trade_calc,
)
from qa.agent.telemetry import trade_geometry
from qa.agent.tracker import close_trade, load_trades, open_trade, verify_chain
from qa.report.dashboard import PROHIBIDOS, render_dashboard

REPO = Path(__file__).resolve().parents[2]
COSTS: dict[str, Any] = {
    "spot": {"taker_fee": 0.001},
    "perp_usdm": {"taker_fee": 0.0005},
}


# ------------------------- capital: libro y cadena -------------------------
def test_capital_ledger_chain_and_net(tmp_path: Path) -> None:
    set_capital(tmp_path, 1000.0, "Capital inicial", example=True)
    add_capital(tmp_path, 200.0, "Adición mensual", example=True)
    add_capital(tmp_path, -100.0, "Retiro parcial")
    ok, n, _ = verify_capital_chain(tmp_path)
    assert ok and n == 3
    recs = load_capital(tmp_path)
    assert net_contributed(recs) == pytest.approx(1100.0)
    # tampering rompe la cadena
    p = tmp_path / "ledger" / "user_capital.jsonl"
    lines = p.read_text(encoding="utf-8").splitlines()
    lines[0] = lines[0].replace("1000.0", "9999.0")
    p.write_text("\n".join(lines) + "\n", encoding="utf-8")
    ok2, _, msg = verify_capital_chain(tmp_path)
    assert not ok2 and "rota" in msg


def test_reset_examples_only_touches_examples(tmp_path: Path) -> None:
    set_capital(tmp_path, 1000.0, "EJEMPLO", example=True)
    add_capital(tmp_path, 500.0, "aporte real")
    t_ex = open_trade(
        tmp_path, "BTCUSDT", "spot", "1d", 100.0, 50.0, 90.0, 130.0, example=True, tag="x"
    )
    close_trade(tmp_path, t_ex["id"], 120.0)
    t_real = open_trade(tmp_path, "ETHUSDT", "spot", "1d", 100.0, 50.0, 90.0, 130.0, tag="real")
    out = reset_examples(tmp_path)
    assert out["capital_removed"] == 1
    assert out["trades_removed"] == 2  # open ejemplo + su close
    assert out["capital_chain"]["ok"] and out["trades_chain"]["ok"]
    cap = load_capital(tmp_path)
    assert len(cap) == 1 and cap[0]["amount"] == 500.0
    trades = load_trades(tmp_path)
    assert [t["id"] for t in trades] == [t_real["id"]]
    assert out["backups"] and all(Path(tmp_path / b).exists() for b in out["backups"])


# ------------------------- ecuación patrimonial -------------------------
def _seed_portfolio(root: Path) -> list[dict[str, Any]]:
    """Cartera sintética con valores esperados calculados a mano."""
    set_capital(root, 1000.0, "inicial", example=True)
    add_capital(root, 200.0, "adición", example=True)
    # ganadora cerrada +2.4R (spot)
    w = open_trade(
        root, "BTCUSDT", "spot", "1d", 78000.0, 400.0, 74000.0, 87756.0, tag="Tendencia 1D"
    )
    close_trade(root, w["id"], 87756.0, ts_utc="2026-10-10T00:00:00+00:00")
    # perdedora cerrada -1.0R (perp)
    lo = open_trade(
        root, "ETHUSDT", "future_long", "4h", 2400.0, 300.0, 2300.0, 2700.0, tag="Ruptura 4H"
    )
    close_trade(root, lo["id"], 2302.40, ts_utc="2026-10-14T00:00:00+00:00")
    # abiertas: normal, SL en zona de ganancia (heat 0), sin SL
    open_trade(root, "BTCUSDT", "spot", "1d", 79500.0, 500.0, 74000.0, 95000.0)
    open_trade(root, "SOLUSDT", "spot", "1d", 100.0, 200.0, 110.0, 150.0)
    open_trade(root, "XRPUSDT", "spot", "1d", 0.5, 100.0, None, None)
    return load_trades(root)


PRICES = {"BTCUSDT": 80848.0, "SOLUSDT": 120.0, "XRPUSDT": 0.55, "ETHUSDT": 2343.77}


def test_compute_status_equity_equation(tmp_path: Path) -> None:
    trades = _seed_portfolio(tmp_path)
    st = compute_status(load_capital(tmp_path), trades, PRICES, COSTS)
    # 1) aportado
    assert st["capital_aportado_neto"] == pytest.approx(1200.0)
    # 2) realizado neto: +49.23 (BTC) - 12.50 (ETH) = +36.73
    assert st["pnl_realizado_usd"] == pytest.approx(36.73, abs=0.02)
    assert st["pnl_realizado_pct_aportado"] == pytest.approx(3.06, abs=0.02)
    # 3) flotante bruto: BTC +8.48, SOL +40.00, XRP +10.00
    assert st["pnl_flotante_usd"] == pytest.approx(58.48, abs=0.05)
    # 4) patrimonio = 1200 + 36.73 + 58.48
    assert st["patrimonio_total"] == pytest.approx(1295.21, abs=0.1)
    # 5) heat: BTC 34.59 + SOL 0 (SL sobre entrada = zona ganancia) + XRP sin SL
    assert st["portfolio_heat_usd"] == pytest.approx(34.59, abs=0.02)
    assert st["abiertas_sin_sl"] and "XRPUSDT" in st["abiertas_sin_sl"][0]
    assert st["portfolio_heat_pct_patrimonio"] == pytest.approx(
        34.59 / st["patrimonio_total"] * 100, abs=0.05
    )


def test_open_risk_sl_in_profit_is_zero() -> None:
    t_long = {"entry_price": 100.0, "sl": 110.0, "size_usd": 200.0, "kind": "spot"}
    assert open_risk_usd(t_long) == 0.0
    t_short = {"entry_price": 100.0, "sl": 90.0, "size_usd": 200.0, "kind": "future_short"}
    assert open_risk_usd(t_short) == 0.0  # SL bajo la entrada en corto = ganancia
    t_short_risk = {"entry_price": 100.0, "sl": 110.0, "size_usd": 200.0, "kind": "future_short"}
    assert open_risk_usd(t_short_risk) == pytest.approx(20.0)
    assert open_risk_usd({"entry_price": 100.0, "sl": None, "size_usd": 1.0}) is None


# ------------------------- geometría R:R -------------------------
def test_rr_neto_trade_formula() -> None:
    # (|115-100| - 0.2) / (|100-95| + 0.2) = 14.8/5.2
    assert rr_neto_trade(100.0, 95.0, 115.0, 0.002) == pytest.approx(2.846, abs=0.001)
    assert rr_neto_trade(100.0, 100.0, 115.0, 0.002) is None  # sin riesgo
    d = check_rr_discipline(100.0, 95.0, 115.0, "spot", COSTS, 2.0)
    assert d["cumple"] is True and "CUMPLE" in d["aviso"]
    d2 = check_rr_discipline(100.0, 95.0, 105.0, "spot", COSTS, 2.0)
    assert d2["cumple"] is False
    assert "ALERTA DE DISCIPLINA" in d2["aviso"] and "< mínimo 2.0x" in d2["aviso"]


def test_rr_tendencia_early_vs_extended_vs_below() -> None:
    early = rr_tendencia(102.0, 100.0, 10.0, 0.002, 2.0)
    assert early["aplica"] and early["cumple"]
    assert early["label"] == f"FILTRO R:R >= 2.0: CUMPLE (Asimetría {early['rr']:.2f}x)"
    # ext=2, risk=max(2,10)+0.204=10.204, reward=30-2=28 -> 2.74x
    assert early["rr"] == pytest.approx(2.744, abs=0.01)

    ext = rr_tendencia(125.0, 100.0, 10.0, 0.002, 2.0)
    assert ext["aplica"] and ext["cumple"] is False
    assert "NO CUMPLE" in ext["label"] and "Extendido" in ext["label"]
    # ext=25, risk=25+0.25, reward=5 -> 0.198x
    assert ext["rr"] == pytest.approx(0.198, abs=0.01)

    very = rr_tendencia(135.0, 100.0, 10.0, 0.002, 2.0)
    assert very["aplica"] and very["cumple"] is False and very["reward_dist"] < 0

    below = rr_tendencia(95.0, 100.0, 10.0, 0.002, 2.0)
    assert below["aplica"] is False and "NO APLICA" in below["label"]
    nodata = rr_tendencia(95.0, None, None, 0.002, 2.0)
    assert nodata["aplica"] is False


def test_breakeven_and_tp_minimos() -> None:
    be_long = breakeven_neto(100.0, "spot", COSTS, long=True)
    assert be_long == pytest.approx(100.0 * 1.001 / 0.999, abs=1e-6)
    be_short = breakeven_neto(100.0, "future_short", COSTS, long=False)
    assert be_short == pytest.approx(100.0 * 0.9995 / 1.0005, abs=1e-6)
    assert be_short < 100.0 < be_long
    # TP minimo 2R long: entry + 2*(risk+fee) + fee = 100 + 2*5.2 + 0.2
    tp2 = tp_minimo_para_rr(100.0, 95.0, "spot", COSTS, long=True, k=2.0)
    assert tp2 == pytest.approx(110.6, abs=1e-6)
    tp3 = tp_minimo_para_rr(100.0, 95.0, "spot", COSTS, long=True, k=3.0)
    assert tp3 == pytest.approx(115.8, abs=1e-6)
    # coherencia: con ese TP, el R:R neto es exactamente k
    assert tp2 is not None and tp3 is not None
    assert rr_neto_trade(100.0, 95.0, tp2, 0.002) == pytest.approx(2.0, abs=1e-6)
    assert rr_neto_trade(100.0, 95.0, tp3, 0.002) == pytest.approx(3.0, abs=1e-6)
    # short perp: tp_min 2R = 100 - (2*5.1 + 0.1) = 89.7
    tp2s = tp_minimo_para_rr(100.0, 105.0, "future_short", COSTS, long=False, k=2.0)
    assert tp2s == pytest.approx(89.7, abs=1e-6)


def test_position_calc_rows() -> None:
    row = position_calc(100.0, 95.0, 1000.0, 1.0)
    assert row is not None
    assert row["risk_usd"] == pytest.approx(10.0)
    assert row["size_usd"] == pytest.approx(200.0)  # 10 / 0.05
    assert row["unidades"] == pytest.approx(2.0)
    assert row["size_pct_equity"] == pytest.approx(20.0)
    assert position_calc(100.0, 100.0, 1000.0, 1.0) is None  # sin riesgo
    res = trade_calc(100.0, 95.0, 115.0, "spot", COSTS, 2.0, 1000.0)
    assert [f["risk_pct"] for f in res["filas_riesgo"]] == [0.5, 1.0, 2.0]
    assert res["cumple_filtro"] is True and res["tp_min_2r"] == pytest.approx(110.6)


# ------------------------- trade geometry (break-even + cota) -------------------------
def test_trade_geometry_breakeven_and_atr_bound() -> None:
    t = {
        "id": "x",
        "asset": "BTCUSDT",
        "kind": "spot",
        "timeframe": "1d",
        "entry_price": 100.0,
        "size_usd": 200.0,
        "sl": 90.0,
        "tp": 130.0,
        "ts_utc": "2026-10-01T00:00:00+00:00",
    }
    g = trade_geometry(t, 110.0, atr_marco=4.0, fee_taker_lado=0.001)
    assert g["breakeven_neto"] == pytest.approx(100.0 * 1.001 / 0.999, abs=1e-4)
    assert g["supero_breakeven"] is True
    assert "ENCIMA" in g["breakeven_txt"]
    assert g["cota_2atr"] == pytest.approx(102.0)  # 110 - 2*4
    assert g["rr_inicial_tp_sl"] == pytest.approx(3.0)
    assert g["rr_actual_tp_sl"] == pytest.approx(1.0)
    # short: cota por encima, break-even bajo la entrada
    ts = dict(t, kind="future_short", sl=110.0, tp=70.0)
    gs = trade_geometry(ts, 99.0, atr_marco=4.0, fee_taker_lado=0.0005)
    assert gs["cota_2atr"] == pytest.approx(107.0)  # 99 + 2*4 (corto: por encima)
    assert gs["breakeven_neto"] == pytest.approx(99.90, abs=0.01)
    assert gs["supero_breakeven"] is True  # precio 99 <= be 99.90


# ------------------------- auditoría -------------------------
def test_audit_metrics_and_tags(tmp_path: Path) -> None:
    trades = _seed_portfolio(tmp_path)
    out = run_audit(trades, COSTS, capital_aportado=1200.0)
    rows, summ = out["rows"], out["summary"]
    assert len(rows) == 2
    assert summ["total_cerradas"] == 2
    assert summ["win_rate_pct"] == pytest.approx(50.0)
    assert summ["pnl_neto_usd"] == pytest.approx(36.73, abs=0.02)
    assert summ["profit_factor"] == pytest.approx(3.94, abs=0.02)
    assert summ["esperanza_R_por_trade"] == pytest.approx(0.7, abs=0.01)
    assert summ["rr_medio_realizado_R"] == pytest.approx(0.7, abs=0.01)
    assert summ["mejor_peor_usd"] is not None
    assert summ["mejor_peor_usd"]["mejor"]["asset"] == "BTCUSDT"
    assert summ["mejor_peor_usd"]["peor"]["asset"] == "ETHUSDT"
    assert summ["mejor_peor_R"]["mejor"]["valor"] == pytest.approx(2.4, abs=0.01)
    assert summ["mejor_peor_R"]["peor"]["valor"] == pytest.approx(-1.0, abs=0.01)
    assert summ["pnl_neto_pct_aportado"] == pytest.approx(3.06, abs=0.02)
    # max dd realizado: cum 49.23 -> 36.73 => dd 12.50
    assert summ["max_drawdown_realizado_usd"] == pytest.approx(12.50, abs=0.02)
    tags = summ["por_tag"]
    assert tags["Tendencia 1D"]["trades"] == 1 and tags["Tendencia 1D"]["win_rate_pct"] == 100.0
    assert tags["Ruptura 4H"]["pnl_neto_usd"] == pytest.approx(-12.50, abs=0.01)
    assert max_drawdown_realizado_usd(rows) >= 0


def test_audit_rows_sorted_and_r_requires_sl(tmp_path: Path) -> None:
    t = open_trade(tmp_path, "BTCUSDT", "spot", "1d", 100.0, 100.0, None, 130.0)
    close_trade(tmp_path, t["id"], 110.0, ts_utc="2026-10-02T00:00:00+00:00")
    rows = closed_rows(load_trades(tmp_path), COSTS)
    assert len(rows) == 1
    assert rows[0]["r_multiplo"] is None  # sin SL -> R no computable
    assert rows[0]["pnl_neto_usd"] == pytest.approx(9.8, abs=0.01)  # 10 - 0.2 fees


# ------------------------- dashboard M5b -------------------------
def _min_states() -> dict[str, Any]:
    return {
        "fetched_at_utc": "2026-10-28T00:00:00Z",
        "cells": {
            "H1_BTCUSDT": {
                "veredicto": "SIN VENTAJA DEMOSTRADA (INCONTRASTABLE)",
                "nota": "n",
                "estado": "LONG",
                "posicion_regla": 0.6,
                "objetivo_actual": 0.6,
                "close": 102.0,
                "sma50": 100.0,
                "close_vs_sma50_pct": 2.0,
                "vol_realizada_20d_ann": 0.4,
                "last_candle_utc": "2026-10-27",
            },
        },
    }


def _min_capital() -> dict[str, Any]:
    return {
        "sin_registros": False,
        "capital_aportado_neto": 1200.0,
        "movimientos": [
            {
                "ts_utc": "2026-09-15T10:00:00+00:00",
                "tipo": "inicial",
                "amount": 1000.0,
                "acumulado": 1000.0,
                "note": "EJEMPLO",
                "example": True,
            },
            {
                "ts_utc": "2026-10-01T10:00:00+00:00",
                "tipo": "flujo",
                "amount": 200.0,
                "acumulado": 1200.0,
                "note": "",
                "example": False,
            },
        ],
        "pnl_realizado_usd": 36.73,
        "pnl_realizado_pct_aportado": 3.06,
        "comisiones_cerradas_est_usd": 1.1,
        "pnl_flotante_usd": 14.19,
        "pnl_flotante_pct_aportado": 1.18,
        "comisiones_abiertas_est_usd": 1.3,
        "flotante_detalle": [],
        "sin_precio_vivo": [],
        "patrimonio_total": 1250.92,
        "portfolio_heat_usd": 67.2,
        "portfolio_heat_pct_patrimonio": 5.37,
        "heat_detalle": [{"id": "a1", "asset": "BTCUSDT", "riesgo_usd": 67.2, "sin_sl": False}],
        "abiertas_sin_sl": [],
        "n_abiertas": 2,
        "n_cerradas": 2,
    }


def _min_audit() -> dict[str, Any]:
    return {
        "rows": [
            {
                "id": "w1",
                "asset": "BTCUSDT",
                "kind": "spot",
                "timeframe": "1d",
                "opened_at": "2026-09-20T00:00:00+00:00",
                "closed_at": "2026-10-10T00:00:00+00:00",
                "duracion": "20d 0h",
                "entry": 78000.0,
                "exit": 87756.0,
                "size_usd": 400.0,
                "rr_inicial_bruto": 2.44,
                "pnl_bruto_usd": 50.03,
                "fees_est_usd": 0.8,
                "pnl_neto_usd": 49.23,
                "pnl_pct": 12.508,
                "r_multiplo": 2.4,
                "tag": "Tendencia 1D",
                "note": "",
                "close_note": "",
                "example": True,
            }
        ],
        "summary": {
            "total_cerradas": 1,
            "win_rate_pct": 100.0,
            "pnl_neto_usd": 49.23,
            "pnl_neto_pct_rotacion": 12.31,
            "pnl_neto_pct_aportado": 4.1,
            "profit_factor": "n/a (sin pérdidas cerradas)",
            "esperanza_usd_por_trade": 49.23,
            "esperanza_R_por_trade": 2.4,
            "rr_medio_realizado_R": 2.4,
            "mejor_peor_usd": {
                "mejor": {"id": "w1", "asset": "BTCUSDT", "valor": 49.23},
                "peor": {"id": "w1", "asset": "BTCUSDT", "valor": 49.23},
            },
            "mejor_peor_R": {
                "mejor": {"id": "w1", "asset": "BTCUSDT", "valor": 2.4},
                "peor": {"id": "w1", "asset": "BTCUSDT", "valor": 2.4},
            },
            "max_drawdown_realizado_usd": 0.0,
            "trades_sin_sl": 0,
            "por_tag": {
                "Tendencia 1D": {
                    "trades": 1,
                    "ganadoras": 1,
                    "pnl_neto_usd": 49.23,
                    "suma_R": 2.4,
                    "n_con_R": 1,
                    "win_rate_pct": 100.0,
                    "R_medio": 2.4,
                }
            },
            "generado_utc": "2026-10-28T00:00:00+00:00",
        },
    }


def test_dashboard_m5b_panels_and_guard() -> None:
    tele = {
        "BTCUSDT": {
            "cambio_24h_pct": 1.2,
            "4h": {
                "disponible": True,
                "precio": 102.0,
                "sma50": 100.0,
                "dist_sma50_pct": 2.0,
                "lado_sma50": "por encima",
                "atr14_pct": 1.0,
                "rr_geom": rr_tendencia(102.0, 100.0, 3.0, 0.002, 2.0),
            },
            "1d": {
                "disponible": True,
                "precio": 102.0,
                "sma50": 100.0,
                "dist_sma50_pct": 2.0,
                "lado_sma50": "por encima",
                "atr14_pct": 2.0,
                "rr_geom": rr_tendencia(125.0, 100.0, 10.0, 0.002, 2.0),
            },
            "1w": {"disponible": False},
        }
    }
    h1_lv = {
        "BTCUSDT": {
            "precio": 102.0,
            "nivel_sma50": 100.0,
            "distancia_a_sma50_pct": 2.0,
            "atr14_usd": 2.0,
            "atr14_pct": 2.0,
            "banda_inf_c_menos_2atr": 98.0,
            "banda_sup_c_mas_3atr": 108.0,
            "exposicion_regla": 0.6,
            "escala_usd_sobre_capital_ref": 750.55,
            "capital_ref_usd": 1250.92,
            "capital_base_origen": "patrimonio vivo (tu contabilidad M5b)",
            "rr_filtro": rr_tendencia(125.0, 100.0, 10.0, 0.002, 2.0),
            "escala_bloqueada_por_rr": True,
        }
    }
    trades = [
        {
            "id": "op1",
            "asset": "BTCUSDT",
            "kind": "spot",
            "timeframe": "1d",
            "pnl_pct": 1.7,
            "pnl_usd": 8.5,
            "dist_sl_pct": 8.4,
            "dist_tp_pct": 17.5,
            "tiempo_abierta": "2d 3h",
            "rr_inicial_tp_sl": 2.71,
            "rr_actual_tp_sl": 2.2,
            "breakeven_neto": 79659.5,
            "supero_breakeven": True,
            "breakeven_txt": "precio por ENCIMA del break-even neto",
            "cota_2atr": 77000.0,
            "contexto_tendencia": "ctx",
            "estado_seguimiento": "SIN ALERTAS — contexto: ctx",
            "example": True,
        }
    ]
    calc = {
        "equity_usd": 1250.92,
        "equity_origen": "patrimonio vivo (tu contabilidad M5b)",
        "min_rr": 2.0,
        "fee_taker_spot": 0.001,
        "fee_taker_perp": 0.0005,
        "risk_pcts": [0.5, 1.0, 2.0],
    }
    html_out = render_dashboard(
        _min_states(),
        trades,
        [],
        {"X": "ok"},
        [],
        {"BTCUSDT": [1.0, 2.0]},
        {"git_sha": "abc", "evidencia": {"filas": []}},
        telemetry=tele,
        h1_levels=h1_lv,
        capital_ref=1000.0,
        capital=_min_capital(),
        audit=_min_audit(),
        calc=calc,
    )
    import html as _html

    up = _html.unescape(html_out).upper()  # texto tal como se VE en el navegador
    for bad in PROHIBIDOS:
        assert bad not in up
        assert bad not in html_out.upper()
    # barra de patrimonio (5 tarjetas)
    assert "CAPITAL APORTADO NETO" in up
    assert "PNL CERRADO (NETO)" in up
    assert "PNL ABIERTO (VIVO)" in up
    assert "PATRIMONIO TOTAL (EQUITY VIVO)" in up
    assert "RIESGO EN MESA (PORTFOLIO HEAT)" in up
    assert "1,250.92" in html_out
    # calculadora
    assert "CALCULADORA DE RIESGO POR OPERACIÓN" in up
    assert "QA_CALC_BTN" in up and "QA_MIN_RR" in up
    assert "TP QUE SATISFACE R:R = 2.0X" in up
    assert "BREAK-EVEN NETO" in up
    # filtro R:R
    assert "FILTRO R:R >= 2.0: NO CUMPLE" in up
    assert "EXTENDIDO" in up
    assert "BLOQUEADO POR FILTRO R:R" in up
    assert "FILTRO R:R >= 2.0: CUMPLE" in up  # celda 4h del watchlist
    # operaciones abiertas mejoradas
    assert "COTA 2×ATR" in up
    assert "SUPERADO ✓" in up
    # auditoría + capital
    assert "TRADE AUDIT" in up
    assert "TENDENCIA 1D" in up
    assert "WIN RATE" in up
    assert "PROFIT FACTOR" in up
    assert "HISTORIAL DE CAPITAL" in up
    assert "ESPERANZA MATEMÁTICA" in up


def test_dashboard_without_capital_shows_hint() -> None:
    html_out = render_dashboard(
        _min_states(), [], [], {}, [], {}, {"git_sha": "x", "evidencia": {"filas": []}}
    )
    assert "qa capital set" in html_out
    up = html_out.upper()
    for bad in PROHIBIDOS:
        assert bad not in up


# ------------------------- CLI (offline) -------------------------
@pytest.fixture()
def cli_root(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    shutil.copytree(REPO / "config", tmp_path / "config")
    monkeypatch.setenv("QA_ROOT", str(tmp_path))
    return tmp_path


def test_cli_capital_set_add_status(cli_root: Path) -> None:
    from qa.cli import app

    r = CliRunner()
    res = r.invoke(app, ["capital", "set", "--amount", "1000", "--note", "Capital inicial"])
    assert res.exit_code == 0, res.output
    res = r.invoke(app, ["capital", "add", "--amount", "200", "--note", "Adición mensual"])
    assert res.exit_code == 0, res.output
    res = r.invoke(app, ["capital", "status"])
    assert res.exit_code == 0, res.output
    assert "1,200.00" in res.output
    assert "PATRIMONIO TOTAL" in res.output
    assert "Portfolio Heat" in res.output


def test_cli_trade_open_rr_block_and_force(cli_root: Path) -> None:
    from qa.cli import app

    r = CliRunner()
    # R:R neto = (5 - 0.2)/(5 + 0.2) = 0.92x < 2.0 -> BLOQUEADO
    res = r.invoke(
        app,
        [
            "trade",
            "open",
            "--asset",
            "BTCUSDT",
            "--kind",
            "spot",
            "--entry",
            "100",
            "--size-usd",
            "50",
            "--sl",
            "95",
            "--tp",
            "105",
        ],
    )
    assert res.exit_code == 2
    assert "ALERTA DE DISCIPLINA" in res.output and "BLOQUEADO" in res.output
    p = cli_root / "ledger" / "user_trades.jsonl"
    assert not p.exists() or not p.read_text(encoding="utf-8").strip()
    # con --force-low-rr se registra marcado
    res = r.invoke(
        app,
        [
            "trade",
            "open",
            "--asset",
            "BTCUSDT",
            "--kind",
            "spot",
            "--entry",
            "100",
            "--size-usd",
            "50",
            "--sl",
            "95",
            "--tp",
            "105",
            "--force-low-rr",
            "--tag",
            "test",
        ],
    )
    assert res.exit_code == 0, res.output
    rec = json.loads(p.read_text(encoding="utf-8").splitlines()[0])
    assert rec["rr_forzado"] is True and rec["rr_neto_inicial"] == pytest.approx(0.923, abs=0.01)
    assert rec["tag"] == "test"
    # R:R cumplidor pasa sin force
    res = r.invoke(
        app,
        [
            "trade",
            "open",
            "--asset",
            "ETHUSDT",
            "--kind",
            "spot",
            "--entry",
            "100",
            "--size-usd",
            "50",
            "--sl",
            "95",
            "--tp",
            "115",
        ],
    )
    assert res.exit_code == 0 and "CUMPLE" in res.output


def test_cli_trade_calc(cli_root: Path) -> None:
    from qa.cli import app

    r = CliRunner()
    res = r.invoke(
        app,
        ["trade", "calc", "--entry", "100", "--sl", "95", "--tp", "115", "--equity", "1000"],
    )
    assert res.exit_code == 0, res.output
    assert "10.00" in res.output  # riesgo $ al 1%
    assert "200.00" in res.output  # tamaño al 1%
    assert "110.60" in res.output  # TP mínimo 2R
    assert "115.80" in res.output  # TP mínimo 3R
    assert "100.20" in res.output  # break-even neto spot
    assert "CUMPLE" in res.output
    res2 = r.invoke(
        app,
        ["trade", "calc", "--entry", "100", "--sl", "95", "--tp", "105", "--equity", "1000"],
    )
    assert res2.exit_code == 2
    assert "NO CUMPLE" in res2.output and "ALERTA DE DISCIPLINA" in res2.output
    res3 = r.invoke(
        app,
        ["trade", "calc", "--entry", "100", "--sl", "95", "--risk-pct", "1.0", "--equity", "1000"],
    )
    assert res3.exit_code == 0 and "no es evaluable" in res3.output


def test_cli_trade_audit_and_reset(cli_root: Path) -> None:
    from qa.cli import app

    r = CliRunner()
    _seed_portfolio(cli_root)
    res = r.invoke(app, ["trade", "audit"])
    assert res.exit_code == 0, res.output
    assert "TRADE AUDIT" in res.output
    assert "Tendencia 1D" in res.output and "Ruptura 4H" in res.output
    assert "50.0%" in res.output  # win rate
    res = r.invoke(app, ["trade", "audit", "--json"])
    assert res.exit_code == 0
    payload = json.loads(res.output)
    assert payload["summary"]["total_cerradas"] == 2
    res = r.invoke(app, ["capital", "reset-examples", "--yes"])
    assert res.exit_code == 0, res.output
    assert "backup" in res.output
    ok, n, _ = verify_chain(cli_root)
    assert ok and n == 7  # los trades sembrados no eran EJEMPLO: permanecen
    cap = load_capital(cli_root)
    assert cap == []  # los 2 movimientos de capital eran EJEMPLO
