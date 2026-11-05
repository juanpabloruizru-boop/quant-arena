"""Tests unitarios para el failover anti-bloqueo geográfico en cloud (HTTP 451)."""

from __future__ import annotations

from typing import Any
from unittest.mock import MagicMock

import httpx

import qa._pandas_compat  # noqa: F401
from qa.agent.live import fetch_live, fetch_prices
from qa.data.client import FAPI_BASE, SPOT_BASE, BinancePublicClient


def test_client_spot_failover_on_451() -> None:
    """Verifica que el cliente conmuta de api a data-api.binance.vision ante HTTP 451."""
    client = BinancePublicClient(max_retries=2, min_interval_s=0.0)

    def mock_get(url: str, params: dict[str, Any] | None = None) -> httpx.Response:
        request = httpx.Request("GET", url, params=params)
        if "api.binance.com" in url:
            return httpx.Response(
                status_code=451, text="Unavailable For Legal Reasons", request=request
            )
        if "data-api.binance.vision" in url:
            data = {"symbol": "BTCUSDT", "price": "76000.0"}
            return httpx.Response(status_code=200, json=data, request=request)
        return httpx.Response(status_code=500, request=request)

    client._client.get = MagicMock(side_effect=mock_get)  # type: ignore[method-assign]

    res = client.get_json(SPOT_BASE, "/api/v3/ticker/price", {"symbol": "BTCUSDT"})
    assert res == {"symbol": "BTCUSDT", "price": "76000.0"}
    # Verifica que el cliente memorizó el host funcional
    assert client._active_spot_base == "https://data-api.binance.vision"

    # Segunda llamada: va directamente a data-api.binance.vision
    res2 = client.get_json(SPOT_BASE, "/api/v3/ticker/price", {"symbol": "ETHUSDT"})
    assert res2 == {"symbol": "BTCUSDT", "price": "76000.0"}


def test_live_funding_neutral_fallback_on_451() -> None:
    """Verifica que si FAPI devuelve HTTP 451, live.py adopta la tasa neutral 0.01%."""
    dummy_klines = [
        [
            1700000000000 + i * 3600000,
            "100.0",
            "105.0",
            "99.0",
            "102.0",
            "1000",
            1700000000000 + (i + 1) * 3600000 - 1,
            "102000",
            100,
            "500",
            "51000",
            "0",
        ]
        for i in range(10)
    ]

    original_get_json = BinancePublicClient.get_json

    def mock_get_json(
        self: BinancePublicClient,
        base_url: str,
        path: str,
        params: dict[str, Any] | None = None,
    ) -> Any:
        if base_url == FAPI_BASE:
            raise RuntimeError("HTTP 451 (bloqueo geográfico US) en fapi.binance.com")
        if path == "/api/v3/klines":
            return dummy_klines
        if path == "/api/v3/ticker/price":
            sym = params.get("symbol", "BTCUSDT") if params else "BTCUSDT"
            return {"symbol": sym, "price": "102.0"}
        return original_get_json(self, base_url, path, params)

    BinancePublicClient.get_json = mock_get_json  # type: ignore[assignment]
    try:
        live = fetch_live(["BTCUSDT"])
        assert "BTCUSDT" in live["klines"]
        assert "BTCUSDT" in live["funding"]
        assert "BTCUSDT" in live["premium"]

        # Comprobar que la serie de funding neutral tiene 35 días (105 eventos de 8h)
        fund_df = live["funding"]["BTCUSDT"]
        assert len(fund_df) == 105
        # Comprobar tasa neutral estricta: 0.0001 (0.01% por ciclo)
        rates = fund_df["funding_rate"].to_list()
        assert all(r == 0.0001 for r in rates)

        # Comprobar premiumIndex neutral
        prem = live["premium"]["BTCUSDT"]
        assert prem["last_funding_rate"] == 0.0001
        assert prem["mark_price"] == 102.0
    finally:
        BinancePublicClient.get_json = original_get_json  # type: ignore[assignment]


def test_fetch_prices_failover() -> None:
    """Verifica que fetch_prices funciona con failover a data-api.binance.vision."""
    def mock_get(url: str, params: dict[str, Any] | None = None) -> httpx.Response:
        request = httpx.Request("GET", url, params=params)
        if "api.binance.com" in url:
            return httpx.Response(status_code=451, text="Unavailable", request=request)
        if "data-api.binance.vision" in url:
            sym = (params or {}).get("symbol", "BTCUSDT")
            price = "75000.0" if sym == "BTCUSDT" else "2500.0"
            res_data = {"symbol": sym, "price": price}
            return httpx.Response(status_code=200, json=res_data, request=request)
        return httpx.Response(status_code=500, request=request)

    original_init = BinancePublicClient.__init__

    def mock_init(self: BinancePublicClient, *args: Any, **kwargs: Any) -> None:
        original_init(self, *args, **kwargs)
        self._min_interval = 0.0
        self._client.get = MagicMock(side_effect=mock_get)  # type: ignore[method-assign]

    BinancePublicClient.__init__ = mock_init  # type: ignore[assignment]
    try:
        prices = fetch_prices(["BTCUSDT", "ETHUSDT"])
        assert prices["BTCUSDT"] == 75000.0
        assert prices["ETHUSDT"] == 2500.0
    finally:
        BinancePublicClient.__init__ = original_init  # type: ignore[assignment]
