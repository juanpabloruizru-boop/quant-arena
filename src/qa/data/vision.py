"""Acceso a los dumps publicos de data.binance.vision (bucket S3) (M1).

Verificado 2026-10-26:
- La raiz https://data.binance.vision sirve HTML al navegador; el listado XML
  funciona contra el bucket S3 subyacente:
  https://s3-ap-northeast-1.amazonaws.com/data.binance.vision?prefix=...
- Datasets futures UM diarios: aggTrades, bookDepth, bookTicker,
  indexPriceKlines, klines, markPriceKlines, metrics, premiumIndexKlines,
  trades. fundingRate solo existe en dumps MENSUALES.
- Los dumps conservan simbolos deslistados (FTTUSDT, LUNABTC verificados).

Uso en M1: (a) fallback para simbolos sin datos en el API actual (NBTUSDT);
(b) segunda fuente de verificacion del funding historico (cross-check).
"""

from __future__ import annotations

import csv
import io
import xml.etree.ElementTree as ET
import zipfile
from typing import Any

from qa.data.client import BytesClient

BUCKET = "https://s3-ap-northeast-1.amazonaws.com/data.binance.vision"


def list_keys(client: BytesClient, prefix: str, max_pages: int = 20) -> list[str]:
    """Lista claves S3 bajo un prefijo (paginado con Marker)."""
    keys: list[str] = []
    marker = ""
    for _ in range(max_pages):
        params: dict[str, Any] = {"prefix": prefix, "max-keys": 1000}
        if marker:
            params["marker"] = marker
        url = BUCKET + "?" + "&".join(f"{k}={v}" for k, v in params.items())
        body = client.get_bytes(url)
        root = ET.fromstring(body)
        ns_uri = root.tag.split("}")[0].strip("{") if root.tag.startswith("{") else ""
        ns = {"s3": ns_uri} if ns_uri else {}
        pref = "s3:" if ns else ""
        keys.extend(k.text or "" for k in root.findall(f"{pref}Contents/{pref}Key", ns))
        truncated = root.findtext(f"{pref}IsTruncated", default="false", namespaces=ns or None)
        next_marker = root.findtext(f"{pref}NextMarker", default="", namespaces=ns or None)
        if truncated != "true" or not next_marker:
            break
        marker = next_marker
    return [k for k in keys if not k.endswith(".CHECKSUM")]


def list_common_prefixes(client: BytesClient, prefix: str, max_pages: int = 20) -> list[str]:
    """Lista prefijos comunes (p. ej. nombres de simbolo) bajo un prefijo."""
    out: list[str] = []
    marker = ""
    for _ in range(max_pages):
        params: dict[str, Any] = {"delimiter": "/", "prefix": prefix, "max-keys": 1000}
        if marker:
            params["marker"] = marker
        url = BUCKET + "?" + "&".join(f"{k}={v}" for k, v in params.items())
        body = client.get_bytes(url)
        root = ET.fromstring(body)
        ns_uri = root.tag.split("}")[0].strip("{") if root.tag.startswith("{") else ""
        ns = {"s3": ns_uri} if ns_uri else {}
        pref = "s3:" if ns else ""
        out.extend(p.text or "" for p in root.findall(f"{pref}CommonPrefixes/{pref}Prefix", ns))
        truncated = root.findtext(f"{pref}IsTruncated", default="false", namespaces=ns or None)
        next_marker = root.findtext(f"{pref}NextMarker", default="", namespaces=ns or None)
        if truncated != "true" or not next_marker:
            break
        marker = next_marker
    return out


def parse_csv_zip(content: bytes) -> list[list[str]]:
    """Parsea un zip de dump (1 CSV dentro), con o sin cabecera (sniffing)."""
    with zipfile.ZipFile(io.BytesIO(content)) as zf:
        names = [n for n in zf.namelist() if n.endswith(".csv")]
        if not names:
            raise ValueError("zip sin CSV")
        text = zf.read(names[0]).decode("utf-8")
    rows = list(csv.reader(io.StringIO(text)))
    if not rows:
        return []
    first = rows[0][0]
    try:
        float(first)
        return rows  # sin cabecera
    except ValueError:
        return rows[1:]  # con cabecera
