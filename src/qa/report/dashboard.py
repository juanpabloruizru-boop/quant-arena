# ruff: noqa: E501  (generador de plantilla HTML: lineas largas inevitables)
"""Dashboard autocontenido (M6 Autopilot): HTML+CSS+SVG+JS inline, sin recursos externos.

M6: Agente Autónomo de Paper Trading — toma decisiones, abre/gestiona posiciones
y muestra su razonamiento sin censura. El dashboard refleja las operaciones
reales del agente autónomo sobre una cuenta simulada de $1,000 USD.
"""

from __future__ import annotations

import html
from datetime import UTC, datetime
from typing import Any

CSS = """
:root{--bg:#0d1117;--panel:#161b22;--line:#30363d;--tx:#e6edf3;--mut:#8b949e;
--ok:#2ea043;--warn:#d29922;--bad:#f85149;--info:#58a6ff}
*{box-sizing:border-box}body{margin:0;background:var(--bg);color:var(--tx);
font:14px/1.5 -apple-system,'Segoe UI',Roboto,Helvetica,Arial,sans-serif;padding:18px;
max-width:1400px;margin:0 auto}
h1{font-size:20px;margin:0 0 4px}h2{font-size:15px;margin:0 0 10px;color:var(--info)}
.sub{color:var(--mut);font-size:12px;margin-bottom:16px}
.banner{background:#1a3d2e;border:1px solid var(--ok);border-radius:8px;
padding:10px 14px;margin-bottom:18px;font-size:13px}
.grid{display:grid;grid-template-columns:repeat(auto-fit,minmax(500px,1fr));gap:16px}
.panel{background:var(--panel);border:1px solid var(--line);border-radius:10px;padding:14px 16px}
.full{margin-bottom:16px}
.cards{display:grid;grid-template-columns:repeat(auto-fit,minmax(180px,1fr));gap:10px;margin-bottom:16px}
.card{background:var(--panel);border:1px solid var(--line);border-radius:10px;padding:10px 14px}
.card .k{font-size:10.5px;color:var(--mut);text-transform:uppercase;letter-spacing:.5px}
.card .v{font-size:20px;font-weight:700;font-variant-numeric:tabular-nums;margin-top:2px}
.card .d{font-size:11px;color:var(--mut)}
table{width:100%;border-collapse:collapse;font-size:12.5px;table-layout:fixed}
th{color:var(--mut);text-align:left;font-weight:600;border-bottom:1px solid var(--line);padding:6px 8px}
td{padding:6px 8px;border-bottom:1px solid #21262d;vertical-align:top;word-wrap:break-word;overflow-wrap:anywhere}
.badge{display:inline-block;padding:2px 8px;border-radius:999px;font-size:11px;font-weight:700;white-space:normal}
.b-ok{background:#12331d;color:var(--ok);border:1px solid var(--ok)}
.b-warn{background:#332701;color:var(--warn);border:1px solid var(--warn)}
.b-bad{background:#3d1d1d;color:var(--bad);border:1px solid var(--bad)}
.b-info{background:#0c2d6b33;color:var(--info);border:1px solid var(--info)}
.num{font-variant-numeric:tabular-nums}
.pos{color:var(--ok)}.neg{color:var(--bad)}.mut{color:var(--mut)}
.small{font-size:11.5px;color:var(--mut)}
input,select{background:#0d1117;color:var(--tx);border:1px solid var(--line);border-radius:6px;
padding:5px 8px;font-size:13px;width:130px}
button{background:#21262d;color:var(--tx);border:1px solid var(--line);border-radius:6px;
padding:6px 14px;font-size:13px;font-weight:600;cursor:pointer}
button:hover{border-color:var(--info)}
.calcrow{display:flex;flex-wrap:wrap;gap:10px;align-items:center;margin:8px 0}
.calcrow label{font-size:11.5px;color:var(--mut);display:block}
svg{display:block;margin-top:6px}
footer{margin-top:20px;color:var(--mut);font-size:11.5px}
"""

def _esc(x: Any) -> str:
    return html.escape(str(x))


def _fmt(x: Any, nd: int = 2) -> str:
    """Formatea un número (o '—' si no lo es)."""
    if x is None:
        return "—"
    try:
        return f"{float(x):,.{nd}f}"
    except (TypeError, ValueError):
        return str(x)


def _signed(x: Any, nd: int = 2, suffix: str = "") -> str:
    if x is None:
        return "—"
    try:
        v = float(x)
    except (TypeError, ValueError):
        return str(x)
    cls = "pos" if v >= 0 else "neg"
    return f"<span class='{cls}'>{v:+,.{nd}f}{suffix}</span>"


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


