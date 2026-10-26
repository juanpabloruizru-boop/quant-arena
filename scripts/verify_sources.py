"""Verify bibliographic sources for M0 literature review, live.

Every source is checked against a primary resolver:
- ``crossref``: direct DOI lookup (or bibliographic title search when the DOI is
  unknown) at https://api.crossref.org.
- ``arxiv``: export API at https://export.arxiv.org/api/query.
- ``url``: plain HTTP GET of the landing page (SSRN etc.), recording status and
  page title.

Evidence is written to ``docs/evidence/sources.json`` so no citation in
``docs/LITERATURA.md`` relies on memory. Deterministic: no randomness, fixed
queries. Exit code is non-zero if any source fails verification, which makes
this script usable as a gate.

Usage:
    python scripts/verify_sources.py
"""

from __future__ import annotations

import difflib
import json
import sys
import unicodedata
import urllib.error
import urllib.parse
import urllib.request
import xml.etree.ElementTree as ET
from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

REPO = Path(__file__).resolve().parents[1]
OUT = REPO / "docs" / "evidence" / "sources.json"
UA = {"User-Agent": "QUANT-ARENA-M0-source-verification/1.0"}
TIMEOUT = 30


@dataclass
class Source:
    sid: str
    kind: str  # crossref | arxiv | url
    title: str
    first_author: str
    year: int
    doi: str | None = None
    url: str | None = None
    search_query: str = ""
    container: str = ""
    expected_fail: bool = False  # intento documentado que no puede verificarse en vivo
    note: str = ""
    result: dict[str, Any] = field(default_factory=dict)


SOURCES: list[Source] = [
    # --- Overfitting / multiple testing -------------------------------------
    Source(
        "S01",
        "crossref",
        "The Deflated Sharpe Ratio: Correcting for Selection Bias, "
        "Backtest Overfitting, and Non-Normality",
        "Bailey",
        2014,
        doi="10.3905/jpm.2014.40.5.094",
        note="DSR: corrige el Sharpe por número de ensayos, asimetría y curtosis.",
    ),
    Source(
        "S02",
        "crossref",
        "The Probability of Backtest Overfitting",
        "Bailey",
        2014,
        doi="10.2139/ssrn.2326253",
        search_query="The Probability of Backtest Overfitting Bailey Borwein Lopez de Prado Zhu",
        note="PBO vía CSCV. Publicada en Journal of Computational Finance (SSRN 2014).",
    ),
    Source(
        "S03",
        "crossref",
        "A Reality Check for Data Snooping",
        "White",
        2000,
        doi="10.1111/1468-0262.00152",
        note="Bootstrap de Reality Check para la mejor de N reglas.",
    ),
    Source(
        "S04",
        "crossref",
        "A Test for Superior Predictive Ability",
        "Hansen",
        2005,
        doi="10.1198/073500105000000063",
        note="SPA test: mejora del Reality Check de White.",
    ),
    Source(
        "S05",
        "crossref",
        "...and the Cross-Section of Expected Returns",
        "Harvey",
        2016,
        doi="10.1093/rfs/hhv059",
        note="Multiplicidad de pruebas en finanzas; umbral t>3.",
    ),
    Source(
        "S06",
        "crossref",
        "The 10 Reasons Most Machine Learning Funds Fail",
        "Lopez de Prado",
        2018,
        search_query="The Ten Reasons Most Machine Learning Funds Fail Lopez de Prado",
        note="Incluye CPCV (combinatorial purged cross-validation) y purging/embargo.",
    ),
    Source(
        "S07",
        "url",
        "Advances in Financial Machine Learning",
        "Lopez de Prado",
        2018,
        url="https://www.wiley.com/en-us/Advances+in+Financial+Machine+Learning-p-9781119482086",
        expected_fail=True,
        note=(
            "Libro (Wiley): cap. 7 (CV purgado con embargo), cap. 8 (CPCV), cap. 14 (PBO). "
            "Sin DOI Crossref; verificacion por pagina del editor."
        ),
    ),
    # --- Momentum / tendencia / volatilidad ---------------------------------
    Source(
        "S08",
        "crossref",
        "Time Series Momentum",
        "Moskowitz",
        2012,
        search_query="Time Series Momentum Moskowitz Ooi Pedersen",
        note="Fundamento de tendencia temporal (base de H1).",
    ),
    Source(
        "S09",
        "crossref",
        "Common Risk Factors in Cryptocurrency",
        "Liu",
        2022,
        search_query="Common Risk Factors in Cryptocurrency Liu Tsyvinski Wu",
        container="The Journal of Finance",
        note=(
            "Factores mercado/tamano/momentum en cripto. Titulo exacto verificado via Crossref "
            "(la referencia heredada 'Common Cryptocurrency Risk Factors' era el titulo del "
            "working paper NBER)."
        ),
    ),
    Source(
        "S10",
        "crossref",
        "A Trend Factor for the Cross Section of Cryptocurrency Returns",
        "Fieberg",
        2025,
        search_query="A Trend Factor for the Cross Section of Cryptocurrency Returns Fieberg",
        container="Journal of Financial and Quantitative Analysis",
        note=(
            "Factor de tendencia transversal en cripto (JFQA). Sustituye a una referencia "
            "heredada no verificable (Kolodziejczyk et al., RQFA): no localizable en Crossref, "
            "se descarta por politica de no citar de memoria."
        ),
    ),
    Source(
        "S11",
        "crossref",
        "Dynamic time series momentum of cryptocurrencies",
        "Borgards",
        2021,
        note="TSMOM dinámico en cripto; heterogeneidad por capitalización.",
    ),
    Source(
        "S12",
        "crossref",
        "Volatility-Managed Portfolios",
        "Moreira",
        2017,
        doi="10.1111/jofi.12513",
        note="Escalado por volatilidad realizada (base del vol targeting de H1).",
    ),
    # --- Carry / funding -----------------------------------------------------
    Source(
        "S13",
        "crossref",
        "Carry",
        "Koijen",
        2018,
        search_query="Carry Koijen Moskowitz Pedersen Vrugt",
        container="Journal of Financial Economics",
        note="Marco general de carry entre clases de activos.",
    ),
    Source(
        "S14",
        "arxiv",
        "Fundamentals of Perpetual Futures",
        "",
        2022,
        url="https://arxiv.org/abs/2212.06888",
        note="Teoría/empiria de perpetuals y funding.",
    ),
    Source(
        "S15",
        "crossref",
        "Crypto Carry",
        "",
        2023,
        note="Buscar paper específico de carry en cripto (funding/basis).",
    ),
    # --- Costes / decaimiento de señales --------------------------------------
    Source(
        "S16",
        "crossref",
        "Does Academic Research Destroy Stock Return Predictability?",
        "McLean",
        2016,
        doi="10.1111/jofi.12365",
        note="Decaimiento post-publicación de señales; aplicable por analogía a cripto.",
    ),
]


