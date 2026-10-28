# ruff: noqa: E501  (generador de plantilla HTML: lineas largas inevitables)
"""Dashboard autocontenido (M5 operativo + M5b): HTML+CSS+SVG+JS inline, sin recursos externos.

REGLA DE LENGUAJE (test obligatorio test_dashboard_language_guard):
- Ningun imperativo de trading (comprar/vender/cerrar/subir stop/reducir).
- Cada regla lleva su etiqueta de veredicto del preregistro.
- H1/H2 muestran SIEMPRE "SIN VENTAJA DEMOSTRADA"; H3-BTC muestra su PASA con
  la caveat de costes x2; H3-ETH muestra NO PASA.
El dashboard es un espejo de estados + contabilidad del usuario, no un asesor.

M5b (ADR-008 addendum B): contabilidad de capital del usuario (equity vivo,
portfolio heat), filtro de disciplina R:R >= min_rr (geometría observable
SMA50/ATR14 + comisiones de costs.yaml), calculadora ARITMÉTICA de riesgo por
operación y Trade Audit del historial cerrado. Todo son hechos matemáticos
sobre los niveles y registros del PROPIO usuario: no hay niveles sugeridos.
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
.full{margin-bottom:16px}
.cards{display:grid;grid-template-columns:repeat(auto-fit,minmax(180px,1fr));gap:10px;margin-bottom:16px}
.card{background:var(--panel);border:1px solid var(--line);border-radius:10px;padding:10px 14px}
.card .k{font-size:10.5px;color:var(--mut);text-transform:uppercase;letter-spacing:.5px}
.card .v{font-size:20px;font-weight:700;font-variant-numeric:tabular-nums;margin-top:2px}
.card .d{font-size:11px;color:var(--mut)}
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

# Cuerpo JS de la calculadora (vanilla, sin dependencias externas). Las
# constantes (comisiones taker, R:R mínimo, filas de riesgo) se inyectan
# desde Python al renderizar: una única fuente de verdad (costs.yaml /
# config/watchlist.yaml). Mismas fórmulas que `qa trade calc`.
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


def _equity_cards(capital: dict[str, Any] | None) -> list[str]:
    """Barra superior de patrimonio (5 tarjetas contables, M5b)."""
    p: list[str] = []
    p.append(
        "<div class='cards'><!-- Barra de Resumen de Cuenta (contabilidad del usuario, M5b) -->"
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

    p.append(
        card(
            "Capital Aportado Neto",
            f"{_fmt(capital['capital_aportado_neto'])} USD",
            "inicial + adiciones − retiros",
        )
    )
    p.append(
        card(
            "PnL Cerrado (Neto)",
            f"{_signed(capital['pnl_realizado_usd'])} <span style='font-size:12px'>USD</span>",
            f"{_fmt(capital.get('pnl_realizado_pct_aportado'))} % s/ aportado · comisiones est. "
            f"{_fmt(capital.get('comisiones_cerradas_est_usd'))} USD ya descontadas",
        )
    )
    p.append(
        card(
            "PnL Abierto (Vivo)",
            f"{_signed(capital['pnl_flotante_usd'])} <span style='font-size:12px'>USD</span>",
            "bruto de comisiones (se descuentan al cerrar) · precios públicos en vivo",
        )
    )
    p.append(
        card(
            "Patrimonio Total (Equity Vivo)",
            f"{_fmt(capital['patrimonio_total'])} USD",
            "= aportado + PnL cerrado + PnL abierto · base de la escala teórica",
        )
    )
    heat_pct = capital.get("portfolio_heat_pct_patrimonio")
    heat_d = (
        f"{_fmt(heat_pct)} % del patrimonio si TODOS los SL saltaran hoy a la vez"
        if heat_pct is not None
        else "si todos los SL saltaran hoy a la vez"
    )
    sin_sl = capital.get("abiertas_sin_sl") or []
    if sin_sl:
        heat_d += f" · ⚠ sin SL (no computable): {_esc(', '.join(sin_sl))}"
    p.append(
        card(
            "Riesgo en Mesa (Portfolio Heat)",
            f"{_fmt(capital['portfolio_heat_usd'])} USD",
            heat_d,
        )
    )
    p.append("</div>")
    return p


def _rr_cell(frame: dict[str, Any] | None) -> str:
    """Celda compacta del filtro R:R por marco (tooltip con la etiqueta completa)."""
    if not frame or not frame.get("disponible"):
        return "<span class='mut'>n/d</span>"
    g = frame.get("rr_geom") or {}
    full = _esc(g.get("label", "FILTRO R:R: NO APLICA"))
    if not g.get("aplica"):
        motivo = _esc(g.get("motivo", ""))
        return f"<span class='mut' title='{full} — {motivo}'>no aplica</span>"
    rr = g.get("rr")
    if g.get("cumple"):
        return f"<span class='pos' title='{full}'>✓ {_esc(rr)}x</span>"
    return f"<span class='neg' title='{full}'>✗ {_esc(rr)}x</span>"


def _calc_panel(calc: dict[str, Any] | None) -> list[str]:
    """Panel 4: calculadora aritmética de riesgo por operación (inputs en pantalla)."""
    p: list[str] = []
    p.append(
        "<div class='panel'><h2>4 · Calculadora de riesgo por operación (simulador aritmético)</h2>"
        "<div class='small'><b>Aritmética sobre TUS propios números — no es sizing recomendado "
        "ni señal.</b> Evaluación para 0.5 %, 1.0 % y 2.0 % de riesgo sobre el patrimonio, "
        "break-even neto y TP que satisface tu regla R:R (2.0x / 3.0x). Idéntico a "
        "<code>qa trade calc --entry … --sl … --tp …</code>.</div>"
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
        "(costs.yaml VERIFICADO) · R:R mínimo de tu disciplina: "
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


def _audit_panel(audit: dict[str, Any] | None) -> list[str]:
    """Panel 5: Trade Audit — operaciones cerradas + métricas globales + por tag."""
    p: list[str] = []
    p.append(
        "<div class='panel'><h2>5 · Trade Audit — historial de operaciones cerradas</h2>"
        "<div class='small'>Contabilidad de TUS operaciones cerradas (neto de comisiones taker "
        "estimadas ida y vuelta: spot 0.20 %, perp 0.10 %). Múltiplo R = PnL neto / riesgo "
        "inicial (|Entrada−SL|). No es un veredicto sobre ninguna estrategia.</div>"
        "<div class='calcrow' style='margin-bottom:8px'>"
        "<button id='qa_audit_csv' type='button' style='background:var(--info);border-color:var(--info);color:#000'>"
        "Exportar CSV</button>"
        "<span class='small' style='margin-left:10px'>Descarga la tabla de operaciones cerradas como CSV</span>"
        "</div>"
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
    p.append(
        "<table><tr><th>Cierre</th><th>Activo/Tipo/Marco</th><th>Duración</th><th>Entrada</th>"
        "<th>Salida</th><th>Tamaño</th><th>R:R inic. (bruto)</th><th>PnL neto $</th>"
        "<th>PnL %</th><th>R logrado</th><th>Tag</th><th>Nota</th></tr>"
    )
    for r in rows:
        ex = " <span class='badge b-info'>EJEMPLO</span>" if r.get("example") else ""
        neto = float(r.get("pnl_neto_usd") or 0.0)
        cls = "pos" if neto >= 0 else "neg"
        cierre = str(r.get("closed_at") or "?")[:10]
        rr_ini = r.get("rr_inicial_bruto")
        rm = r.get("r_multiplo")
        nota = " · ".join(x for x in (r.get("note"), r.get("close_note")) if x)
        p.append(
            f"<tr><td class='small num'>{_esc(cierre)}{ex}</td>"
            f"<td>{_esc(r.get('asset'))}<br><span class='small'>{_esc(r.get('kind'))} · "
            f"{_esc(r.get('timeframe'))}</span></td>"
            f"<td class='small num'>{_esc(r.get('duracion'))}</td>"
            f"<td class='num'>{_fmt(r.get('entry'))}</td><td class='num'>{_fmt(r.get('exit'))}</td>"
            f"<td class='num'>{_fmt(r.get('size_usd'))} USD</td>"
            f"<td class='num'>{_esc(rr_ini) if rr_ini is not None else '—'}x</td>"
            f"<td class='num {cls}'>{neto:+,.2f} USD<br><span class='small'>bruto "
            f"{_fmt(r.get('pnl_bruto_usd'))} − fees {_fmt(r.get('fees_est_usd'))}</span></td>"
            f"<td class='num {cls}'>{_esc(r.get('pnl_pct'))} %</td>"
            f"<td class='num {cls}'>{_esc(rm) + 'R' if rm is not None else 'sin SL'}</td>"
            f"<td class='small'>{_esc(r.get('tag') or '—')}</td>"
            f"<td class='small'>{_esc(nota) if nota else '—'}</td></tr>"
        )
    p.append("</table>")
    if summ:
        mp_usd = summ.get("mejor_peor_usd") or {}
        mp_r = summ.get("mejor_peor_R") or {}

        def _mw(d: dict[str, Any]) -> str:
            mej, peo = d.get("mejor") or {}, d.get("peor") or {}
            if not mej:
                return "—"
            return (
                f"mejor {_esc(mej.get('asset'))} {_fmt(mej.get('valor'))} · peor "
                f"{_esc(peo.get('asset'))} {_fmt(peo.get('valor'))}"
            )

        p.append(
            "<table style='margin-top:10px'><tr><th>Métrica global de auditoría</th><th>Valor</th></tr>"
            f"<tr><td>Operaciones cerradas</td><td class='num'>{_esc(summ.get('total_cerradas'))}</td></tr>"
            f"<tr><td>Win Rate</td><td class='num'>{_fmt(summ.get('win_rate_pct'), 1)} %</td></tr>"
            f"<tr><td>Ganancia/Pérdida Neta</td><td class='num'>"
            f"{_signed(summ.get('pnl_neto_usd'))} USD"
            f" · {_fmt(summ.get('pnl_neto_pct_aportado'))} % s/ capital aportado"
            f" · {_fmt(summ.get('pnl_neto_pct_rotacion'))} % s/ rotación desplegada</td></tr>"
            f"<tr><td>Profit Factor</td><td class='num'>{_esc(summ.get('profit_factor'))}</td></tr>"
            f"<tr><td>Esperanza matemática por operación</td><td class='num'>"
            f"{_fmt(summ.get('esperanza_usd_por_trade'))} USD · "
            f"{_fmt(summ.get('esperanza_R_por_trade'), 3)} R</td></tr>"
            f"<tr><td>R:R medio realizado</td><td class='num'>"
            f"{_fmt(summ.get('rr_medio_realizado_R'), 3)} R</td></tr>"
            f"<tr><td>Mejor / peor operación ($)</td><td class='small'>{_mw(mp_usd)}</td></tr>"
            f"<tr><td>Mejor / peor operación (R)</td><td class='small'>{_mw(mp_r)}</td></tr>"
            f"<tr><td>Max Drawdown realizado (sobre PnL acumulado)</td><td class='num'>"
            f"{_fmt(summ.get('max_drawdown_realizado_usd'))} USD</td></tr>"
            f"<tr><td>Operaciones sin SL (R no computable)</td><td class='num'>"
            f"{_esc(summ.get('trades_sin_sl'))}</td></tr></table>"
        )
        por_tag = summ.get("por_tag") or {}
        if por_tag:
            p.append(
                "<table style='margin-top:10px'><tr><th>Tag (diario de trading)</th><th>Ops</th>"
                "<th>Win Rate</th><th>PnL neto</th><th>R medio</th></tr>"
            )
            for tag, d in sorted(por_tag.items()):
                p.append(
                    f"<tr><td>{_esc(tag)}</td><td class='num'>{_esc(d.get('trades'))}</td>"
                    f"<td class='num'>{_fmt(d.get('win_rate_pct'), 1)} %</td>"
                    f"<td class='num'>{_signed(d.get('pnl_neto_usd'))} USD</td>"
                    f"<td class='num'>{_fmt(d.get('R_medio'), 3)} R</td></tr>"
                )
            p.append("</table>")
    p.append("</div>")

    # JS para exportar CSV de la tabla de auditoría
    p.append("""
