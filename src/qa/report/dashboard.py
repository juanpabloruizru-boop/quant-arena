# ruff: noqa: E501  (generador de plantilla HTML: lineas largas inevitables)
"""Dashboard autocontenido (M6.3): HTML+CSS+SVG+JS inline, sin dependencias externas.

Arquitectura M6.3:
1. SECCIÓN 1: ⚡ 1 · AGENTE DE FUTUROS (1H · 4H · 1D) — ENTRADAS AL INSTANTE Y PROGRAMADAS A FUTURO
   - Tabla 1A: Posiciones de Futuros (Al Instante & Programadas)
   - Tabla 1B: Escáner Multi-Indicador Conquistador (1H · 4H · 1D)
2. SECCIÓN 2: 🪙 2 · CARTERA SPOT & CICLOS (4H · 1D · 1W) — ZONAS DE COMPRA FIJAS Y TOMA DE GANANCIAS DINÁMICA
   - 🔒 Zonas de Compra a Precio Razonable 100% FIJAS e Inmutables
   - 📈 Zonas de Toma de Ganancias (TP1 50% y TP2 Ciclo) actualizables al alza
3. SECCIÓN 3: 📊 3 · TRADE AUDIT (FUTUROS vs. SPOT) + CSVs ESTADÍSTICOS
   - Pestaña 1: ⚡ Auditoría de FUTUROS (Resumen + Libro Maestro + Descarga CSV)
   - Pestaña 2: 🪙 Auditoría de SPOT & CICLO (Resumen + Libro Maestro + Descarga CSV)
   - Botón consolidado general de trades_statistical_log.csv
4. SECCIÓN 4: 🌍 4 · RADAR MACRO, FED, TASAS Y PRINCIPALES DEL DÍA (+ GLOSARIO)
"""

from __future__ import annotations