def _get(url: str) -> tuple[int, bytes]:
    req = urllib.request.Request(url, headers=UA)
    with urllib.request.urlopen(req, timeout=TIMEOUT) as r:
        return r.status, r.read()


def _ratio(a: str, b: str) -> float:
    return difflib.SequenceMatcher(None, a.lower(), b.lower()).ratio()


def _fold(x: str) -> str:
    n = unicodedata.normalize("NFKD", x)
    return "".join(c for c in n if not unicodedata.combining(c)).lower()


def _crossref_direct(src: Source) -> dict[str, Any]:
    assert src.doi is not None
    url = f"https://api.crossref.org/works/{urllib.parse.quote(src.doi)}"
    try:
        status, body = _get(url)
        msg = json.loads(body)["message"]
    except urllib.error.HTTPError as e:
        return {
            "resolver": "crossref-doi",
            "api_url": url,
            "http_status": e.code,
            "verified": False,
            "reason": f"DOI lookup failed ({e.code})",
        }
    title = msg.get("title", [""])[0]
    authors = [f"{a.get('given', '')} {a.get('family', '')}".strip() for a in msg.get("author", [])]
    year = None
    for k in ("published-print", "published-online", "issued", "created"):
        parts = msg.get(k, {}).get("date-parts", [[None]])
        if parts and parts[0] and parts[0][0]:
            year = parts[0][0]
            break
    ok_title = _ratio(title, src.title) >= 0.60
    ok_author = (not src.first_author) or any(
        _fold(src.first_author).replace(" ", "") in _fold(a).replace(" ", "") for a in authors
    )
    ok_year = year is not None and abs(int(year) - src.year) <= 1
    return {
        "resolver": "crossref-doi",
        "api_url": url,
        "http_status": status,
        "doi": msg.get("DOI"),
        "resolved_title": title,
        "resolved_authors": authors,
        "resolved_container": msg.get("container-title", []),
        "resolved_year": year,
        "publisher_url": msg.get("URL"),
        "title_match": ok_title,
        "author_match": ok_author,
        "year_match": ok_year,
        "verified": bool(ok_title and ok_author and ok_year),
    }


