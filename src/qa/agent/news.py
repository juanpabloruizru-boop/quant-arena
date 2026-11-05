# ruff: noqa: E501
"""Vigilante de noticias y choques tecnicos (M4/M5) — SOLO DESCRIPTIVO.

- Noticias: RSS publicos (sin claves), criba por keywords de riesgo y por
  activos del usuario/watchlist. Nunca genera ordenes: produce "motivos para
  revisar tu posicion".
- Choques: movimiento vs ATR14 en 1h/4h, spike de volumen y funding extremo.
  Umbrales en config/watchlist.yaml (convenciones de riesgo documentadas, no
  senales pre-registradas).
"""

from __future__ import annotations

import re
import xml.etree.ElementTree as ET
from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta
from email.utils import parsedate_to_datetime
from typing import Any

import numpy as np

_USER_AGENT = {"User-Agent": "QUANT-ARENA-agent/1.0 (monitor de riesgos, solo lectura)"}


@dataclass
class NewsItem:
    feed: str
    title: str
    link: str
    published_utc: str
    keywords: list[str] = field(default_factory=list)
    assets: list[str] = field(default_factory=list)
    categoria: str = "⚡ PRINCIPAL DEL DÍA"


_BASE_ALIASES = {
    "btc": ("btc", "bitcoin"),
    "eth": ("eth", "ethereum", "ether"),
    "sol": ("sol", "solana"),
    "bnb": ("bnb", "binance coin"),
    "xrp": ("xrp", "ripple"),
}


def screen_title(
    title: str, keywords: list[str], assets_bases: list[str]
) -> tuple[list[str], list[str]]:
    """Criba pura de un titular: (keywords de riesgo, bases mencionadas).

    Las bases se buscan con alias comunes (BTC -> 'bitcoin', etc.) para no
    perder titulares que no usan el ticker.
    """
    low = title.lower()
    kws = [k for k in keywords if re.search(rf"\b{re.escape(k.lower())}", low)]
    bases = []
    for b in assets_bases:
        variants = _BASE_ALIASES.get(b.lower(), (b.lower(),))
        if any(re.search(rf"\b{re.escape(v)}\b", low) for v in variants):
            bases.append(b)
    return kws, bases


def _http_get(url: str, timeout: float = 15.0) -> bytes | None:
    import httpx

    try:
        r = httpx.get(url, headers=_USER_AGENT, timeout=timeout, follow_redirects=True)
        return r.content if r.status_code == 200 else None
    except httpx.HTTPError:
        return None


def clasificar_titular(title: str, kws: list[str]) -> str:
    """Clasifica un titular en una de las 4 categorías solicitadas."""
    low = title.lower()
    # 1. Alerta de riesgo (keywords críticas o de seguridad)
    riesgo_terms = ["hack", "exploit", "sec ", " sec", "ban ", "banned", "halt", "crash", "fraud", "lawsuit", "delist", "insolven", "depeg", "scam"]
    if any(k in low for k in riesgo_terms) or any(k in ["hack", "exploit", "halt", "crash", "insolvency"] for k in kws):
        return "⚠️ ALERTA RIESGO"
    # 2. Macro / Fed / Tasas / Inflación
    macro_terms = ["fed", "fomc", "rate", "rates", "powell", "cpi", "inflation", "economy", "economic", "tariff", "dollar", "jobs", "treasury", "central bank", "ecb", "gdp", "warsh", "lagarde"]
    if any(re.search(rf"\b{re.escape(w)}\b", low) for w in macro_terms):
        return "🏦 MACRO / FED / TASAS"
    # 3. ETF / Institucional
    etf_terms = ["etf", "blackrock", "fidelity", "inflow", "outflow", "whale", "wall street", "institution", "fund", "grayscale", "microstrategy"]
    if any(re.search(rf"\b{re.escape(w)}\b", low) for w in etf_terms):
        return "🏛️ ETF / INSTITUCIONAL"
    # 4. Resto principal del día
    return "⚡ PRINCIPAL DEL DÍA"


def calcular_termometro_macro(items: list[NewsItem]) -> str:
    """Calcula el 'Termómetro Macro y Mercado Hoy' a partir de los titulares recientes."""
    if not items:
        return "NEUTRAL"
    texto = " ".join(it.title.lower() for it in items[:15])
    bad_count = sum(1 for w in ["crash", "hack", "ban", "lawsuit", "inflation accelerates", "tariff", "recession", "drop", "plunge"] if w in texto)
    fed_count = sum(1 for w in ["fed", "fomc", "rate", "powell", "interest rate"] if w in texto)
    good_count = sum(1 for w in ["rally", "surge", "all-time high", "ath", "inflow", "record", "gdp increases", "approval", "bull"] if w in texto)

    if bad_count >= 3:
        return "DEFENSIVO (Alertas y Presión Macro)"
    elif fed_count >= 2:
        return "NEUTRAL - ATENCIÓN FED Y TASAS"
    elif good_count >= 2:
        return "ALCISTA (Flujo y Momentum Favorable)"
    else:
        return "NEUTRAL (Mercado Estable)"


