# Claude Trading Skills Engine (TraderMonty Process Framework) — QUANT-ARENA v2
"""Motor de procesos y disciplina operativa de Claude Trading Skills.

Componentes:
1. ExposureCoach & CryptoRegimeAnalyzer:
   - Market Health Score (0-100) combinando régimen macro BTC vs SMA200(1D),
     amplitud de Cesta Élite (% sobre EMA21 4H), funding rates y volatilidad ATR.
   - Posturas: FULL_OFFENSE (25%), SELECTIVE (16%), REDUCE_ONLY (8%), CASH_PRIORITY (0%).
2. DrawdownCircuitBreaker & PreTradeDisciplineGate:
   - Circuit Breaker: COOLDOWN_HALT ante >=2 pérdidas consecutivas en 12h o DD diario >4%.
   - Pre-Trade Gate: Checklist determinista (exposición, cortacircuitos, anti-chasing,
     news reaction failure).
3. TraderMemoryCore & SignalPostmortem:
   - Seguimiento continuo de MFE y MAE (excursión favorable y adversa) en R.
   - Diagnóstico post-mortem (CLEAN_TREND_WIN, CHOP_STOP_OUT, LATE_CHASE_REVERSAL, PREMATURE_EXIT).
   - Bitácora inmutable en ledger/trader_memory.jsonl para inyección en el Cerebro Cognitivo.
"""

from __future__ import annotations

import contextlib
import json
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

import numpy as np

from qa.data.paths import get_root

CRUISE_ELITE = ["BTCUSDT", "ETHUSDT", "SOLUSDT", "SUIUSDT"]


# =====================================================================
# 1. ExposureCoach & CryptoRegimeAnalyzer
# =====================================================================


def compute_market_health(
    live_klines: dict[str, dict[str, Any]],
    funding_rates: dict[str, float] | None = None,
) -> dict[str, Any]:
    """Calcula el Market Health Score (0-100) y determina la postura del ExposureCoach."""
    # 1. Régimen Macro Bitcoin: BTC 1D vs SMA200 (hasta 30 pts)
    btc_frames = live_klines.get("BTCUSDT", {})
    btc_1d = btc_frames.get("1d")
    btc_macro_bull = True
    score_macro = 15.0

    if btc_1d is not None and len(btc_1d) >= 30:
        c_btc = btc_1d["close"].astype(float).to_numpy()
        w = min(200, len(c_btc))
        sma200_val = float(np.mean(c_btc[-w:]))
        btc_macro_bull = float(c_btc[-1]) >= sma200_val
        score_macro = 30.0 if btc_macro_bull else 5.0

    # 2. Amplitud de Cesta Élite: % de activos sobre EMA21(4H) (hasta 30 pts)
    elite_above_count = 0
    elite_total = len(CRUISE_ELITE)
    for sym in CRUISE_ELITE:
        df_4h = live_klines.get(sym, {}).get("4h")
        if df_4h is not None and len(df_4h) >= 21:
            c = df_4h["close"].astype(float)
            ema21 = c.ewm(span=21, adjust=False).mean().iloc[-1]
            if float(c.iloc[-1]) >= float(ema21):
                elite_above_count += 1
        else:
            elite_above_count += 1

    breadth_pct = (elite_above_count / elite_total) * 100.0 if elite_total > 0 else 50.0
    score_breadth = round((breadth_pct / 100.0) * 30.0, 1)

    # 3. Estado de Tasas de Funding (hasta 20 pts)
    f_rates = [
        abs(float(funding_rates.get(s, 0.0)))
        for s in CRUISE_ELITE
        if funding_rates and s in funding_rates
    ]
    avg_funding = float(np.mean(f_rates)) if f_rates else 0.0001
    if avg_funding > 0.0003:  # > 30% anualizado: mercado eufórico/hacinado
        score_funding = 5.0
        funding_status = "EXTREMO (RIESGO DE BARRIDO)"
    elif avg_funding > 0.00018:
        score_funding = 12.0
        funding_status = "MODERADO ALTO"
    else:
        score_funding = 20.0
        funding_status = "SALUDABLE / EQUILIBRADO"

    # 4. Volatilidad y Calidad de Tendencia ATR/ADX (hasta 20 pts)
    score_vol = 15.0
    vol_status = "COMPRESIÓN NORMAL"
    btc_4h = btc_frames.get("4h")
    if btc_4h is not None and len(btc_4h) >= 15:
        c4 = btc_4h["close"].astype(float)
        h4 = btc_4h["high"].astype(float)
        l4 = btc_4h["low"].astype(float)
        tr = np.maximum(h4 - l4, np.maximum(np.abs(h4 - c4.shift(1)), np.abs(l4 - c4.shift(1))))
        atr14 = tr.rolling(14).mean().dropna()
        if len(atr14) >= 10:
            curr_atr = float(atr14.iloc[-1])
            pctl = float((atr14 <= curr_atr).mean())
            if pctl < 0.35:
                score_vol = 20.0
                vol_status = "COMPRESIÓN ATR (RESORTE TENDENCIAL)"
            elif pctl > 0.85:
                score_vol = 6.0
                vol_status = "SOBRE-EXTENSIÓN ATR (RIESGO DE AGOTAMIENTO)"
            else:
                score_vol = 15.0
                vol_status = "VOLATILIDAD REGULAR SALUDABLE"

    total_health_score = int(round(score_macro + score_breadth + score_funding + score_vol))
    total_health_score = max(0, min(100, total_health_score))

    # Determinar Postura del ExposureCoach y Techo de Portfolio Heat (Mínimo siempre 15% a 25%)
    if total_health_score >= 70:
        posture = "FULL_OFFENSE"
        max_heat_pct = 25.0
        desc = "Condiciones óptimas: alta convicción y amplitud. Techo máximo de calor (25%)."
    elif total_health_score >= 45:
        posture = "PROACTIVE_BILATERAL"
        max_heat_pct = 20.0
        desc = "Mercado activo bilateral: buscando ganancias al alza y a la baja (20%)."
    else:
        posture = "SELECTIVE_BILATERAL"
        max_heat_pct = 15.0
        desc = (
            "Mercado selectivo: operando con disciplina y piso mínimo de calor garantizado (15%)."
        )

    return {
        "market_health_score": total_health_score,
        "posture": posture,
        "max_heat_pct": max_heat_pct,
        "description": desc,
        "btc_macro_bullish": btc_macro_bull,
        "breadth_pct": round(breadth_pct, 1),
        "funding_status": funding_status,
        "volatility_status": vol_status,
        "breakdown": {
            "macro_score": score_macro,
            "breadth_score": score_breadth,
            "funding_score": score_funding,
            "volatility_score": score_vol,
        },
    }


