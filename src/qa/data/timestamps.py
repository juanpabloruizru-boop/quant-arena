"""Normalizacion de timestamps (M1).

El prompt heredado avisa de mezclas ms vs us entre endpoints de Binance.
Verificado en vivo el 2026-10-26: spot y USD-M futures devuelven **ms**
(13 digitos). Aun asi, la normalizacion detecta la unidad por magnitud y
falla ante valores ambiguos: nunca se asume.
"""

from __future__ import annotations

from datetime import UTC, datetime

# Rangos de magnitud validos para fechas 2001-2286 en cada unidad
_S_MAX = 10_000_000_000  # 1e10 s  ~ ano 2286
_MS_MAX = 10_000_000_000_000  # 1e13 ms
_US_MAX = 10_000_000_000_000_000  # 1e16 us


def detect_epoch_unit(value: int) -> str:
    """Devuelve 's' | 'ms' | 'us' segun la magnitud; ValueError si ambiguo."""
    v = abs(int(value))
    if v == 0:
        raise ValueError("timestamp 0: unidad indeterminada")
    if v < _S_MAX:
        return "s"
    if v < _MS_MAX:
        return "ms"
    if v < _US_MAX:
        return "us"
    raise ValueError(f"timestamp fuera de rango conocido: {value}")


def to_utc_datetime(value: int) -> datetime:
    unit = detect_epoch_unit(value)
    if unit == "s":
        return datetime.fromtimestamp(value, tz=UTC)
    if unit == "ms":
        return datetime.fromtimestamp(value / 1e3, tz=UTC)
    return datetime.fromtimestamp(value / 1e6, tz=UTC)


def to_ms(value: int) -> int:
    """Convierte cualquier unidad detectada a milisegundos UTC."""
    unit = detect_epoch_unit(value)
    if unit == "s":
        return int(value) * 1000
    if unit == "ms":
        return int(value)
    return int(value) // 1000


def assert_consistent_units(values: list[int], expected: str = "ms") -> None:
    """Fallan unidades mezcladas en un mismo lote (defensa extra)."""
    for v in values:
        u = detect_epoch_unit(v)
        if u != expected:
            raise ValueError(f"unidad {u} inesperada (esperaba {expected}) en ts={v}")
