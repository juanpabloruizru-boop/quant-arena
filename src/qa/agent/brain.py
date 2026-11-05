# Cerebro Cognitivo ("Jefe de Mesa IA") — QUANT-ARENA v2
"""Módulo de Inteligencia Artificial Analítica para validación cognitiva de setups.

Utiliza el modelo Google Gemini a través de la API REST nativa de Google AI Studio
usando httpx síncrono con timeout de 15 segundos y formato JSON estructurado.
Implementa fallback automático ante errores 429/404/503 y un sistema de caché de
15 minutos por activo en ledger/ai_brain_state.json para preservar cuotas y agilizar
el bucle operativo de 30 segundos.
"""

from __future__ import annotations

import contextlib
import json
import os
import re
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import httpx

from qa.data.paths import get_root

DEFAULT_MODEL = "gemini-2.5-flash"
FALLBACK_MODELS = [
    "gemini-2.5-flash",
    "gemini-2.5-flash-lite",
    "gemini-3-flash-preview",
    "gemini-3.5-flash-lite",
    "gemini-3.8-flash",
    "gemini-flash-latest",
]
CACHE_TTL_SECONDS = 900  # 15 minutos de validez por activo


def _load_env_if_needed() -> None:
    """Carga variables desde el archivo .env en la raíz del proyecto si existe."""
    if "PYTEST_CURRENT_TEST" in os.environ:
        return
    with contextlib.suppress(Exception):
        env_file = get_root() / ".env"
        if env_file.exists():
            for line in env_file.read_text(encoding="utf-8").splitlines():
                line = line.strip()
                if not line or line.startswith("#") or "=" not in line:
                    continue
                k, v = line.split("=", 1)
                k = k.strip()
                v = v.strip().strip("'\"")
                if k and k not in os.environ:
                    os.environ[k] = v


def get_gemini_config() -> tuple[str | None, str]:
    """Obtiene la API key y el modelo configurado de Gemini."""
    _load_env_if_needed()
    api_key = os.environ.get("QA_GEMINI_API_KEY") or None
    model = os.environ.get("QA_GEMINI_MODEL") or DEFAULT_MODEL
    return api_key, model


def _brain_state_path(root: Path | None = None) -> Path:
    r = root or get_root()
    return r / "ledger" / "ai_brain_state.json"


def load_brain_state(root: Path | None = None) -> dict[str, Any]:
    """Carga el estado persistente del Cerebro Cognitivo desde ledger/ai_brain_state.json."""
    p = _brain_state_path(root)
    if not p.exists():
        return {}
    try:
        data = json.loads(p.read_text(encoding="utf-8"))
        return data if isinstance(data, dict) else {}
    except Exception:
        return {}


def save_brain_state(state: dict[str, Any], root: Path | None = None) -> None:
    """Guarda el estado del Cerebro Cognitivo de forma atómica en ledger/ai_brain_state.json."""
    p = _brain_state_path(root)
    p.parent.mkdir(parents=True, exist_ok=True)
    with contextlib.suppress(Exception):
        p.write_text(json.dumps(state, indent=2, ensure_ascii=False), encoding="utf-8")


def _is_cache_fresh(entry: dict[str, Any], max_age_seconds: int = CACHE_TTL_SECONDS) -> bool:
    ts_str = entry.get("timestamp_utc")
    if not ts_str:
        return False
    try:
        ts = datetime.fromisoformat(ts_str)
        if ts.tzinfo is None:
            ts = ts.replace(tzinfo=UTC)
        age = (datetime.now(UTC) - ts).total_seconds()
        return 0 <= age <= max_age_seconds
    except Exception:
        return False


def format_recent_candles(klines_4h: Any = None, max_candles: int = 15) -> str:
    """Formatea las últimas velas de 4H con Open, High, Low, Close, % cuerpo y mechas."""
    if klines_4h is None or klines_4h.empty:
        return "Sin datos recientes de velas 4H."
    tail = klines_4h.tail(max_candles)
    lines: list[str] = []
    for i, (_, row) in enumerate(tail.iterrows()):
        o = float(row.get("open", 0.0))
        h = float(row.get("high", 0.0))
        low_px = float(row.get("low", 0.0))
        c = float(row.get("close", 0.0))
        body_pct = abs(c - o) / (o + 1e-9) * 100.0
        upper_wick = h - max(o, c)
        lower_wick = min(o, c) - low_px
        color = "🟢 ALCISTA" if c >= o else "🔴 BAJISTA"
        nd = 4 if c < 10 else 2
        line = (
            f"Vela {i+1}: {color} | O:{o:.{nd}f} H:{h:.{nd}f} L:{low_px:.{nd}f} C:{c:.{nd}f} | "
            f"Cuerpo:{body_pct:.1f}% | MSup:{upper_wick:.{nd}f} | MInf:{lower_wick:.{nd}f}"
        )
        lines.append(line)
    return "\n".join(lines)