# =====================================================================
# 2. DrawdownCircuitBreaker & PreTradeDisciplineGate
# =====================================================================


def check_circuit_breaker(
    trades: list[dict[str, Any]],
    current_equity: float,
    starting_equity: float = 1000.0,
) -> dict[str, Any]:
    """Evalúa si el sistema debe entrar en COOLDOWN_HALT para frenar el overtrading."""
    now_utc = datetime.now(UTC)
    twelve_hours_ago = now_utc - timedelta(hours=12)

    # 1. Revisar pérdidas consecutivas recientes en las últimas 12 horas
    closed_recent: list[dict[str, Any]] = []
    for t in trades:
        if t.get("status") == "closed":
            exit_ts = t.get("exit_ts_utc") or t.get("ts_utc")
            if exit_ts:
                with contextlib.suppress(Exception):
                    dt = datetime.fromisoformat(exit_ts)
                    if dt.tzinfo is None:
                        dt = dt.replace(tzinfo=UTC)
                    if dt >= twelve_hours_ago:
                        closed_recent.append(t)

    # Ordenar por fecha de salida descendente
    closed_recent.sort(key=lambda x: str(x.get("exit_ts_utc") or x.get("ts_utc")), reverse=True)

    consecutive_losses = 0
    for ct in closed_recent:
        pnl = float(ct.get("pnl_neto_usd") or ct.get("pnl_usd") or 0.0)
        if pnl < 0:
            consecutive_losses += 1
        else:
            break

    # 2. Revisar drawdown diario respecto al capital de referencia
    dd_pct = (
        ((starting_equity - current_equity) / starting_equity) * 100.0
        if starting_equity > 0
        else 0.0
    )

    is_halted = False
    reasons: list[str] = []

    if consecutive_losses >= 2:
        is_halted = True
        reasons.append(
            f"{consecutive_losses} pérdidas consecutivas en <12h"
        )

    if dd_pct >= 4.0:
        is_halted = True
        reasons.append(
            f"Drawdown diario de {dd_pct:.1f}% excede el umbral de disciplina de 4.0%"
        )

    status = "COOLDOWN_HALT" if is_halted else "NORMAL"
    reason_txt = " + ".join(reasons) if is_halted else "Operativa normal autorizada"

    return {
        "status": status,
        "is_halted": is_halted,
        "reason": reason_txt,
        "consecutive_losses_12h": consecutive_losses,
        "daily_drawdown_pct": round(dd_pct, 2),
    }


