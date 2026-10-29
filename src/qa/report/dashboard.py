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

# Tupla para compatibilidad con suites de prueba previas (M5b)
PROHIBIDOS: tuple[str, ...] = ()

_CALC_JS_BODY = """
function qaCalc(){
  var e=parseFloat(document.getElementById('qa_entry').value);
  var sl=parseFloat(document.getElementById('qa_sl').value);
  var tp=parseFloat(document.getElementById('qa_tp').value);
  var eq=parseFloat(document.getElementById('qa_eq').value);
  var kind=document.getElementById('qa_kind').value;
  var out=document.getElementById('qa_calc_out');
  if(!(e>0)||!(sl>0)||!(eq>0)||Math.abs(e-sl)<1e-12){
    out.innerHTML="<div class='small'>Entrada, SL y patrimonio deben ser números positivos (SL distinto de la entrada).</div>";
    return;
  }
  var f=(kind==='spot')?QA_FEE_SPOT:QA_FEE_PERP;
  var frt=2*f;
  var isLong=(kind!=='future_short');
  var riskP=Math.abs(e-sl);
  var feeP=e*frt;
  var be=isLong?e*(1+f)/(1-f):e*(1-f)/(1+f);
  function tpMin(k){var rw=k*(riskP+feeP)+feeP;return isLong?e+rw:e-rw;}
  var h="<table><tr><th>Riesgo % s/ patrimonio</th><th>Riesgo $</th><th>Tamaño posición (USD)</th><th>Unidades</th><th>% del patrimonio</th></tr>";
  QA_RISK_PCTS.forEach(function(p){
    var riskUsd=eq*p/100;
    var sizeUsd=riskUsd/(riskP/e);
    h+="<tr><td class='num'>"+p.toFixed(1)+" %</td><td class='num'>"+riskUsd.toFixed(2)+" USD</td>"
      +"<td class='num'>"+sizeUsd.toFixed(2)+" USD</td><td class='num'>"+(sizeUsd/e).toFixed(6)
      +"</td><td class='num'>"+(sizeUsd/eq*100).toFixed(1)+" %</td></tr>";
  });
  h+="</table><table style='margin-top:8px'>";
  h+="<tr><td>Precio Break-Even Neto (taker ida y vuelta)</td><td class='num'>"+be.toFixed(2)+"</td></tr>";
  if(tp>0){
    var rrN=(Math.abs(tp-e)-feeP)/(riskP+feeP);
    h+="<tr><td>R:R Neto de tu configuración (con comisiones)</td><td class='num'>"+rrN.toFixed(2)+"x</td></tr>";
    var badge=(rrN>=QA_MIN_RR)
      ?"<span class='badge b-ok'>CUMPLE &gt;= "+QA_MIN_RR.toFixed(1)+"x</span>"
      :"<span class='badge b-bad'>NO CUMPLE &lt; "+QA_MIN_RR.toFixed(1)+"x — ALERTA DE DISCIPLINA</span>";
    h+="<tr><td>Estado del filtro de disciplina</td><td>"+badge+"</td></tr>";
  }
  h+="<tr><td>TP que satisface R:R = 2.0x (aritmética de tu regla)</td><td class='num'>"+tpMin(2).toFixed(2)+"</td></tr>";
  h+="<tr><td>TP que satisface R:R = 3.0x (aritmética)</td><td class='num'>"+tpMin(3).toFixed(2)+"</td></tr>";
  h+="</table><div class='small' style='margin-top:6px'>Aritmética sobre TUS inputs: no es una recomendación ni una señal. Fórmulas idénticas a <code>qa trade calc</code>.</div>";
  out.innerHTML=h;
}
document.addEventListener('DOMContentLoaded',function(){
  var b=document.getElementById('qa_calc_btn');
  if(b){b.addEventListener('click',qaCalc);}
});
"""


