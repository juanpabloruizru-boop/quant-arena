"""Paginacion de klines con cliente falso (sin red): cobertura, orden, dedupe."""

from __future__ import annotations

from typing import Any

from qa.data.client import SPOT_BASE
from qa.data.klines import INTERVAL_MS, fetch_klines_paged, klines_frame


class FakeClient:
    """Emula /api/v3/klines: paginas de tamanno 3, con solape duplicado."""

    def __init__(self, n_rows: int, start_ms: int = 1_500_000_000_000) -> None:
        self.n_rows = n_rows
        self.start_ms = start_ms
        self.calls: list[dict[str, Any]] = []
        self.used_weight_1m = 0
        self.n_requests = 0

    def get_json(self, base_url: str, path: str, params: dict[str, Any] | None = None) -> Any:
        assert base_url == SPOT_BASE and path == "/api/v3/klines"
        assert params is not None
        self.calls.append(dict(params))
        self.n_requests += 1
        start = int(params["startTime"])
        end = int(params["endTime"])
        limit = int(params["limit"])
        step = INTERVAL_MS[params["interval"]]
        last_valid = self.start_ms + (self.n_rows - 1) * step
        rows: list[list[Any]] = []
        t = max(start, self.start_ms)
        while t <= min(end, last_valid) and len(rows) < limit:
            rows.append([t, "1", "2", "0.5", "1.5", "10", t + step - 1, "15", 7, "5", "7.5", "0"])
            t += step
        return rows


def test_pagination_full_coverage_no_dups() -> None:
    client = FakeClient(n_rows=8)
    end_ms = client.start_ms + 20 * INTERVAL_MS["1d"]
    rows = fetch_klines_paged(
        client, SPOT_BASE, "/api/v3/klines", "TESTUSDT", "1d", client.start_ms, end_ms
    )
    assert len(rows) == 8
    opens = [r[0] for r in rows]
    assert opens == sorted(set(opens))  # ordenadas y sin duplicados
    assert client.calls[0]["startTime"] == client.start_ms
    # cada pagina siguiente arranca en ultimo_open + 1 dia
    step = INTERVAL_MS["1d"]
    for prev, cur in zip(client.calls, client.calls[1:], strict=False):
        assert cur["startTime"] >= prev["startTime"] + step


def test_pagination_stops_on_short_page() -> None:
    client = FakeClient(n_rows=2)  # menos que limit -> fin
    end_ms = client.start_ms + 50 * INTERVAL_MS["1d"]
    rows = fetch_klines_paged(
        client, SPOT_BASE, "/api/v3/klines", "TESTUSDT", "1d", client.start_ms, end_ms
    )
    assert len(rows) == 2
    assert len(client.calls) == 1


def test_klines_frame_typing() -> None:
    client = FakeClient(n_rows=3)
    end_ms = client.start_ms + 10 * INTERVAL_MS["1d"]
    rows = fetch_klines_paged(
        client, SPOT_BASE, "/api/v3/klines", "TESTUSDT", "1d", client.start_ms, end_ms
    )
    df = klines_frame(rows, "TESTUSDT", "1d")
    assert list(df.columns)[:4] == ["symbol", "interval", "open_time", "open"]
    assert str(df["open_time"].dt.tz) == "UTC"
    assert df["open"].dtype == float
    assert df["n_trades"].dtype == int
    assert len(df) == 3