# ── 1. Barra superior: 5 tarjetas de estado de la cuenta ──
def _equity_cards(capital: dict[str, Any] | None) -> list[str]:
    """Barra superior de patrimonio (5 tarjetas contables, M6 Autopilot)."""
    p: list[str] = []
    p.append(
        "<div class='cards'><!-- Barra de Resumen de Cuenta (Autopilot M6) -->"
    )
    if not capital or capital.get("sin_registros"):
        p.append(
            "</div><div class='panel full'><div class='small'>Sin libro de capital todavía: "
            'crea tu contabilidad con <code>qa capital set --amount 1000 --note "Capital '
            'inicial"</code> y registra aportes con <code>qa capital add</code>. El patrimonio '
            "vivo se usa como base de la columna <i>Escala teórica</i> de H1.</div></div>"
        )
        return p

    def card(k: str, v: str, d: str = "") -> str:
        return f"<div class='card'><div class='k'>{k}</div><div class='v num'>{v}</div><div class='d'>{d}</div></div>"

    # Capital inicial/aportado
    cap_inicial = capital.get("capital_inicial", 1000.0)
    p.append(card(
        "Capital Inicial",
        f"{_fmt(cap_inicial)} USD",
        "Base del paper trading simulado"
    ))
    # PnL cerrado neto
    pnl_realizado = capital.get("pnl_realizado_usd", 0.0)
    p.append(card(
        "PnL Cerrado Neto",
        f"{_signed(pnl_realizado)} <span style='font-size:12px'>USD</span>",
        f"{_fmt(capital.get('pnl_realizado_pct_aportado'))} % s/ aportado"
    ))
    # PnL abierto vivo
    pnl_flotante = capital.get("pnl_flotante_usd", 0.0)
    p.append(card(
        "PnL Abierto Vivo",
        f"{_signed(pnl_flotante)} <span style='font-size:12px'>USD</span>",
        "bruto de comisiones (se descuentan al cerrar)"
    ))
    # Patrimonio total
    patrimonio = capital.get("patrimonio_total", cap_inicial)
    p.append(card(
        "Patrimonio Total",
        f"{_fmt(patrimonio)} USD",
        "= aportado + PnL cerrado + PnL abierto · base de la escala teórica"
    ))
    # Heat / riesgo en mesa
    heat_usd = capital.get("portfolio_heat_usd", 0.0)
    heat_pct = capital.get("portfolio_heat_pct_patrimonio", 0.0)
    p.append(card(
        "Riesgo en Mesa",
        f"{_fmt(heat_usd)} USD",
        f"{_fmt(heat_pct)} % del patrimonio si TODOS los SL saltaran hoy a la vez"
    ))
    p.append("</div>")
    return p


