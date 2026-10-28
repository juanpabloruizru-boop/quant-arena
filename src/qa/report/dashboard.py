# ruff: noqa: E501  (generador de plantilla HTML: lineas largas inevitables)
"""Dashboard autocontenido (M5 operativo): HTML+CSS+SVG inline, sin JS externo.

REGLA DE LENGUAJE (test obligatorio test_dashboard_language_guard):
- Ningun imperativo de trading (comprar/vender/cerrar/subir stop/reducir).
- Cada regla lleva su etiqueta de veredicto del preregistro.
- H1/H2 muestran SIEMPRE "SIN VENTAJA DEMOSTRADA"; H3-BTC muestra su PASA con
  la caveat de costes x2; H3-ETH muestra NO PASA.
El dashboard es un espejo de estados + registro del usuario, no un asesor.
"""

from __future__ import annotations

import html
from datetime import UTC, datetime
from typing import Any

CSS = """
:root{--bg:#0d1117;--panel:#161b22;--line:#30363d;--tx:#e6edf3;--mut:#8b949e;
--ok:#2ea043;--warn:#d29922;--bad:#f85149;--info:#58a6ff}
*{box-sizing:border-box}body{margin:0;background:var(--bg);color:var(--tx);
font:14px/1.5 -apple-system,'Segoe UI',Roboto,Helvetica,Arial,sans-serif;padding:18px}
h1{font-size:20px;margin:0 0 4px}h2{font-size:15px;margin:0 0 10px;color:var(--info)}
.sub{color:var(--mut);font-size:12px;margin-bottom:16px}
.banner{background:#3d1d1d;border:1px solid var(--bad);border-radius:8px;
padding:10px 14px;margin-bottom:18px;font-size:13px}
.grid{display:grid;grid-template-columns:repeat(auto-fit,minmax(430px,1fr));gap:16px}
.panel{background:var(--panel);border:1px solid var(--line);border-radius:10px;padding:14px 16px}
table{width:100%;border-collapse:collapse;font-size:12.5px}
th{color:var(--mut);text-align:left;font-weight:600;border-bottom:1px solid var(--line);padding:5px 6px}
td{padding:5px 6px;border-bottom:1px solid #21262d;vertical-align:top}
.badge{display:inline-block;padding:2px 8px;border-radius:999px;font-size:11px;font-weight:700}
.b-ok{background:#12331d;color:var(--ok);border:1px solid var(--ok)}
.b-warn{background:#332701;color:var(--warn);border:1px solid var(--warn)}
.b-bad{background:#3d1d1d;color:var(--bad);border:1px solid var(--bad)}
.b-info{background:#0c2d6b33;color:var(--info);border:1px solid var(--info)}
.num{font-variant-numeric:tabular-nums}
.pos{color:var(--ok)}.neg{color:var(--bad)}.mut{color:var(--mut)}
.small{font-size:11.5px;color:var(--mut)}
svg{display:block;margin-top:6px}
footer{margin-top:20px;color:var(--mut);font-size:11.5px}
"""

PROHIBIDOS = (
    "COMPRAR",
    "VENDER",
    "ABRE LONG",
    "ABRIR LONG",
    "ABRE SHORT",
    "CIERRA",
    "CIERRE ANTICIPADO",
    "SUBIR STOP",
    "SUBE STOP",
    "REDUCIR 50",
    "TOMA GANANCIAS",
    "PRECIO DE ENTRADA SUGERIDO",
    "SL SUGERIDO",
    "TP SUGERIDO",
    "STOP SUGERIDO",
)


def _esc(x: Any) -> str:
    return html.escape(str(x))


def _spark(closes: list[float], width: int = 400, height: int = 46) -> str:
    if len(closes) < 2:
        return ""
    lo, hi = min(closes), max(closes)
    span = (hi - lo) or 1.0
    pts = " ".join(
        f"{i * width / (len(closes) - 1):.1f},{height - (c - lo) / span * (height - 6) - 3:.1f}"
        for i, c in enumerate(closes)
    )
    color = "#2ea043" if closes[-1] >= closes[0] else "#f85149"
    return (
        f'<svg viewBox="0 0 {width} {height}" width="100%" height="{height}">'
        f'<polyline points="{pts}" fill="none" stroke="{color}" stroke-width="1.5"/></svg>'
    )


