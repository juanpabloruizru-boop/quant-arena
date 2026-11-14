"""Gestor de telemetría y notificaciones unidireccionales (Telegram / Discord).

Módulo desacoplado y seguro:
- Lee URLs de webhook o tokens opcionales desde variables de entorno y archivo .env.
- Si las variables no están configuradas, opera en silencio sin arrojar excepciones.
- Solo emite peticiones POST de salida (unidireccional); sin servidores ni listeners.
"""

from __future__ import annotations

import contextlib
import html
import json
import os
from pathlib import Path
from typing import Any

import httpx

from qa.data.paths import get_root


def load_env_file() -> None:
    """Carga variables desde el archivo .env en la raíz del proyecto si existe."""
    if "PYTEST_CURRENT_TEST" in os.environ:
        return
    try:
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
    except Exception:
        pass


def _discord_webhook_url() -> str | None:
    load_env_file()
    return os.environ.get("QA_DISCORD_WEBHOOK_URL") or None


def _telegram_config() -> tuple[str, str] | None:
    load_env_file()
    token = os.environ.get("QA_TELEGRAM_BOT_TOKEN")
    chat_id = os.environ.get("QA_TELEGRAM_CHAT_ID") or "8552827176"
    if token and chat_id:
        return token.strip(), chat_id.strip()
    return None


def get_sent_signals(root: Path | None = None) -> set[str]:
    """Carga los trade_id de señales ya notificadas a Telegram."""
    p = (root or get_root()) / "ledger" / "telegram_sent_signals.json"
    if not p.exists():
        return set()
    try:
        data = json.loads(p.read_text(encoding="utf-8"))
        if isinstance(data, list):
            return set(data)
        if isinstance(data, dict):
            return set(data.get("sent_trade_ids", []))
    except Exception:
        pass
    return set()


def mark_signal_sent(trade_id: str, root: Path | None = None) -> None:
    """Registra un trade_id como notificado en ledger/telegram_sent_signals.json."""
    if not trade_id:
        return
    p = (root or get_root()) / "ledger" / "telegram_sent_signals.json"
    p.parent.mkdir(parents=True, exist_ok=True)
    sent = get_sent_signals(root)
    sent.add(str(trade_id))
    with contextlib.suppress(Exception):
        p.write_text(
            json.dumps({"sent_trade_ids": sorted(list(sent))}, indent=2),
            encoding="utf-8",
        )