def evaluate_discipline_gate(
    symbol: str,
    direction: str,
    current_price: float,
    ema21: float,
    current_heat_pct: float,
    trade_risk_pct: float,
    max_heat_allowed: float,
    circuit_breaker_status: str,
    news_items: list[Any] | None = None,
    funding_rate: float | None = None,
    kronos_forecast: dict[str, Any] | None = None,
    max_extension_pct: float = 0.018,
) -> dict[str, Any]:
    """Checklist Determinista de Pre-Trade antes de abrir cualquier posición."""
    reasons: list[str] = []

    # 1. Techo de Exposición (Exposure Coach)
    exposure_allowed = (current_heat_pct + trade_risk_pct) <= (max_heat_allowed + 0.001)
    if not exposure_allowed:
        reasons.append(
            f"Exposición excedida: {current_heat_pct+trade_risk_pct:.1f}% > "
            f"techo permitido {max_heat_allowed:.1f}%"
        )

    # 2. Cortacircuitos (Circuit Breaker)
    circuit_breaker_ok = circuit_breaker_status != "COOLDOWN_HALT"
    if not circuit_breaker_ok:
        reasons.append("Cortacircuitos activo (COOLDOWN_HALT por pérdidas recientes)")

    # 3. Anti-Chasing (No comprar sobre-extendido sobre EMA21)
    anti_chasing_ok = True
    eff_limit = (
        max(max_extension_pct, 0.045)
        if (kronos_forecast and float(kronos_forecast.get("confidence_score", 0)) >= 70)
        else max_extension_pct
    )
    if ema21 > 0:
        if direction == "LONG":
            dist_pct = (current_price - ema21) / ema21
            if dist_pct > eff_limit:
                anti_chasing_ok = False
                reasons.append(
                    f"Anti-Chasing: precio +{dist_pct*100:.1f}% sobre EMA21 "
                    f"(máx {eff_limit*100:.1f}%)"
                )
        else:
            dist_pct = (ema21 - current_price) / ema21
            if dist_pct > eff_limit:
                anti_chasing_ok = False
                reasons.append(
                    f"Anti-Chasing: precio -{dist_pct*100:.1f}% bajo EMA21 "
                    f"(máx {eff_limit*100:.1f}%)"
                )

    # 4. News Reaction Failure (Buenas noticias + funding alto pero precio cayendo)
    news_reaction_ok = True
    if news_items and funding_rate is not None and funding_rate > 0.00035:
        base = symbol.replace("USDT", "").lower()
        bull_words = ["hack", "insolvent", "lawsuit", "exploit"]
        has_negative_news = any(
            base in str(getattr(n, "assets", "")).lower()
            and any(w in str(getattr(n, "title", "")).lower() for w in bull_words)
            for n in news_items
        )
        if has_negative_news and direction == "LONG":
            news_reaction_ok = False
            reasons.append(
                "News Reaction Veto: Noticias de riesgo detectadas para el activo en LONG"
            )

    # 5. Alineación con Oráculo K-Line Kronos (kronos_alignment_ok)
    kronos_alignment_ok = True
    if kronos_forecast:
        k_verdict = str(kronos_forecast.get("kronos_verdict", "KRONOS_NEUTRAL"))
        k_bull_prob = float(kronos_forecast.get("bullish_prob", 50.0))
        if direction == "LONG" and k_verdict == "KRONOS_BEAR" and k_bull_prob <= 25.0:
            kronos_alignment_ok = False
            reasons.append(
                f"Kronos K-Line Veto: Proyección bajista extrema ({k_bull_prob:.1f}% <= 25%)"
            )
        elif direction == "SHORT" and k_verdict == "KRONOS_BULL" and k_bull_prob >= 75.0:
            kronos_alignment_ok = False
            reasons.append(
                f"Kronos K-Line Veto: Proyección alcista extrema ({k_bull_prob:.1f}% >= 75%)"
            )

    gate_passed = all(
        [
            exposure_allowed,
            circuit_breaker_ok,
            anti_chasing_ok,
            news_reaction_ok,
            kronos_alignment_ok,
        ]
    )
    return {
        "gate_passed": gate_passed,
        "exposure_allowed": exposure_allowed,
        "circuit_breaker_ok": circuit_breaker_ok,
        "anti_chasing_ok": anti_chasing_ok,
        "news_reaction_ok": news_reaction_ok,
        "kronos_alignment_ok": kronos_alignment_ok,
        "reasons": reasons,
    }


# =====================================================================
# 3. TraderMemoryCore & SignalPostmortem (Bucle de Memoria MAE / MFE)
# =====================================================================


def _memory_log_path(root: Path | None = None) -> Path:
    r = root or get_root()
    return r / "ledger" / "trader_memory.jsonl"


