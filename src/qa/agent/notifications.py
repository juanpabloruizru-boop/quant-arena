"""Gestor de telemetría y notificaciones unidireccionales (Telegram / Discord).

Módulo desacoplado y seguro:
- Lee URLs de webhook o tokens opcionales desde variables de entorno y archivo .env.
- Si las variables no están configuradas, opera en silencio sin arrojar excepciones.
- Solo emite peticiones POST de salida (unidireccional); sin servidores ni listeners.
"""

from __future__ import annotations

import os
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
    chat_id = os.environ.get("QA_TELEGRAM_CHAT_ID")
    if token and chat_id:
        return token.strip(), chat_id.strip()
    return None


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
        title = "🏁 Operación Cerrada"
        asset = data.get("asset", "")
        tag = data.get("tag", "CIERRE")
        exit_px = float(data.get("exit_price", 0.0))
        pnl_net = float(data.get("pnl_neto_usd", 0.0))
        pnl_pct = float(data.get("pnl_pct", 0.0))
        r_mult = data.get("r_multiplo")
        r_str = f"{float(r_mult):+.2f}R" if r_mult is not None else "N/A"
        icon = "🎉" if pnl_net > 0 else "🛑"
        msg = (
            f"<b>{icon} POSICIÓN CERRADA: {asset} ({tag})</b>\n\n"
            f"• <b>Precio de Salida:</b> ${exit_px:,.4f}\n"
            f"• <b>PnL Neto Total:</b> ${pnl_net:+.2f} USD ({pnl_pct:+.2f}%)\n"
            f"• <b>Múltiplo R:</b> {r_str}\n"
            f"• <b>Detalle:</b> {data.get('note', '')}"
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