def format_trade_signal(trade: dict[str, Any]) -> str:
    """Construye el formato estricto y obligatorio de Señal Activa para Telegram."""
    tf_raw = str(trade.get("timeframe", "")).lower()
    tag_raw = str(trade.get("tag", "")).lower()
    thesis_raw = str(trade.get("thesis", "")).lower()

    is_1h = tf_raw == "1h" or "sniper" in tag_raw or "sniper" in thesis_raw
    timeframe = "1H" if is_1h else "4H"
    motor = "1H Sniper Scalper" if is_1h else "4H Tendencia"
    timeframe_lbl = "1H Sniper Scalper" if is_1h else "4H Tendencia"

    symbol = str(trade.get("asset", "")).upper()
    kind = str(trade.get("kind", "")).lower()
    is_long = "long" in kind
    direction_txt = "LONG 📈" if is_long else "SHORT 📉"

    lev_val = str(trade.get("leverage", "5x" if is_1h else "4x")).lower().replace("x", "")
    leverage = f"{lev_val}x"

    entry = float(
        trade.get("entry_price")
        or trade.get("entry")
        or trade.get("target_entry")
        or 0.0
    )
    sl = float(trade.get("sl_price") or trade.get("sl") or trade.get("initial_sl") or 0.0)

    dist_sl = abs(entry - sl) if (entry > 0 and sl > 0) else 0.0
    sl_pct = (dist_sl / entry * 100.0) if entry > 0 else 0.0

    tp1 = float(trade.get("tp1_price") or trade.get("tp1") or 0.0)
    tp2 = float(trade.get("tp2_price") or trade.get("tp2") or trade.get("tp") or 0.0)
    tp3 = float(trade.get("tp3_price") or trade.get("tp3") or 0.0)

    if dist_sl > 0:
        nd_calc = 4 if entry < 10 else 2
        if tp1 <= 0:
            tp1 = round(entry + 1.8 * dist_sl if is_long else entry - 1.8 * dist_sl, nd_calc)
        if tp2 <= 0:
            tp2 = round(entry + 3.0 * dist_sl if is_long else entry - 3.0 * dist_sl, nd_calc)
        if tp3 <= 0:
            tp3 = round(entry + 4.5 * dist_sl if is_long else entry - 4.5 * dist_sl, nd_calc)

    rr_val = trade.get("rr_neto") or trade.get("rr_neto_inicial") or 3.0
    try:
        rr_num = float(rr_val)
    except Exception:
        rr_num = 3.0
    rr_str = f"{rr_num:.1f}"

    risk_usd = float(trade.get("risk_usd") or 20.0)

    fallback_reason = "Sinergia técnica confirmada con oráculo Kronos e IA Gemini."
    raw_reason = (
        trade.get("ai_reasoning")
        or trade.get("thesis")
        or trade.get("note")
        or fallback_reason
    )
    # Limpiar prefijos internos de tesis si están presentes
    if " · [" in raw_reason and "IA" in raw_reason:
        parts = raw_reason.split(" · [")
        raw_reason = parts[-1].rstrip("]")
        if ":" in raw_reason:
            raw_reason = raw_reason.split(":", 1)[-1].strip()

    escaped_reasoning = html.escape(str(raw_reason).strip(), quote=False)
    nd = 4 if entry < 10 else 2

    return (
        f"🚨 <b>SEÑAL ACTIVA: {motor} ({timeframe})</b>\n"
        f"━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
        f"🪙 <b>Activo:</b> {symbol}\n"
        f"📐 <b>Dirección:</b> {direction_txt} ({leverage})\n"
        f"⏱️ <b>Temporalidad:</b> {timeframe_lbl}\n\n"
        f"📍 <b>Precio de Entrada:</b> ${entry:,.{nd}f}\n"
        f"🛡️ <b>Stop Loss (Freno):</b> ${sl:,.{nd}f} ({sl_pct:.2f}%)\n\n"
        f"🎯 <b>TP1 (Parcial 30%):</b> ${tp1:,.{nd}f} (+1.8R)\n"
        f"🎯 <b>TP2 (Objetivo 40%):</b> ${tp2:,.{nd}f} (+3.0R)\n"
        f"🎯 <b>TP3 (Runner 30%):</b> ${tp3:,.{nd}f} (+4.5R)\n\n"
        f"⚖️ <b>Riesgo / Beneficio:</b> 1 : {rr_str} ({rr_str}R)\n"
        f"💵 <b>Riesgo Asignado:</b> ${risk_usd:.2f} USD\n"
        f"🧠 <b>Tesis IA + Kronos:</b> {escaped_reasoning}\n"
        f"━━━━━━━━━━━━━━━━━━━━━━━━━━"
    )


def send_trade_signal_telegram(trade: dict[str, Any], root: Path | None = None) -> bool:
    """Despacha la señal completa de una operación activa a Telegram asegurando id único."""
    tid = trade.get("id")
    if tid and str(tid) in get_sent_signals(root):
        return True

    msg = format_trade_signal(trade)
    ok = send_telegram_alert(msg)
    if ok and tid:
        mark_signal_sent(str(tid), root)
    return ok


def send_discord_alert(content: str, title: str = "QUANT-ARENA v2") -> bool:
    """Envía un mensaje formateado a un Webhook de Discord si está configurado."""
    url = _discord_webhook_url()
    if not url:
        return False
    payload = {
        "username": "QUANT-ARENA Autopilot",
        "embeds": [
            {
                "title": title,
                "description": content,
                "color": 0x00FF88 if "🟢" in content or "🎯" in content else 0x00A2FF,
            }
        ],
    }
    try:
        with httpx.Client(timeout=5.0) as client:
            resp = client.post(url, json=payload)
            return resp.status_code in (200, 204)
    except Exception:
        return False