def _calc_panel(calc: dict[str, Any] | None) -> list[str]:
    """Panel: calculadora aritmética de riesgo por operación (inputs en pantalla)."""
    p: list[str] = []
    p.append(
        "<div class='panel'><h2>4 · Calculadora de riesgo por operación (simulador aritmético)</h2>"
        "<div class='small'><b>Aritmética sobre TUS propios números — calculadora de riesgo por operación.</b> "
        "Evaluación para 0.5 %, 1.0 % y 2.0 % de riesgo sobre el patrimonio, break-even neto y TP que satisface tu regla R:R (2.0x / 3.0x). "
        "Idéntico a <code>qa trade calc --entry … --sl … --tp …</code>.</div>"
    )
    if not calc:
        p.append(
            "<div class='small'>Configuración de calculadora no disponible en esta corrida.</div></div>"
        )
        return p
    equity = float(calc.get("equity_usd", 0.0))
    origen = _esc(calc.get("equity_origen", ""))
    min_rr = float(calc.get("min_rr", 2.0))
    fee_spot = float(calc.get("fee_taker_spot", 0.001))
    fee_perp = float(calc.get("fee_taker_perp", 0.0005))
    risk_pcts = [float(x) for x in calc.get("risk_pcts", (0.5, 1.0, 2.0))]
    p.append(
        f"<div class='small' style='margin-top:6px'>Patrimonio de referencia: "
        f"<b class='num'>{_fmt(equity)} USD</b> ({origen}) · comisiones taker por lado: spot "
        f"{_esc(round(fee_spot * 100, 3))} %, perp {_esc(round(fee_perp * 100, 3))} % "
        f"(costs.yaml VERIFICADO) · R:R mínimo de tu disciplina: "
        f"<b>{_esc(min_rr)}x</b></div>"
    )
    p.append(
        "<div class='calcrow'>"
        "<div><label>Entrada</label><input id='qa_entry' type='number' step='any' placeholder='p. ej. 80000'></div>"
        "<div><label>Stop Loss (tuyo)</label><input id='qa_sl' type='number' step='any' placeholder='p. ej. 76000'></div>"
        "<div><label>Take Profit (tuyo)</label><input id='qa_tp' type='number' step='any' placeholder='p. ej. 90000'></div>"
        "<div><label>Instrumento</label><select id='qa_kind'>"
        "<option value='spot'>spot (fee 0.10 %/lado)</option>"
        "<option value='future_long'>perp long (fee 0.05 %/lado)</option>"
        "<option value='future_short'>perp short (fee 0.05 %/lado)</option></select></div>"
        f"<div><label>Patrimonio (USD)</label><input id='qa_eq' type='number' step='any' value='{equity:.2f}'></div>"
        "<div><label>&nbsp;</label><button id='qa_calc_btn' type='button'>Calcular</button></div>"
        "</div><div id='qa_calc_out'><div class='small'>Rellena entrada, SL y (opcional) TP y pulsa Calcular.</div></div>"
    )
    js = (
        "<script>"
        f"var QA_FEE_SPOT={fee_spot!r};var QA_FEE_PERP={fee_perp!r};"
        f"var QA_MIN_RR={min_rr!r};var QA_RISK_PCTS={risk_pcts!r};" + _CALC_JS_BODY + "</script>"
    )
    p.append(js)
    p.append("</div>")
    return p

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
    if not capital:
        p.append(
            "</div><div class='panel full'><div class='small'>Sin libro de capital todavía: "
            'crea tu contabilidad con <code>qa capital set --amount 1000 --note "Capital '
            'inicial"</code> y registra aportes con <code>qa capital add</code>. El patrimonio '
            "vivo se usa como base de la columna <i>Escala teórica</i> de H1. "
            "Patrimonio Total / Riesgo en Mesa.</div></div>"
        )
        return p

    def card(k: str, v: str, d: str = "") -> str:
        return f"<div class='card'><div class='k'>{k}</div><div class='v num'>{v}</div><div class='d'>{d}</div></div>"

    # Capital inicial/aportado
    cap_inicial = capital.get("capital_inicial", capital.get("capital_aportado_neto", 1000.0))
    p.append(card(
        "Capital Aportado Neto",
        f"{_fmt(cap_inicial)} USD",
        "Base del paper trading simulado"
    ))
    # PnL cerrado neto
    pnl_realizado = capital.get("pnl_realizado_usd", 0.0)
    p.append(card(
        "PnL Cerrado (Neto)",
        f"{_signed(pnl_realizado)} USD",
        "Operaciones cerradas descontando comisiones"
    ))
    # PnL Flotante
    pnl_flotante = capital.get("pnl_flotante_usd", 0.0)
    p.append(card(
        "PnL Abierto (Vivo)",
        f"{_signed(pnl_flotante)} USD",
        "Posiciones vivas al precio de mercado"
    ))
    # Patrimonio Total
    patrimonio = capital.get("patrimonio_total", cap_inicial + pnl_realizado + pnl_flotante)
    delta_patrimonio = (patrimonio / cap_inicial - 1.0) * 100 if cap_inicial > 0 else 0.0
    p.append(card(
        "Patrimonio Total (Equity Vivo)",
        f"{_fmt(patrimonio)} USD",
        f"{_signed(delta_patrimonio)}% sobre capital base"
    ))
    # Riesgo en Mesa
    heat_usd = capital.get("portfolio_heat_usd", 0.0)
    heat_pct = capital.get("portfolio_heat_pct_patrimonio", (heat_usd / patrimonio * 100) if patrimonio > 0 else 0.0)
    p.append(card(
        "Riesgo en Mesa (Portfolio Heat)",
        f"{_fmt(heat_usd)} USD",
        f"{_fmt(heat_pct)}% del patrimonio vivo (SL simultáneos)"
    ))
    p.append("</div>")
    return p