def _local_heuristics_verdict(
    symbol: str,
    direction: str,
    current_price: float,
    indicators: dict[str, Any],
    swing_high: float,
    swing_low: float,
    btc_macro_bullish: bool,
) -> dict[str, Any]:
    """Heurística cuantitativa causal de respaldo si la API externa no está disponible."""
    ema21 = float(indicators.get("ema21") or current_price)
    rsi = float(indicators.get("rsi") or indicators.get("rsi14") or 50.0)
    adx_val = float(indicators.get("adx14") or 25.0)
    nd = 2 if current_price > 10 else 4

    if symbol != "BTCUSDT" and not btc_macro_bullish and direction == "LONG":
        return {
            "veredicto": "VETAR_TRAMPA",
            "confianza": 85,
            "precio_entrada_sugerido": round(ema21 * 0.95, nd),
            "razonamiento": "Macro bajista en BTC (<SMA200). Prohibido comprar en altcoins.",
            "timestamp_utc": datetime.now(UTC).isoformat(timespec="seconds"),
            "symbol": symbol,
            "direction": direction,
            "model_used": "local_heuristics",
        }

    if direction == "LONG":
        dist_ema21_pct = (current_price - ema21) / (ema21 + 1e-9) * 100.0
        if dist_ema21_pct > 2.2 or rsi > 70:
            suggested = round(ema21 * 1.002, nd)
            return {
                "veredicto": "ORDEN_LIMITE_PULLBACK",
                "confianza": 78,
                "precio_entrada_sugerido": suggested,
                "razonamiento": (
                    f"Precio extendido +{dist_ema21_pct:.1f}% sobre EMA21. "
                    f"Esperar pullback hacia {suggested} para no perseguir el precio."
                )[:240],
                "timestamp_utc": datetime.now(UTC).isoformat(timespec="seconds"),
                "symbol": symbol,
                "direction": direction,
                "model_used": "local_heuristics",
            }
        elif dist_ema21_pct < -3.0 and adx_val < 22:
            return {
                "veredicto": "VETAR_TRAMPA",
                "confianza": 75,
                "precio_entrada_sugerido": round(ema21, nd),
                "razonamiento": "Pérdida de EMA21 con bajo momentum. Riesgo de trampa.",
                "timestamp_utc": datetime.now(UTC).isoformat(timespec="seconds"),
                "symbol": symbol,
                "direction": direction,
                "model_used": "local_heuristics",
            }
        else:
            return {
                "veredicto": "EJECUTAR_AHORA",
                "confianza": 82,
                "precio_entrada_sugerido": current_price,
                "razonamiento": "Estructura alcista sana apoyada sobre EMA21 sin sobrecompra.",
                "timestamp_utc": datetime.now(UTC).isoformat(timespec="seconds"),
                "symbol": symbol,
                "direction": direction,
                "model_used": "local_heuristics",
            }
    else:
        dist_ema21_pct = (ema21 - current_price) / (ema21 + 1e-9) * 100.0
        if dist_ema21_pct > 2.2 or rsi < 30:
            suggested = round(ema21 * 0.998, nd)
            return {
                "veredicto": "ORDEN_LIMITE_PULLBACK",
                "confianza": 78,
                "precio_entrada_sugerido": suggested,
                "razonamiento": (
                    f"Short extendido -{dist_ema21_pct:.1f}% bajo EMA21. "
                    f"Esperar rebote correctivo a {suggested} para entrar con mejor R:R."
                )[:240],
                "timestamp_utc": datetime.now(UTC).isoformat(timespec="seconds"),
                "symbol": symbol,
                "direction": direction,
                "model_used": "local_heuristics",
            }
        else:
            return {
                "veredicto": "EJECUTAR_AHORA",
                "confianza": 80,
                "precio_entrada_sugerido": current_price,
                "razonamiento": "Presión bajista regular bajo EMA21 con espacio a soporte.",
                "timestamp_utc": datetime.now(UTC).isoformat(timespec="seconds"),
                "symbol": symbol,
                "direction": direction,
                "model_used": "local_heuristics",
            }