# ── 2. Panel 1 unificado: Posiciones Activas + Escáner de Decisión ──
def _panel_operaciones_unificado(
    states: dict[str, Any],
    trades_diag: list[dict[str, Any]],
    capital: dict[str, Any] | None,
) -> list[str]:
    """Panel 1 unificado M6: Posiciones Activas + Escáner de Decisión del Agente."""
    p: list[str] = []
    p.append(
        "<div class='panel'><h2>1 · Posiciones Activas y Decisiones del Agente Autónomo</h2>"
    )
    # Sub-bloque 1A: Posiciones abiertas del agente
    p.append("<h3>1A · Posiciones Abiertas del Agente (para copiar / evaluar en vivo)</h3>")
    p.append(
        "<table><tr><th>Activo</th><th>Dirección y Apalancamiento</th><th>Margen / Tamaño ($)</th>"
        "<th>Riesgo ($ y %)</th><th>Entrada</th><th>Precio Actual</th>"
        "<th>Stop Loss Vigente</th><th>TP1 (Asegurar)</th><th>TP2 (Meta Final)</th>"
        "<th>R:R Neto</th><th>PnL Vivo ($ y %)</th><th>Estado y Decisión del Agente</th></tr>"
    )
    # Filtrar solo operaciones abiertas del agente
    abiertas = [t for t in trades_diag if t.get("status") == "open"] if trades_diag else []
    for t in abiertas[:10]:  # límite de 10 operaciones muestra
        activo = t.get("asset", "?")
        direccion = t.get("kind", "spot")
        leverage = t.get("leverage", "1x")
        margen = t.get("margin_usd", 0.0)
        riesgo = t.get("risk_usd", 0.0)
        entrada = t.get("entry", "?")
        precio_actual = t.get("precio_actual", "?")
        sl = t.get("sl", "?")
        tp1 = t.get("tp1", "?")
        tp2 = t.get("tp2", "?")
        rr = t.get("rr_neto", "?")
        pnl_vivo = t.get("pnl_flotante_usd", 0.0)
        # Estado y decisión del agente
        tp1_hit = t.get("tp1_hit", False)
        if tp1_hit:
            decision = "TP1 Alcanzado ✓ · SL subido a Break-Even/TP1"
        else:
            decision = "Activa — Esperando TP1 o SL"
        p.append(
            f"<tr><td>{_esc(activo)}</td>"
            f"<td>{_esc(f'{direccion} · {leverage}')}</td>"
            f"<td>{_fmt(margen)} / {_fmt(riesgo)} USD</td>"
            f"<td>{_fmt(riesgo)} / {_fmt(riesgo/capital.get('patrimonio_total',1000.0)*100)} %</td>"
            f"<td>{_esc(entrada)}</td>"
            f"<td>{_esc(precio_actual)}</td>"
            f"<td>{_esc(sl)}</td>"
            f"<td>{_esc(tp1)}</td>"
            f"<td>{_esc(tp2)}</td>"
            f"<td>{_fmt(rr)}x</td>"
            f"<td>{_signed(pnl_vivo)} / {_fmt(capital.get('pnl_flotante_pct',0))} %</td>"
            f"<td>{_esc(decision)}</td></tr>"
        )
    if not abiertas:
        p.append("<tr><td colspan='12' class='small mut'>Ninguna operación abierta hoy — el agente está escaneando el mercado.</td></tr>")
    p.append("</table>")
    # Sub-bloque 1B: Escáner de Decisión en Vivo
    p.append("<h3>1B · Escáner de Decisión en Vivo (4H · 1D · 1W)</h3>")
    p.append(
        "<table><tr><th>Activo</th><th>Precio</th><th>Tendencia (4H / 1D / 1W)</th>"
        "<th>Geometría R:R Hoy</th><th>Noticias / Riesgo</th><th>DECISIÓN DEL AGENTE HOY</th></tr>"
    )
    # Universo de 10 monedas + carry H3
    universo = [
        ("BTCUSDT", "BTC"),
        ("ETHUSDT", "ETH"),
        ("SOLUSDT", "SOL"),
        ("BNBUSDT", "BNB"),
        ("XRPUSDT", "XRP"),
        ("ZECUSDT", "ZEC"),
        ("NEARUSDT", "NEAR"),
        ("SUIUSDT", "SUI"),
        ("UNIUSDT", "UNI"),
        ("DOGEUSDT", "DOGE"),
    ]
    # Simulación de decisiones basándose en datos disponibles
    for activo, simbolo in universo:
        # Obtener datos del estado si están disponibles
        price = states.get("prices", {}).get(activo, "?")
        tendencia_4h = states.get("tendencia_4h", {}).get(activo, "neutral")
        tendencia_1d = states.get("tendencia_1d", {}).get(activo, "neutral")
        tendencia_1w = states.get("tendencia_1w", {}).get(activo, "neutral")
        rr_hoje = states.get("rr_hoje", {}).get(activo, "0.88x")
        noticias = states.get("noticias_riesgo", {}).get(activo, "")
        
        # Determinar decisión del agente
        if not rr_hoje or rr_hoje.strip() == "n/d":
            decision = "⚪ DESCARTADA: Datos insuficientes"
            badge_class = "b-warn"
        elif "< 2.0" in rr_hoje:
            decision = "🟡 DESCARTADA: Precio extendido (R:R < 2.0)"
            badge_class = "b-warn"
        elif "bajista" in (tendencia_4h + tendencia_1d + tendencia_1w).lower():
            decision = "🔴 BLOQUEADA: Tendencia 4H/1D no alineada"
            badge_class = "b-bad"
        elif "hack" in (noticias + "").lower() or "exploit" in (noticias + "").lower():
            decision = "🔴 BLOQUEADA: Noticia/Choque adverso"
            badge_class = "b-bad"
        else:
            decision = "🟢 ABIERTA EN CARTERA"
            badge_class = "b-ok"
        
        full_decision = f"{decision}"
        p.append(
            f"<tr><td>{_esc(activo)}</td>"
            f"<td>{_esc(price)}</td>"
            f"<td>{_esc(f'{tendencia_4h} / {tendencia_1d} / {tendencia_1w}')}</td>"
            f"<td>{_esc(rr_hoje)}</td>"
            f"<td>{_esc(noticias[:60] if noticias else '—')}</td>"
            f"<td>{_badge(full_decision)}</td></tr>"
        )
    p.append("</table>")
    p.append("</div>")
    return p


