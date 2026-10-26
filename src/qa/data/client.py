"""Cliente HTTP publico (solo lectura) con rate-limit y backoff (M1).

- Solo endpoints publicos de lectura (GET). Nunca claves, nunca ordenes.
- Respeta el presupuesto de peso por minuto leyendo X-MBX-USED-WEIGHT-1M.
- Reintentos con backoff exponencial ante 429/418/5xx; respeta Retry-After.
"""

from __future__ import annotations

import contextlib
import time
from types import TracebackType
from typing import Any, Protocol

import httpx

SPOT_BASE = "https://api.binance.com"
FAPI_BASE = "https://fapi.binance.com"
_HEADERS = {"User-Agent": "QUANT-ARENA-M1/1.0 (investigacion publica, solo lectura)"}


class BinancePublicClient:
    def __init__(
        self,
        weight_budget_per_min: int = 4200,
        min_interval_s: float = 0.07,
        max_retries: int = 5,
        timeout_s: float = 30.0,
    ) -> None:
        self._client = httpx.Client(timeout=timeout_s, headers=_HEADERS)
        self._budget = weight_budget_per_min
        self._min_interval = min_interval_s
        self._max_retries = max_retries
        self._last_call = 0.0
        self.used_weight_1m = 0
        self.n_requests = 0

    # -- contexto -----------------------------------------------------------
    def __enter__(self) -> BinancePublicClient:
        return self

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc: BaseException | None,
        tb: TracebackType | None,
    ) -> None:
        self.close()

    def close(self) -> None:
        self._client.close()

    # -- nucleo ---------------------------------------------------------------
    def _throttle(self) -> None:
        now = time.monotonic()
        wait = self._min_interval - (now - self._last_call)
        if wait > 0:
            time.sleep(wait)
        if self.used_weight_1m > self._budget:
            # esperar al siguiente minuto natural con margen
            time.sleep(max(0.0, 61.0 - (time.time() % 60.0)))

    def get_json(self, base_url: str, path: str, params: dict[str, Any] | None = None) -> Any:
        last_err: Exception | None = None
        for attempt in range(self._max_retries):
            self._throttle()
            self._last_call = time.monotonic()
            try:
                resp = self._client.get(base_url + path, params=params)
            except httpx.HTTPError as e:  # red/timeout: reintentar
                last_err = e
                time.sleep(min(2.0**attempt, 30.0))
                continue
            self.n_requests += 1
            w = resp.headers.get("x-mbx-used-weight-1m") or resp.headers.get("x-mbx-used-weight")
            if w is not None:
                with contextlib.suppress(ValueError):
                    self.used_weight_1m = int(w)
            if resp.status_code == 200:
                return resp.json()
            if resp.status_code in (429, 418):
                retry_after = resp.headers.get("retry-after")
                sleep_s = float(retry_after) if retry_after else min(2.0**attempt * 10, 120.0)
                last_err = RuntimeError(f"rate-limit {resp.status_code}: {resp.text[:150]}")
                time.sleep(sleep_s)
                continue
            if resp.status_code >= 500:
                last_err = RuntimeError(f"server {resp.status_code}: {resp.text[:150]}")
                time.sleep(min(2.0**attempt, 30.0))
                continue
            raise RuntimeError(f"HTTP {resp.status_code} en {path}: {resp.text[:200]}")
        raise RuntimeError(f"agotados {self._max_retries} reintentos en {path}: {last_err}")

    def get_bytes(self, url: str) -> bytes:
        last_err: Exception | None = None
        for attempt in range(self._max_retries):
            self._throttle()
            self._last_call = time.monotonic()
            try:
                resp = self._client.get(url)
                self.n_requests += 1
                if resp.status_code == 200:
                    return resp.content
                last_err = RuntimeError(f"HTTP {resp.status_code} en {url}")
                if resp.status_code >= 500 or resp.status_code in (429, 418):
                    time.sleep(min(2.0**attempt * 2, 30.0))
                    continue
                raise RuntimeError(f"HTTP {resp.status_code} en {url}: {resp.text[:200]}")
            except httpx.HTTPError as e:
                last_err = e
                time.sleep(min(2.0**attempt, 30.0))
        raise RuntimeError(f"agotados reintentos en {url}: {last_err}")


class JsonClient(Protocol):
    """Tipo estructural para clientes de lectura publica (tests usan fakes)."""

    def get_json(self, base_url: str, path: str, params: dict[str, Any] | None = None) -> Any: ...


class BytesClient(Protocol):
    def get_bytes(self, url: str) -> bytes: ...
