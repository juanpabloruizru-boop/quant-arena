"""Configurador automatizado de Telegram para QUANT-ARENA v2.

Consulta getUpdates en la API de Telegram, auto-detecta el chat.id del usuario,
persiste las credenciales en el archivo .env de la raíz y envía el mensaje de
confirmación operativo.
"""

from __future__ import annotations

import argparse
import os
import sys
import time
from typing import Any

import httpx

from qa.data.paths import get_root

DEFAULT_TOKEN = os.environ.get("QA_TELEGRAM_BOT_TOKEN", "")
CONFIRMATION_MSG = (
    "🚀 <b>QUANT-ARENA v2 conectado con éxito.</b>\n\n"
    "Alertas de órdenes instantáneas en Futuros y Cartera Spot activas 24/7."
)


def get_bot_info(token: str) -> dict[str, Any] | None:
    """Verifica el token y extrae los datos del bot."""
    url = f"https://api.telegram.org/bot{token}/getMe"
    try:
        with httpx.Client(timeout=10.0) as client:
            resp = client.get(url)
            if resp.status_code == 200:
                data = resp.json()
                if data.get("ok"):
                    return data.get("result", {})
    except Exception:
        pass
    return None


def extract_chat_id(update: dict[str, Any]) -> int | None:
    """Extrae el chat_id de diversas estructuras de actualización de Telegram."""
    if "message" in update and "chat" in update["message"]:
        return update["message"]["chat"].get("id")
    if "my_chat_member" in update and "chat" in update["my_chat_member"]:
        return update["my_chat_member"]["chat"].get("id")
    if "channel_post" in update and "chat" in update["channel_post"]:
        return update["channel_post"]["chat"].get("id")
    if "callback_query" in update:
        msg = update["callback_query"].get("message", {})
        if "chat" in msg:
            return msg["chat"].get("id")
    return None


def fetch_latest_chat_id(token: str) -> int | None:
    """Consulta getUpdates de Telegram para encontrar el chat_id más reciente."""
    url = f"https://api.telegram.org/bot{token}/getUpdates"
    try:
        with httpx.Client(timeout=10.0) as client:
            resp = client.get(url)
            if resp.status_code == 200:
                data = resp.json()
                updates = data.get("result", [])
                for upd in reversed(updates):
                    cid = extract_chat_id(upd)
                    if cid is not None:
                        return cid
    except Exception:
        pass
    return None


def poll_for_chat_id(
    token: str,
    timeout_sec: int = 45,
    bot_info: dict[str, Any] | None = None,
) -> int | None:
    """Espera activamente a que el usuario interactúe con el bot."""
    cid = fetch_latest_chat_id(token)
    if cid is not None:
        return cid

    info = bot_info or get_bot_info(token) or {}
    username = info.get("username", "crypto_agent_acer_bot")
    bot_id = info.get("id") or (token.split(":")[0] if ":" in token else "N/A")
    print(f"[*] Bot: @{username} (ID: {bot_id})")
    print("[*] Esperando que el usuario presione /start o envíe un mensaje...")
    print(f"    👉 Abre Telegram y busca: https://t.me/{username}")

    start_time = time.time()
    while time.time() - start_time < timeout_sec:
        time.sleep(2.0)
        cid = fetch_latest_chat_id(token)
        if cid is not None:
            return cid
        elapsed = int(time.time() - start_time)
        print(f"[*] Escaneando getUpdates ({elapsed}s/{timeout_sec}s)...", end="\r", flush=True)

    print()
    return None