<script>
document.addEventListener('DOMContentLoaded', function(){
  var btn = document.getElementById('qa_audit_csv');
  if(!btn) return;
  btn.addEventListener('click', function(){
    var table = document.querySelector('div.panel:nth-of-type(5) table');
    if(!table) return;
    var rows = table.querySelectorAll('tr');
    var csv = [];
    rows.forEach(function(row){
      var cells = row.querySelectorAll('th, td');
      var rowData = [];
      cells.forEach(function(cell){
        var text = cell.innerText.replace(/\\"/g, '""');
        if(text.indexOf(',') >= 0 || text.indexOf('"') >= 0 || text.indexOf('\\n') >= 0) {
          text = '"' + text + '"';
        }
        rowData.push(text);
      });
      csv.push(rowData.join(','));
    });
    var blob = new Blob([csv.join('\\n')], {type: 'text/csv;charset=utf-8;'});
    var link = document.createElement('a');
    link.href = URL.createObjectURL(blob);
    link.download = 'trade_audit_' + new Date().toISOString().slice(0,10) + '.csv';
    link.click();
  });
});
</script>
""")
    return p


def _capital_panel(capital: dict[str, Any] | None) -> list[str]:
    """Panel 6: historial de capital (libro append-only del usuario)."""
    p: list[str] = []
    p.append(
        "<div class='panel'><h2>6 · Historial de capital (libro contable del usuario)</h2>"
        "<div class='small'>Registro append-only con cadena de hashes "
        "(<code>ledger/user_capital.jsonl</code>). Comandos: <code>qa capital set/add/status/"
        "reset-examples</code>.</div>"
    )
    movs = (capital or {}).get("movimientos") or []
    if not movs:
        p.append("<div class='small'>Sin movimientos de capital registrados.</div></div>")
        return p
    p.append(
        "<table><tr><th>Fecha (UTC)</th><th>Tipo</th><th>Importe</th><th>Acumulado</th><th>Nota</th></tr>"
    )
    for m in movs:
        ex = " <span class='badge b-info'>EJEMPLO</span>" if m.get("example") else ""
        amt = float(m.get("amount") or 0.0)
        p.append(
            f"<tr><td class='small num'>{_esc(str(m.get('ts_utc'))[:16])}{ex}</td>"
            f"<td class='small'>{_esc(m.get('tipo'))}</td>"
            f"<td class='num'>{_signed(amt)} USD</td>"
            f"<td class='num'>{_fmt(m.get('acumulado'))} USD</td>"
            f"<td class='small'>{_esc(m.get('note') or '—')}</td></tr>"
        )
    p.append("</table>")
    sin_precio = (capital or {}).get("sin_precio_vivo") or []
    if sin_precio:
        p.append(
            "<div class='small' style='margin-top:6px'>⚠ Sin precio vivo para: "
            f"{_esc(', '.join(sin_precio))} — su PnL flotante no se computó en esta corrida.</div>"
        )
    p.append("</div>")
    return p


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
        "investigadas y la CONTABILIDAD de tus propias operaciones. No da órdenes de compra/venta. "
        "H1 y H2 están <b>SIN VENTAJA DEMOSTRADA</b> (veredicto INCONTRASTABLE del "
        "preregistro v1.4); H3-BTC pasó a nivel de signo con edge frágil a costes ×2. "
        "El filtro R:R, la calculadora y el Trade Audit son aritmética sobre TUS niveles y "
        "TUS registros. Ningún número de aquí es una promesa de rentabilidad.</div>"
    )

    # 0) Barra de patrimonio (contabilidad del usuario, M5b)
    p.extend(_equity_cards(capital))

    # 1) Operaciones abiertas del usuario (panel a ancho completo: muchas columnas)
    p.append("<div class='panel full'><h2>1 · Mis operaciones abiertas (registro del usuario)</h2>")
    open_trades = [t for t in trades_diag if t.get("status", "open") == "open"]
    if open_trades:
        p.append(
            "<table><tr><th>Op</th><th>Activo/Tipo/Marco</th><th>PnL</th><th>Dist. SL / TP (tuyos)</th>"
            "<th>Tiempo</th><th>R:R inic. → residual hoy</th><th>Break-even neto</th>"
            "<th>Cota 2×ATR (tu marco)</th><th>SMA50 de tu marco</th>"
            "<th>Contexto de tendencia</th><th>Seguimiento</th></tr>"
        )
        for t in open_trades:
            ex = " <span class='badge b-info'>EJEMPLO</span>" if t.get("example") else ""
            forced = " <span class='badge b-warn'>RR FORZADO</span>" if t.get("rr_forzado") else ""
            pnl = t.get("pnl_pct")
            cls = "pos" if (pnl or 0) >= 0 else "neg"
            sl = f"{t.get('dist_sl_pct', '—')}%" if t.get("dist_sl_pct") is not None else "—"
            tp = f"{t.get('dist_tp_pct', '—')}%" if t.get("dist_tp_pct") is not None else "—"
            be = t.get("breakeven_neto")
            if be is not None:
                sup = bool(t.get("supero_breakeven"))
                be_html = (
                    f"<span class='num'>{_fmt(be)}</span><br><span class='small "
                    f"{'pos' if sup else 'mut'}'>{'superado ✓' if sup else 'no superado'}</span>"
                )
            else:
                be_html = "<span class='mut'>—</span>"
            cota = t.get("cota_2atr")
            cota_html = (
                f"<span class='num'>{_fmt(cota)}</span><br><span class='small'>marco "
                f"{_esc(t.get('timeframe', '?'))} · estadística, no stop</span>"
                if cota is not None
                else "<span class='mut'>n/d</span>"
            )
            rr_i = t.get("rr_inicial_tp_sl", "—")
            rr_a = t.get("rr_actual_tp_sl", "—")
            p.append(
                f"<tr><td class='num'>{_esc(t['id'])}{ex}{forced}</td>"
                f"<td>{_esc(t['asset'])}<br><span class='small'>{_esc(t.get('kind', ''))} · "
                f"{_esc(t.get('timeframe', ''))}</span></td>"
                f"<td class='num {cls}'>{pnl if pnl is not None else '—'}%"
                f"<br><span class='small'>{t.get('pnl_usd', '—')} USD</span></td>"
                f"<td class='num'>{sl} / {tp}</td>"
                f"<td class='small'>{_esc(t.get('tiempo_abierta', '—'))}</td>"
                f"<td class='num small'>{_esc(rr_i)} → {_esc(rr_a)}</td>"
                f"<td class='small'>{be_html}</td>"
                f"<td class='small'>{cota_html}</td>"
                f"<td class='small'>{_esc(t.get('sma50_marco_txt', '—'))}</td>"
                f"<td class='small'>{_esc(t.get('contexto_tendencia', '—'))}</td>"
                f"<td class='small'>{_esc(t.get('estado_seguimiento', '—'))}</td></tr>"
            )
        p.append("</table>")
        p.append(
            "<div class='small' style='margin-top:6px'>Break-even neto = precio donde tu PnL es 0 "
            "tras comisiones taker ida y vuelta. Cota 2×ATR = precio actual ∓ 2×ATR(14) del marco "
            "de tu operación: referencia estadística de rango, NO un stop propuesto por el sistema. "
            "R:R residual = distancia a tu TP / distancia a tu SL desde el precio de hoy.</div>"
        )
    else:
        p.append(
            "<div class='small'>Sin operaciones registradas. Usa <code>qa trade open …</code> "
            "para anotar TUS operaciones (el agente no abre nada).</div>"
        )
    p.append("</div>")

    p.append("<div class='grid'>")

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
            "<th>Filtro R:R ≥ min (geometría de una entrada nueva hoy)</th>"
            "<th>Exposición de la regla</th><th>Escala teórica s/ capital de referencia</th></tr>"
        )
        for asset, lv in h1_levels.items():
            expo_pct = round(float(lv["exposicion_regla"]) * 100)
            rrf = lv.get("rr_filtro") or {}
            if rrf.get("aplica"):
                badge_cls = "b-ok" if rrf.get("cumple") else "b-bad"
                rr_html = (
                    f"<span class='badge {badge_cls}'>{_esc(rrf.get('label'))}</span><br>"
                    f"<span class='small num'>Reward {_fmt(rrf.get('reward_dist'))} / Risk "
                    f"{_fmt(rrf.get('risk_dist'))} · extensión desde SMA50 "
                    f"{_fmt(rrf.get('extension_pct'))}%</span>"
                )
            else:
                rr_html = (
                    f"<span class='badge b-info'>{_esc(rrf.get('label', 'FILTRO R:R: NO APLICA'))}</span>"
                    f"<br><span class='small'>{_esc(rrf.get('motivo', ''))}</span>"
                )
            if lv.get("escala_bloqueada_por_rr"):
                escala_html = (
                    "<b class='num'>0 USD</b> <span class='badge b-bad'>Bloqueado por filtro "
                    f"R:R &lt; {_esc(rrf.get('min_rr', 2.0))}</span><br><span class='small'>"
                    "entrada nueva hoy NO cumpliría la asimetría mínima configurada por ti "
                    f"(Asimetría {_fmt(rrf.get('rr'))}x); la exposición aritmética de la regla "
                    f"sigue siendo {expo_pct}% × {_fmt(lv.get('capital_ref_usd'))} USD = "
                    f"{_fmt(lv.get('escala_usd_sobre_capital_ref'))} USD (informativo, sin filtro)</span>"
                )
            else:
                base_txt = _esc(lv.get("capital_base_origen", "config capital_ref_usd"))
                escala_html = (
                    f"{_esc(lv['escala_usd_sobre_capital_ref'])} USD "
                    f"<span class='small'>(= {expo_pct}% × {_fmt(lv['capital_ref_usd'], 0)} USD "
                    f"[{base_txt}]; escala teórica/informativo)</span>"
                )
            p.append(
                f"<tr><td>{_esc(asset)}</td><td class='num'>{_esc(lv['precio'])}</td>"
                f"<td class='num'>{_esc(lv['nivel_sma50'])} ({_esc(lv['distancia_a_sma50_pct'])}%)</td>"
                f"<td class='num'>{_esc(lv['atr14_usd'])} ({_esc(lv['atr14_pct'])}%)</td>"
                f"<td class='num'>[{_esc(lv['banda_inf_c_menos_2atr'])}, "
                f"{_esc(lv['banda_sup_c_mas_3atr'])}]</td>"
                f"<td class='small'>{rr_html}</td>"
                f"<td class='num'>{expo_pct}%</td>"
                f"<td class='num'>{escala_html}</td></tr>"
            )
        p.append("</table>")
    p.append("</div>")

    # 3) Telemetria watchlist multi-marco (descriptiva) + filtro R:R por marco
    min_rr_cfg = (calc or {}).get("min_rr", 2.0)
    p.append(
        "<div class='panel'><h2>3 · Telemetría watchlist 4H·1D·1W</h2>"
        "<div class='small'><b>Telemetría descriptiva de precios — No constituye "
        "hipótesis evaluada ni señal de trading.</b> SMA50 y ATR14 son hechos "
        "matemáticos del precio en cada marco. El filtro R:R mide la asimetría "
        "geométrica de una entrada nueva hipotética HOY contra tu mínimo "
        f"configurado ({_esc(min_rr_cfg)}x): ✓ = <i>FILTRO R:R ≥ {_esc(min_rr_cfg)}: CUMPLE "
        "(Asimetría X.Xx)</i> · ✗ = <i>NO CUMPLE (Asimetría X.Xx &lt; "
        f"{_esc(min_rr_cfg)} — Extendido)</i> · «no aplica» = precio bajo SMA50 o datos "
        "insuficientes (pasar el cursor muestra la etiqueta completa).</div>"
    )
    if telemetry:
        p.append(
            "<table><tr><th>Símbolo</th><th>Precio</th><th>24 h</th><th>Choque activo</th>"
            "<th>4H vs SMA50</th><th>1D vs SMA50</th><th>1W vs SMA50</th>"
            "<th>ATR14 % (4H/1D/1W)</th>"
            f"<th>Filtro R:R ≥ {_esc(min_rr_cfg)} (4H·1D·1W)</th></tr>"
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
            rr_cells = " · ".join(_rr_cell(row.get(tf) or None) for tf in ("4h", "1d", "1w"))
            precio = (row.get("1d") or {}).get("precio")
            c24 = row.get("cambio_24h_pct")
            cls24 = "pos" if (c24 or 0) >= 0 else "neg"
            p.append(
                f"<tr><td><b>{_esc(sym)}</b></td><td class='num'>{_esc(precio)}</td>"
                f"<td class='num {cls24}'>{_esc(c24)}%</td><td>{choque}</td>"
                f"<td class='small'>{_tf('4h')}</td><td class='small'>{_tf('1d')}</td>"
                f"<td class='small'>{_tf('1w')}</td><td class='num small'>{atrs}</td>"
                f"<td class='small num'>{rr_cells}</td></tr>"
            )
        p.append("</table>")
    else:
        p.append("<div class='small'>Sin datos de watchlist en esta corrida.</div>")
    p.append("</div>")

    # 4) Calculadora aritmética de riesgo (M5b)
    p.extend(_calc_panel(calc))

    # 5) Trade Audit (M5b)
    p.extend(_audit_panel(audit))

    # 6) Historial de capital (M5b)
    p.extend(_capital_panel(capital))

    # 7) Choques y noticias (vigilancia)
    p.append("<div class='panel'><h2>7 · Choques técnicos y noticias (vigilancia)</h2>")
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

    # 8) Evidencia cientifica + sparklines
    p.append("<div class='panel'><h2>8 · Evidencia científica (resumen M0-M3)</h2>")
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
        "<div class='panel full'><h2>9 · Glosario para JP</h2>"
        "<details><summary style='cursor:pointer;color:var(--info)'>Abrir explicaciones "
        "en lenguaje llano</summary><table>"
        "<tr><td><b>SMA50</b></td><td>Media del precio de las últimas 50 velas. "
        "«Por encima/por debajo» dice de qué lado está el precio hoy; la regla H1 "
        "investigada pasa a FLAT cuando el cierre diario cae por debajo.</td></tr>"
        "<tr><td><b>ATR14</b></td><td>Rango típico (alto−bajo) de las últimas 14 velas: "
        "cuánto se mueve el activo por vela. Las cotas close±k×ATR son una regla de rango "
        "estadístico, no niveles mágicos.</td></tr>"
        "<tr><td><b>Cota 2×ATR</b></td><td>Precio actual ∓ 2×ATR(14) del marco de tu "
        "operación: referencia estadística de cuánto se mueve ese marco. NO es un stop "
        "propuesto por el sistema.</td></tr>"
        "<tr><td><b>Break-even neto</b></td><td>Precio exacto donde tu operación queda a "
        "cero DESPUÉS de pagar las comisiones taker de ida y vuelta (spot 0.1 %×2, "
        "perp 0.05 %×2). Por encima (long) ya no puedes perder en esa operación cerrándola "
        "ahora… en teoría: el precio sigue moviéndose.</td></tr>"
        "<tr><td><b>R:R Neto</b></td><td>(distancia a tu TP − comisiones) / (distancia a tu "
        "SL + comisiones). Mide la asimetría de TU configuración: cuánto ganas si aciertas "
        "por cada 1 que arriesgas si fallas.</td></tr>"
        "<tr><td><b>Filtro R:R ≥ 2.0</b></td><td>Tu regla de disciplina (min_rr_ratio en "
        "config/watchlist.yaml). En la watchlist mide la geometría observable "
        "SMA50/ATR14: riesgo = distancia a la SMA50 (mín. 1×ATR) + comisiones; recompensa = "
        "3×ATR − lo ya subido desde la SMA50. «Extendido» = el precio ya recorrió tanto que "
        "la asimetría de una entrada nueva hoy cae bajo tu mínimo.</td></tr>"
        "<tr><td><b>Múltiplo R</b></td><td>PnL neto dividido por el riesgo inicial de la "
        "operación (|Entrada−SL| sobre el tamaño). +2.4R = ganaste 2.4 veces lo que "
        "arriesgabas; −1R = perdiste justo tu riesgo.</td></tr>"
        "<tr><td><b>Portfolio Heat (riesgo en mesa)</b></td><td>Cuánto perderías de tu "
        "capital APORTADO si TODOS tus stops saltaran hoy a la vez. Un stop ya en zona de "
        "ganancia aporta 0. Operaciones sin stop no son computables: se listan aparte.</td></tr>"
        "<tr><td><b>Equity Vivo (patrimonio total)</b></td><td>Capital aportado + PnL cerrado "
        "(neto de comisiones) + PnL flotante (bruto) de tus operaciones abiertas a precio de "
        "mercado actual.</td></tr>"
        "<tr><td><b>Profit Factor / Esperanza</b></td><td>Profit Factor = ganancias netas / "
        "pérdidas netas (&gt;1 = saldo positivo). Esperanza = PnL medio por operación ($ y R): "
        "lo que «ganas» de media por trade, en dinero y en riesgos.</td></tr>"
        "<tr><td><b>Exposición de la regla</b></td><td>Fracción de capital que la celda "
        "congelada tendría hoy (0-100 %), tras volatilidad objetivo y banda de 10 pp.</td></tr>"
        "<tr><td><b>Escala teórica</b></td><td>Multiplicación informativa: exposición × tu "
        "patrimonio vivo (o capital de referencia). No es una cantidad sugerida. Si el filtro "
        "R:R no cumple hoy, se muestra bloqueada ($0): es TU disciplina aplicada a la escala "
        "informativa, no un juicio del sistema.</td></tr>"
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
        "<footer>QUANT-ARENA v2 · M4/M5 operativo + M5b contabilidad del usuario "
        "(alcance conforme ADR-008 + addendum B) · "
        "holdout usado una única vez en M3b · datos: Binance API pública (solo lectura) + RSS públicos · "
        "Este archivo se regenera con <code>qa agent run</code>.</footer>"
    )
    out = "\n".join(p)
    for bad in PROHIBIDOS:
        if bad in out.upper():
            raise AssertionError(f"lenguaje prohibido en dashboard: {bad}")
    return out