# ── 3. Panel 2: Trade Audit ──
def _audit_panel(audit: dict[str, Any] | None) -> list[str]:
    """Panel 2: Trade Audit — operaciones cerradas + métricas globales."""
    p: list[str] = []
    p.append(
        "<div class='panel'><h2>2 · Trade Audit — Resultados del Agente</h2>"
        "<div class='small'>Historial de todas las operaciones que el agente ha cerrado "
        "(por TP1+TP2, por SL o por cierre anticipado de noticias) con Win Rate %, "
        "Profit Factor, Esperanza en $ y R, y ganancia acumulada.</div>"
    )
    rows = (audit or {}).get("rows") or []
    summ = (audit or {}).get("summary") or {}
    if not rows:
        p.append(
            "<div class='small'>Sin operaciones cerradas registradas. Los cierres se anotan "
            "con <code>qa trade close --id … --exit …</code> y aparecen aquí al regenerar "
            "el dashboard.</div></div>"
        )
        return p
    # Métricas globales
    total_ops = summ.get("total_ops", len(rows))
    win_rate = summ.get("win_rate_pct", 0.0)
    pnl_neto = summ.get("pnl_neto_usd", 0.0)
    pf = summ.get("profit_factor", 0.0)
    esperanza = summ.get("esperanza_usd", 0.0)
    rr_medio = summ.get("rr_medio", 0.0)
    p.append(
        f"<div class='cards'>"
        f"<div class='card'><div class='k'>Total Cerradas</div><div class='v num'>{total_ops}</div></div>"
        f"<div class='card'><div class='k'>Win Rate</div><div class='num'>{_fmt(win_rate)} %</div></div>"
        f"<div class='card'><div class='k'>PnL Neto</div><div class='num'>{_signed(pnl_neto)} USD</div></div>"
        f"<div class='card'><div class='k'>Profit Factor</div><div class='num'>{_fmt(pf)}x</div></div>"
        f"<div class='card'><div class='k'>Esperanza / Op.</div><div class='num'>{_signed(esperanza)} USD</div></div>"
        f"<div class='card'><div class='k'>R:R Medio</div><div class='num'>{_fmt(rr_medio)} R</div></div>"
        f"</div>"
    )
    # Tabla de operaciones
    p.append(
        "<table><tr><th>Cierre</th><th>Activo/Tipo/Marco</th><th>Duración</th>"
        "<th>Entrada</th><th>Salida</th><th>Tamaño</th>"
        "<th>R:R inic. (bruto)</th><th>PnL neto $</th><th>PnL %</th>"
        "<th>R logrado</th><th>Tag</th><th>Nota / Razón Agente</th></tr>"
    )
    for r in rows:
        cierre = r.get("ts_cierre", "?")
        activo = r.get("activo", "?")
        tipo = r.get("tipo", "?")
        marco = r.get("marco", "?")
        entrada = r.get("entrada", "?")
        salida = r.get("salida", "?")
        tamaño = r.get("tamaño", "?")
        rr_inic = r.get("rr_inicial", "?")
        pnl_neto = r.get("pnl_neto_usd", 0.0)
        pnl_pct = r.get("pnl_pct", 0.0)
        r_logrado = r.get("r_logrado", "?")
        tag = r.get("tag", "?")
        nota = r.get("nota", "?")
        p.append(
            f"<tr><td class='small num'>{_esc(str(cierre)[:16])}</td>"
            f"<td>{_esc(f'{activo} / {tipo} / {marco}')}</td>"
            f"<td>{_esc('')}</td>"
            f"<td>{_esc(entrada)}</td>"
            f"<td>{_esc(salida)}</td>"
            f"<td>{_esc(tamaño)}</td>"
            f"<td>{_fmt(rr_inic)}x</td>"
            f"<td>{_signed(pnl_neto)} USD</td>"
            f"<td>{_fmt(pnl_pct)} %</td>"
            f"<td>{_fmt(r_logrado)} R</td>"
            f"<td>{_esc(tag)}</td>"
            f"<td>{_esc(nota)}</td></tr>"
        )
    p.append("</table>")
    p.append("</div>")
    return p