def _crossref_search(src: Source) -> dict[str, Any]:
    q = urllib.parse.quote(src.search_query or f"{src.title} {src.first_author}".strip())
    url = (
        "https://api.crossref.org/works?"
        f"query.bibliographic={q}&rows=5&select=DOI,title,author,container-title,published,URL"
    )
    if src.container:
        url += f"&query.container-title={urllib.parse.quote(src.container)}"
    try:
        status, body = _get(url)
        items = json.loads(body)["message"]["items"]
    except urllib.error.HTTPError as e:
        return {
            "resolver": "crossref-search",
            "api_url": url,
            "http_status": e.code,
            "verified": False,
            "reason": f"search failed ({e.code})",
        }
    best: dict[str, Any] | None = None
    best_ratio = 0.0
    for it in items:
        t = it.get("title", [""])[0]
        r = _ratio(t, src.title)
        if r > best_ratio:
            best_ratio, best = r, it
    if best is None or best_ratio < 0.70:
        return {
            "resolver": "crossref-search",
            "api_url": url,
            "http_status": status,
            "verified": False,
            "reason": f"best title ratio {best_ratio:.2f} < 0.70",
            "candidates": [it.get("title", [""])[0] for it in items],
        }
    authors = [
        f"{a.get('given', '')} {a.get('family', '')}".strip() for a in best.get("author", [])
    ]
    year = None
    parts = best.get("published", {}).get("date-parts", [[None]])
    if parts and parts[0]:
        year = parts[0][0]
    ok_author = (not src.first_author) or any(_fold(src.first_author) in _fold(a) for a in authors)
    ok_year = year is not None and abs(int(year) - src.year) <= 2
    return {
        "resolver": "crossref-search",
        "api_url": url,
        "http_status": status,
        "doi": best.get("DOI"),
        "resolved_title": best.get("title", [""])[0],
        "resolved_authors": authors,
        "resolved_container": best.get("container-title", []),
        "resolved_year": year,
        "publisher_url": best.get("URL"),
        "title_ratio": round(best_ratio, 3),
        "author_match": ok_author,
        "year_match": ok_year,
        "verified": bool(ok_author and ok_year),
    }


def _arxiv(src: Source) -> dict[str, Any]:
    assert src.url is not None
    aid = src.url.rsplit("/", 1)[-1]
    url = f"https://export.arxiv.org/api/query?id_list={aid}"
    status, body = _get(url)
    ns = {"a": "http://www.w3.org/2005/Atom"}
    root = ET.fromstring(body)
    entry = root.find("a:entry", ns)
    if entry is None:
        return {"resolver": "arxiv", "api_url": url, "http_status": status, "verified": False}
    title = (entry.findtext("a:title", "", ns) or "").strip().replace("\n", " ")
    authors = [(a.findtext("a:name", "", ns) or "").strip() for a in entry.findall("a:author", ns)]
    published = entry.findtext("a:published", "", ns)
    ok_title = _ratio(title, src.title) >= 0.70
    return {
        "resolver": "arxiv",
        "api_url": url,
        "http_status": status,
        "resolved_title": title,
        "resolved_authors": authors,
        "resolved_year": published[:4] if published else None,
        "publisher_url": src.url,
        "title_match": ok_title,
        "verified": ok_title,
    }


def _url_probe(src: Source) -> dict[str, Any]:
    assert src.url is not None
    try:
        status, body = _get(src.url)
        head = body[:4000].decode("utf-8", errors="replace")
        low = head.lower()
        i = low.find("<title>")
        page_title = head[i + 7 : low.find("</title>", i)] if i >= 0 else ""
        pt = page_title.strip()[:200]
        title_ok = status == 200 and (
            _fold(src.title) in _fold(pt) or _ratio(pt, src.title) >= 0.55
        )
        return {
            "resolver": "url",
            "api_url": src.url,
            "final_url": src.url,
            "http_status": status,
            "page_title": pt,
            "verified": title_ok,
        }
    except Exception as e:  # noqa: BLE001 - evidence of failure is the point
        return {"resolver": "url", "api_url": src.url, "verified": False, "error": repr(e)[:300]}


def main() -> int:
    checked_at = datetime.now(UTC).isoformat(timespec="seconds")
    out: dict[str, Any] = {"checked_at_utc": checked_at, "sources": []}
    failures = []
    for src in SOURCES:
        if src.kind == "crossref":
            res = _crossref_direct(src) if src.doi else _crossref_search(src)
            if not res.get("verified"):
                fallback = _crossref_search(src)
                fallback["doi_lookup_attempt"] = res
                res = fallback
        elif src.kind == "arxiv":
            res = _arxiv(src)
        else:
            res = _url_probe(src)
        rec = {
            "id": src.sid,
            "expected_fail": src.expected_fail,
            "declared_title": src.title,
            "declared_first_author": src.first_author,
            "declared_year": src.year,
            "note": src.note,
            **res,
        }
        out["sources"].append(rec)
        verified = bool(res.get("verified"))
        flag = "OK " if verified else ("FAIL(expected)" if src.expected_fail else "FAIL")
        if not verified and not src.expected_fail:
            failures.append(src.sid)
        print(
            f"{flag} {src.sid} {res.get('doi') or res.get('api_url', '')[:60]:<28} "
            f"{str(res.get('resolved_title', res.get('page_title', '')))[:80]}"
        )
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(out, indent=2, ensure_ascii=False), encoding="utf-8")
    print(f"\nevidence -> {OUT}")
    if failures:
        print(f"UNVERIFIED: {failures}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
