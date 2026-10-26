"""Normalizacion de timestamps ms/us/s (defensa contra unidades mezcladas)."""

from __future__ import annotations

from datetime import UTC, datetime

import pytest

from qa.data.timestamps import (
    assert_consistent_units,
    detect_epoch_unit,
    to_ms,
    to_utc_datetime,
)


def test_detect_units() -> None:
    assert detect_epoch_unit(1_793_022_107) == "s"  # 2026 en segundos
    assert detect_epoch_unit(1_793_022_107_550) == "ms"  # 2026 en ms (13 digitos)
    assert detect_epoch_unit(1_793_022_107_550_000) == "us"  # 2026 en us (16 digitos)


def test_detect_units_rejects_ambiguous() -> None:
    with pytest.raises(ValueError):
        detect_epoch_unit(0)
    with pytest.raises(ValueError):
        detect_epoch_unit(10**17)


def test_to_utc_datetime_consistent_across_units() -> None:
    expected = datetime(2026, 10, 27, 13, 20, 0, tzinfo=UTC)
    assert to_utc_datetime(1_793_107_200) == expected
    assert to_utc_datetime(1_793_107_200_000) == expected
    assert to_utc_datetime(1_793_107_200_000_000) == expected


def test_to_ms_normalizes() -> None:
    assert to_ms(1_793_107_200) == 1_793_107_200_000
    assert to_ms(1_793_107_200_000) == 1_793_107_200_000
    assert to_ms(1_793_107_200_000_123) == 1_793_107_200_000


def test_assert_consistent_units_fails_on_mix() -> None:
    assert_consistent_units([1_793_022_107_550, 1_793_022_108_000], "ms")
    with pytest.raises(ValueError):
        assert_consistent_units([1_793_022_107_550, 1_793_022_107_550_000], "ms")