def evaluar_setup_con_ia(
    symbol: str,
    direction: str,
    current_price: float,
    indicators: dict[str, Any],
    swing_high: float,
    swing_low: float,
    btc_macro_bullish: bool,
    news_headlines: list[str] | None = None,
    klines_4h: Any | None = None,
    root: Path | None = None,
    force_refresh: bool = False,
    kronos_forecast: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Evalúa un setup cuantitativo con el Jefe de Mesa IA (Google Gemini REST nativo).

    Utiliza caché inteligente de 15 minutos en ledger/ai_brain_state.json.
    Retorna un diccionario estructurado con:
    - veredicto: 'EJECUTAR_AHORA' | 'ORDEN_LIMITE_PULLBACK' | 'VETAR_TRAMPA'
    - confianza: int (0-100)
    - precio_entrada_sugerido: float
    - razonamiento: str (máx 240 caracteres)
    - timestamp_utc: str
    - symbol: str
    - direction: str
    - model_used: str
    """
    root_path = root or get_root()
    cache = load_brain_state(root_path)

    # 1. Verificar si hay un veredicto fresco en caché
    cached = cache.get(symbol)
    if not force_refresh and cached and _is_cache_fresh(cached):
        return cached

    api_key, configured_model = get_gemini_config()
    if not api_key:
        verdict = _local_heuristics_verdict(
            symbol, direction, current_price, indicators, swing_high, swing_low, btc_macro_bullish
        )
        cache[symbol] = verdict
        save_brain_state(cache, root_path)
        return verdict

    # 2. Construir prompt cuantitativo exhaustivo
    from qa.agent.skills_engine import load_recent_lessons

    candles_summary = format_recent_candles(klines_4h, max_candles=15)
    news_text = (
        "\n".join(f"- {h}" for h in (news_headlines or [])[:5])
        if news_headlines
        else "Sin noticias de impacto reciente."
    )
    past_lessons = load_recent_lessons(root_path, limit=5)
    lessons_txt = (
        "\n".join(f"- {les}" for les in past_lessons)
        if past_lessons
        else "Sin lecciones registradas aún."
    )

    if kronos_forecast is None and klines_4h is not None and not klines_4h.empty:
        from qa.agent.kronos_oracle import predict_kline_horizon

        kronos_forecast = predict_kline_horizon(klines_4h, symbol=symbol, timeframe="4h", horizon=6)

    if kronos_forecast:
        k_verd = kronos_forecast.get("kronos_verdict", "KRONOS_NEUTRAL")
        k_prob = float(kronos_forecast.get("bullish_prob", 50.0))
        k_ret = float(kronos_forecast.get("expected_return_pct", 0.0))
        k_high = kronos_forecast.get("forecast_high", current_price)
        k_low = kronos_forecast.get("forecast_low", current_price)
        k_conf = kronos_forecast.get("confidence_score", 50)
        kronos_txt = (
            f"Veredicto Kronos (6 velas): {k_verd} | Prob. Alcista: {k_prob:.1f}% | "
            f"Retorno Esperado: {k_ret:+.2f}% | Banda [P20..P80]: [{k_low}, {k_high}] | "
            f"Convergencia: {k_conf}/100"
        )
    else:
        kronos_txt = "Sin proyección disponible del Oráculo Kronos."

    ema9 = float(indicators.get("ema9") or current_price)
    ema21 = float(indicators.get("ema21") or current_price)
    sma50 = float(indicators.get("sma50") or current_price)
    rsi14 = float(indicators.get("rsi") or indicators.get("rsi14") or 50.0)
    atr14 = float(indicators.get("atr14") or current_price * 0.02)
    atr_pctl = float(indicators.get("atr_pctl") or 0.5)
    adx14 = float(indicators.get("adx14") or 25.0)
    adx_slope = float(indicators.get("adx_slope") or 0.0)

    schema_json = (
        '{\n'
        '  "veredicto": "EJECUTAR_AHORA" | "ORDEN_LIMITE_PULLBACK" | "VETAR_TRAMPA",\n'
        '  "confianza": 0-100,\n'
        '  "precio_entrada_sugerido": 0.0,\n'
        '  "razonamiento": "Explicación directa en español (máx 240 caracteres)."\n'
        '}'
    )

    system_instruction = (
        "Eres el Director de Riesgo y Jefe de Mesa de un fondo cuantitativo de criptoactivos. "
        "Tu trabajo es evitar que el bot entre tarde ('chasing' tras varias velas verdes), "
        "evitar compras pegadas a resistencias o con mechas de rechazo (bull traps), "
        "y priorizar entradas limpias. Analiza las últimas 15 velas y el macro, "
        f"y responde en JSON:\n{schema_json}"
    )

    macro_txt = (
        "ALCISTA (BTC >= SMA200 1D)"
        if btc_macro_bullish
        else "BAJISTA / INVIERNO CRIPTO (BTC < SMA200 1D)"
    )

    user_prompt = (
        f"{system_instruction}\n\n"
        f"--- CONTEXTO TÉCNICO Y MACRO ---\n"
        f"Activo: {symbol}\n"
        f"Dirección Candidata: {direction}\n"
        f"Precio Actual de Mercado: {current_price}\n"
        f"EMA9(4H): {ema9:.2f} | EMA21(4H): {ema21:.2f} | SMA50(4H): {sma50:.2f}\n"
        f"RSI(14): {rsi14:.1f} | ADX(14): {adx14:.1f} (pendiente: {adx_slope:+.2f})\n"
        f"ATR(14): {atr14:.2f} (percentil: {atr_pctl*100:.0f}%)\n"
        f"Swing High 4H: {swing_high:.2f} | Swing Low 4H: {swing_low:.2f}\n"
        f"Régimen Macro Bitcoin: {macro_txt}\n\n"
        f"--- TITULARES RECIENTES DE MERCADO ---\n"
        f"{news_text}\n\n"
        f"--- ACCIÓN DEL PRECIO: ÚLTIMAS 15 VELAS DE 4 HORAS ---\n"
        f"{candles_summary}\n\n"
        f"--- MEMORIA DEL OPERADOR: LECCIONES APRENDIDAS (POST-MORTEM) ---\n"
        f"{lessons_txt}\n\n"
        f"--- PROYECCIÓN ORÁCULO K-LINE KRONOS (PRÓXIMAS 6 VELAS) ---\n"
        f"{kronos_txt}\n\n"
        f"Criterios cuantitativos obligatorios:\n"
        f"1. Si el precio está extendido sobre EMA21, dictamina 'ORDEN_LIMITE_PULLBACK' "
        f"sugiriendo entrada cerca de EMA21 ({ema21:.2f}).\n"
        f"2. Si la vela presenta mecha superior larga en resistencia, dictamina 'VETAR_TRAMPA'.\n"
        f"3. Si la estructura apoya sobre EMA21 con absorción, dictamina 'EJECUTAR_AHORA' (>=75)."
    )

    # 3. Lista de modelos con fallback en cascada
    model_chain: list[str] = []
    if configured_model not in model_chain:
        model_chain.append(configured_model)
    for fm in FALLBACK_MODELS:
        if fm not in model_chain:
            model_chain.append(fm)

    last_error: str | None = None
    chosen_result: dict[str, Any] | None = None

    for model in model_chain:
        endpoint_url = (
            f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent"
            f"?key={api_key}"
        )
        payload = {
            "contents": [{"parts": [{"text": user_prompt}]}],
            "generationConfig": {"responseMimeType": "application/json"},
        }
        try:
            with httpx.Client(timeout=15.0) as client:
                resp = client.post(endpoint_url, json=payload)
                if resp.status_code == 200:
                    data = resp.json()
                    candidates = data.get("candidates") or []
                    if candidates:
                        parts = candidates[0].get("content", {}).get("parts", [])
                        if parts:
                            raw_text = parts[0].get("text", "")
                            clean_json = re.sub(
                                r"^```(?:json)?\s*|\s*```$",
                                "",
                                raw_text.strip(),
                                flags=re.MULTILINE,
                            )
                            parsed = json.loads(clean_json)

                            verd = str(
                                parsed.get("veredicto", "ORDEN_LIMITE_PULLBACK")
                            ).upper().strip()
                            if verd not in (
                                "EJECUTAR_AHORA",
                                "ORDEN_LIMITE_PULLBACK",
                                "VETAR_TRAMPA",
                            ):
                                verd = "ORDEN_LIMITE_PULLBACK"

                            conf = int(parsed.get("confianza", 75))
                            conf = max(0, min(100, conf))

                            sugg_px = float(parsed.get("precio_entrada_sugerido") or current_price)
                            if sugg_px <= 0:
                                sugg_px = current_price

                            razon = str(parsed.get("razonamiento", "")).strip()[:240]
                            if not razon:
                                razon = f"Estructura técnica validada por {model}."

                            chosen_result = {
                                "veredicto": verd,
                                "confianza": conf,
                                "precio_entrada_sugerido": round(
                                    sugg_px, 2 if current_price > 10 else 4
                                ),
                                "razonamiento": razon,
                                "timestamp_utc": datetime.now(UTC).isoformat(timespec="seconds"),
                                "symbol": symbol,
                                "direction": direction,
                                "model_used": model,
                            }
                            break
                elif resp.status_code in (404, 429, 503):
                    last_error = f"HTTP {resp.status_code} ({model})"
                    if resp.status_code in (429, 503):
                        import time
                        time.sleep(1.0)
                    continue
                else:
                    last_error = f"HTTP {resp.status_code}: {resp.text[:120]}"
        except Exception as e:
            last_error = f"Excepción ({model}): {e}"
            continue

    if not chosen_result:
        # Fallback a heurística cuantitativa local
        chosen_result = _local_heuristics_verdict(
            symbol, direction, current_price, indicators, swing_high, swing_low, btc_macro_bullish
        )
        chosen_result["fallback_note"] = f"Fallback activo tras: {last_error}"

    # 4. Guardar en caché y retornar
    cache[symbol] = chosen_result
    save_brain_state(cache, root_path)
    return chosen_result
