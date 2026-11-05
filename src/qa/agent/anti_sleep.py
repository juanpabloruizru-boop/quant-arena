"""Módulo Anti-Sueño (Windows Sleep Prevention).

Invoca SetThreadExecutionState del Kernel de Windows para evitar que el
sistema operativo entre en suspensión o duerma la CPU durante la operativa 24/7.
La pantalla puede apagarse normalmente para ahorrar energía sin interrumpir el bot.
"""

from __future__ import annotations

import ctypes
import sys


def prevent_windows_sleep() -> bool:
    """Evita la suspensión de Windows manteniendo la CPU activa de forma continua."""
    if sys.platform == "win32":
        try:
            # ES_CONTINUOUS (0x80000000) | ES_SYSTEM_REQUIRED (0x00000001)
            ctypes.windll.kernel32.SetThreadExecutionState(0x80000001)
            return True
        except Exception:
            return False
    return False


def restore_windows_sleep() -> bool:
    """Restaura el comportamiento normal de suspensión del sistema."""
    if sys.platform == "win32":
        try:
            # ES_CONTINUOUS (0x80000000)
            ctypes.windll.kernel32.SetThreadExecutionState(0x80000000)
            return True
        except Exception:
            return False
    return False