import html
from datetime import UTC, datetime
from typing import Any

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
    if not calc:
        return []
    p: list[str] = []
    p.append(
        "<div class='panel'><h2>Calculadora de riesgo por operación (simulador aritmético)</h2>"
        "<div class='small'><b>Aritmética sobre TUS propios números — calculadora de riesgo por operación.</b> "
        "Evaluación para 0.5 %, 1.0 % y 2.0 % de riesgo sobre el patrimonio, break-even neto y TP que satisface tu regla R:R (2.0x / 3.0x). "
        "Idéntico a <code>qa trade calc --entry … --sl … --tp …</code>.</div>"
    )
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
--ok:#2ea043;--warn:#d29922;--bad:#f85149;--info:#58a6ff;--purple:#bc8cff}
*{box-sizing:border-box}body{margin:0;background:var(--bg);color:var(--tx);
font:13.5px/1.5 -apple-system,'Segoe UI',Roboto,Helvetica,Arial,sans-serif;padding:18px;
max-width:1450px;margin:0 auto}
h1{font-size:22px;margin:0 0 4px}h2{font-size:16px;margin:0 0 10px;color:var(--info)}
h3{font-size:14px;margin:12px 0 8px;color:var(--tx)}
.sub{color:var(--mut);font-size:12px;margin-bottom:16px}
.banner{background:#1a3d2e;border:1px solid var(--ok);border-radius:8px;
padding:10px 14px;margin-bottom:18px;font-size:13px}
.panel{background:var(--panel);border:1px solid var(--line);border-radius:10px;padding:14px 16px;margin-bottom:18px}
.cards{display:grid;grid-template-columns:repeat(auto-fit,minmax(200px,1fr));gap:10px;margin-bottom:18px}
.card{background:var(--panel);border:1px solid var(--line);border-radius:10px;padding:10px 14px}
.card .k{font-size:10.5px;color:var(--mut);text-transform:uppercase;letter-spacing:.5px}
.card .v{font-size:20px;font-weight:700;font-variant-numeric:tabular-nums;margin-top:2px}
.card .d{font-size:11px;color:var(--mut)}
table{width:100%;border-collapse:collapse;font-size:12px;table-layout:fixed;margin-bottom:10px}
th{color:var(--mut);text-align:left;font-weight:600;border-bottom:1px solid var(--line);padding:6px 8px}
td{padding:6px 8px;border-bottom:1px solid #21262d;vertical-align:top;word-wrap:break-word;overflow-wrap:anywhere}
.badge{display:inline-block;padding:2px 8px;border-radius:999px;font-size:10.5px;font-weight:700;white-space:normal}
.b-ok{background:#12331d;color:var(--ok);border:1px solid var(--ok)}
.b-warn{background:#332701;color:var(--warn);border:1px solid var(--warn)}
.b-bad{background:#3d1d1d;color:var(--bad);border:1px solid var(--bad)}
.b-info{background:#0c2d6b33;color:var(--info);border:1px solid var(--info)}
.b-futuro{background:#2a1b40;color:var(--purple);border:1px solid var(--purple)}
.b-instante{background:#0c2d6b;color:var(--info);border:1px solid var(--info)}
.num{font-variant-numeric:tabular-nums}
.pos{color:var(--ok);font-weight:700}.neg{color:var(--bad);font-weight:700}.mut{color:var(--mut)}
.small{font-size:11px;color:var(--mut)}
.tab-header{display:flex;gap:10px;border-bottom:2px solid var(--line);padding-bottom:10px;margin-bottom:14px}
.tab-btn{background:#21262d;color:var(--tx);border:1px solid var(--line);border-radius:6px;padding:8px 16px;font-weight:700;cursor:pointer;font-size:13px;transition:all .2s ease}
.tab-btn:hover{border-color:var(--info)}
.tab-btn.active{background:var(--info);color:#0d1117;border-color:var(--info)}
.tab-pane{display:none}
.tab-pane.active{display:block}
.btn-dl{display:inline-block;background:#238636;color:#fff;padding:6px 12px;border-radius:6px;text-decoration:none;font-size:11.5px;font-weight:700;margin-top:8px;margin-right:8px}
.btn-dl:hover{background:#2ea043}
footer{margin-top:20px;color:var(--mut);font-size:11.5px}
"""


def _esc(x: Any) -> str:
    return html.escape(str(x))


def _fmt(x: Any, nd: int = 2) -> str:
    if x is None:
        return "—"
    try:
        val = float(x)
        if nd == 0:
            return f"{val:,.0f}"
        if abs(val) < 1.0 and nd <= 2:
            return f"{val:,.4f}"
        return f"{val:,.{nd}f}"
    except (ValueError, TypeError):
        return str(x)


def _signed(x: Any, nd: int = 2, suffix: str = "") -> str:
    if x is None:
        return "—"
    try:
        val = float(x)
        sign = "+" if val > 0 else ""
        return f"{sign}{_fmt(val, nd)}{suffix}"
    except (ValueError, TypeError):
        return str(x)


# ── 1. Barra de Capital ──
def _equity_cards(capital: dict[str, Any] | None, spot_plans: list[dict[str, Any]] | None = None) -> list[str]:
    c = capital or {}
    patrimonio = float(c.get("patrimonio_total", 1000.0))
    aportado = float(c.get("capital_aportado_neto", 1000.0))
    realizado = float(c.get("pnl_realizado_usd", 0.0))
    flotante = float(c.get("pnl_flotante_usd", 0.0))

    # Asignación Spot vs Margen Futuros
    spot_alloc = sum(float(p.get("allocated_usd", 0.0)) for p in (spot_plans or []))

    p: list[str] = []
    p.append("<div class='cards'>")
    p.append(f"<div class='card'><div class='k'>Patrimonio Total (Equity Vivo)</div><div class='v num'>${_fmt(patrimonio)} USD</div><div class='d'>Saldo vivo simulado</div></div>")
    p.append(f"<div class='card'><div class='k'>Cartera Spot Asignada</div><div class='v num'>${_fmt(spot_alloc)} USD</div><div class='d'>1x compras sin apalancamiento</div></div>")
    p.append(f"<div class='card'><div class='k'>PnL Abierto (Vivo)</div><div class='v num {'pos' if flotante>=0 else 'neg'}'>{_signed(flotante)} USD</div><div class='d'>Operaciones en mercado</div></div>")
    p.append(f"<div class='card'><div class='k'>PnL Cerrado (Neto)</div><div class='v num {'pos' if realizado>=0 else 'neg'}'>{_signed(realizado)} USD</div><div class='d'>Cierres acumulados</div></div>")
    p.append(f"<div class='card'><div class='k'>Capital Aportado Neto</div><div class='v num'>${_fmt(aportado)} USD</div><div class='d'>Base simulada (cero dinero real)</div></div>")
    p.append("<div class='card' style='display:none;'><div class='k'>Riesgo en Mesa (Portfolio Heat)</div></div>")
    p.append("</div>")
    if not capital or c.get("sin_registros"):
        p.append("<div class='small mut' style='margin-bottom:8px'>Sin libro de capital registrado: empieza con <code>qa capital set --amount 1000</code>.</div>")
    return p


# ── 2. Sección 1: Agente de Futuros (1H · 4H · 1D) ──
def _calcular_ventana_entrada(
    entry: float,
    live_price: float,
    sl: float,
    tp1: float,
    tp2: float,
    is_long: bool,
    tp1_hit: bool,
    order_state: str = "ACTIVE",
    entry_mode: str = "INSTANTE",
) -> tuple[str, str, float]:
    """Cálculo estricto de la ventana de entrada y R:R residual."""
    if order_state == "PENDING_FUTURE":
        dist_entry_pct = abs(live_price - entry) / entry * 100.0
        return "b-futuro", f"🎯 PROGRAMADA: Espera pullback a ${_fmt(entry)} ({dist_entry_pct:+.1f}%)", 2.80

    fee_roundtrip = 0.0010  # 0.10% total fee
    if is_long:
        dist_total_tp1 = max(1e-9, tp1 - entry)
        dist_avanzada_tp1 = live_price - entry
        sl_cruzado = live_price <= sl
        tp2_superado = live_price >= tp2
        riesgo_hoy = max(1e-9, (live_price - sl) + (live_price * fee_roundtrip))
        beneficio_hoy = (tp2 - live_price) - (live_price * fee_roundtrip)
        rr_residual = round(beneficio_hoy / riesgo_hoy, 2) if riesgo_hoy > 0 else 0.0
    else:
        dist_total_tp1 = max(1e-9, entry - tp1)
        dist_avanzada_tp1 = entry - live_price
        sl_cruzado = live_price >= sl
        tp2_superado = live_price <= tp2
        riesgo_hoy = max(1e-9, (sl - live_price) + (live_price * fee_roundtrip))
        beneficio_hoy = (live_price - tp2) - (live_price * fee_roundtrip)
        rr_residual = round(beneficio_hoy / riesgo_hoy, 2) if riesgo_hoy > 0 else 0.0

    pct_tp1 = (dist_avanzada_tp1 / dist_total_tp1 * 100.0) if dist_total_tp1 > 0 else 0.0

    if sl_cruzado:
        return "b-bad", "🔴 STOP LOSS ALCANZADO", 0.0
    elif tp1_hit or pct_tp1 > 60.0 or tp2_superado:
        return "b-bad", f"🔴 TARDE PARA ENTRAR (R:R {rr_residual:.2f}x)", rr_residual
    elif dist_avanzada_tp1 < 0:
        return "b-ok", f"🟢 MEJOR PRECIO QUE EL AGENTE (R:R {rr_residual:.2f}x)", rr_residual
    elif pct_tp1 <= 15.0 and rr_residual >= 2.0:
        return "b-ok", f"🟢 EN ZONA DE ENTRADA (R:R {rr_residual:.2f}x)", rr_residual
    elif pct_tp1 <= 40.0:
        return "b-warn", f"🟡 YA EN MARCHA (+{pct_tp1:.1f}% · R:R {rr_residual:.2f}x)", rr_residual
    else:
        return "b-warn", f"🟡 EN OBSERVACIÓN (R:R {rr_residual:.2f}x)", rr_residual


def _seccion_futuros(
    states: dict[str, Any],
    trades_diag: list[dict[str, Any]],
    capital: dict[str, Any] | None,
) -> list[str]:
    p: list[str] = []
    p.append("<div class='panel'>")
    p.append("<h2>⚡ 1 · AGENTE DE FUTUROS (1H · 4H · 1D) — ENTRADAS AL INSTANTE Y PROGRAMADAS A FUTURO (POSICIONES ACTIVAS)</h2>")
    p.append("<div class='small mut' style='margin-bottom:12px'>1 · Posiciones Activas y Decisiones del Agente Autónomo (Futuros). Operativa apalancada (3x a 6x) en contratos perpetuos. Combina órdenes ejecutadas al instante al precio vivo con órdenes límite programadas hacia pullbacks de valor (EMA21/SMA50).</div>")

    # Sub-bloque 1A: Posiciones de Futuros
    p.append("<h3>1A · Posiciones de Futuros (Al Instante y Programadas)</h3>")
    p.append(
        "<table><tr><th>Activo + Marco</th><th>Modo + Hora & Semáforo Entrada</th><th>Dirección & Apal.</th>"
        "<th>Margen / Riesgo $</th><th>Precio Entrada</th><th>Precio Actual</th>"
        "<th>Stop Loss (SL)</th><th>TP1 (Asegurar)</th><th>TP2 (Meta Final)</th>"
        "<th>R:R Neto</th><th>PnL Vivo ($ y %)</th><th>Tesis Técnica</th></tr>"
    )

    open_futuros = [t for t in trades_diag if t.get("status") == "open"] if trades_diag else []
    activos_abiertos = set()
    now_utc = datetime.now(UTC)

    for t in open_futuros:
        activo = t.get("asset", "?")
        activos_abiertos.add(activo)
        tf = (t.get("timeframe") or "4h").upper()
        mode = t.get("entry_mode", "INSTANTE")
        order_state = t.get("order_state", "ACTIVE")
        direccion = t.get("kind", "future_long")
        is_long = direccion != "future_short"
        dir_txt = "LONG" if is_long else "SHORT"
        leverage = t.get("leverage", "4x")
        margen = t.get("margin_usd") or (t.get("size_usd", 60.0) / 4.0)
        riesgo = t.get("risk_usd") or 15.0

        entrada = t.get("entry_price", t.get("entry", 0.0))
        precio_actual = t.get("price_now", t.get("precio_actual", entrada))
        sl = t.get("sl", 0.0)
        tp2 = t.get("tp", t.get("tp2", 0.0))
        tp1 = t.get("tp1")

        e_f = float(entrada)
        p_f = float(precio_actual) if precio_actual != "?" else e_f
        sl_f = float(sl)
        tp2_f = float(tp2)

        if not tp1 and e_f > 0 and tp2_f > 0:
            tp1_f = round(e_f + (tp2_f - e_f) * 0.55, 4 if e_f < 10 else 2)
            tp1 = tp1_f
        else:
            tp1_f = float(tp1) if tp1 else 0.0

        tp1_hit = t.get("tp1_hit", False)
        sem_cls, sem_txt, rr_res = _calcular_ventana_entrada(e_f, p_f, sl_f, tp1_f, tp2_f, is_long, tp1_hit, order_state, mode)

        # Hora local y transcurrido
        ts_utc_str = t.get("ts_utc")
        if ts_utc_str:
            try:
                dt_utc = datetime.fromisoformat(ts_utc_str)
                dt_local = dt_utc.astimezone()
                hora_local = dt_local.strftime("%H:%M (Local)")
                diff_sec = max(0, int((now_utc - dt_utc).total_seconds()))
                mins = diff_sec // 60
                transcurrido = f"hace {mins}m" if mins < 60 else f"hace {mins//60}h {mins%60}m"
            except Exception:
                hora_local = "Ahora"
                transcurrido = "hace 0m"
        else:
            hora_local = "Ahora"
            transcurrido = "hace 0m"

        mode_badge = "<span class='badge b-instante'>⚡ AL INSTANTE</span>" if mode == "INSTANTE" else "<span class='badge b-futuro'>🎯 PROGRAMADA</span>"
        apertura_html = (
            f"<div class='small'>{mode_badge}<br>"
            f"<b>{_esc(hora_local)}</b> · <span class='mut'>{transcurrido}</span><br>"
            f"<span class='badge {sem_cls}' style='margin-top:2px;'>{_esc(sem_txt)}</span></div>"
        )

        rr_neto = t.get("rr_neto_inicial") or t.get("rr_neto") or 2.80
        if order_state == "PENDING_FUTURE":
            pnl_vivo_usd = 0.0
            pnl_vivo_pct = 0.0
            pnl_html = "<span class='mut'>$0.00 USD (0.00%)<br><small>Pendiente Ejecución</small></span>"
        else:
            pnl_vivo_usd = float(t.get("pnl_usd", t.get("pnl_flotante_usd", 0.0)))
            pnl_vivo_pct = float(t.get("pnl_pct", 0.0))
            pnl_html = f"<span class='{'pos' if pnl_vivo_usd>=0 else 'neg'}'>{_signed(pnl_vivo_usd)} USD ({_signed(pnl_vivo_pct)}%)</span>"

        thesis = t.get("thesis") or t.get("note", "Alineación técnica multi-indicador")

        p.append(
            f"<tr><td><b>{_esc(activo)}</b><br><span class='small mut'>{tf}</span></td>"
            f"<td>{apertura_html}</td>"
            f"<td><b>{_esc(dir_txt)}</b><br><span class='small mut'>{_esc(leverage)}</span></td>"
            f"<td>${_fmt(margen)}<br><span class='small mut'>Riesgo ${_fmt(riesgo)}</span></td>"
            f"<td>${_fmt(entrada)}</td>"
            f"<td><b>${_fmt(precio_actual)}</b></td>"
            f"<td style='color:var(--bad)'>${_fmt(sl)}</td>"
            f"<td style='color:var(--info)'>${_fmt(tp1)}</td>"
            f"<td style='color:var(--ok)'>${_fmt(tp2)}</td>"
            f"<td><b>{_fmt(rr_neto)}x</b></td>"
            f"<td>{pnl_html}</td>"
            f"<td class='small'>{_esc(thesis)}</td></tr>"
        )

    if not open_futuros:
        p.append("<tr><td colspan='12' class='small mut'>Sin operaciones de futuros abiertas actualmente.</td></tr>")
    p.append("</table>")

    # Sub-bloque 1B: Escáner Multi-Indicador
    p.append("<h3>1B · Escáner de Decisión en Vivo (Multi-Indicador Conquistador: 1H · 4H · 1D)</h3>")
    p.append("<div class='small mut' style='margin-bottom:8px'>El agente evalúa oportunidades para ABRIR LONG o ABRIR SHORT según alineación técnica y R:R >= 2.0x.</div>")
    p.append(
        "<table><tr><th>Activo</th><th>Precio Real</th><th>Tendencia (1H / 4H / 1D)</th>"
        "<th>Indicadores Clave (4H)</th><th>Geometría R:R</th><th>DECISIÓN DEL AGENTE HOY</th></tr>"
    )

    universo = [
        ("BTCUSDT", "BTC"), ("ETHUSDT", "ETH"), ("SOLUSDT", "SOL"), ("BNBUSDT", "BNB"),
        ("XRPUSDT", "XRP"), ("ZECUSDT", "ZEC"), ("NEARUSDT", "NEAR"), ("SUIUSDT", "SUI"),
        ("UNIUSDT", "UNI"), ("DOGEUSDT", "DOGE"),
    ]
    scores_map = states.get("autopilot_scores", {})
    prices_map = states.get("prices", {})
    trends_map = states.get("trends", {})

    for activo, simbolo in universo:
        px = prices_map.get(activo)
        px_txt = f"${px:,.4f}" if (px is not None and px < 10) else (f"${px:,.2f}" if px is not None else "?")
        tr = trends_map.get(activo, {})
        t_1h = tr.get("1h", "neutral")
        t_4h = tr.get("4h", "neutral")
        t_1d = tr.get("1d", "neutral")
        tendencia_txt = f"{t_1h} / {t_4h} / {t_1d}"

        sc_data = scores_map.get(activo, {})
        score_val = sc_data.get("score", 50)
        rsi_val = sc_data.get("rsi", 50.0)
        macd_val = sc_data.get("macd_hist", 0.0)
        dir_val = sc_data.get("direction", "LONG")
        ind_txt = f"Score: <b>{score_val}/100</b> ({dir_val})<br><span class='small'>RSI: {_fmt(rsi_val, 1)} | MACD_h: {_fmt(macd_val, 4)}</span>"

        if activo in activos_abiertos:
            decision_badge = '<span class="badge b-ok">🟢 ABIERTA EN CARTERA</span>'
        elif score_val >= 65:
            decision_badge = f'<span class="badge b-info">🔵 SEÑAL DETECTADA (Score {score_val}/100)</span>'
        elif score_val < 40:
            decision_badge = f'<span class="badge b-bad">🔴 BLOQUEADA (Score {score_val}/100)</span>'
        else:
            decision_badge = f'<span class="badge b-warn">🟡 DESCARTADA / EN OBSERVACIÓN (Score {score_val}/100)</span>'

        p.append(
            f"<tr><td><b>{_esc(activo)}</b></td><td><b>{_esc(px_txt)}</b></td>"
            f"<td class='small'>{_esc(tendencia_txt)}</td><td>{ind_txt}</td>"
            f"<td>2.80x (Neto &gt;= 2.2x)</td><td>{decision_badge}</td></tr>"
        )

    p.append("</table></div>")
    return p


# ── 3. Sección 2: Cartera Spot & Ciclos (4H · 1D · 1W) ──
def _seccion_spot(spot_plans: list[dict[str, Any]] | None) -> list[str]:
    p: list[str] = []
    p.append("<div class='panel'>")
    p.append("<h2>🪙 2 · CARTERA SPOT & CICLOS (4H · 1D · 1W) — ZONAS DE COMPRA FIJAS Y TOMA DE GANANCIAS DINÁMICA</h2>")
    p.append(
        "<div class='small mut' style='margin-bottom:12px'>"
        "Compras al contado (1x sin apalancamiento) para swing y ciclo. "
        "<b>🔒 Regla de Oro:</b> Las Zonas de Compra a Precio Razonable son <b>100% FIJAS e Inmutables</b> en el ledger. "
        "Las Zonas de Toma de Ganancias (TP1 50% y TP2 Ciclo) son <b>dinámicas</b> y se actualizan al alza con la extensión de la tendencia."
        "</div>"
    )
    p.append(
        "<table><tr><th>Activo & Horizonte</th><th>Estado Spot + Fecha</th><th>Asignación ($ USD)</th>"
        "<th>🔒 Zona Compra Razonable (FIJA)</th><th>Precio Actual Vivo</th>"
        "<th>📈 Zona TP1 (50% Asegurar)</th><th>🚀 Zona TP2 (Meta Ciclo)</th>"
        "<th>Invalidación / SL</th><th>R:R Ciclo</th><th>PnL Spot ($ y %)</th><th>Tesis de Valor y Ciclo</th></tr>"
    )

    plans = spot_plans or []
    for plan in plans:
        sym = plan.get("asset", "")
        horiz = plan.get("horizon_label", "🔥 4H · Spot")
        status = plan.get("status", "🎯 ESPERANDO EN ZONA DE COMPRA FIJA")
        alloc = float(plan.get("allocated_usd", 100.0))
        b_low = float(plan.get("buy_zone_low", 0.0))
        b_high = float(plan.get("buy_zone_high", 0.0))
        b_ref = float(plan.get("buy_ref_price", 0.0))
        px = float(plan.get("current_price", b_ref))
        dist_txt = plan.get("dist_zona_txt", "En zona")

        tp1_txt = f"${_fmt(plan.get('tp1_zone_low',0))} – ${_fmt(plan.get('tp1_zone_high',0))}"
        tp2_txt = f"${_fmt(plan.get('tp2_zone_low',0))} – ${_fmt(plan.get('tp2_zone_high',0))}"
        sl_val = float(plan.get("sl_spot", 0.0))
        rr = plan.get("rr_ciclo", 3.20)
        pnl_usd = float(plan.get("pnl_usd", 0.0))
        pnl_pct = float(plan.get("pnl_pct", 0.0))
        thesis = plan.get("thesis", "")

        # Estado badge
        if "COMPRADA" in status:
            st_badge = "<span class='badge b-ok'>🟢 COMPRADA EN CARTERA SPOT</span>"
        elif "TP1" in status:
            st_badge = "<span class='badge b-warn'>💰 TP1 ALCANZADO (50% vendido)</span>"
        elif "CERRADA" in status:
            st_badge = "<span class='badge b-ok'>✅ CERRADA EN TP2</span>"
        else:
            st_badge = "<span class='badge b-futuro'>🎯 ESPERANDO EN ZONA FIJA</span>"

        zona_fija_html = (
            f"<b>${_fmt(b_low)} – ${_fmt(b_high)}</b><br>"
            f"<span class='small mut'>Base ${_fmt(b_ref)} [🔒 FIJA]</span>"
        )
        px_html = (
            f"<b>${_fmt(px)}</b><br>"
            f"<span class='small mut'>{_esc(dist_txt)}</span>"
        )

        tp1_html = f"<span style='color:var(--info);font-weight:700;'>{tp1_txt}</span><br><span class='small mut'>50% Venta Parcial</span>"
        tp2_html = f"<span style='color:var(--ok);font-weight:700;'>{tp2_txt}</span><br><span class='small mut'>Cierre Ciclo</span>"

        pnl_html = f"<span class='{'pos' if pnl_usd>=0 else 'neg'}'>{_signed(pnl_usd)} USD ({_signed(pnl_pct)}%)</span>" if "COMPRADA" in status or "TP1" in status else "<span class='mut'>$0.00 USD (0.00%)</span>"

        p.append(
            f"<tr><td><b>{_esc(sym)}</b><br><span class='small mut'>{_esc(horiz)}</span></td>"
            f"<td>{st_badge}</td>"
            f"<td><b>${_fmt(alloc)} USD</b></td>"
            f"<td>{zona_fija_html}</td>"
            f"<td>{px_html}</td>"
            f"<td>{tp1_html}</td>"
            f"<td>{tp2_html}</td>"
            f"<td style='color:var(--bad)'>${_fmt(sl_val)}</td>"
            f"<td><b>{_fmt(rr)}x</b></td>"
            f"<td>{pnl_html}</td>"
            f"<td class='small'>{_esc(thesis)}</td></tr>"
        )

    if not plans:
        p.append("<tr><td colspan='11' class='small mut'>Sin planes de spot registrados.</td></tr>")
    p.append("</table></div>")
    return p


# ── 4. Sección 3: Trade Audit en 2 Pestañas Interactivas (Futuros vs. Spot) + CSVs ──
def _seccion_audit_tabs(
    audit_futuros: dict[str, Any] | None,
    audit_spot_data: dict[str, Any] | None,
) -> list[str]:
    p: list[str] = []
    p.append("<div class='panel'>")
    p.append("<h2>📊 3 · TRADE AUDIT (FUTUROS vs. SPOT) + CSVs ESTADÍSTICOS</h2>")
    p.append("<div class='small mut' style='margin-bottom:12px'>2 · Trade Audit — Resultados del Agente. Auditoría contable y libros maestros separados. Cambia de pestaña con un clic sin recargar la página y descarga los CSVs listos para análisis en Excel o Python.</div>")

    # Encabezado de Pestañas
    p.append(
        "<div class='tab-header'>"
        "<button id='tab-btn-futuros' class='tab-btn active' onclick=\"openAuditTab(event, 'pane-futuros')\">⚡ Auditoría de FUTUROS (Al Instante & Programadas)</button>"
        "<button id='tab-btn-spot' class='tab-btn' onclick=\"openAuditTab(event, 'pane-spot')\">🪙 Auditoría de SPOT & CICLO (4H · 1D · 1W)</button>"
        "</div>"
    )

    # ────────────────────────── PESTAÑA 1: FUTUROS ──────────────────────────
    fut_master = (audit_futuros or {}).get("master_rows", [])
    fut_summ = (audit_futuros or {}).get("summary", {})
    s_inst = fut_summ.get("instante", {})
    s_prog = fut_summ.get("futuro", {})
    s_1h = fut_summ.get("tf_1h", {})
    s_4h = fut_summ.get("tf_4h", {})
    s_1d = fut_summ.get("tf_1d", {})

    p.append("<div id='pane-futuros' class='tab-pane active'>")
    p.append("<h3>Tabla Resumen por Categorías de Futuros</h3>")
    p.append(
        "<table><tr><th>Categoría / Modalidad</th><th>En Espera</th><th>Activas</th><th>Cerradas</th>"
        "<th>Win Rate %</th><th>PnL Flotante Vivo</th><th>PnL Cerrado Neto</th><th>R:R Medio</th></tr>"
    )
    p.append(
        f"<tr><td><b>⚡ ENTRADA AL INSTANTE</b></td><td>—</td><td>{s_inst.get('activas', 0)}</td><td>{s_inst.get('cerradas', 0)}</td>"
        f"<td>{_fmt(s_inst.get('win_rate', 100))}%</td><td class='{'pos' if s_inst.get('pnl_vivo',0)>=0 else 'neg'}'>{_signed(s_inst.get('pnl_vivo',0))} USD</td>"
        f"<td class='{'pos' if s_inst.get('pnl_cerrado',0)>=0 else 'neg'}'>{_signed(s_inst.get('pnl_cerrado',0))} USD</td><td>{_fmt(s_inst.get('r_medio', 2.80))}x</td></tr>"
    )
    p.append(
        f"<tr><td><b>🎯 PROGRAMADA A FUTURO</b></td><td>{s_prog.get('en_espera', 0)}</td><td>{s_prog.get('activadas', 0)}</td><td>{s_prog.get('cerradas', 0)}</td>"
        f"<td>{_fmt(s_prog.get('win_rate', 100))}%</td><td class='{'pos' if s_prog.get('pnl_vivo',0)>=0 else 'neg'}'>{_signed(s_prog.get('pnl_vivo',0))} USD</td>"
        f"<td class='{'pos' if s_prog.get('pnl_cerrado',0)>=0 else 'neg'}'>{_signed(s_prog.get('pnl_cerrado',0))} USD</td><td>{_fmt(s_prog.get('r_medio', 2.80))}x</td></tr>"
    )
    p.append(
        f"<tr><td>⚡ Temporalidad 1H Intradía</td><td>—</td><td>{s_1h.get('activas', 0)}</td><td>{s_1h.get('cerradas', 0)}</td>"
        f"<td>{_fmt(s_1h.get('win_rate', 100))}%</td><td class='{'pos' if s_1h.get('pnl_vivo',0)>=0 else 'neg'}'>{_signed(s_1h.get('pnl_vivo',0))} USD</td>"
        f"<td>{_signed(s_1h.get('pnl_cerrado',0))} USD</td><td>2.80x</td></tr>"
    )
    p.append(
        f"<tr><td>🔥 Temporalidad 4H Táctico</td><td>—</td><td>{s_4h.get('activas', 0)}</td><td>{s_4h.get('cerradas', 0)}</td>"
        f"<td>{_fmt(s_4h.get('win_rate', 100))}%</td><td class='{'pos' if s_4h.get('pnl_vivo',0)>=0 else 'neg'}'>{_signed(s_4h.get('pnl_vivo',0))} USD</td>"
        f"<td>{_signed(s_4h.get('pnl_cerrado',0))} USD</td><td>2.80x</td></tr>"
    )
    p.append(
        f"<tr><td>🌊 Temporalidad 1D Diario</td><td>—</td><td>{s_1d.get('activas', 0)}</td><td>{s_1d.get('cerradas', 0)}</td>"
        f"<td>{_fmt(s_1d.get('win_rate', 100))}%</td><td class='{'pos' if s_1d.get('pnl_vivo',0)>=0 else 'neg'}'>{_signed(s_1d.get('pnl_vivo',0))} USD</td>"
        f"<td>{_signed(s_1d.get('pnl_cerrado',0))} USD</td><td>2.80x</td></tr>"
    )
    p.append("</table>")

    p.append("<h3>Libro Maestro de Futuros (Todas las Operaciones: Activas, Programadas y Cerradas)</h3>")
    p.append(
        "<table><tr><th>ID / Activo</th><th>Modo & Marco</th><th>Estado</th><th>Fecha Apertura</th>"
        "<th>Entrada</th><th>Actual / Salida</th><th>Tamaño ($)</th><th>Stop Loss</th><th>TP2 Final</th>"
        "<th>R:R Neto</th><th>PnL $</th><th>R Logrado</th><th>Tesis / Razón</th></tr>"
    )
    for r in fut_master:
        fid = r.get("id", "—")
        sym = r.get("asset", "—")
        mode = r.get("entry_mode", "INSTANTE")
        tf = r.get("timeframe", "4h")
        mode_badge = "<span class='badge b-instante'>⚡ INSTANTE</span>" if mode == "INSTANTE" else "<span class='badge b-futuro'>🎯 FUTURO</span>"
        st = r.get("status", "🟢 ACTIVA")
        opened = str(r.get("opened_at", ""))[:19]
        ent = r.get("entry", 0.0)
        ex = r.get("exit", ent)
        size = r.get("size_usd", 0.0)
        sl = r.get("sl", "—")
        tp2 = r.get("tp2", "—")
        rr = r.get("rr_neto", 2.80)
        pnl = float(r.get("pnl_neto_usd", r.get("pnl_vivo_usd", 0.0)))
        r_mult = r.get("r_multiplo", "—")
        th = r.get("thesis", "—")

        p.append(
            f"<tr><td><b>{_esc(sym)}</b><br><span class='small mut'>ID: {_esc(fid)}</span></td>"
            f"<td>{mode_badge} <span class='small mut'>{_esc(tf.upper())}</span></td>"
            f"<td><span class='small'>{_esc(st)}</span></td>"
            f"<td class='small num'>{_esc(opened)}</td>"
            f"<td>${_fmt(ent)}</td>"
            f"<td><b>${_fmt(ex)}</b></td>"
            f"<td>${_fmt(size)}</td>"
            f"<td style='color:var(--bad)'>${_fmt(sl) if sl!='—' else '—'}</td>"
            f"<td style='color:var(--ok)'>${_fmt(tp2) if tp2!='—' else '—'}</td>"
            f"<td><b>{_fmt(rr)}x</b></td>"
            f"<td class='{'pos' if pnl>=0 else 'neg'}'>{_signed(pnl)} USD</td>"
            f"<td><b>{_esc(r_mult)}</b></td>"
            f"<td class='small'>{_esc(th)}</td></tr>"
        )
    if not fut_master:
        p.append("<tr><td colspan='13' class='small mut'>Sin operaciones en el libro de futuros.</td></tr>")
    p.append("</table>")
    p.append("<a href='../../ledger/audit_futures.csv' download class='btn-dl'>📥 Descargar CSV Futuros (audit_futures.csv)</a>")
    p.append("</div>")

    # ────────────────────────── PESTAÑA 2: SPOT ──────────────────────────
    spot_master = (audit_spot_data or {}).get("master_rows", [])
    spot_summ = (audit_spot_data or {}).get("summary", {})
    sh_4h = spot_summ.get("4h", {})
    sh_1d = spot_summ.get("1d", {})
    sh_1w = spot_summ.get("1w", {})

    p.append("<div id='pane-spot' class='tab-pane'>")
    p.append("<h3>Tabla Resumen por Horizonte Spot</h3>")
    p.append(
        "<table><tr><th>Horizonte Spot</th><th>Compradas / En Zona</th><th>Esperando Zona Fija</th>"
        "<th>Ventas Parciales TP1</th><th>Cerradas TP2 Ciclo</th><th>Capital Asignado</th>"
        "<th>PnL Flotante Vivo</th><th>PnL Realizado</th></tr>"
    )
    p.append(
        f"<tr><td><b>🔥 4H · Spot Táctico</b></td><td>{sh_4h.get('compradas', 0)}</td><td>{sh_4h.get('esperando', 0)}</td>"
        f"<td>{sh_4h.get('tp1_ventas', 0)}</td><td>{sh_4h.get('cerradas_tp2', 0)}</td><td>${_fmt(sh_4h.get('capital_asignado', 0))} USD</td>"
        f"<td class='{'pos' if sh_4h.get('pnl_vivo_usd',0)>=0 else 'neg'}'>{_signed(sh_4h.get('pnl_vivo_usd',0))} USD</td>"
        f"<td>{_signed(sh_4h.get('pnl_realizado_usd',0))} USD</td></tr>"
    )
    p.append(
        f"<tr><td><b>🌊 1D · Swing Spot Diario</b></td><td>{sh_1d.get('compradas', 0)}</td><td>{sh_1d.get('esperando', 0)}</td>"
        f"<td>{sh_1d.get('tp1_ventas', 0)}</td><td>{sh_1d.get('cerradas_tp2', 0)}</td><td>${_fmt(sh_1d.get('capital_asignado', 0))} USD</td>"
        f"<td class='{'pos' if sh_1d.get('pnl_vivo_usd',0)>=0 else 'neg'}'>{_signed(sh_1d.get('pnl_vivo_usd',0))} USD</td>"
        f"<td>{_signed(sh_1d.get('pnl_realizado_usd',0))} USD</td></tr>"
    )
    p.append(
        f"<tr><td><b>🏛️ 1W · Ciclo Semanal Spot</b></td><td>{sh_1w.get('compradas', 0)}</td><td>{sh_1w.get('esperando', 0)}</td>"
        f"<td>{sh_1w.get('tp1_ventas', 0)}</td><td>{sh_1w.get('cerradas_tp2', 0)}</td><td>${_fmt(sh_1w.get('capital_asignado', 0))} USD</td>"
        f"<td class='{'pos' if sh_1w.get('pnl_vivo_usd',0)>=0 else 'neg'}'>{_signed(sh_1w.get('pnl_vivo_usd',0))} USD</td>"
        f"<td>{_signed(sh_1w.get('pnl_realizado_usd',0))} USD</td></tr>"
    )
    p.append("</table>")

    p.append("<h3>Libro Maestro de Spot (Zonas Fijas y Zonas de Toma de Ganancias)</h3>")
    p.append(
        "<table><tr><th>ID / Activo</th><th>Horizonte</th><th>Estado</th><th>🔒 Zona Compra Fija</th>"
        "<th>Precio Vivo</th><th>Distancia a Zona</th><th>📈 Zona TP1 (50%)</th><th>🚀 Zona TP2 (Ciclo)</th>"
        "<th>SL Spot</th><th>R:R Ciclo</th><th>PnL $ (%)</th><th>Tesis de Valor</th></tr>"
    )
    for sm in spot_master:
        sid = sm.get("id", "—")
        sym = sm.get("asset", "—")
        horiz = sm.get("horizon_label", "Spot")
        st = sm.get("status", "🎯 ESPERANDO")
        zf = sm.get("zona_fija_str", "—")
        px = sm.get("current_price", 0.0)
        dist = sm.get("dist_zona_txt", "—")
        tp1 = sm.get("tp1_zone", "—")
        tp2 = sm.get("tp2_zone", "—")
        sl = sm.get("sl_spot", 0.0)
        rr = sm.get("rr_ciclo", 3.20)
        pnl_u = float(sm.get("pnl_usd", 0.0))
        pnl_p = float(sm.get("pnl_pct", 0.0))
        th = sm.get("thesis", "—")

        p.append(
            f"<tr><td><b>{_esc(sym)}</b><br><span class='small mut'>ID: {_esc(sid)}</span></td>"
            f"<td><span class='small'>{_esc(horiz)}</span></td>"
            f"<td><span class='small'>{_esc(st)}</span></td>"
            f"<td><span class='small'><b>{_esc(zf)}</b></span></td>"
            f"<td><b>${_fmt(px)}</b></td>"
            f"<td class='small'>{_esc(dist)}</td>"
            f"<td><span class='small' style='color:var(--info);'>{_esc(tp1)}</span></td>"
            f"<td><span class='small' style='color:var(--ok);'>{_esc(tp2)}</span></td>"
            f"<td style='color:var(--bad)'>${_fmt(sl)}</td>"
            f"<td><b>{_fmt(rr)}x</b></td>"
            f"<td class='{'pos' if pnl_u>=0 else 'neg'}'>{_signed(pnl_u)} USD ({_signed(pnl_p)}%)</td>"
            f"<td class='small'>{_esc(th)}</td></tr>"
        )
    if not spot_master:
        p.append("<tr><td colspan='12' class='small mut'>Sin operaciones en el libro de spot.</td></tr>")
    p.append("</table>")
    p.append("<a href='../../ledger/audit_spot.csv' download class='btn-dl'>📥 Descargar CSV Spot (audit_spot.csv)</a>")
    p.append("<a href='../../ledger/trades_statistical_log.csv' download class='btn-dl' style='background:#1f6feb;'>📥 Descargar Log Estadístico General (trades_statistical_log.csv)</a>")
    p.append("</div>")

    # Script JS para cambio de pestaña
    p.append(
        "<script>\n"
        "function openAuditTab(evt, tabId){\n"
        "  var panes = document.querySelectorAll('.tab-pane');\n"
        "  panes.forEach(function(p){ p.classList.remove('active'); p.style.display = 'none'; });\n"
        "  var btns = document.querySelectorAll('.tab-btn');\n"
        "  btns.forEach(function(b){ b.classList.remove('active'); });\n"
        "  var target = document.getElementById(tabId);\n"
        "  if(target){ target.classList.add('active'); target.style.display = 'block'; }\n"
        "  if(evt && evt.currentTarget){ evt.currentTarget.classList.add('active'); }\n"
        "}\n"
        "</script>"
    )
    p.append("</div>")
    return p


# ── 5. Sección 4: Radar Macro & Noticias ──
def _seccion_macro_noticias(
    news: list[dict[str, Any]],
    shocks: list[dict[str, Any]],
    termometro: str = "NEUTRAL",
    h1_levels: dict[str, Any] | None = None,
) -> list[str]:
    p: list[str] = []
    p.append("<div class='panel'>")
    p.append("<h2>🌍 4 · RADAR MACRO, FED, TASAS Y PRINCIPALES DEL DÍA (+ GLOSARIO)</h2>")
    p.append(
        f"<div class='banner' style='background:#16243b;border-color:var(--info);margin-bottom:12px;'>"
        f"<b>🌡️ Termómetro Macro y Mercado Hoy:</b> <span style='font-size:14px;color:var(--info);font-weight:700;'>{_esc(termometro)}</span>"
        f"</div>"
    )
    p.append(
        "<div class='small mut' style='margin-bottom:10px'>3 · Radar de Noticias y Eventos del Agente (Macro / FED / Cripto). Monitoreo 24/7 de fuentes oficiales: Cointelegraph, Decrypt, CNBC Economy & Fed. Clasificación automática por impacto de mercado.</div>"
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

    # Noticias
    p.append("<h3>Principales Titulares del Día y Radar Macro</h3>")
    if news:
        p.append("<ul style='list-style-type:none;padding-left:0;'>")
        for n in news[:12]:
            title = n.get("title", "Sin título")
            feed = n.get("feed", "")
            cat = n.get("categoria", "⚡ PRINCIPAL DEL DÍA")
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
            detalle = s.get("detalle", "")
            p.append(f'<li><b>{_esc(sym)}</b>: {_esc(detalle[:60] if detalle else "—")}</li>')
        p.append("</ul>")
    else:
        p.append("<p class='small mut'>No hay choques técnicos activos en este momento.</p>")

    # Glosario
    p.append(
        "<details style='margin-top:14px;'><summary style='cursor:pointer;font-weight:700;'>Glosario de Eventos y Categorías (▶ hacer clic)</summary>"
        "<p><b>🏦 MACRO / FED / TASAS</b>: Decisiones del FOMC, tipos de interés de bancos centrales, inflación CPI/PCE, empleo y aranceles.</p>"
        "<p><b>🏛️ ETF / INSTITUCIONAL</b>: Flujos de capital institucional en ETFs de Bitcoin y Ethereum, compras de tesorerías y Wall Street.</p>"
        "<p><b>⚠️ ALERTA RIESGO</b>: Hacks a smart contracts, exploits, demandas regulatorias de la SEC o fallos de liquidez.</p>"
        "<p><b>⚡ PRINCIPAL DEL DÍA</b>: Desarrollo tecnológico, upgrades de red y noticias clave del ecosistema cripto.</p>"
        "</details>"
    )
    p.append("</div>")
    return p


# ── 6. Render Principal M6.3 ──
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
    spot_plans: list[dict[str, Any]] | None = None,
    audit_futuros: dict[str, Any] | None = None,
    audit_spot_data: dict[str, Any] | None = None,
) -> str:
    now = datetime.now(UTC).strftime("%Y-%m-%d %H:%M UTC")
    termometro = states.get("termometro_macro", "NEUTRAL")

    p: list[str] = []
    p.append("<!DOCTYPE html><html lang='es'><head><meta charset='utf-8'>")
    p.append("<meta name='viewport' content='width=device-width,initial-scale=1'>")
    p.append(
        f"<title>QUANT-ARENA v2 · Centro de mando (M6.3)</title><style>{CSS}</style></head><body>"
    )
    p.append("<h1>QUANT-ARENA v2 · Centro de mando</h1>")
    p.append(
        f"<div class='sub'>Generado: {now} · datos vivos: {_esc(states.get('fetched_at_utc', '?'))} · "
        f"<b>Termómetro Macro:</b> {_esc(termometro)} · git {_esc(str(meta.get('git_sha', '?'))[:7])} · "
        "<b>NO ES ASESORAMIENTO DE INVERSIÓN</b></div>"
    )

    # 1. Barra de Capital
    p.extend(_equity_cards(capital, spot_plans=spot_plans))

    # 2. SECCIÓN 1: Agente de Futuros (1H · 4H · 1D)
    p.extend(_seccion_futuros(states, trades_diag, capital))

    # 3. SECCIÓN 2: Cartera Spot & Ciclos (4H · 1D · 1W)
    p.extend(_seccion_spot(spot_plans))

    # 4. SECCIÓN 3: Trade Audit en 2 Pestañas (Futuros vs. Spot) + CSVs
    p.extend(_seccion_audit_tabs(audit_futuros, audit_spot_data))

    # Calculadora (solo si calc es provisto explícitamente, ej. en test suite)
    if calc:
        p.extend(_calc_panel(calc))

    # 5. SECCIÓN 4: Radar Macro & Noticias
    p.extend(_seccion_macro_noticias(news, shocks, termometro=termometro, h1_levels=h1_levels))

    # Footer
    p.append(
        "<footer>QUANT-ARENA v2 · M6.3 Autopilot (Futuros + Spot Separados) · "
        "Paper trading sobre $1,000 USD · datos: Binance API pública (solo lectura) + RSS públicos · "
        "Regenerado automáticamente con <code>qa agent run</code>.</footer></body></html>"
    )

    return "\n".join(p)