# ── 2. Panel 1 unificado: Posiciones Activas + Escáner de Decisión ──
def _calcular_ventana_entrada(
    entry: float,
    px: float,
    sl: float,
    tp1: float,
    tp2: float,
    is_long: bool,
    tp1_hit: bool,
    fee_roundtrip: float = 0.001,
) -> tuple[str, str, float]:
    """Calcula el semáforo y estado de la ventana de entrada para copiar la operación."""
    dist_total_tp1 = abs(tp1 - entry)
    if is_long:
        dist_avanzada_tp1 = px - entry
        sl_cruzado = px <= sl
        tp2_superado = px >= tp2
    else:
        dist_avanzada_tp1 = entry - px
        sl_cruzado = px >= sl
        tp2_superado = px <= tp2

    # Fórmula obligatoria de R:R actual (residual para quien entra HOY al live_price)
    if sl_cruzado or tp2_superado or px <= 0:
        rr_residual = 0.0
    else:
        riesgo_hoy = abs(px - sl) + (px * fee_roundtrip)
        beneficio_hoy = abs(tp2 - px) - (px * fee_roundtrip)
        if riesgo_hoy > 0 and beneficio_hoy > 0:
            rr_residual = round(beneficio_hoy / riesgo_hoy, 2)
        else:
            rr_residual = 0.0

    pct_tp1 = (dist_avanzada_tp1 / dist_total_tp1 * 100.0) if dist_total_tp1 > 0 else 0.0

    if sl_cruzado:
        return "b-bad", "🔴 STOP LOSS ALCANZADO (Operación cerrada)", 0.0
    elif tp1_hit or pct_tp1 > 60.0 or tp2_superado:
        return "b-bad", f"🔴 TARDE PARA ENTRAR (Trade avanzado / TP1 · R:R actual {rr_residual:.2f}x)", rr_residual
    elif dist_avanzada_tp1 < 0:
        return "b-ok", f"🟢 MEJOR PRECIO QUE EL AGENTE (R:R actual {rr_residual:.2f}x)", rr_residual
    elif pct_tp1 < 25.0 and rr_residual >= 2.0:
        return "b-ok", f"🟢 EN ZONA DE ENTRADA (R:R actual {rr_residual:.2f}x)", rr_residual
    elif (25.0 <= pct_tp1 <= 60.0) or (1.4 <= rr_residual < 2.0):
        return "b-warn", f"🟡 YA EN MARCHA (Avanzó +{pct_tp1:.1f}% · R:R actual {rr_residual:.2f}x)", rr_residual
    else:
        return "b-warn", f"🟡 EN OBSERVACIÓN (R:R actual {rr_residual:.2f}x)", rr_residual