def send_telegram_alert(message: str) -> bool:
    """Envía un mensaje a Telegram usando la Bot API estándar."""
    cfg = _telegram_config()
    if not cfg:
        return False
    token, chat_id = cfg
    url = f"https://api.telegram.org/bot{token}/sendMessage"
    payload = {
        "chat_id": chat_id,
        "text": message,
        "parse_mode": "HTML",
        "disable_web_page_preview": True,
    }
    try:
        with httpx.Client(timeout=5.0) as client:
            resp = client.post(url, json=payload)
            return resp.status_code == 200
    except Exception:
        return False


def notify_order_open(data: dict[str, Any]) -> None:
    """Dispara notificación inmediata al abrirse una orden (ej. '⚡ AL INSTANTE')."""
    notify_event("ORDER_OPEN", data)


def notify_event(event_type: str, data: dict[str, Any]) -> None:
    """Despacha un evento operativo a los canales configurados (Telegram / Discord)."""
    msg = ""
    title = "QUANT-ARENA v2 — Notificación"

    if event_type == "ORDER_OPEN":
        # Despachar formato estricto y obligatorio de Señal Activa a Telegram
        send_trade_signal_telegram(data)

        asset = data.get("asset", "")
        tf = str(data.get("timeframe", "")).upper()
        kind = str(data.get("kind", "")).upper()
        lev = data.get("leverage", "1x")
        entry = float(data.get("entry_price", 0.0))
        sl = float(data.get("sl", 0.0))
        tp1 = float(data.get("tp1", 0.0))
        tp2 = float(data.get("tp2", 0.0))
        score = data.get("score", 0)
        risk_usd = float(data.get("risk_usd", 0.0))
        risk_pct = float(data.get("risk_pct", 0.0)) * 100.0
        mode = str(data.get("entry_mode", "INSTANTE")).upper()
        thesis = data.get("thesis", "N/A")
        ai_reasoning = data.get("ai_reasoning")
        ai_verdict = data.get("ai_verdict")

        is_instant = mode == "INSTANTE" or "INSTANTE" in str(thesis) or "AL INSTANTE" in str(thesis)

        if is_instant:
            title = "⚡ ORDEN AL INSTANTE EJECUTADA"
            header = f"<b>⚡ ALERTA: ORDEN AL INSTANTE EJECUTADA: {asset} ({tf})</b>\n\n"
        else:
            title = "🎯 Nueva Orden Programada"
            header = f"<b>🎯 ORDEN PROGRAMADA (MAKER): {asset} ({tf})</b>\n\n"

        msg = (
            f"{header}"
            f"• <b>Dirección / Apalancamiento:</b> {kind} ({lev})\n"
            f"• <b>Entrada:</b> ${entry:,.4f}\n"
            f"• <b>Stop Loss:</b> ${sl:,.4f}\n"
            f"• <b>TP1 (30%/50% Parcial):</b> ${tp1:,.4f}\n"
            f"• <b>TP2 (Final de Ciclo):</b> ${tp2:,.4f}\n"
            f"• <b>Score Conquistador:</b> {score}/100\n"
            f"• <b>Riesgo Asignado:</b> ${risk_usd:.2f} USD ({risk_pct:.2f}%)\n"
            f"• <b>Tesis Técnica:</b> {thesis}"
        )
        if ai_reasoning:
            ai_lbl = ai_verdict or "Gemini"
            msg += f"\n• <b>🧠 Dictamen Jefe de Mesa IA ({ai_lbl}):</b> {ai_reasoning}"

        # Discord alert
        send_discord_alert(msg, title=title)
        return


    elif event_type == "TP1_PARTIAL":
        title = "🎯 TP1 Alcanzado — Cierre Parcial"
        asset = data.get("asset", "")
        exit_px = float(data.get("exit_price", 0.0))
        pnl = float(data.get("pnl_usd", 0.0))
        new_sl = float(data.get("new_sl", 0.0))
        rem_size = float(data.get("remaining_size_usd", 0.0))
        msg = (
            f"<b>🎯 OBJETIVO TP1 ALCANZADO: {asset}</b>\n\n"
            f"• <b>Precio Ejecución Parcial:</b> ${exit_px:,.4f}\n"
            f"• <b>PnL Realizado Parcial:</b> +${pnl:.2f} USD\n"
            f"• <b>Nocional Remanente:</b> ${rem_size:.2f} USD\n"
            f"• <b>Nuevo Stop Loss Protegido:</b> ${new_sl:,.4f} (Anti-Wick Trailing)\n"
            f"<i>La operación queda libre de riesgo y con ganancias aseguradas en caja.</i>"
        )

    elif event_type == "PYRAMID_EXECUTED":
        title = "🚀 Piramidación Protectora Ejecutada (+25%)"
        asset = data.get("asset", "")
        add_px = float(data.get("price_now", 0.0))
        new_sl = float(data.get("new_sl", 0.0))
        msg = (
            f"<b>🚀 PIRAMIDACIÓN A RIESGO CERO: {asset}</b>\n\n"
            f"• <b>Adición:</b> +25% de posición ejecutada @ ${add_px:,.4f}\n"
            f"• <b>Condición de Activación:</b> Ganancia no realizada ≥ +4.0R\n"
            f"• <b>Stop Loss Combinado Blindado:</b> ${new_sl:,.4f} (Garantiza beneficio ≥ +0.5R)\n"
            f"<i>Margen expandido con riesgo matemático cero garantizado.</i>"
        )

    elif event_type == "TRADE_CLOSED":
        asset = data.get("asset", "")
        tag = str(data.get("tag", "CIERRE")).upper()
        exit_px = float(data.get("exit_price", 0.0))
        pnl_net = float(data.get("pnl_neto_usd", 0.0))
        pnl_pct = float(data.get("pnl_pct", 0.0))
        r_mult = data.get("r_multiplo")
        r_str = f"{float(r_mult):+.2f}R" if r_mult is not None else "N/A"

        if "TP" in tag:
            title = f"🎯 TP Alcanzado: {asset}"
            header = f"<b>🎯 OBJETIVO DE GANANCIA ALCANZADO: {asset}</b>"
        elif "BE" in tag or "TRAILING" in tag or "PYRAMID" in tag:
            title = f"🔒 Trailing Profit / BE: {asset}"
            header = f"<b>🔒 SALIDA DE GANANCIA PROTEGIDA: {asset}</b>"
        elif "SL" in tag:
            title = f"🛡️ Stop Loss Ejecutado: {asset}"
            header = f"<b>🛡️ FRENO DE SEGURIDAD (STOP LOSS): {asset}</b>"
        else:
            title = f"🏁 Posición Cerrada: {asset}"
            header = f"<b>🏁 POSICIÓN CERRADA: {asset} ({tag})</b>"

        nd = 4 if exit_px < 10 else 2
        msg = (
            f"{header}\n\n"
            f"• <b>Precio de Salida:</b> ${exit_px:,.{nd}f}\n"
            f"• <b>PnL Neto Real:</b> ${pnl_net:+.2f} USD ({pnl_pct:+.2f}%)\n"
            f"• <b>Múltiplo R:</b> {r_str}\n"
            f"• <b>Motivo:</b> {html.escape(str(data.get('note', '')), quote=False)}"
        )

    elif event_type == "HEAT_WARNING":
        title = "🛡️ Alerta de Portfolio Heat"
        heat_usd = float(data.get("heat_usd", 0.0))
        heat_pct = float(data.get("heat_pct", 0.0))
        msg = (
            f"<b>🛡️ ALERTA DE RIESGO: PORTFOLIO HEAT ELEVADO</b>\n\n"
            f"• <b>Riesgo Total en Mesa:</b> ${heat_usd:.2f} USD ({heat_pct:.1f}%)\n"
            f"• <b>Umbral Preventivo:</b> 20.0% del patrimonio (Techo 25.0%)\n"
            f"• <b>Acción:</b> Nuevas aperturas restringidas hasta reducción de exposición."
        )

    if msg:
        send_discord_alert(msg, title=title)
        send_telegram_alert(msg)