def save_env_file(token: str, chat_id: str | int) -> None:
    """Escribe o actualiza las variables de Telegram de forma persistente en .env."""
    root = get_root()
    env_path = root / ".env"

    existing_lines: list[str] = []
    if env_path.exists():
        existing_lines = env_path.read_text(encoding="utf-8").splitlines()

    updated_token = False
    updated_chat = False
    new_lines: list[str] = []

    for line in existing_lines:
        stripped = line.strip()
        if stripped.startswith("QA_TELEGRAM_BOT_TOKEN="):
            new_lines.append(f"QA_TELEGRAM_BOT_TOKEN={token}")
            updated_token = True
        elif stripped.startswith("QA_TELEGRAM_CHAT_ID="):
            new_lines.append(f"QA_TELEGRAM_CHAT_ID={chat_id}")
            updated_chat = True
        else:
            new_lines.append(line)

    if not updated_token:
        new_lines.append(f"QA_TELEGRAM_BOT_TOKEN={token}")
    if not updated_chat:
        new_lines.append(f"QA_TELEGRAM_CHAT_ID={chat_id}")

    content = "\n".join(new_lines) + "\n"
    env_path.write_text(content, encoding="utf-8")

    # Inyectar inmediatamente en os.environ del proceso actual
    import os

    os.environ["QA_TELEGRAM_BOT_TOKEN"] = str(token)
    os.environ["QA_TELEGRAM_CHAT_ID"] = str(chat_id)


def send_confirmation(token: str, chat_id: str | int) -> bool:
    """Envía el mensaje de bienvenida y confirmación al usuario."""
    url = f"https://api.telegram.org/bot{token}/sendMessage"
    payload = {
        "chat_id": str(chat_id),
        "text": CONFIRMATION_MSG,
        "parse_mode": "HTML",
    }
    try:
        with httpx.Client(timeout=10.0) as client:
            resp = client.post(url, json=payload)
            return resp.status_code == 200
    except Exception:
        return False


def setup_telegram(
    token: str = DEFAULT_TOKEN,
    chat_id: str | None = None,
    timeout_sec: int = 45,
) -> bool:
    """Flujo completo de configuración y validación de Telegram."""
    bot = get_bot_info(token)
    if not bot:
        print(f"[!] Error: No se pudo conectar a Telegram con el token: {token[:12]}...")
        return False

    resolved_chat_id = chat_id
    if not resolved_chat_id:
        detected = poll_for_chat_id(token, timeout_sec=timeout_sec, bot_info=bot)
        if detected is not None:
            resolved_chat_id = str(detected)

    if not resolved_chat_id:
        print("[!] No se detectó interacción del usuario en el tiempo límite.")
        print("[*] Puedes configurar el Chat ID manualmente ejecutando:")
        print("    python -m qa.agent.setup_telegram --chat-id <TU_CHAT_ID>")
        return False

    print(f"[OK] Chat ID detectado: {resolved_chat_id}")
    save_env_file(token, resolved_chat_id)
    print(f"[OK] Archivo .env guardado en {get_root() / '.env'}")

    # Enviar mensaje de prueba
    sent = send_confirmation(token, resolved_chat_id)
    if sent:
        print("[OK] Mensaje de confirmación enviado exitosamente a Telegram.")
        print(f"     \"{CONFIRMATION_MSG}\"")
        return True
    else:
        print("[!] Advertencia: No se pudo entregar el mensaje de confirmación.")
        return False


def main() -> None:
    parser = argparse.ArgumentParser(description="Configuración automática de Telegram QUANT-ARENA")
    parser.add_argument(
        "--token",
        default=DEFAULT_TOKEN or None,
        help="Token del Bot de Telegram (lee QA_TELEGRAM_BOT_TOKEN por defecto)",
    )
    parser.add_argument("--chat-id", default=None, help="Chat ID específico (opcional)")
    parser.add_argument("--timeout", type=int, default=30, help="Segundos máximos de espera")
    args = parser.parse_args()

    if not args.token:
        print("[!] Error: No se indicó --token y falta QA_TELEGRAM_BOT_TOKEN en .env.")
        sys.exit(1)

    success = setup_telegram(token=args.token, chat_id=args.chat_id, timeout_sec=args.timeout)
    sys.exit(0 if success else 1)


if __name__ == "__main__":
    main()