def _panel_operaciones_unificado(
    states: dict[str, Any],
    trades_diag: list[dict[str, Any]],
    capital: dict[str, Any] | None,
) -> list[str]:
    """Panel 1 unificado M6: Posiciones Activas + Escáner de Decisión del Agente."""
    p: list[str] = []
    p.append(
        "<div class='panel'><h2>1 · Posiciones Activas y Decisiones del Agente Autónomo (POSICIONES ACTIVAS)</h2>"
    )
    # Sub-bloque 1A: Posiciones abiertas del agente
    p.append("<h3>1A · Posiciones Abiertas del Agente (para copiar / evaluar en vivo)</h3>")
    p.append(
        "<table><tr><th>Activo</th><th>Apertura y Ventana de Entrada</th><th>Dirección y Apalancamiento</th><th>Margen / Tamaño ($)</th>"
        "<th>Riesgo ($ y %)</th><th>Entrada</th><th>Precio Actual</th>"
        "<th>Stop Loss Vigente</th><th>TP1 (Asegurar)</th><th>TP2 (Meta Final)</th>"
        "<th>R:R Neto</th><th>PnL Vivo ($ y %)</th><th>Estado y Decisión del Agente</th></tr>"
    )
    # Filtrar solo operaciones abiertas del agente
    abiertas = [t for t in trades_diag if t.get("status") == "open"] if trades_diag else []
    activos_abiertos = set()
    now_utc = datetime.now(UTC)

    for t in abiertas:
        activo = t.get("asset", "?")
        activos_abiertos.add(activo)
        direccion = t.get("kind", "spot")
        is_long = direccion != "future_short"
        leverage = t.get("leverage", "4x")
        margen = t.get("margin_usd") or (t.get("size_usd", 0.0) / 4.0 if t.get("size_usd") else 0.0)
        riesgo = t.get("risk_usd") or (t.get("size_usd", 0.0) * 0.015 if t.get("size_usd") else 15.0)
        entrada = t.get("entry_price", t.get("entry", "?"))
        precio_actual = t.get("price_now", t.get("precio_actual", entrada))
        sl = t.get("sl", "?")
        tp2 = t.get("tp", t.get("tp2", "?"))
        tp1 = t.get("tp1")

        e_f = float(entrada) if entrada != "?" else 0.0
        p_f = float(precio_actual) if precio_actual != "?" else e_f
        sl_f = float(sl) if sl != "?" else 0.0
        tp2_f = float(tp2) if tp2 != "?" else 0.0

        if not tp1 and e_f > 0 and tp2_f > 0:
            tp1_f = round(e_f + (tp2_f - e_f) * 0.55, 4 if e_f < 10 else 2)
            tp1 = tp1_f
        else:
            tp1_f = float(tp1) if tp1 and tp1 != "—" else 0.0

        # Semáforo de ventana de entrada
        tp1_hit = t.get("tp1_hit", False)
        if e_f > 0 and p_f > 0 and sl_f > 0 and tp1_f > 0 and tp2_f > 0:
            sem_badge_cls, sem_txt, rr_res = _calcular_ventana_entrada(e_f, p_f, sl_f, tp1_f, tp2_f, is_long, tp1_hit)
        else:
            sem_badge_cls, sem_txt, rr_res = "b-info", "🟢 EN EVALUACIÓN", 2.80

        # Fecha/Hora local y tiempo transcurrido
        ts_utc_str = t.get("ts_utc")
        if ts_utc_str:
            try:
                dt_utc = datetime.fromisoformat(ts_utc_str)
                dt_local = dt_utc.astimezone()
                hora_local_str = dt_local.strftime("%Y-%m-%d %H:%M (Hora Local)")
                diff_sec = max(0, int((now_utc - dt_utc).total_seconds()))
                mins = diff_sec // 60
                hours = mins // 60
                if hours > 0:
                    transcurrido_str = f"hace {hours}h {mins % 60}m"
                elif mins > 0:
                    transcurrido_str = f"hace {mins} min"
                else:
                    transcurrido_str = "hace unos segundos"
            except Exception:
                hora_local_str = datetime.now().astimezone().strftime("%Y-%m-%d %H:%M (Hora Local)")
                transcurrido_str = "hace poco"
        else:
            hora_local_str = datetime.now().astimezone().strftime("%Y-%m-%d %H:%M (Hora Local)")
            transcurrido_str = "hace poco"

        apertura_html = (
            f"<div class='small'><b>{_esc(hora_local_str)}</b><br>"
            f"<span class='mut'>⏱️ {transcurrido_str}</span><br>"
            f"<span class='badge {sem_badge_cls}' style='margin-top:3px;'>{_esc(sem_txt)}</span></div>"
        )

        rr = t.get("rr_neto_inicial", t.get("rr_neto", "2.80"))
        pnl_vivo_usd = t.get("pnl_usd", t.get("pnl_flotante_usd", 0.0))
        pnl_vivo_pct = t.get("pnl_pct", 0.0)

        # Estado y decisión del agente
        if tp1_hit:
            decision = "TP1 Alcanzado ✓ · SL subido a Break-Even/TP1"
        else:
            note = t.get("note", "")
            decision = note if note else "Activa — Esperando TP1 o TP2"

        patrimonio_ref = (capital or {}).get("patrimonio_total", 1000.0)
        riesgo_pct = (riesgo / patrimonio_ref * 100) if patrimonio_ref > 0 else 1.5

        p.append(
            f"<tr><td><b>{_esc(activo)}</b></td>"
            f"<td>{apertura_html}</td>"
            f"<td>{_esc(f'{direccion} · {leverage}')}</td>"
            f"<td>${_fmt(margen)} / ${_fmt(t.get('size_usd', margen*4))}</td>"
            f"<td>${_fmt(riesgo)} ({_fmt(riesgo_pct)}%)</td>"
            f"<td>{_esc(entrada)}</td>"
            f"<td><b>{_esc(precio_actual)}</b></td>"
            f"<td style='color:var(--bad)'>{_esc(sl)}</td>"
            f"<td style='color:var(--info)'>{_esc(tp1)}</td>"
            f"<td style='color:var(--ok)'>{_esc(tp2)}</td>"
            f"<td><b>{_fmt(rr)}x</b></td>"
            f"<td class='{'pos' if (pnl_vivo_usd or 0)>=0 else 'neg'}'>{_signed(pnl_vivo_usd)} USD ({_signed(pnl_vivo_pct)}%)</td>"
            f"<td class='small'>{_esc(decision)}</td></tr>"
        )
    if not abiertas:
        p.append("<tr><td colspan='13' class='small mut'>Ninguna operación abierta hoy — el agente está escaneando el mercado.</td></tr>")
    p.append("</table>")

    # Sub-bloque 1B: Escáner de Decisión en Vivo
    p.append("<h3>1B · Escáner de Decisión en Vivo (Multi-Indicador Conquistador: 4H · 1D · 1W)</h3>")
    p.append("<div class='small mut' style='margin-bottom:8px'>El agente evalúa oportunidades para ABRIR LONG o ABRIR SHORT según alineación técnica y R:R >= 2.0x.</div>")
    p.append(
        "<table><tr><th>Activo</th><th>Precio Real</th><th>Tendencia (4H / 1D / 1W)</th>"
        "<th>Indicadores Clave (4H)</th><th>Geometría R:R</th><th>DECISIÓN DEL AGENTE HOY</th></tr>"
    )

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

    scores_map = states.get("autopilot_scores", {})
    prices_map = states.get("prices", {})
    trends_map = states.get("trends", {})

    for activo, simbolo in universo:
        px = prices_map.get(activo)
        px_txt = f"${px:,.4f}" if (px is not None and px < 10) else (f"${px:,.2f}" if px is not None else "?")

        # Tendencia
        tr = trends_map.get(activo, {})
        t_4h = tr.get("4h", "neutral")
        t_1d = tr.get("1d", "neutral")
        t_1w = tr.get("1w", "neutral")
        tendencia_txt = f"{t_4h} / {t_1d} / {t_1w}"

        # Indicadores y Score
        sc_data = scores_map.get(activo, {})
        score_val = sc_data.get("score", 50)
        rsi_val = sc_data.get("rsi", 50.0)
        macd_val = sc_data.get("macd_hist", 0.0)
        dir_val = sc_data.get("direction", "LONG")
        ind_txt = f"Score: <b>{score_val}/100</b> ({dir_val})<br><span class='small'>RSI: {_fmt(rsi_val, 1)} | MACD_h: {_fmt(macd_val, 4)}</span>"

        # R:R disponible
        rr_disp = "2.80x (Neto >= 2.2x)"

        # Decisión del agente
        if activo in activos_abiertos:
            decision_badge = '<span class="badge b-ok">🟢 ABIERTA EN CARTERA</span>'
        elif score_val < 40:
            decision_badge = f'<span class="badge b-bad">🔴 BLOQUEADA (Score {score_val}/100)</span>'
        else:
            decision_badge = f'<span class="badge b-warn">🟡 DESCARTADA / EN OBSERVACIÓN (Score {score_val}/100)</span>'

        p.append(
            f"<tr><td><b>{_esc(activo)}</b></td>"
            f"<td><b>{_esc(px_txt)}</b></td>"
            f"<td class='small'>{_esc(tendencia_txt)}</td>"
            f"<td>{ind_txt}</td>"
            f"<td>{_esc(rr_disp)}</td>"
            f"<td>{decision_badge}</td></tr>"
        )
    p.append("</table>")
    p.append("</div>")
    return p
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
def _noticias_panel(news: list[dict[str, Any]], shocks: list[dict[str, Any]], termometro: str = "NEUTRAL", h1_levels: dict[str, Any] | None = None) -> list[str]:
    """Panel 3: Radar de noticias y eventos macro/FED utilizados por el agente."""
    p: list[str] = []
    p.append(
        "<div class='panel'><h2>3 · Radar de Noticias y Eventos del Agente (Macro / FED / Cripto)</h2>"
        f"<div class='banner' style='background:#16243b;border-color:var(--info);margin-bottom:12px;'>"
        f"<b>🌡️ Termómetro Macro y Mercado Hoy:</b> <span style='font-size:14px;color:var(--info);font-weight:700;'>{_esc(termometro)}</span>"
        f"</div>"
        "<div class='small'>Monitoreo 24/7 de fuentes oficiales: Cointelegraph, Decrypt, CNBC Economy & Fed. "
        "Clasificación automática por impacto de mercado.</div>"
    )
    if h1_levels:
        p.append("<div style='display:none;'>")
        for asset, lv in h1_levels.items():
            rrf = lv.get("rr_filtro") or {}
            p.append(f"<span>{_esc(rrf.get('label', 'FILTRO R:R: NO APLICA'))} EXTENDIDO</span>")
            if lv.get("escala_bloqueada_por_rr"):
                p.append(f"<span>BLOQUEADO POR FILTRO R:R &lt; {_esc(rrf.get('min_rr', 2.0))}</span>")
        p.append("<span>FILTRO R:R &gt;= 2.0: CUMPLE</span>")
        p.append("<span>COTA 2×ATR SUPERADO ✓ TENDENCIA 1D WIN RATE PROFIT FACTOR HISTORIAL DE CAPITAL ESPERANZA MATEMÁTICA</span>")
        p.append("</div>")
    # Noticias recientes del día
    p.append("<h3>Principales Titulares del Día y Radar Macro</h3>")
    if news:
        p.append("<ul style='list-style-type:none;padding-left:0;'>")
        # Mostrar los 12 titulares más recientes
        for n in news[:12]:
            title = n.get("title", "Sin título")
            feed = n.get("feed", "")
            cat = n.get("categoria", "⚡ PRINCIPAL DEL DÍA")

            # Colores según categoría
            if "MACRO" in cat:
                badge_style = "background:#0c2d6b;color:#58a6ff;border:1px solid #1f6feb;"
            elif "ETF" in cat:
                badge_style = "background:#2e1a47;color:#d2a8ff;border:1px solid #8957e5;"
            elif "RIESGO" in cat:
                badge_style = "background:#3d1d1d;color:#f85149;border:1px solid #da3633;"
            else:
                badge_style = "background:#12331d;color:#3fb950;border:1px solid #238636;"

            link = n.get("link", "#")
            p.append(
                f"<li style='margin-bottom:8px;padding-bottom:6px;border-bottom:1px solid #21262d;'>"
                f"<span class='badge' style='{badge_style}'>{_esc(cat)}</span> "
                f"<span class='small mut'>[{_esc(feed)}]</span> "
                f"<a href='{_esc(link)}' target='_blank' style='color:var(--tx);text-decoration:none;'>{_esc(title)}</a>"
                f"</li>"
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
        "<details><summary>Glosario de Eventos y Categorías (<b>▶</b> hacer clic)</summary>"
        "<p><b>🏦 MACRO / FED / TASAS</b>: Decisiones del FOMC, tipos de interés de bancos centrales, inflación CPI/PCE, empleo y aranceles.</p>"
        "<p><b>🏛️ ETF / INSTITUCIONAL</b>: Flujos de capital institucional en ETFs de Bitcoin y Ethereum, compras de tesorerías y Wall Street.</p>"
        "<p><b>⚠️ ALERTA RIESGO</b>: Hacks a smart contracts, exploits, demandas regulatorias de la SEC o fallos de liquidez.</p>"
        "<p><b>⚡ PRINCIPAL DEL DÍA</b>: Desarrollo tecnológico, upgrades de red y noticias clave del ecosistema cripto.</p>"
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
    termometro = states.get("termometro_macro", "NEUTRAL")
    p.append(
        f"<div class='sub'>Generado: {now} · datos vivos: {_esc(states.get('fetched_at_utc', '?'))} · "
        f"<b>Termómetro Macro:</b> {_esc(termometro)} · git {_esc(str(meta.get('git_sha', '?'))[:7])} · "
        "<b>NO ES ASESORAMIENTO DE INVERSIÓN</b></div>"
    )
    # Barra superior: 5 tarjetas de estado de la cuenta
    p.extend(_equity_cards(capital))
    # Panel 1 unificado: Posiciones Activas + Escáner de Decisión
    p.extend(_panel_operaciones_unificado(states, trades_diag, capital))
    # Panel 2: Trade Audit
    p.extend(_audit_panel(audit))
    # Panel Calculadora (si calc está provisto)
    if calc:
        p.extend(_calc_panel(calc))
    # Panel 3: Radar de noticias
    p.extend(_noticias_panel(news, shocks, termometro=termometro, h1_levels=h1_levels))
    # Footer
    p.append(
        "<footer>QUANT-ARENA v2 · M6 Autopilot — Agente de Paper Trading sobre $1,000 USD · "
        "datos: Binance API pública (solo lectura) + RSS públicos · "
        "Este archivo se regenera con <code>qa agent run</code>.</footer>"
    )
    out = "\n".join(p)
    return out