# ── 4. Panel 3: Radar de noticias ──
def _noticias_panel(news: list[dict[str, Any]], shocks: list[dict[str, Any]]) -> list[str]:
    """Panel 3: Radar de noticias y eventos utilizados por el agente."""
    p: list[str] = []
    p.append(
        "<div class='panel'><h2>3 · Radar de Noticias y Eventos del Agente</h2>"
        "<div class='small'>RSS 72h + eventos críticos que el agente Autónomo está monitoreando. "
        "Glosario plegable abajo.</div>"
    )
    # Noticias recientes
    p.append("<h3>Noticias Recientes (últimas 72h)</h3>")
    if news:
        p.append("<ul>")
        for n in news[:10]:  # límite de 10 noticias
            title = n.get("title", "Sin título")
            keywords = n.get("keywords", [])
            source = n.get("source", "")
            fecha = n.get("published", "")
            # Determinar tipo de noticia
            tipo = "informativa"
            if any(k in (title + " ").lower() for k in ["hack", "exploit", "delist", "insolvency", "ban", "sec"]):
                tipo = "riesgo"
            elif any(k in (title + " ").lower() for k in ["upgrade", "adoption", "lista", "parche"]):
                tipo = "positiva"
            p.append(
                f'<li><span class="badge {["b-bad","b-ok","b-info"][["hack","exploit","upgrade","adoption"].index(tipo) if tipo in ["hack","exploit","upgrade","adoption"] else 2]}">'
                f'{_esc(tipo).upper()}</span> {_esc(title[:80])}'
            )
        p.append("</ul>")
    else:
        p.append("<p class='small'>Sin noticias nuevas en las últimas 72h.</p>")
    # Choques técnicos
    p.append("<h3>Choques Técnicos Activos</h3>")
    if shocks:
        p.append("<ul>")
        for s in shocks[:5]:
            sym = s.get("symbol", "?")
            tipo = s.get("tipo", "?")
            detalle = s.get("detalle", "")
            p.append(f'<li><b>{_esc(sym)}</b>: {_esc(detalle[:60] if detalle else "—")}</li>')
        p.append("</ul>")
    else:
        p.append("<p class='small'>No hay choques técnicos activos.</p>")
    # Glosario plegable (simplificado)
    p.append(
        "<details><summary>Glosario de Eventos (<b>▶</b> hacer clic)</summary>"
        "<p><b>hack</b>: vulnerabilidad o ataque a protocolo/Exchange</p>"
        "<p><b>exploit</b>: código que aprovecha vulnerabilidad</p>"
        "<p><b>delist</b>: eliminación de par de trading</p>"
        "<p><b>insolvency</b>: situación de insolvencia del emisor</p>"
        "<p><b>ban</b>: restricción regulatoria o prohibición</p>"
        "<p><b>sec</b>: investigación o acción de la SEC</p>"
        "</details>"
    )
    p.append("</div>")
    return p


# ── 5. Render principal ──
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
    capital: dict[str, Any] | None = None,
    audit: dict[str, Any] | None = None,
    calc: dict[str, Any] | None = None,
) -> str:
    now = datetime.now(UTC).strftime("%Y-%m-%d %H:%M UTC")
    p: list[str] = []
    p.append("<!DOCTYPE html><html lang='es'><head><meta charset='utf-8'>")
    p.append("<meta name='viewport' content='width=device-width,initial-scale=1'>")
    p.append(
        f"<title>QUANT-ARENA v2 · Centro de mando (estado, no consejo)</title><style>{CSS}</style></head><body>"
    )
    p.append("<h1>QUANT-ARENA v2 · Centro de mando</h1>")
    p.append(
        f"<div class='sub'>Generado: {now} · datos vivos: {_esc(states.get('fetched_at_utc', '?'))} · "
        f"git {_esc(str(meta.get('git_sha', '?'))[:7])} · herramienta de investigación, "
        "<b>no es asesoramiento de inversión</b></div>"
    )
    # Barra superior: 5 tarjetas de estado de la cuenta
    p.extend(_equity_cards(capital))
    # Panel 1 unificado: Posiciones Activas + Escáner de Decisión
    p.extend(_panel_operaciones_unificado(states, trades_diag, capital))
    # Panel 2: Trade Audit
    p.extend(_audit_panel(audit))
    # Panel 3: Radar de noticias
    p.extend(_noticias_panel(news, shocks))
    # Footer
    p.append(
        "<footer>QUANT-ARENA v2 · M6 Autopilot — Agente de Paper Trading sobre $1,000 USD · "
        "datos: Binance API pública (solo lectura) + RSS públicos · "
        "Este archivo se regenera con <code>qa agent run</code>.</footer>"
    )
    out = "\n".join(p)
    return out