def update_live_excursions(trade: dict[str, Any], live_price: float) -> dict[str, Any]:
    """Actualiza en caliente el MFE y MAE en R de una posición abierta."""
    entry = float(trade.get("entry_price") or live_price)
    sl = float(trade.get("sl") or (entry * 0.985))
    dist_sl = float(trade.get("dist_sl") or abs(entry - sl))
    if dist_sl <= 0:
        dist_sl = entry * 0.015

    is_long = trade.get("kind") != "future_short"
    unrealized_r = (live_price - entry) / dist_sl if is_long else (entry - live_price) / dist_sl

    prev_mfe = float(trade.get("mfe_r", 0.0))
    prev_mae = float(trade.get("mae_r", 0.0))

    new_mfe = max(prev_mfe, unrealized_r)
    new_mae = min(prev_mae, unrealized_r)

    trade["mfe_r"] = round(new_mfe, 2)
    trade["mae_r"] = round(new_mae, 2)
    return trade


def record_postmortem(
    root: Path,
    trade: dict[str, Any],
    exit_price: float,
    pnl_neto_usd: float,
) -> dict[str, Any]:
    """Genera diagnóstico post-mortem de la operación y lo persiste en trader_memory.jsonl."""
    sym = trade.get("asset", "")
    mfe_r = float(trade.get("mfe_r", 0.0))
    mae_r = float(trade.get("mae_r", 0.0))
    mode = str(trade.get("entry_mode", "INSTANTE")).upper()

    # Clasificación causal de Claude Trading Skills
    if pnl_neto_usd > 0 and mfe_r >= 2.0:
        diag = "CLEAN_TREND_WIN"
        lesson = (
            f"Captura tendencial limpia en {sym}: MFE de +{mfe_r:.1f}R con baja excursión "
            f"adversa ({mae_r:.1f}R). Respeto ejemplar de estructura."
        )
    elif pnl_neto_usd <= 0 and abs(mae_r) >= 0.85 and mfe_r < 1.0:
        diag = "CHOP_STOP_OUT"
        lesson = (
            f"Stop alcanzado en {sym} sin expansión (+{mfe_r:.1f}R MFE). Evitar aperturas "
            f"cuando el ADX sea inferior a 22 o el régimen sea lateral sucio."
        )
    elif mode == "INSTANTE" and pnl_neto_usd < 0:
        diag = "LATE_CHASE_REVERSAL"
        lesson = (
            f"Giro adverso tras entrada a mercado en {sym}. Priorizar órdenes límite Maker "
            f"en retrocesos a la EMA21 para evitar comprar sobre-extendido."
        )
    elif pnl_neto_usd > 0 and mfe_r >= 3.5:
        diag = "PREMATURE_EXIT"
        lesson = (
            f"Salida temprana en {sym}: El impulso alcanzó +{mfe_r:.1f}R MFE. Permitir que "
            f"el trailing stop Anti-Mecha deje correr la posición en tendencias fuertes."
        )
    else:
        diag = "STANDARD_EXECUTION"
        lesson = f"Operación concluida en {sym} con PnL neto de ${pnl_neto_usd:+.2f} USD."

    rec = {
        "ts_utc": datetime.now(UTC).isoformat(timespec="seconds"),
        "trade_id": trade.get("id"),
        "asset": sym,
        "kind": trade.get("kind"),
        "timeframe": trade.get("timeframe", "4h"),
        "entry_price": float(trade.get("entry_price", 0.0)),
        "exit_price": float(exit_price),
        "pnl_neto_usd": round(float(pnl_neto_usd), 2),
        "mfe_r": mfe_r,
        "mae_r": mae_r,
        "diagnostic": diag,
        "lesson": lesson,
    }

    path = _memory_log_path(root)
    path.parent.mkdir(parents=True, exist_ok=True)
    with contextlib.suppress(Exception), open(path, "a", encoding="utf-8") as f:
        f.write(json.dumps(rec, ensure_ascii=False) + "\n")

    return rec


def load_trader_memory(root: Path | None = None, limit: int = 20) -> list[dict[str, Any]]:
    """Carga los registros post-mortem de trader_memory.jsonl."""
    path = _memory_log_path(root)
    if not path.exists():
        return []
    records: list[dict[str, Any]] = []
    with contextlib.suppress(Exception):
        for line in path.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if line:
                records.append(json.loads(line))
    return records[-limit:]


def load_recent_lessons(root: Path | None = None, limit: int = 5) -> list[str]:
    """Devuelve las últimas lecciones aprendidas para alimentar el prompt de Gemini."""
    records = load_trader_memory(root, limit=limit)
    lessons: list[str] = []
    for r in reversed(records):
        diag = r.get("diagnostic", "NOTE")
        asset = r.get("asset", "")
        les = r.get("lesson", "")
        if les:
            lessons.append(f"[{diag} en {asset}] {les}")
    return lessons