def fetch_news(
    feeds: list[dict[str, Any]],
    keywords: list[str],
    assets_bases: list[str],
    max_age_hours: int = 72,
) -> tuple[list[NewsItem], dict[str, str]]:
    """Devuelve (items relevantes, estado por feed). Tolerante a fallos."""
    items: list[NewsItem] = []
    status: dict[str, str] = {}
    cutoff = datetime.now(UTC) - timedelta(hours=max_age_hours)
    for f in feeds:
        name = str(f.get("nombre", f.get("url", "?")))
        body = _http_get(str(f["url"]))
        if body is None:
            status[name] = "no disponible (feed bloqueado o caido)"
            continue
        try:
            root = ET.fromstring(body)
        except ET.ParseError:
            status[name] = "XML invalido"
            continue
        n_ok = 0
        for it in root.iter("item"):
            title = (it.findtext("title") or "").strip()
            link = (it.findtext("link") or "").strip()
            pub = it.findtext("pubDate") or ""
            try:
                when = parsedate_to_datetime(pub)
                if when.tzinfo is None:
                    when = when.replace(tzinfo=UTC)
                when = when.astimezone(UTC)
            except (TypeError, ValueError):
                continue
            if when < cutoff:
                continue
            kws, bases = screen_title(title, keywords, assets_bases)
            categoria = clasificar_titular(title, kws)
            items.append(
                NewsItem(
                    feed=name,
                    title=title[:200],
                    link=link,
                    published_utc=when.isoformat(timespec="minutes"),
                    keywords=kws,
                    assets=bases,
                    categoria=categoria,
                )
            )
            n_ok += 1
        status[name] = f"ok ({n_ok} titulares / {max_age_hours}h)"
    items.sort(key=lambda x: x.published_utc, reverse=True)
    return items[:40], status


def atr14(df: Any) -> float:
    """ATR(14) sobre velas (high/low/close), en unidades de precio."""
    if len(df) < 15:
        return float("nan")
    h = df["high"].to_numpy(dtype=float)
    lo = df["low"].to_numpy(dtype=float)
    c = df["close"].to_numpy(dtype=float)
    pc = np.concatenate(([c[0]], c[:-1]))
    tr = np.maximum(h - lo, np.maximum(np.abs(h - pc), np.abs(lo - pc)))
    return float(tr[-14:].mean())


def detect_shocks(
    klines: dict[str, dict[str, Any]],
    premium: dict[str, dict[str, Any]],
    cfg: dict[str, Any],
) -> list[dict[str, Any]]:
    """Choques tecnicos por simbolo (descriptivo)."""
    out: list[dict[str, Any]] = []
    atr_w = int(cfg.get("atr_window", 14))
    th4 = float(cfg.get("umbral_4h_atr", 2.5))
    th1 = float(cfg.get("umbral_1h_atr", 3.0))
    thv = float(cfg.get("umbral_volumen", 3.0))
    thf = float(cfg.get("umbral_funding_abs", 0.0005))
    for sym, frames in klines.items():
        f4 = frames.get("4h")
        f1 = frames.get("1h")
        if f4 is not None and len(f4) > atr_w + 8:
            a = atr14(f4.tail(atr_w + 1).reset_index(drop=True))
            c = f4["close"].to_numpy(dtype=float)
            move24 = abs(c[-1] / c[-7] - 1.0) if len(c) >= 7 else 0.0
            if a > 0 and move24 * c[-1] > th4 * a:
                out.append(
                    {
                        "symbol": sym,
                        "tipo": "choque_4h",
                        "detalle": f"movimiento 24h {move24 * 100:.1f}% > {th4}x ATR14(4h)",
                        "move_pct": round(move24 * 100, 2),
                        "atr": round(a, 2),
                    }
                )
            vol = f4["quote_volume"].to_numpy(dtype=float)
            if len(vol) > 31 and vol[-31:-1].mean() > 0:
                ratio = vol[-1] / vol[-31:-1].mean()
                if ratio > thv:
                    out.append(
                        {
                            "symbol": sym,
                            "tipo": "spike_volumen_4h",
                            "detalle": f"volumen ultima vela 4h = {ratio:.1f}x media(30)",
                            "ratio": round(ratio, 2),
                        }
                    )
        if f1 is not None and len(f1) > atr_w + 8:
            a1 = atr14(f1.tail(atr_w + 1).reset_index(drop=True))
            c1 = f1["close"].to_numpy(dtype=float)
            move6 = abs(c1[-1] / c1[-7] - 1.0) if len(c1) >= 7 else 0.0
            if a1 > 0 and move6 * c1[-1] > th1 * a1:
                out.append(
                    {
                        "symbol": sym,
                        "tipo": "choque_1h",
                        "detalle": f"movimiento 6h {move6 * 100:.1f}% > {th1}x ATR14(1h)",
                        "move_pct": round(move6 * 100, 2),
                    }
                )
        p = premium.get(sym)
        if p and abs(float(p.get("last_funding_rate", 0.0))) > thf:
            out.append(
                {
                    "symbol": sym,
                    "tipo": "funding_extremo",
                    "detalle": f"lastFunding {float(p['last_funding_rate']) * 100:.4f}% / 8h",
                }
            )
    return out