def _badge(veredicto: str) -> str:
    v = veredicto.upper()
    if "SIN VENTAJA" in v or "INCONTRASTABLE" in v:
        cls = "b-warn"
    elif "NO PASA" in v:
        cls = "b-bad"
    elif "VALIDADA" in v or "PASA" in v:
        cls = "b-ok"
    else:
        cls = "b-info"
    return f'<span class="badge {cls}">{_esc(veredicto)}</span>'


def render_dashboard(
    states: dict[str, Any],
    trades_diag: list[dict[str, Any]],
    news: list[dict[str, Any]],
    feed_status: dict[str, str],
    shocks: list[dict[str, Any]],
    spark_data: dict[str, list[float]],
    meta: dict[str, Any],
    telemetry: dict[str, Any] | None = None,
    h1_levels: dict[str, Any] | None = None,
    capital_ref: float = 0.0,
) -> str:
    now = datetime.now(UTC).strftime("%Y-%m-%d %H:%M UTC")
    p: list[str] = []
    p.append("<!DOCTYPE html><html lang='es'><head><meta charset='utf-8'>")
    p.append("<meta name='viewport' content='width=device-width,initial-scale=1'>")
    p.append(
        f"<title>QUANT-ARENA · Centro de mando (estado, no consejo)</title><style>{CSS}</style></head><body>"
    )
    p.append("<h1>QUANT-ARENA v2 · Centro de mando</h1>")
    p.append(
        f"<div class='sub'>Generado: {now} · datos vivos: {_esc(states.get('fetched_at_utc', '?'))} · "
        f"git {_esc(str(meta.get('git_sha', '?'))[:7])} · herramienta de investigación, "
        "<b>no es asesoramiento de inversión</b></div>"
    )
    p.append(
        "<div class='banner'>⚠ Este panel muestra <b>estados descriptivos</b> de reglas "
        "investigadas y el registro de TUS operaciones. No da órdenes de compra/venta. "
        "H1 y H2 están <b>SIN VENTAJA DEMOSTRADA</b> (veredicto INCONTRASTABLE del "
        "preregistro v1.4); H3-BTC pasó a nivel de signo con edge frágil a costes ×2. "
        "Ningún número de aquí es una promesa de rentabilidad.</div>"
    )

    # 1) Operaciones del usuario
    p.append("<div class='grid'>")
    p.append("<div class='panel'><h2>1 · Mis operaciones abiertas (registro del usuario)</h2>")
    if trades_diag:
        p.append(
            "<table><tr><th>Op</th><th>Activo/Tipo</th><th>PnL</th><th>Dist. SL / TP (tuyos)</th>"
            "<th>Tiempo</th><th>RR TP/SL inic.→actual</th><th>SMA50 de tu marco</th>"
            "<th>Contexto de tendencia</th><th>Seguimiento</th></tr>"
        )
        for t in trades_diag:
            ex = " <span class='badge b-info'>EJEMPLO</span>" if t.get("example") else ""
            pnl = t.get("pnl_pct")
            cls = "pos" if (pnl or 0) >= 0 else "neg"
            sl = f"{t.get('dist_sl_pct', '—')}%" if t.get("dist_sl_pct") is not None else "—"
            tp = f"{t.get('dist_tp_pct', '—')}%" if t.get("dist_tp_pct") is not None else "—"
            p.append(
                f"<tr><td class='num'>{_esc(t['id'])}{ex}</td>"
                f"<td>{_esc(t['asset'])}<br><span class='small'>{_esc(t.get('kind', ''))}</span></td>"
                f"<td class='num {cls}'>{pnl if pnl is not None else '—'}%"
                f"<br><span class='small'>{t.get('pnl_usd', '—')} USD</span></td>"
                f"<td class='num'>{sl} / {tp}</td>"
                f"<td class='small'>{_esc(t.get('tiempo_abierta', '—'))}</td>"
                f"<td class='num small'>{_esc(t.get('rr_inicial_tp_sl', '—'))} → "
                f"{_esc(t.get('rr_actual_tp_sl', '—'))}</td>"
                f"<td class='small'>{_esc(t.get('sma50_marco_txt', '—'))}</td>"
                f"<td class='small'>{_esc(t.get('contexto_tendencia', '—'))}</td>"
                f"<td class='small'>{_esc(t.get('estado_seguimiento', '—'))}</td></tr>"
            )
        p.append("</table>")
    else:
        p.append(
            "<div class='small'>Sin operaciones registradas. Usa <code>qa trade open …</code> "
            "para anotar TUS operaciones (el agente no abre nada).</div>"
        )
    p.append("</div>")

    # 4) Choques y noticias (junto a operaciones: alertas de riesgo)
    p.append("<div class='panel'><h2>4 · Choques técnicos y noticias (vigilancia)</h2>")
    if shocks:
        p.append("<table><tr><th>Símbolo</th><th>Tipo</th><th>Detalle</th></tr>")
        for s in shocks[:12]:
            p.append(
                f"<tr><td>{_esc(s['symbol'])}</td><td><span class='badge b-bad'>{_esc(s['tipo'])}</span></td>"
                f"<td class='small'>{_esc(s['detalle'])}</td></tr>"
            )
        p.append("</table>")
    else:
        p.append(
            "<div class='small'>Sin choques técnicos ahora (umbrales en config/watchlist.yaml).</div>"
        )
    if news:
        p.append(
            "<table style='margin-top:10px'><tr><th>Titular (últimas 72 h)</th><th>Fuente</th></tr>"
        )
        for n in news[:10]:
            kw = " ".join(f"[{_esc(k)}]" for k in n.get("keywords", []))
            ast = " ".join(_esc(a) for a in n.get("assets", []))
            p.append(
                f"<tr><td><a style='color:var(--info)' href='{_esc(n['link'])}'>{_esc(n['title'])}</a>"
                f"<br><span class='small'>{kw} {ast} · {_esc(n['published_utc'])}</span></td>"
                f"<td class='small'>{_esc(n['feed'])}</td></tr>"
            )
        p.append("</table>")
    else:
        p.append("<div class='small'>Sin titulares relevantes en las últimas 72 h.</div>")
    p.append(
        "<div class='small' style='margin-top:6px'>Feeds: "
        + " · ".join(f"{_esc(k)}: {_esc(v)}" for k, v in feed_status.items())
        + "</div>"
    )
    p.append("</div>")

    # 2) Reglas congeladas
    p.append("<div class='panel'><h2>2 · Reglas congeladas (m3a-freeze) — estados de hoy</h2>")
    cells = states.get("cells", {})
    p.append(
        "<table><tr><th>Regla</th><th>Veredicto del preregistro</th><th>Estado hoy</th><th>Detalle</th></tr>"
    )
    for key in ("H1_BTCUSDT", "H1_ETHUSDT"):
        c = cells.get(key)
        if not c:
            continue
        det = (
            f"close {_esc(round(c['close'], 2))} vs SMA50 {_esc(round(c['sma50'], 2) if c['sma50'] else '—')} "
            f"({c['close_vs_sma50_pct']:+.1f}%) · vol20d {_esc(round((c['vol_realizada_20d_ann'] or 0) * 100, 1))}% "
            f"· posición de la regla {_esc(round(c['posicion_regla'] * 100))}%"
        )
        p.append(
            f"<tr><td><b>H1 tendencia {_esc(key.split('_')[1])}</b><br>"
            f"<span class='small'>sma50_s25 · diario</span></td>"
            f"<td>{_badge(c['veredicto'])}<br><span class='small'>{_esc(c['nota'])}</span></td>"
            f"<td><span class='badge {'b-ok' if c['estado'] == 'LONG' else 'b-info'}'>{_esc(c['estado'])}</span></td>"
            f"<td class='small num'>{det}</td></tr>"
        )
    h2 = cells.get("H2_L26_N10")
    if h2:
        cesta = ", ".join(h2.get("cesta_teoretica", []))
        p.append(
            f"<tr><td><b>H2 momentum</b><br><span class='small'>L26_N10 · semanal</span></td>"
            f"<td>{_badge(h2['veredicto'])}<br><span class='small'>{_esc(h2['nota'])}</span></td>"
            f"<td><span class='badge b-info'>CESTA TEÓRICA</span></td>"
            f"<td class='small'>{_esc(cesta)}<br>top-10 PIT: {_esc(', '.join(h2.get('universo_top10_actual', [])))}</td></tr>"
        )
    for key in ("H3_BTCUSDT", "H3_ETHUSDT"):
        c = cells.get(key)
        if not c:
            continue
        lf = c.get("last_funding_rate")
        p.append(
            f"<tr><td><b>H3 carry {_esc(key.split('_')[1])}</b><br><span class='small'>w30_t5 · delta-neutral</span></td>"
            f"<td>{_badge(c['veredicto'])}<br><span class='small'>{_esc(c['nota'])}</span></td>"
            f"<td><span class='badge {'b-ok' if c['senal_activa'] else 'b-info'}'>{_esc(c['estado'])}</span></td>"
            f"<td class='small num'>MA30d {_esc(round((c['funding_ma30_ann'] or 0) * 100, 2))}% · "
            f"MA7d {_esc(round((c['funding_ma7_ann'] or 0) * 100, 2))}% · umbral 5% · "
            f"último funding {_esc(round((lf or 0) * 100, 4))}%/8h · próximo {_esc(c.get('next_funding_utc', '—'))}</td></tr>"
        )
    p.append("</table>")
    if h1_levels:
        p.append(
            "<div class='small' style='margin-top:10px'><b>Niveles observables de H1 "
            "(diario) — estadística descriptiva del precio, no hipótesis ni señal:</b></div>"
        )
        p.append(
            "<table><tr><th>Activo</th><th>Precio</th><th>Nivel SMA50 (dist.)</th>"
            "<th>ATR14</th><th>Rango estadístico [close−2×ATR, close+3×ATR]</th>"
            "<th>Exposición de la regla</th><th>Escala teórica s/ capital ref.</th></tr>"
        )
        for asset, lv in h1_levels.items():
            expo_pct = round(float(lv["exposicion_regla"]) * 100)
            p.append(
                f"<tr><td>{_esc(asset)}</td><td class='num'>{_esc(lv['precio'])}</td>"
                f"<td class='num'>{_esc(lv['nivel_sma50'])} ({_esc(lv['distancia_a_sma50_pct'])}%)</td>"
                f"<td class='num'>{_esc(lv['atr14_usd'])} ({_esc(lv['atr14_pct'])}%)</td>"
                f"<td class='num'>[{_esc(lv['banda_inf_c_menos_2atr'])}, "
                f"{_esc(lv['banda_sup_c_mas_3atr'])}]</td>"
                f"<td class='num'>{expo_pct}%</td>"
                f"<td class='num'>{_esc(lv['escala_usd_sobre_capital_ref'])} USD "
                f"<span class='small'>(= {expo_pct}% × {_esc(int(lv['capital_ref_usd']))} USD; "
                f"informativo)</span></td></tr>"
            )
        p.append("</table>")
    p.append("</div>")

    # 3) Telemetria watchlist multi-marco (descriptiva)
    p.append(
        "<div class='panel'><h2>3 · Telemetría watchlist 4H·1D·1W</h2>"
        "<div class='small'><b>Telemetría descriptiva de precios — No constituye "
        "hipótesis evaluada ni señal de trading.</b> SMA50 y ATR14 son hechos "
        "matemáticos del precio en cada marco.</div>"
    )
    if telemetry:
        p.append(
            "<table><tr><th>Símbolo</th><th>Precio</th><th>24 h</th><th>Choque activo</th>"
            "<th>4H vs SMA50</th><th>1D vs SMA50</th><th>1W vs SMA50</th>"
            "<th>ATR14 % (4H/1D/1W)</th></tr>"
        )
        shock_syms = {s_["symbol"] for s_ in shocks}
        for sym, row in telemetry.items():

            def _tf(tf: str, _row: dict[str, Any] = row) -> str:
                f = _row.get(tf) or {}
                if not f.get("disponible"):
                    return "<span class='mut'>n/d</span>"
                d = f.get("dist_sma50_pct")
                lado = f.get("lado_sma50", "?")
                signo = "+" if (d or 0) >= 0 else ""
                cls = "pos" if (d or 0) >= 0 else "neg"
                return f"<span class='{cls}'>{_esc(lado)} {signo}{_esc(d)}%</span>"

            choque = (
                "<span class='badge b-bad'>SÍ</span>"
                if sym in shock_syms
                else "<span class='mut'>no</span>"
            )
            atrs = " / ".join(
                str((row.get(tf) or {}).get("atr14_pct", "—")) for tf in ("4h", "1d", "1w")
            )
            precio = (row.get("1d") or {}).get("precio")
            c24 = row.get("cambio_24h_pct")
            cls24 = "pos" if (c24 or 0) >= 0 else "neg"
            p.append(
                f"<tr><td><b>{_esc(sym)}</b></td><td class='num'>{_esc(precio)}</td>"
                f"<td class='num {cls24}'>{_esc(c24)}%</td><td>{choque}</td>"
                f"<td class='small'>{_tf('4h')}</td><td class='small'>{_tf('1d')}</td>"
                f"<td class='small'>{_tf('1w')}</td><td class='num small'>{atrs}</td></tr>"
            )
        p.append("</table>")
    else:
        p.append("<div class='small'>Sin datos de watchlist en esta corrida.</div>")
    p.append("</div>")

    # 5) Evidencia cientifica + sparklines
    p.append("<div class='panel'><h2>5 · Evidencia científica (resumen M0-M3)</h2>")
    p.append(
        "<table><tr><th>Familia</th><th>In-sample 2017-2025</th><th>Holdout 2025-26</th><th>Veredicto final</th></tr>"
    )
    ev = meta.get("evidencia", {})
    for row in ev.get("filas", []):
        p.append("<tr>" + "".join(f"<td class='small'>{_esc(c)}</td>" for c in row) + "</tr>")
    p.append("</table>")
    for sym, closes in spark_data.items():
        p.append(
            f"<div class='small' style='margin-top:8px'>{_esc(sym)} · últimas {len(closes)} velas diarias</div>"
        )
        p.append(_spark(closes))
    p.append(
        "<div class='small' style='margin-top:8px'>Rigor: n_trials=38 registrado en ledger; "
        "DSR/PBO/CPCV/RC; holdout abierto UNA vez (log auditado); potencia de H1 9.5-18.5% "
        "(INCONTRASTABLE por diseño). Informes: reports/M3a_REPORT.md, M3b_REPORT.md.</div>"
    )
    p.append("</div></div>")  # grid

    p.append(
        "<div class='panel' style='margin-top:16px'><h2>6 · Glosario para JP</h2>"
        "<details><summary style='cursor:pointer;color:var(--info)'>Abrir explicaciones "
        "en lenguaje llano</summary><table>"
        "<tr><td><b>SMA50</b></td><td>Media del precio de las últimas 50 velas. "
        "«Por encima/por debajo» dice de qué lado está el precio hoy; la regla H1 "
        "investigada pasa a FLAT cuando el cierre diario cae por debajo.</td></tr>"
        "<tr><td><b>ATR14</b></td><td>Rango típico (alto−bajo) de las últimas 14 velas: "
        "cuánto se mueve el activo por vela. Las cotas close±k×ATR son una regla de rango "
        "estadístico, no niveles mágicos.</td></tr>"
        "<tr><td><b>Exposición de la regla</b></td><td>Fracción de capital que la celda "
        "congelada tendría hoy (0-100 %), tras volatilidad objetivo y banda de 10 pp.</td></tr>"
        "<tr><td><b>Escala teórica</b></td><td>Multiplicación informativa: exposición × tu "
        "capital de referencia. No es una cantidad sugerida.</td></tr>"
        "<tr><td><b>Funding / carry</b></td><td>Pago cada 8 h entre largos y cortos del "
        "perpetuo. H3 cobra ese flujo con posición neutral (spot largo + perp corto); "
        "MA30d anualizada &gt; 5 % = señal activa en la regla congelada.</td></tr>"
        "<tr><td><b>ΔmaxDD vol-matched / p de permutación</b></td><td>Cuánto mejora la "
        "regla el peor bache frente a un rival con tu misma volatilidad, y cuántas veces "
        "tu propio calendario barajado lo iguala (p pequeño = difícil de explicar por azar).</td></tr>"
        "<tr><td><b>DSR / PBO / RC</b></td><td>Exámenes anti-autoengaño: descuentan los "
        "38 intentos registrados, miden la probabilidad de sobreajuste y de que la mejor "
        "celda sea chiripa.</td></tr>"
        "<tr><td><b>INCONTRASTABLE</b></td><td>«La balanza no da para más»: el efecto, si "
        "existe, es menor que lo que estos datos pueden detectar. No significa «malo»; "
        "significa «no demostrado».</td></tr>"
        "<tr><td><b>Cadena de hashes</b></td><td>Cada línea del registro firma a la "
        "anterior: editar historia rompe el sello.</td></tr>"
        "</table></details></div>"
    )
    p.append(
        "<footer>QUANT-ARENA v2 · M4/M5 operativo (alcance conforme ADR-008) · "
        "holdout usado una única vez en M3b · datos: Binance API pública (solo lectura) + RSS públicos · "
        "Este archivo se regenera con <code>qa agent run</code>.</footer></body></html>"
    )
    out = "\n".join(p)
    for bad in PROHIBIDOS:
        if bad in out.upper():
            raise AssertionError(f"lenguaje prohibido en dashboard: {bad}")
    return out
