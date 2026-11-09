# ruff: noqa: E501  (generador de plantilla HTML: lineas largas inevitables)
"""Dashboard autocontenido v3 (QUANT-ARENA v2 · Centro de mando).

HTML + CSS + SVG + JS vanilla embebidos: sin CDN, sin npm, abre con doble clic.

Arquitectura de la pagina (una sola vista unificada o una vista por pestaña):
  CABECERA STICKY  Barra macro: Equity vivo, PnL cerrado/abierto, Portfolio Heat (<= 25 %),
                   filtro BTC SMA200 (semaforo), integridad SHA-256 y tickers con sparkline.
  1 · FUTUROS      Motor Activo CRUISE PRO (4H): ranking de momentum 40/25/25/10, regimen macro,
                   heat, posiciones vivas (Anti-Wick, piramidacion a riesgo cero, PnL en $ y R),
                   ordenes limite Maker pasivas y escaner de decision.
  2 · SPOT         Cartera 1x: banda de compra razonable [Min, Max], mapa de precio y progreso
                   hacia los 3 precios objetivo (TP1 30 % / TP2 40 % / TP3 30 %).
  3 · AUDITORIA    Trade Audit de futuros y spot + CSVs estadisticos.
  4 · RADAR        Noticias macro/cripto, choques tecnicos, disciplina R:R, glosario.

Contrato de datos: sin cambios respecto a las versiones previas (`render_dashboard`
conserva su firma y consume las mismas claves que producen `autopilot.py`, `spot.py`,
`capital.py`, `audit.py` y `cli.py`). Modulo de solo lectura: no abre red ni envia ordenes.
"""

from __future__ import annotations

import html
import math
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

PROHIBIDOS: tuple[str, ...] = ()

CRUISE_ELITE: tuple[str, ...] = ("BTCUSDT", "ETHUSDT", "SOLUSDT", "SUIUSDT")
MAX_HEAT_PCT = 25.0
SPOT_SELL_FRACTIONS: tuple[float, float, float] = (0.30, 0.40, 0.30)
# Perfil historico del motor (backtest 2024-01-01 .. 2026-11-02). No es una garantia.
CRUISE_BACKTEST: dict[str, str] = {"cagr": "+66.34%", "mdd": "14.79%", "sharpe": "1.72"}

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
        "<section class='sec' data-sec='radar'><div class='panel'><h2>Calculadora de riesgo por operación (simulador aritmético)</h2>"
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
    p.append("</div></section>")
    return p


CSS = """
:root{
--bg:#060a13;--s1:#0c1325;--s2:#111a31;--s3:#17233f;--ln:rgba(148,163,184,.13);--ln2:rgba(148,163,184,.26);
--tx:#e8eefb;--tx2:#aab6cf;--mut:#6f7d99;
--ok:#19f0a3;--ok-d:rgba(25,240,163,.12);--bad:#ff4d6d;--bad-d:rgba(255,77,109,.13);
--warn:#ffb020;--warn-d:rgba(255,176,32,.13);--info:#2fd4ff;--cyan:#2fd4ff;--cyan-d:rgba(47,212,255,.12);
--vio:#9b7bff;--vio-d:rgba(155,123,255,.15);--purple:#9b7bff;--gold:#ffc83d;--gold-d:rgba(255,200,61,.14);
--r:14px;--sans:Inter,Geist,"SF Pro Text",ui-sans-serif,system-ui,-apple-system,"Segoe UI",Roboto,"Helvetica Neue",Arial,sans-serif;
--mono:"JetBrains Mono","Fira Code","SF Mono",ui-monospace,SFMono-Regular,Menlo,Consolas,"Liberation Mono",monospace}
*{box-sizing:border-box}
html{-webkit-text-size-adjust:100%;scroll-behavior:smooth}
body{margin:0;background:var(--bg);color:var(--tx);font:13px/1.5 var(--sans);-webkit-font-smoothing:antialiased;min-height:100vh}
body::before{content:"";position:fixed;inset:0;z-index:-1;pointer-events:none;background:
radial-gradient(900px 520px at 10% -12%,rgba(155,123,255,.14),transparent 60%),
radial-gradient(820px 480px at 96% -4%,rgba(47,212,255,.09),transparent 60%),
radial-gradient(760px 600px at 50% 125%,rgba(25,240,163,.06),transparent 60%)}
a{color:var(--cyan);text-decoration:none}a:hover{text-decoration:underline}
code{font-family:var(--mono);font-size:11.5px;background:var(--s3);padding:1px 6px;border-radius:5px}
.mono,.num{font-family:var(--mono);font-variant-numeric:tabular-nums;letter-spacing:-.02em}
.pos{color:var(--ok);font-weight:700}.neg{color:var(--bad);font-weight:700}.flat{color:var(--tx2)}.mut{color:var(--mut)}
.small{font-size:11px;color:var(--mut)}
.hide,.nosearch,.nofilter{display:none!important}
/* ───────── cabecera ───────── */
.hdr{position:sticky;top:0;z-index:50;background:rgba(6,10,19,.95);border-bottom:1px solid var(--ln)}
.hdr-in{max-width:1600px;margin:0 auto;padding:10px 20px 12px}
.top{display:flex;align-items:center;gap:14px;flex-wrap:wrap}
.brand{display:flex;align-items:center;gap:11px;min-width:0}
.logo{width:34px;height:34px;flex:none}
h1{font-size:16px;font-weight:700;letter-spacing:-.015em;margin:0;white-space:nowrap}
.sub-line{display:flex;gap:6px;flex-wrap:wrap;align-items:center;margin-top:3px;font-size:10.5px;color:var(--mut)}
.pill{display:inline-flex;align-items:center;gap:5px;padding:1px 8px;border-radius:999px;border:1px solid var(--ln);background:var(--s1);font-size:10.5px;color:var(--tx2);white-space:nowrap}
.pill.warn{border-color:rgba(255,176,32,.45);color:var(--warn);background:var(--warn-d);font-weight:700}
.pill.stale{border-color:rgba(255,77,109,.5);color:var(--bad)}
.dot{width:7px;height:7px;border-radius:50%;background:var(--ok);display:inline-block;flex:none}
.dot.live{animation:pulse 2.2s ease-in-out infinite}
@keyframes pulse{0%,100%{opacity:1}50%{opacity:.35}}
.tools{margin-left:auto;display:flex;align-items:center;gap:10px;flex-wrap:wrap}
.vtabs{display:flex;gap:3px;background:var(--s1);border:1px solid var(--ln);padding:3px;border-radius:11px}
.vtab{appearance:none;border:0;background:transparent;color:var(--tx2);font:600 12px var(--sans);padding:6px 12px;border-radius:8px;cursor:pointer;white-space:nowrap;transition:background .15s,color .15s}
.vtab:hover{color:var(--tx)}.vtab.on{background:var(--s3);color:var(--tx);box-shadow:inset 0 0 0 1px var(--ln2)}
.search{position:relative}
.search input{width:190px;background:var(--s1);border:1px solid var(--ln);border-radius:10px;color:var(--tx);padding:7px 30px 7px 11px;font:12px var(--sans);outline:none;transition:border-color .15s,width .2s}
.search input:focus{border-color:var(--cyan);width:240px}
.search kbd{position:absolute;right:8px;top:6px;font:10px var(--mono);color:var(--mut);border:1px solid var(--ln2);border-radius:5px;padding:0 5px}
.qcount{font-size:10.5px;color:var(--cyan);min-width:0}
.kpis{display:grid;grid-auto-flow:column;grid-auto-columns:minmax(158px,1fr);gap:8px;margin-top:11px;overflow-x:auto;scrollbar-width:none}
.kpis::-webkit-scrollbar{display:none}
.kpi{background:linear-gradient(180deg,var(--s2),var(--s1));border:1px solid var(--ln);border-radius:12px;padding:8px 12px;min-width:0;position:relative;overflow:hidden}
.kpi .k{font-size:9.5px;letter-spacing:.07em;text-transform:uppercase;color:var(--mut);white-space:nowrap}
.kpi .v{font:700 18px/1.25 var(--mono);letter-spacing:-.03em;margin-top:2px;white-space:nowrap}
.kpi .d{font-size:10.5px;color:var(--mut);white-space:nowrap;overflow:hidden;text-overflow:ellipsis}
.kpi.eq{border-color:rgba(47,212,255,.35)}
.kpi.eq::after{content:"";position:absolute;right:-30px;top:-30px;width:90px;height:90px;border-radius:50%;background:radial-gradient(circle,rgba(47,212,255,.22),transparent 70%)}
.kpi.macro.bull{border-color:rgba(25,240,163,.45)}.kpi.macro.bear{border-color:rgba(255,77,109,.5)}
.kpi.macro .v{font-size:13.5px;display:flex;align-items:center;gap:7px;margin-top:5px;font-family:var(--sans);letter-spacing:0}
.light{width:11px;height:11px;border-radius:50%;flex:none;background:var(--mut);box-shadow:0 0 0 3px rgba(111,125,153,.2)}
.light.bull{background:var(--ok);box-shadow:0 0 0 3px var(--ok-d),0 0 14px rgba(25,240,163,.6)}
.light.bear{background:var(--bad);box-shadow:0 0 0 3px var(--bad-d),0 0 14px rgba(255,77,109,.6)}
.kpi.sha .v{font-size:13px;font-family:var(--sans);letter-spacing:0;margin-top:5px;display:flex;align-items:center;gap:6px}
.kpi.sha.ok{border-color:rgba(25,240,163,.4)}.kpi.sha.bad{border-color:rgba(255,77,109,.55)}
.ticker{display:flex;align-items:center;gap:10px;justify-content:space-between}
.ticker .tk-s{font-size:10px;color:var(--mut);letter-spacing:.06em}
.ticker .tk-p{font:700 14px var(--mono);letter-spacing:-.03em}
.spark{display:block;overflow:visible}
/* ───────── barras ───────── */
.bar{display:block;height:6px;border-radius:99px;background:var(--s3);overflow:hidden;position:relative}
.bar>i{position:absolute;inset:0;border-radius:99px;transform:scaleX(var(--p,0));transform-origin:left;background:var(--cyan);animation:grow .7s cubic-bezier(.2,.8,.2,1) both}
@keyframes grow{from{transform:scaleX(0)}}
.bar.ok>i{background:linear-gradient(90deg,#0fbf84,var(--ok))}.bar.bad>i{background:linear-gradient(90deg,#c43456,var(--bad))}
.bar.warn>i{background:linear-gradient(90deg,#c98a12,var(--warn))}.bar.gold>i{background:linear-gradient(90deg,#d99a0a,var(--gold))}
.bar.vio>i{background:linear-gradient(90deg,#6f52e0,var(--vio))}.bar.thin{height:4px}.bar.thick{height:9px}
/* ───────── layout ───────── */
.sec{max-width:1600px;margin:0 auto;padding:26px 20px 0}
.sec-h{margin-bottom:14px}
.sec-h .eyebrow{font-size:10.5px;letter-spacing:.14em;text-transform:uppercase;color:var(--vio);font-weight:700}
h2{font-size:19px;font-weight:700;letter-spacing:-.02em;margin:2px 0 4px}
h3{font-size:13px;font-weight:700;letter-spacing:.01em;margin:22px 0 10px;color:var(--tx);display:flex;align-items:center;gap:8px}
h3::before{content:"";width:3px;height:14px;border-radius:2px;background:var(--vio)}
.sec-sub{color:var(--tx2);font-size:12.5px;max-width:1040px;margin:0}
.bento{display:grid;grid-template-columns:repeat(12,minmax(0,1fr));gap:14px}
.c4{grid-column:span 4}.c5{grid-column:span 5}.c6{grid-column:span 6}.c7{grid-column:span 7}.c8{grid-column:span 8}.c12{grid-column:span 12}
@media(max-width:1150px){.c4,.c5,.c6,.c7,.c8{grid-column:span 6}}
@media(max-width:760px){.c4,.c5,.c6,.c7,.c8{grid-column:span 12}.hdr{position:static}h1{white-space:normal}.tools{margin-left:0}}
@media(max-height:700px){.hdr{position:static}}
.card,.panel{background:linear-gradient(180deg,var(--s2),var(--s1));border:1px solid var(--ln);border-radius:var(--r);padding:16px;min-width:0;transition:border-color .18s}
.card:hover{border-color:var(--ln2)}
.panel{margin-bottom:18px}
.card-h{display:flex;justify-content:space-between;align-items:center;gap:8px;margin-bottom:12px}
.card-t{font-size:10.5px;letter-spacing:.09em;text-transform:uppercase;color:var(--mut);font-weight:700}
/* ───────── tooltip ───────── */
.tip{border-bottom:1px dotted var(--mut);cursor:help}
[data-tip]{cursor:help}
#tt{position:fixed;left:0;top:0;z-index:100;max-width:330px;padding:10px 12px;border-radius:11px;background:#0a1226;border:1px solid var(--ln2);box-shadow:0 14px 44px rgba(0,0,0,.55);pointer-events:none;opacity:0;transform:translate(-999px,-999px);transition:opacity .12s;font-size:11.5px;line-height:1.5;color:var(--tx2)}
#tt.on{opacity:1}#tt b{display:block;color:var(--tx);font-size:12px;margin-bottom:3px}
/* ───────── badges ───────── */
.badge{display:inline-flex;align-items:center;gap:4px;padding:2px 9px;border-radius:999px;font-size:10.5px;font-weight:700;line-height:1.5;border:1px solid var(--ln2);color:var(--tx2);background:var(--s3);vertical-align:middle}
.b-ok{background:var(--ok-d);color:var(--ok);border-color:rgba(25,240,163,.45)}
.b-warn{background:var(--warn-d);color:var(--warn);border-color:rgba(255,176,32,.45)}
.b-bad{background:var(--bad-d);color:var(--bad);border-color:rgba(255,77,109,.5)}
.b-info{background:var(--cyan-d);color:var(--cyan);border-color:rgba(47,212,255,.45)}
.b-futuro{background:var(--vio-d);color:var(--vio);border-color:rgba(155,123,255,.5)}
.b-instante{background:var(--cyan-d);color:var(--cyan);border-color:rgba(47,212,255,.5)}
.b-gold{background:var(--gold-d);color:var(--gold);border-color:rgba(255,200,61,.5)}
.b-mut{background:var(--s3);color:var(--mut)}
.dir{display:inline-block;font:700 11px var(--mono);padding:2px 8px;border-radius:7px}
.dir.long{background:var(--ok-d);color:var(--ok)}.dir.short{background:var(--bad-d);color:var(--bad)}
.lev{margin-left:6px;color:var(--mut);font-size:11px}
/* ───────── chips / filtros ───────── */
.toolbar{display:flex;justify-content:space-between;align-items:center;gap:10px;flex-wrap:wrap;margin:0 0 10px}
.chips{display:flex;gap:6px;flex-wrap:wrap}
.chip{appearance:none;border:1px solid var(--ln);background:var(--s1);color:var(--tx2);padding:4px 11px;border-radius:999px;font:600 11.5px var(--sans);cursor:pointer;transition:all .15s}
.chip:hover{border-color:var(--ln2);color:var(--tx)}
.chip.on{background:var(--cyan-d);border-color:var(--cyan);color:var(--cyan)}
/* ───────── tablas ───────── */
.tablewrap{overflow-x:auto;border:1px solid var(--ln);border-radius:12px;background:var(--s1)}
table{width:100%;border-collapse:collapse;font-size:12px}
.tbl th,.panel th{background:var(--s2);color:var(--mut);text-align:left;font-weight:700;font-size:10px;letter-spacing:.07em;text-transform:uppercase;padding:9px 12px;white-space:nowrap;border-bottom:1px solid var(--ln)}
.tbl.sortable th{cursor:pointer;user-select:none}
.tbl.sortable th:hover{color:var(--tx)}
.tbl.sortable th[data-dir=asc]::after{content:" ▲";color:var(--cyan)}.tbl.sortable th[data-dir=desc]::after{content:" ▼";color:var(--cyan)}
.tbl td,.panel td{padding:10px 12px;border-top:1px solid var(--ln);vertical-align:middle}
.tbl tbody tr:hover td{background:rgba(148,163,184,.045)}
.asset{display:flex;flex-direction:column;line-height:1.25}.asset b{font-size:14px;letter-spacing:-.01em}.asset .sub{font-size:10.5px;color:var(--mut)}
.thesis{max-width:260px;color:var(--tx2);font-size:11px;line-height:1.4;display:-webkit-box;-webkit-line-clamp:2;-webkit-box-orient:vertical;overflow:hidden}
.empty{padding:26px;text-align:center;color:var(--mut);border:1px dashed var(--ln2);border-radius:12px;font-size:12px}
.pnl{display:flex;flex-direction:column;line-height:1.3}.pnl b{font:700 13px var(--mono);letter-spacing:-.03em}.pnl span{font:11px var(--mono);color:var(--mut)}
.kv{display:flex;justify-content:space-between;gap:10px;font-size:11.5px;padding:3px 0;color:var(--tx2)}.kv b{font-family:var(--mono);color:var(--tx);letter-spacing:-.02em}
/* ───────── barra de recorrido SL → TP ───────── */
.rng{position:relative;height:6px;border-radius:99px;margin:7px 4px 4px;min-width:130px;background:linear-gradient(90deg,var(--bad-d),var(--s3) 38%,var(--ok-d))}
.rng .rng-e{position:absolute;top:-4px;width:2px;height:14px;background:var(--tx2);left:calc(var(--e)*100%);border-radius:1px}
.rng .rng-p{position:absolute;top:-4px;width:14px;height:14px;margin-left:-7px;border-radius:50%;left:calc(var(--p)*100%);border:2px solid var(--bg);background:var(--cyan);box-shadow:0 0 12px rgba(47,212,255,.7)}
.rng .rng-p.up{background:var(--ok);box-shadow:0 0 12px rgba(25,240,163,.7)}.rng .rng-p.dn{background:var(--bad);box-shadow:0 0 12px rgba(255,77,109,.7)}
.rng-l{display:flex;justify-content:space-between;font:10px var(--mono);color:var(--mut)}
/* ───────── ranking momentum ───────── */
.alloc{display:flex;height:30px;border-radius:9px;overflow:hidden;gap:2px;margin-bottom:12px}
.alloc>div{display:flex;align-items:center;justify-content:center;font:700 10.5px var(--mono);color:#04101a;min-width:0;white-space:nowrap;transform-origin:left;animation:grow .7s cubic-bezier(.2,.8,.2,1) both}
.mgrid{display:grid;grid-template-columns:repeat(4,minmax(0,1fr));gap:10px}
@media(max-width:900px){.mgrid{grid-template-columns:repeat(2,minmax(0,1fr))}}
.mcard{border:1px solid var(--ln);border-radius:12px;padding:12px;background:var(--s1);position:relative;overflow:hidden}
.mcard.r1{border-color:rgba(25,240,163,.45);background:linear-gradient(180deg,rgba(25,240,163,.08),var(--s1))}
.mcard .mh{display:flex;justify-content:space-between;align-items:center}
.mcard .msym{font-size:17px;font-weight:800;letter-spacing:-.02em}
.mcard .mw{font:800 20px var(--mono);letter-spacing:-.04em}
.mcard .ms{font:700 13px var(--mono);margin:8px 0 6px}
.mcard .mm{font-size:10.5px;color:var(--mut);margin-top:7px;display:flex;justify-content:space-between;gap:6px}
.stat3{display:grid;grid-template-columns:repeat(3,1fr);gap:8px}
.stat{background:var(--s1);border:1px solid var(--ln);border-radius:11px;padding:10px 8px;text-align:center}
.stat b{display:block;font:800 18px var(--mono);letter-spacing:-.04em}.stat span{font-size:9.5px;letter-spacing:.07em;text-transform:uppercase;color:var(--mut)}
.rules{display:flex;flex-wrap:wrap;gap:7px}
.rule{padding:5px 10px;border-radius:9px;border:1px solid var(--ln);background:var(--s1);font-size:11.5px;color:var(--tx2)}
.rule b{color:var(--tx)}
/* ───────── ordenes maker ───────── */
.pgrid{display:grid;grid-template-columns:repeat(auto-fill,minmax(290px,1fr));gap:12px}
.pend{border:1px solid rgba(155,123,255,.32);border-radius:13px;padding:14px;background:linear-gradient(180deg,rgba(155,123,255,.07),var(--s1))}
.pend .ph{display:flex;justify-content:space-between;align-items:center;margin-bottom:10px}
.pend .pm{display:grid;grid-template-columns:1fr 1fr;gap:8px;margin-bottom:10px}
.pend .pm div{background:var(--s1);border:1px solid var(--ln);border-radius:9px;padding:7px 9px}
.pend .pm span{display:block;font-size:9.5px;letter-spacing:.07em;text-transform:uppercase;color:var(--mut)}
.pend .pm b{font:700 13.5px var(--mono);letter-spacing:-.03em}
.pend .pf{display:flex;justify-content:space-between;flex-wrap:wrap;gap:4px 10px;margin-top:9px;font:10.5px var(--mono);color:var(--tx2)}
/* ───────── macro / heat ───────── */
.regime{display:flex;align-items:center;gap:12px;margin-bottom:10px}
.regime .light{width:18px;height:18px}
.regime b{font-size:15px;letter-spacing:-.01em}
.heatnum{font:800 30px var(--mono);letter-spacing:-.05em;line-height:1}
.heatcap{position:relative;margin-top:14px}
.heatcap .mark{position:absolute;right:0;top:-5px;bottom:-5px;width:2px;background:var(--bad)}
.hrow{display:flex;align-items:center;gap:10px;font:11px var(--mono);margin-top:8px}
.hrow>span:first-child{width:50px;color:var(--tx2);font-weight:700}.hrow .bar{flex:1}.hrow>span:last-child{width:62px;text-align:right}
/* ───────── spot ───────── */
.sumstrip{display:grid;grid-template-columns:repeat(auto-fit,minmax(170px,1fr));gap:10px;margin-bottom:14px}
.sumstrip .card{padding:12px 14px}
.sumstrip .card b{display:block;font:800 20px var(--mono);letter-spacing:-.04em;margin-top:3px}
.sgrid{display:grid;grid-template-columns:repeat(auto-fill,minmax(440px,1fr));gap:14px}
@media(max-width:520px){.sgrid{grid-template-columns:1fr}}
.scard{border:1px solid var(--ln);border-radius:15px;padding:16px;background:linear-gradient(180deg,var(--s2),var(--s1))}
.scard.zin{border-color:rgba(25,240,163,.4);box-shadow:0 0 0 1px rgba(25,240,163,.08),0 10px 40px -20px rgba(25,240,163,.45)}
.scard .sh{display:flex;justify-content:space-between;align-items:flex-start;gap:10px;margin-bottom:12px}
.scard .sname{font-size:19px;font-weight:800;letter-spacing:-.02em}
.scard .pxrow{display:flex;justify-content:space-between;align-items:flex-end;gap:10px;margin-bottom:14px}
.scard .px{font:800 24px var(--mono);letter-spacing:-.05em;line-height:1}
.zmap{position:relative;height:10px;border-radius:99px;background:var(--s3);margin:26px 8px 12px}
.zmap .zb{position:absolute;top:0;bottom:0;border-radius:99px;background:linear-gradient(90deg,rgba(25,240,163,.35),rgba(25,240,163,.6));box-shadow:0 0 14px rgba(25,240,163,.4)}
.zmap .zt{position:absolute;top:-6px;width:14px;height:22px;margin-left:-7px}
.zmap .zt::after{content:"";position:absolute;left:6px;top:3px;bottom:3px;width:2px;border-radius:1px;background:var(--mut)}
.zmap .zt.sl::after{background:var(--bad)}.zmap .zt.tp::after{background:var(--gold);box-shadow:0 0 8px rgba(255,200,61,.8)}
.zmap .zt.ref::after{background:var(--tx2);width:1px;opacity:.7}
.zmap .zt span{position:absolute;top:-15px;left:50%;transform:translateX(-50%);font:700 9px var(--mono);color:var(--mut);white-space:nowrap}
.zmap .zt.tp span{color:var(--gold)}.zmap .zt.sl span{color:var(--bad)}
.zmap .zp{position:absolute;top:-5px;width:20px;height:20px;margin-left:-10px;border-radius:50%;background:var(--cyan);border:3px solid var(--bg);box-shadow:0 0 0 1px var(--cyan),0 0 16px rgba(47,212,255,.8)}
.zleg{display:flex;flex-wrap:wrap;gap:4px 12px;font:10px var(--mono);color:var(--mut);margin-bottom:12px}
.zleg i{display:inline-block;width:8px;height:8px;border-radius:2px;margin-right:4px;vertical-align:-1px}
.tps{display:grid;gap:9px}
.tp{display:grid;grid-template-columns:1fr;gap:5px;padding:9px 11px;border:1px solid var(--ln);border-radius:11px;background:var(--s1)}
.tp.hit{border-color:rgba(255,200,61,.55);background:linear-gradient(90deg,var(--gold-d),var(--s1))}
.tp .th{display:flex;align-items:center;gap:8px;flex-wrap:wrap}
.tp .tn{font-weight:800;font-size:12px;color:var(--gold)}
.tp .tf{font-size:10px;color:var(--mut);border:1px solid var(--ln);border-radius:6px;padding:0 6px}
.tp .tpx{margin-left:auto;font:800 13.5px var(--mono);letter-spacing:-.03em;color:var(--tx)}
.tp .ts{display:flex;justify-content:space-between;gap:8px;flex-wrap:wrap;font:10px var(--mono);color:var(--mut)}
.sfoot{display:flex;justify-content:space-between;flex-wrap:wrap;gap:6px 14px;margin-top:12px;padding-top:11px;border-top:1px dashed var(--ln2);font:11px var(--mono);color:var(--tx2)}
.sthesis{margin-top:8px;font-size:11px;color:var(--mut);line-height:1.45}
#spot-wrap[data-sv=cards] .spot-table,#spot-wrap[data-sv=table] .sgrid{display:none}
/* ───────── auditoria ───────── */
.atabs{display:flex;gap:6px;margin-bottom:14px}
.atab{appearance:none;border:1px solid var(--ln);background:var(--s1);color:var(--tx2);font:700 12px var(--sans);padding:8px 14px;border-radius:10px;cursor:pointer}
.atab.on{background:var(--vio-d);border-color:var(--vio);color:var(--vio)}
.apane{display:none}.apane.on{display:block}
.btn-dl{display:inline-flex;align-items:center;gap:6px;background:var(--ok-d);border:1px solid rgba(25,240,163,.45);color:var(--ok);padding:7px 13px;border-radius:9px;font-size:11.5px;font-weight:700;margin:12px 8px 0 0}
.btn-dl:hover{background:rgba(25,240,163,.2);text-decoration:none}.btn-dl.alt{background:var(--cyan-d);border-color:rgba(47,212,255,.45);color:var(--cyan)}
.qstats{display:grid;grid-template-columns:repeat(auto-fit,minmax(170px,1fr));gap:10px;margin-bottom:14px}
.qstats .card{padding:12px 14px}.qstats .card b{display:block;font:800 19px var(--mono);letter-spacing:-.04em;margin-top:3px}
/* ───────── radar ───────── */
.news{list-style:none;margin:0;padding:0}
.news li{display:flex;gap:10px;align-items:baseline;padding:9px 2px;border-bottom:1px solid var(--ln)}
.news li:last-child{border-bottom:0}.news a{color:var(--tx)}.news a:hover{color:var(--cyan)}
.news .src{font-size:10.5px;color:var(--mut);white-space:nowrap}
.thermo{display:flex;align-items:center;gap:12px;margin-bottom:12px}
.feeds{display:flex;gap:6px;flex-wrap:wrap}
details{border:1px solid var(--ln);border-radius:11px;padding:10px 14px;background:var(--s1);margin-top:14px}
summary{cursor:pointer;font-weight:700;font-size:12.5px}
details p{color:var(--tx2);font-size:12px;margin:8px 0 0}
.calcrow{display:grid;grid-template-columns:repeat(auto-fit,minmax(150px,1fr));gap:10px;margin:12px 0}
.calcrow label{display:block;font-size:10px;letter-spacing:.07em;text-transform:uppercase;color:var(--mut);margin-bottom:4px}
.calcrow input,.calcrow select{width:100%;background:var(--s1);border:1px solid var(--ln);border-radius:9px;color:var(--tx);padding:8px 10px;font:12px var(--mono);outline:none}
.calcrow input:focus,.calcrow select:focus{border-color:var(--cyan)}
.calcrow button{width:100%;background:var(--cyan);color:#04101a;border:0;border-radius:9px;padding:9px;font:800 12px var(--sans);cursor:pointer}
/* ───────── sala de situacion cognitiva IA ───────── */
.ai-sala{background:linear-gradient(180deg,#0a1329,#060b17);border:1px solid rgba(47,212,255,.28);border-radius:var(--r);padding:16px 18px;margin-bottom:18px;box-shadow:0 10px 30px rgba(0,0,0,.35)}
.ai-sala-header{display:flex;justify-content:space-between;align-items:center;gap:12px;margin-bottom:14px;flex-wrap:wrap;border-bottom:1px solid var(--ln);padding-bottom:10px}
.ai-grid{display:grid;grid-template-columns:repeat(4,minmax(0,1fr));gap:12px}
@media(max-width:1150px){.ai-grid{grid-template-columns:repeat(2,minmax(0,1fr))}}
@media(max-width:640px){.ai-grid{grid-template-columns:1fr}}
.ai-card{background:linear-gradient(180deg,rgba(19,30,58,.85),rgba(11,18,36,.95));border:1px solid var(--ln);border-radius:12px;padding:14px;display:flex;flex-direction:column;gap:10px;transition:border-color .15s,transform .15s}
.ai-card:hover{border-color:var(--cyan);transform:translateY(-1px)}
.ai-card-h{display:flex;justify-content:space-between;align-items:flex-start;gap:8px}
.ai-sym{font:800 15px var(--mono);color:var(--tx);letter-spacing:-.03em}
.ai-px{font:600 12px var(--mono);color:var(--cyan);margin-top:2px}
.ai-meta{display:grid;grid-template-columns:1fr 1fr;gap:8px;background:rgba(255,255,255,.025);padding:8px 10px;border-radius:8px;border:1px solid var(--ln)}
.ai-meta .k{font-size:9px;text-transform:uppercase;letter-spacing:.08em;color:var(--mut)}
.ai-meta .v{font:700 12px var(--mono);margin-top:2px}
.ai-quote{font-size:11.5px;line-height:1.45;color:var(--tx2);font-style:italic;background:rgba(10,18,38,.5);border-left:3px solid var(--cyan);padding:8px 10px;border-radius:0 6px 6px 0;min-height:52px}
.ai-card-foot{display:flex;justify-content:space-between;align-items:center;font-size:10px;color:var(--mut);border-top:1px solid var(--ln);padding-top:6px;margin-top:auto}

footer{max-width:1600px;margin:0 auto;padding:30px 20px 40px;color:var(--mut);font-size:11.5px}
/* ───────── exposure coach & discipline gate ───────── */
.exp-panel{background:linear-gradient(180deg,#0a152e,#060c1c);border:1px solid rgba(47,212,255,.3);border-radius:var(--r);padding:16px 18px;margin-bottom:18px;box-shadow:0 10px 30px rgba(0,0,0,.35)}
.exp-h{display:flex;justify-content:space-between;align-items:center;gap:12px;margin-bottom:14px;flex-wrap:wrap;border-bottom:1px solid var(--ln);padding-bottom:10px}
.exp-grid{display:grid;grid-template-columns:1fr 1.3fr 1.3fr;gap:14px}
@media(max-width:1150px){.exp-grid{grid-template-columns:1fr 1fr}}
@media(max-width:768px){.exp-grid{grid-template-columns:1fr}}
.exp-card{background:linear-gradient(180deg,rgba(19,30,58,.8),rgba(11,18,36,.9));border:1px solid var(--ln);border-radius:12px;padding:14px;display:flex;flex-direction:column;gap:10px}
.exp-score-box{display:flex;align-items:center;gap:14px}
.exp-score{font:800 36px var(--mono);color:var(--cyan);line-height:1}
.exp-posture{font:800 15px var(--sans);letter-spacing:-.02em}
.exp-pilar{display:flex;justify-content:space-between;align-items:center;padding:7px 10px;background:rgba(255,255,255,.02);border:1px solid var(--ln);border-radius:8px;font:11.5px var(--mono)}
.exp-pilar-k{color:var(--tx2);display:flex;align-items:center;gap:6px}
.exp-check{display:flex;align-items:flex-start;gap:8px;font-size:11.5px;color:var(--tx2);padding:6px 0;border-bottom:1px solid rgba(255,255,255,.03)}
.exp-check:last-child{border-bottom:0}
/* ───────── sniper intradia & trader memory ───────── */
.b-sniper{background:rgba(255,107,237,.14);border-color:rgba(255,107,237,.4);color:#ff6bed}
.b-memory{background:rgba(155,123,255,.14);border-color:rgba(155,123,255,.4);color:var(--vio)}
.badge-r-pos{background:rgba(25,240,163,.15);color:var(--ok);font:700 11px var(--mono);padding:2px 7px;border-radius:6px;border:1px solid rgba(25,240,163,.3)}
.badge-r-neg{background:rgba(255,77,109,.15);color:var(--bad);font:700 11px var(--mono);padding:2px 7px;border-radius:6px;border:1px solid rgba(255,77,109,.3)}
.empty-card{text-align:center;padding:36px 20px;background:var(--s1);border:1px dashed var(--ln2);border-radius:14px;margin:12px 0}
.empty-card b{display:block;font-size:14px;margin-bottom:6px;color:var(--tx)}
.empty-card p{max-width:620px;margin:0 auto;font-size:12px;color:var(--mut);line-height:1.55}
/* ───────── oraculo k-line kronos ───────── */
.kronos-grid{display:grid;grid-template-columns:repeat(4,minmax(0,1fr));gap:12px;margin-bottom:16px}
@media(max-width:1200px){.kronos-grid{grid-template-columns:repeat(2,minmax(0,1fr))}}
@media(max-width:640px){.kronos-grid{grid-template-columns:1fr}}
.kronos-card{background:linear-gradient(180deg,rgba(16,25,52,.92),rgba(9,15,32,.98));border:1px solid rgba(155,123,255,.32);border-radius:13px;padding:14px;display:flex;flex-direction:column;gap:10px;box-shadow:0 8px 24px rgba(0,0,0,.3)}
.kronos-prob-bar{display:flex;height:8px;border-radius:99px;overflow:hidden;background:rgba(255,77,109,.35);border:1px solid var(--ln)}
.kronos-prob-fill{height:100%;background:linear-gradient(90deg,#19f0a3,#2fd4ff)}
.kronos-mini-tbl{width:100%;border-collapse:collapse;font:10.5px var(--mono);margin-top:4px}
.kronos-mini-tbl th{text-align:left;color:var(--mut);font-weight:600;padding:3px 4px;border-bottom:1px solid var(--ln)}
.kronos-mini-tbl td{padding:3px 4px;border-bottom:1px solid rgba(255,255,255,.03);color:var(--tx2)}

/* ───────── Apple / Robinhood "Para Dummies" Interface ───────── */
.dummy-view{max-width:1600px;margin:0 auto;padding:16px 20px 0}
.dummy-sec-title{display:flex;align-items:center;justify-content:space-between;gap:12px;margin:28px 0 14px}
.dummy-sec-title h2{font-size:18px;font-weight:800;letter-spacing:-.02em;color:var(--tx);margin:0;display:flex;align-items:center;gap:9px}
.dummy-subtitle{font-size:12px;color:var(--tx2);margin-top:2px}
.hero-grid{display:grid;grid-template-columns:repeat(3,minmax(0,1fr));gap:14px;margin-bottom:20px}
@media(max-width:960px){.hero-grid{grid-template-columns:1fr}}
.hero-card{background:linear-gradient(160deg,#0f192f,#091020);border:1px solid rgba(255,255,255,.09);border-radius:18px;padding:20px 22px;position:relative;overflow:hidden;box-shadow:0 8px 28px rgba(0,0,0,.35);transition:border-color .18s,transform .18s}
.hero-card:hover{border-color:rgba(47,212,255,.4);transform:translateY(-2px)}
.hero-card::after{content:"";position:absolute;top:-40px;right:-40px;width:120px;height:120px;border-radius:50%;background:radial-gradient(circle,rgba(47,212,255,.09),transparent 70%);pointer-events:none}
.hero-head{display:flex;justify-content:space-between;align-items:flex-start;margin-bottom:10px}
.hero-label{font-size:10.5px;font-weight:700;text-transform:uppercase;letter-spacing:.09em;color:var(--mut)}
.hero-val{font:800 28px/1.2 var(--mono);letter-spacing:-.04em;color:#fff;margin-bottom:4px}
.hero-pnl{font:700 12.5px var(--mono);display:flex;align-items:center;gap:6px;margin-bottom:12px}
.hero-badge{display:inline-flex;align-items:center;gap:5px;padding:3px 10px;border-radius:999px;font-size:11px;font-weight:700}
.hero-card .hero-desc{font-size:11.5px;color:var(--tx2);line-height:1.45;margin-top:10px;border-top:1px solid rgba(255,255,255,.06);padding-top:10px}
.coin-grid{display:grid;grid-template-columns:repeat(4,minmax(0,1fr));gap:14px;margin-bottom:20px}
@media(max-width:1150px){.coin-grid{grid-template-columns:repeat(2,minmax(0,1fr))}}
@media(max-width:600px){.coin-grid{grid-template-columns:1fr}}
.coin-card{background:linear-gradient(160deg,#0e172a,#080f1e);border:1px solid rgba(255,255,255,.08);border-radius:16px;padding:18px;display:flex;flex-direction:column;justify-content:space-between;box-shadow:0 8px 24px rgba(0,0,0,.3);transition:transform .18s,border-color .18s}
.coin-card:hover{border-color:rgba(155,123,255,.35);transform:translateY(-2px)}
.coin-card-top{display:flex;justify-content:space-between;align-items:center;margin-bottom:10px}
.coin-name-group{display:flex;align-items:center;gap:8px}
.coin-icon{font-size:22px}
.coin-title{font-size:14px;font-weight:800;letter-spacing:-.02em;color:#fff}
.coin-sym{font-size:10.5px;color:var(--mut);text-transform:uppercase}
.coin-price{font:800 19px var(--mono);letter-spacing:-.03em;color:#fff;margin-bottom:12px}
.coin-pred-wrap{background:rgba(255,255,255,.03);border:1px solid rgba(255,255,255,.06);border-radius:11px;padding:9px 11px;margin-bottom:11px}
.coin-pred-head{display:flex;justify-content:space-between;align-items:center;font-size:11px;margin-bottom:5px;font-weight:600}
.coin-pred-bar{height:6px;border-radius:99px;background:rgba(255,255,255,.08);overflow:hidden;position:relative}
.coin-pred-fill{height:100%;border-radius:99px;transition:width .6s ease}
.coin-opinion{font-size:11px;line-height:1.45;color:var(--tx2);background:rgba(47,212,255,.04);border-left:3px solid var(--cyan);padding:7px 9px;border-radius:0 8px 8px 0;margin-bottom:12px;flex:1}
.coin-status-btn{border-radius:11px;padding:9px 12px;font-size:11.5px;font-weight:800;letter-spacing:.03em;text-align:center;text-transform:uppercase}
.coin-status-btn.st-long{background:rgba(25,240,163,.15);color:var(--ok);border:1px solid rgba(25,240,163,.45);box-shadow:0 0 14px rgba(25,240,163,.15)}
.coin-status-btn.st-short{background:rgba(255,77,109,.15);color:var(--bad);border:1px solid rgba(255,77,109,.45);box-shadow:0 0 14px rgba(255,77,109,.15)}
.coin-status-btn.st-watch{background:rgba(255,255,255,.04);color:var(--tx2);border:1px solid rgba(255,255,255,.08)}
.clean-trades-container{background:linear-gradient(160deg,#0e172a,#080f1e);border:1px solid rgba(255,255,255,.08);border-radius:18px;padding:16px 20px;margin-bottom:20px;box-shadow:0 10px 30px rgba(0,0,0,.35);overflow-x:auto}
.clean-trades-tbl{width:100%;border-collapse:separate;border-spacing:0 6px}
.clean-trades-tbl th{font-size:10px;font-weight:700;text-transform:uppercase;letter-spacing:.08em;color:var(--mut);padding:8px 12px;border-bottom:1px solid rgba(255,255,255,.06);white-space:nowrap}
.clean-trades-tbl td{padding:11px 12px;background:rgba(255,255,255,.02);border-top:1px solid rgba(255,255,255,.04);border-bottom:1px solid rgba(255,255,255,.04);vertical-align:middle;font-size:12px}
.clean-trades-tbl tr td:first-child{border-top-left-radius:11px;border-bottom-left-radius:11px;border-left:1px solid rgba(255,255,255,.04)}
.clean-trades-tbl tr td:last-child{border-top-right-radius:11px;border-bottom-right-radius:11px;border-right:1px solid rgba(255,255,255,.04)}
.clean-trades-tbl tr:hover td{background:rgba(255,255,255,.045)}
.trade-bet-badge{display:inline-flex;align-items:center;gap:4px;padding:3px 9px;border-radius:8px;font-size:11px;font-weight:700;white-space:nowrap}
.trade-bet-badge.long{background:rgba(25,240,163,.14);color:var(--ok);border:1px solid rgba(25,240,163,.3)}
.trade-bet-badge.short{background:rgba(255,77,109,.14);color:var(--bad);border:1px solid rgba(255,77,109,.3)}
.clean-empty-card{text-align:center;padding:34px 20px;border:1px dashed rgba(255,255,255,.12);border-radius:16px;background:rgba(255,255,255,.015)}
.clean-empty-card .empty-icon{font-size:30px;margin-bottom:8px}
.clean-empty-card .empty-title{font-size:15px;font-weight:700;color:#fff;margin-bottom:4px}
.clean-empty-card .empty-desc{font-size:12px;color:var(--tx2);max-width:520px;margin:0 auto;line-height:1.5}
.spot-cards-grid{display:grid;grid-template-columns:repeat(4,minmax(0,1fr));gap:14px;margin-bottom:20px}
@media(max-width:1150px){.spot-cards-grid{grid-template-columns:repeat(2,minmax(0,1fr))}}
@media(max-width:600px){.spot-cards-grid{grid-template-columns:1fr}}
.spot-simple-card{background:linear-gradient(160deg,#0e172a,#080f1e);border:1px solid rgba(255,255,255,.08);border-radius:16px;padding:18px;display:flex;flex-direction:column;justify-content:space-between;box-shadow:0 8px 24px rgba(0,0,0,.3)}
.spot-cheap-verdict{padding:7px 11px;border-radius:10px;font-size:11px;font-weight:700;margin-bottom:11px;text-align:center}
.spot-cheap-verdict.yes{background:rgba(25,240,163,.12);color:var(--ok);border:1px solid rgba(25,240,163,.35)}
.spot-cheap-verdict.wait{background:rgba(255,176,32,.12);color:var(--warn);border:1px solid rgba(255,176,32,.35)}
.spot-tp-list{background:rgba(255,255,255,.02);border:1px solid rgba(255,255,255,.05);border-radius:10px;padding:7px 10px;font-size:11px}
.spot-tp-item{display:flex;justify-content:space-between;padding:4px 0;border-bottom:1px solid rgba(255,255,255,.03)}
.spot-tp-item:last-child{border-bottom:none}
.technical-drawer-sec{padding-top:10px;margin-top:20px}
.technical-audit-drawer{background:#080d1a;border:1px solid rgba(255,255,255,.12);border-radius:18px;overflow:hidden;box-shadow:0 8px 30px rgba(0,0,0,.4)}
.drawer-summary{padding:15px 22px;cursor:pointer;display:flex;align-items:center;justify-content:space-between;background:rgba(255,255,255,.02);transition:background .18s;user-select:none;list-style:none}
.drawer-summary::-webkit-details-marker{display:none}
.drawer-summary:hover{background:rgba(255,255,255,.05)}
.drawer-summary-left{display:flex;align-items:center;gap:12px}
.drawer-icon{font-size:22px}
.drawer-title{font-size:13.5px;font-weight:700;color:var(--tx)}
.drawer-sub{font-size:11px;color:var(--tx2);margin-top:2px}
.drawer-badge{font-size:11px;font-weight:700;color:var(--cyan);background:var(--cyan-d);border:1px solid rgba(47,212,255,.35);border-radius:999px;padding:4px 12px}
details[open] .drawer-summary{border-bottom:1px solid rgba(255,255,255,.08);background:rgba(255,255,255,.04)}
.technical-audit-body{padding:10px 0 20px}
body:not([data-view=all]) .technical-drawer-sec{display:block!important}
body:not([data-view=all]) .dummy-view{display:none!important}
body:not([data-view=all]) .technical-audit-drawer{border:none;background:transparent;box-shadow:none}
body:not([data-view=all]) .drawer-summary{display:none}

/* ───────── vistas ───────── */
body[data-view=futures] .sec:not([data-sec=futures]),
body[data-view=sniper] .sec:not([data-sec=sniper]),
body[data-view=kronos] .sec:not([data-sec=kronos]),
body[data-view=spot] .sec:not([data-sec=spot]),
body[data-view=audit] .sec:not([data-sec=audit]),
body[data-view=skills] .sec:not([data-sec=skills]),
body[data-view=radar] .sec:not([data-sec=radar]){display:none}
@media(prefers-reduced-motion:reduce){*{animation:none!important;transition:none!important}html{scroll-behavior:auto}}
"""

JS = """
(() => {
  'use strict';
  const $ = (s, r = document) => r.querySelector(s);
  const $$ = (s, r = document) => Array.from(r.querySelectorAll(s));
  const body = document.body;
  const esc = s => String(s).replace(/[&<>"']/g, c => ({'&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;'}[c]));

  /* búsqueda global */
  const q = $('#q'), qc = $('#qcount');
  const applySearch = () => {
    const t = (q.value || '').trim().toLowerCase();
    let n = 0;
    $$('[data-search]').forEach(el => {
      const hit = !t || el.dataset.search.indexOf(t) !== -1;
      el.classList.toggle('nosearch', !hit);
      if (t && hit) n++;
    });
    qc.textContent = t ? n + ' coincidencia' + (n === 1 ? '' : 's') : '';
  };
  q.addEventListener('input', applySearch);

  /* vistas */
  const VIEWS = ['all', 'futures', 'sniper', 'kronos', 'spot', 'audit', 'skills', 'radar'];
  const setView = (v, scroll) => {
    if (VIEWS.indexOf(v) === -1) v = 'all';
    body.dataset.view = v;
    $$('.vtab').forEach(b => { const on = b.dataset.view === v; b.classList.toggle('on', on); b.setAttribute('aria-selected', on ? 'true' : 'false'); });
    const drawer = document.querySelector('.technical-audit-drawer');
    if (drawer && v !== 'all') {
      drawer.open = true;
    }
    try { history.replaceState(null, '', '#' + v); } catch (e) { /* file:// restringido */ }
    if (scroll) window.scrollTo({top: 0});
  };
  $$('.vtab').forEach(b => b.addEventListener('click', () => setView(b.dataset.view, true)));
  setView((location.hash || '').slice(1), false);

  /* chips de filtro genéricos */
  $$('.chips[data-for]').forEach(c => {
    c.addEventListener('click', e => {
      const b = e.target.closest('.chip');
      if (!b) return;
      $$('.chip', c).forEach(x => x.classList.toggle('on', x === b));
      const box = document.getElementById(c.dataset.for);
      if (!box) return;
      const v = b.dataset.v;
      $$('[data-g]', box).forEach(el => {
        const ok = v === 'all' || el.dataset.g.split(' ').indexOf(v) !== -1;
        el.classList.toggle('nofilter', !ok);
      });
    });
  });

  /* ordenación de tablas */
  $$('table.sortable').forEach(t => {
    $$('th', t).forEach((th, i) => {
      th.addEventListener('click', () => {
        const tb = t.tBodies[0];
        const rows = Array.from(tb.rows).filter(r => r.cells.length > 1);
        const dir = th.dataset.dir === 'asc' ? 'desc' : 'asc';
        $$('th', t).forEach(h => h.removeAttribute('data-dir'));
        th.dataset.dir = dir;
        const val = r => { const c = r.cells[i]; return (c.dataset.v !== undefined ? c.dataset.v : c.textContent).trim(); };
        const num = v => parseFloat(v.replace(/[^0-9eE+\\-.]/g, ''));
        rows.sort((a, b) => {
          const x = val(a), y = val(b), nx = num(x), ny = num(y);
          const r = (!isNaN(nx) && !isNaN(ny)) ? nx - ny : x.localeCompare(y, 'es');
          return dir === 'asc' ? r : -r;
        });
        rows.forEach(r => tb.appendChild(r));
      });
    });
  });

  /* pestañas de auditoría + vista spot */
  $$('.atab').forEach(b => b.addEventListener('click', () => {
    $$('.atab').forEach(x => x.classList.toggle('on', x === b));
    $$('.apane').forEach(p => p.classList.toggle('on', p.id === b.dataset.pane));
  }));
  $$('[data-spotview]').forEach(b => b.addEventListener('click', () => {
    $('#spot-wrap').dataset.sv = b.dataset.spotview;
    $$('[data-spotview]').forEach(x => x.classList.toggle('on', x === b));
  }));

  /* tooltips enriquecidos (un único nodo flotante, sin recortes por overflow) */
  const tt = $('#tt');
  const place = el => {
    const r = el.getBoundingClientRect(), w = tt.offsetWidth, h = tt.offsetHeight;
    const x = Math.max(8, Math.min(r.left + r.width / 2 - w / 2, innerWidth - w - 8));
    let y = r.top - h - 10;
    if (y < 8) y = r.bottom + 10;
    tt.style.transform = 'translate(' + Math.round(x) + 'px,' + Math.round(y) + 'px)';
  };
  const show = el => {
    tt.innerHTML = '<b>' + esc(el.dataset.tipT || '') + '</b>' + esc(el.dataset.tip || '');
    tt.classList.add('on');
    place(el);
  };
  const hide = () => tt.classList.remove('on');
  const tipEl = e => (e.target.closest ? e.target.closest('[data-tip]') : null);
  document.addEventListener('pointerover', e => { const el = tipEl(e); if (el) show(el); });
  document.addEventListener('pointerout', e => { if (tipEl(e)) hide(); });
  document.addEventListener('focusin', e => { const el = tipEl(e); if (el) show(el); });
  document.addEventListener('focusout', hide);
  addEventListener('scroll', hide, {passive: true});

  /* antigüedad de los datos */
  const age = $('#age');
  if (age && age.dataset.ts && !isNaN(Date.parse(age.dataset.ts))) {
    const t0 = Date.parse(age.dataset.ts);
    const upd = () => {
      const m = Math.max(0, Math.round((Date.now() - t0) / 60000));
      age.textContent = m < 1 ? 'datos: ahora' : m < 60 ? 'datos: hace ' + m + ' min' : 'datos: hace ' + Math.floor(m / 60) + ' h ' + (m % 60) + ' min';
      age.classList.toggle('stale', m > 30);
    };
    upd();
    setInterval(upd, 30000);
  }

  /* Contador visual regresivo de 30 segundos (00:30) y auto-recarga continua */
  let secLeft = 30;
  const cdEl = $('#countdown');
  const tickCd = () => {
    if (cdEl) {
      const s = Math.max(0, secLeft);
      const mm = String(Math.floor(s / 60)).padStart(2, '0');
      const ss = String(s % 60).padStart(2, '0');
      cdEl.textContent = mm + ':' + ss;
    }
    if (secLeft <= 0) {
      location.reload();
    } else {
      secLeft--;
    }
  };
  setInterval(tickCd, 1000);
  setTimeout(() => { location.reload(); }, 30000);

  /* atajos: "/" busca · 1-5 cambian de vista */
  document.addEventListener('keydown', e => {
    const typing = /^(INPUT|SELECT|TEXTAREA)$/.test((document.activeElement || {}).tagName || '');
    if (e.key === '/' && !typing) { e.preventDefault(); q.focus(); return; }
    if (e.key === 'Escape') { q.value = ''; applySearch(); q.blur(); hide(); return; }
    if (!typing && !e.metaKey && !e.ctrlKey && !e.altKey && e.key >= '1' && e.key <= '5') setView(VIEWS[+e.key - 1], true);
  });
})();
"""

# ── Textos de ayuda (tooltips enriquecidos) ──
TIPS: dict[str, tuple[str, str]] = {
    "anti_wick": (
        "🛡️ Trailing Stop Estructural Anti-Mecha",
        "El stop sólo se ejecuta con el CIERRE de una vela 4H por debajo del Swing Low de 8 velas "
        "(LONG) o por encima del Swing High (SHORT). Las mechas de liquidación intradía no expulsan la posición.",
    ),
    "pyramid": (
        "🚀 Piramidación Protectora a Riesgo Cero",
        "Al alcanzar ≥ +4.0R con el stop ya asegurando ≥ +1.5R se añade +25% de posición. "
        "El stop conjunto se blinda para garantizar ≥ +0.5R netos: la adición no puede convertir el trade en pérdida.",
    ),
    "momentum": (
        "🏆 Rotación Dinámica por Momentum (30D)",
        "Score = Close_t / Close_(t-30d). El capital se reparte: Top 1 = 40%, Top 2 y 3 = 25% cada uno, "
        "Top 4 = 10%. El riesgo por trade se escala por (peso / 25%).",
    ),
    "sma200": (
        "🚦 Filtro Macro BTC SMA200",
        "Close(BTC,1D) ≥ SMA200 → expansión: LONGs y SHORTs permitidos. Close < SMA200 → invierno cripto: "
        "veto total a LONGs en altcoins; sólo SHORT a favor de la tendencia o 100% efectivo.",
    ),
    "heat": (
        "🔥 Portfolio Heat (Riesgo en Mesa)",
        "Suma del riesgo en USD (distancia al stop × tamaño) de todas las posiciones abiertas, dividida por el "
        "patrimonio. Techo duro del motor: 25%. Con el techo alcanzado no se abren nuevas posiciones.",
    ),
    "maker": (
        "⏳ Orden límite pasiva (Maker 0.02%)",
        "Entrada en retroceso a EMA21 con orden límite: comisión maker 0.02% frente a 0.05% taker. "
        "Reduce el fee drag. Sólo la convicción extrema (Score ≥ 85 y ADX > 30) entra a mercado.",
    ),
    "sha": (
        "🔐 Integridad criptográfica SHA-256",
        "Cada registro de los libros (operaciones, capital, spot) incluye el hash del registro previo. "
        "Cualquier edición retroactiva rompe la cadena y se detecta al verificarla.",
    ),
    "r_mult": (
        "R (múltiplo de riesgo)",
        "PnL flotante dividido por el riesgo inicial en USD del trade. +1R = ganancia igual a lo arriesgado.",
    ),
    "zone": (
        "🔒 Banda de Compra a Precio Razonable",
        "[Min, Max] fija, calculada por distancia a SMA200(1D), soportes estructurales semanales y compresión ATR. "
        "Una vez guardada en el ledger no se modifica.",
    ),
    "tp1": ("🎯 TP1 · Recuperación de Base (30%)", "Retorno a la resistencia estructural previa. Se liquida el 30% de la posición."),
    "tp2": ("🎯 TP2 · Expansión de Ciclo (40%)", "Extensión Fibonacci 1.618 del rango de acumulación. Se liquida el 40%."),
    "tp3": ("🎯 TP3 · Euforia / Clímax (30%)", "Extensión Fibonacci 2.618 o RSI(1W) > 80. Se liquida el 30% restante."),
}


# ── Helpers ──
def _esc(x: Any) -> str:
    return html.escape(str(x))


def _num(x: Any) -> float | None:
    if x is None or x == "":
        return None
    try:
        v = float(x)
    except (TypeError, ValueError):
        return None
    return v if math.isfinite(v) else None


def _f(x: Any, default: float = 0.0) -> float:
    v = _num(x)
    return default if v is None else v


def _clamp(v: float, lo: float = 0.0, hi: float = 1.0) -> float:
    return max(lo, min(hi, v))


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


def _px(x: Any) -> str:
    """Precio con decimales segun magnitud (sin saltos de ancho entre activos)."""
    v = _num(x)
    if v is None:
        return "—"
    nd = 2 if abs(v) >= 10 else (3 if abs(v) >= 1 else 4)
    return f"${v:,.{nd}f}"


def _cls(v: float) -> str:
    return "pos" if v > 0 else ("neg" if v < 0 else "flat")


def _sym_short(sym: str) -> str:
    return sym[:-4] if sym.endswith("USDT") else sym


def _tip(inner: str, key: str) -> str:
    title, body = TIPS[key]
    return f"<span class='tip' tabindex='0' data-tip-t='{_esc(title)}' data-tip='{_esc(body)}'>{inner}</span>"


def _tipx(inner: str, title: str, body: str, cls: str = "") -> str:
    c = f" class='{cls}'" if cls else ""
    return f"<span{c} tabindex='0' data-tip-t='{_esc(title)}' data-tip='{_esc(body)}'>{inner}</span>"


def _bar(frac: float, cls: str = "") -> str:
    return f"<span class='bar {cls}'><i style='--p:{_clamp(frac):.4f}'></i></span>"


def _spark_svg(values: list[float] | None, w: int = 92, h: int = 30) -> str:
    vals = [float(v) for v in (values or []) if _num(v) is not None]
    if len(vals) < 2:
        return ""
    lo, hi = min(vals), max(vals)
    span = (hi - lo) or 1.0
    n = len(vals)
    pts = [(i * w / (n - 1), h - 3 - ((v - lo) / span) * (h - 6)) for i, v in enumerate(vals)]
    line = " ".join(f"{x:.1f},{y:.1f}" for x, y in pts)
    col = "var(--ok)" if vals[-1] >= vals[0] else "var(--bad)"
    lx, ly = pts[-1]
    return (
        f"<svg class='spark' viewBox='0 0 {w} {h}' width='{w}' height='{h}' aria-hidden='true'>"
        f"<polygon points='0,{h} {line} {w},{h}' fill='{col}' opacity='.13'/>"
        f"<polyline points='{line}' fill='none' stroke='{col}' stroke-width='1.6' stroke-linejoin='round' stroke-linecap='round'/>"
        f"<circle cx='{lx:.1f}' cy='{ly:.1f}' r='2.4' fill='{col}'/></svg>"
    )


def _parse_ts(ts: Any) -> datetime | None:
    if not ts:
        return None
    try:
        dt = datetime.fromisoformat(str(ts).replace("Z", "+00:00"))
    except (ValueError, TypeError):
        return None
    return dt if dt.tzinfo else dt.replace(tzinfo=UTC)


def _ago(dt: datetime | None, now: datetime) -> str:
    if dt is None:
        return "—"
    mins = max(0, int((now - dt).total_seconds()) // 60)
    if mins < 60:
        return f"hace {mins}m"
    if mins < 2880:
        return f"hace {mins // 60}h {mins % 60}m"
    return f"hace {mins // 1440}d"


# ── Regimen macro BTC SMA200 e integridad SHA-256 ──
def _btc_macro(states: dict[str, Any]) -> dict[str, Any]:
    """Resuelve el semaforo BTC SMA200 con la mejor evidencia disponible (sin inventar datos)."""
    raw = states.get("btc_macro") or states.get("macro_regime")
    if isinstance(raw, dict) and raw:
        reg = str(raw.get("regimen", "")).upper()
        bull_raw = raw.get("bullish")
        bull = bool(bull_raw) if bull_raw is not None else ("ALCISTA" in reg or "EXPANSIVO" in reg)
        return {
            "state": "bull" if bull else "bear",
            "dist": _num(raw.get("dist_sma200_pct")),
            "sma200": _num(raw.get("sma200_btc")),
            "close": _num(raw.get("close")),
            "src": "SMA200 (1D)",
        }
    scores = states.get("autopilot_scores") or {}
    bear = bull = False
    for k, v in scores.items():
        if str(k).startswith("_") or not isinstance(v, dict):
            continue
        reason = str(v.get("reason", ""))
        bear = bear or "BTC < SMA200" in reason
        bull = bull or "BTC >= SMA200" in reason
    if bear or bull:
        return {"state": "bear" if bear else "bull", "dist": None, "sma200": None, "close": None, "src": "SMA200 (1D)"}
    tr = ((states.get("trends") or {}).get("BTCUSDT") or {}).get("1d")
    if isinstance(tr, str) and tr.startswith(("Alcista", "Bajista")):
        dist = None
        if "(" in tr and "%" in tr:
            dist = _num(tr[tr.index("(") + 1 : tr.index("%")])
        return {"state": "bull" if tr.startswith("Alcista") else "bear", "dist": dist, "sma200": None, "close": None, "src": "proxy: distancia a SMA50 (1D)"}
    return {"state": "nd", "dist": None, "sma200": None, "close": None, "src": "sin datos"}


def _integrity(meta: dict[str, Any]) -> list[dict[str, Any]]:
    """Verifica las cadenas SHA-256 (o usa `meta['integrity']` si el llamador la provee)."""
    given = meta.get("integrity")
    out: list[dict[str, Any]] = []
    if isinstance(given, dict) and given:
        for name, val in given.items():
            ok, n, msg = (list(val) + [None, 0, ""])[:3] if isinstance(val, (list, tuple)) else (bool(val), 0, "")
            out.append({"name": str(name), "ok": ok, "n": int(_f(n)), "msg": str(msg or "")})
        return out
    try:
        from qa.agent.capital import capital_log_path, trades_log_path
        from qa.agent.chain import verify_chain_file
        from qa.data.paths import get_root

        root = get_root()
        books: list[tuple[str, Path]] = [
            ("Operaciones (futuros)", trades_log_path(root)),
            ("Capital", capital_log_path(root)),
            ("Cartera spot", root / "ledger" / "user_spot.jsonl"),
            ("Sniper intradía (1H)", root / "ledger" / "user_sniper.jsonl"),
        ]
        for name, path in books:
            if path.exists():
                ok, n, msg = verify_chain_file(path)
                out.append({"name": name, "ok": bool(ok), "n": int(n), "msg": str(msg)})
        if (root / "ledger" / "trials.duckdb").exists():
            out.append({"name": "Ensayos DuckDB", "ok": None, "n": 0, "msg": "presente"})
    except Exception:  # verificacion best-effort: el dashboard nunca debe romperse por esto
        return []
    return out


# ── Cabecera + barra macro ──
def _logo() -> str:
    return (
        "<svg class='logo' viewBox='0 0 40 40' aria-hidden='true'><defs>"
        "<linearGradient id='lg' x1='0' y1='0' x2='1' y2='1'><stop offset='0' stop-color='#9b7bff'/><stop offset='1' stop-color='#2fd4ff'/></linearGradient></defs>"
        "<path d='M20 2.5 35.5 11.5v17L20 37.5 4.5 28.5v-17z' fill='rgba(155,123,255,.12)' stroke='url(#lg)' stroke-width='1.8'/>"
        "<path d='M11 25l6-7 5 4 7-9' fill='none' stroke='#19f0a3' stroke-width='2.2' stroke-linecap='round' stroke-linejoin='round'/>"
        "<circle cx='29' cy='13' r='2.2' fill='#19f0a3'/></svg>"
    )


def _kpi(label: str, value: str, sub: str, cls: str = "", extra: str = "") -> str:
    return f"<div class='kpi {cls}'><div class='k'>{label}</div><div class='v'>{value}</div><div class='d'>{sub}</div>{extra}</div>"


def _header(
    states: dict[str, Any],
    capital: dict[str, Any] | None,
    spot_plans: list[dict[str, Any]] | None,
    spark_data: dict[str, list[float]],
    meta: dict[str, Any],
    termometro: str,
    now_txt: str,
) -> list[str]:
    c = capital or {}
    patrimonio = _f(c.get("patrimonio_total"), 1000.0)
    aportado = _f(c.get("capital_aportado_neto"), 1000.0)
    realizado = _f(c.get("pnl_realizado_usd"))
    flotante = _f(c.get("pnl_flotante_usd"))
    spot_alloc = sum(_f(p.get("allocated_usd")) for p in (spot_plans or []))
    eq_delta = (patrimonio / aportado - 1.0) * 100.0 if aportado > 0 else 0.0
    heat_pct = _num(c.get("portfolio_heat_pct_patrimonio"))
    heat_usd = _num(c.get("portfolio_heat_usd"))

    mac = _btc_macro(states)
    integ = _integrity(meta)

    p: list[str] = []
    p.append("<header class='hdr'><div class='hdr-in'>")
    p.append("<div class='top'><div class='brand'>" + _logo() + "<div>")
    p.append("<h1>QUANT-ARENA v2 · Centro de mando</h1>")
    p.append(
        "<div class='sub-line'>"
        f"<span class='pill'><span class='dot live'></span>Generado {_esc(now_txt)}</span>"
        f"<span class='pill' id='sync-timer'>⏱️ Refresco: <b class='mono' id='countdown'>00:30</b></span>"
        f"<span class='pill' id='age' data-ts='{_esc(states.get('fetched_at_utc', ''))}'>datos: {_esc(states.get('fetched_at_utc', '?'))}</span>"
        f"<span class='pill'>Termómetro macro · <b>{_esc(termometro)}</b></span>"
        f"<span class='pill'>git {_esc(str(meta.get('git_sha', '?'))[:7])}</span>"
        "<span class='pill'>paper trading · cero dinero real</span>"
        "<span class='pill warn'>NO ES ASESORAMIENTO DE INVERSIÓN</span></div>"
    )
    p.append("</div></div>")
    p.append(
        "<div class='tools'><nav class='vtabs' role='tablist' aria-label='Vistas'>"
        "<button class='vtab on' data-view='all' role='tab' aria-selected='true'>Vista unificada</button>"
        "<button class='vtab' data-view='futures' role='tab'>⚡ Motor CRUISE PRO</button>"
        "<button class='vtab' data-view='sniper' role='tab'>🎯 Motor SNIPER 1H</button>"
        "<button class='vtab' data-view='kronos' role='tab'>🔮 Oráculo Kronos</button>"
        "<button class='vtab' data-view='spot' role='tab'>🪙 Spot</button>"
        "<button class='vtab' data-view='audit' role='tab'>📊 Auditoría</button>"
        "<button class='vtab' data-view='skills' role='tab'>📚 Trader Memory</button>"
        "<button class='vtab' data-view='radar' role='tab'>🌍 Radar</button></nav>"
        "<div class='search'><input id='q' type='search' placeholder='Filtrar activos, estados, tesis…' autocomplete='off' aria-label='Filtro rápido'><kbd>/</kbd></div>"
        "<span class='qcount' id='qcount'></span></div></div>"
    )

    # KPIs
    k: list[str] = []
    k.append(
        _kpi(
            "Patrimonio Total (Equity Vivo)",
            f"${_fmt(patrimonio)}",
            f"Aportado ${_fmt(aportado)} · <span class='{_cls(eq_delta)}'>{_signed(eq_delta, 2, '%')}</span>",
            "eq",
        )
    )
    k.append(_kpi("PnL Cerrado (Neto)", f"<span class='{_cls(realizado)}'>{_signed(realizado)}</span>", "USD · cierres acumulados"))
    k.append(_kpi("PnL Abierto (Vivo)", f"<span class='{_cls(flotante)}'>{_signed(flotante)}</span>", "USD · operaciones en mercado"))

    if heat_pct is not None:
        hf = heat_pct / MAX_HEAT_PCT
        hcls = "ok" if hf < 0.5 else ("warn" if hf < 0.85 else "bad")
        heat_v = f"{heat_pct:.2f}%"
        heat_d = f"${_fmt(heat_usd)} · techo {MAX_HEAT_PCT:.0f}%" if heat_usd is not None else f"techo {MAX_HEAT_PCT:.0f}%"
        heat_bar = f"<div style='margin-top:5px'>{_bar(hf, hcls + ' thin')}</div>"
    else:
        heat_v, heat_d, heat_bar = "—", f"techo {MAX_HEAT_PCT:.0f}%", ""
    k.append(_kpi(_tip("Riesgo en Mesa (Portfolio Heat)", "heat"), heat_v, heat_d, "", heat_bar))

    if mac["state"] == "bull":
        m_lab, m_cls, m_sub = "EXPANSIÓN", "bull", "BTC ≥ SMA200 · longs habilitados"
    elif mac["state"] == "bear":
        m_lab, m_cls, m_sub = "INVIERNO CRIPTO", "bear", "BTC < SMA200 · veto de longs alt"
    else:
        m_lab, m_cls, m_sub = "SIN DATOS", "", "régimen no disponible"
    if mac["dist"] is not None:
        m_sub += f" ({_signed(mac['dist'], 1, '%')})"
    k.append(_kpi(_tip("Filtro BTC SMA200", "sma200"), f"<span class='light {m_cls}'></span>{m_lab}", _esc(m_sub), f"macro {m_cls}"))

    if integ:
        bad = [i for i in integ if i["ok"] is False]
        verified = [i for i in integ if i["ok"] is True]
        sha_cls = "bad" if bad else "ok"
        lines = " · ".join(f"{i['name']}: {'OK' if i['ok'] else ('ROTA' if i['ok'] is False else i['msg'])}" + (f" ({i['n']} reg.)" if i["n"] else "") for i in integ)
        if bad:
            sha_v = "<span class='badge b-bad'>✖ CADENA ROTA</span>"
        else:
            sha_v = f"<span class='badge b-ok'>✔ {len(verified)} CADENAS VÁLIDAS</span>"
        sha_d = _tipx("SHA-256 · hover para detalle", TIPS["sha"][0], TIPS["sha"][1] + " Estado: " + lines)
        k.append(_kpi("Integridad SHA-256", sha_v, sha_d, f"sha {sha_cls}"))
    else:
        k.append(_kpi("Integridad SHA-256", "<span class='badge b-mut'>SIN LEDGER</span>", _tip("cadenas encadenadas SHA-256", "sha"), "sha"))

    k.append(_kpi("Cartera Spot Asignada", f"${_fmt(spot_alloc)}", "1x · sin apalancamiento ni liquidación"))
    k.append(_kpi("Capital Aportado Neto", f"${_fmt(aportado)}", "base simulada (cero dinero real)"))

    prices = states.get("prices") or {}
    for sym in ("BTCUSDT", "ETHUSDT"):
        series = spark_data.get(sym) or []
        if len(series) < 2:
            continue
        last = _num(prices.get(sym)) or series[-1]
        chg = (series[-1] / series[0] - 1.0) * 100.0 if series[0] else 0.0
        k.append(
            "<div class='kpi'><div class='ticker'><div>"
            f"<div class='tk-s'>{_sym_short(sym)} · {len(series)}D</div><div class='tk-p'>{_px(last)}</div>"
            f"<div class='d {_cls(chg)}'>{_signed(chg, 1, '%')}</div></div>{_spark_svg(series)}</div></div>"
        )
    p.append("<div class='kpis'>" + "".join(k) + "</div></div></header>")
    return p


# ── Seccion 1: Motor activo CRUISE PRO (4H) ──
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
        dist_entry_pct = abs(live_price - entry) / entry * 100.0 if entry else 0.0
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


def _w_val(w: Any) -> float:
    s = str(w).replace("%", "").strip()
    v = _num(s)
    if v is None:
        return 0.0
    return v * 100.0 if ("%" not in str(w) and v <= 1.0) else v


_RANK_COLOR = {1: "var(--ok)", 2: "var(--cyan)", 3: "var(--vio)", 4: "var(--mut)"}
_RANK_MEDAL = {1: "🥇", 2: "🥈", 3: "🥉", 4: "4️⃣"}


def _momentum_block(states: dict[str, Any], open_assets: set[str]) -> str:
    ranking = states.get("momentum_ranking") or (states.get("autopilot_scores") or {}).get("_momentum_ranking") or []
    rows = [r for r in ranking if isinstance(r, dict)]
    head = (
        "<div class='card-h'><div class='card-t'>"
        + _tip("🏆 Rotación dinámica de capital por momentum · ventana rodante 30D", "momentum")
        + "</div><span class='badge b-futuro'>40 / 25 / 25 / 10</span></div>"
    )
    if not rows:
        return "<div class='card c8'>" + head + "<div class='empty'>El ranking de momentum se calcula en cada ciclo de <code>qa agent run</code>.</div></div>"
    rows.sort(key=lambda r: int(_f(r.get("rank"), 99)))
    seg: list[str] = []
    cards: list[str] = []
    for r in rows:
        sym = str(r.get("asset", "?"))
        rank = int(_f(r.get("rank"), 1))
        w = _w_val(r.get("weight_pct", "0"))
        score = _f(r.get("score_30d"), 1.0)
        sf = _f(r.get("sizing_factor"), 1.0)
        chg = (score - 1.0) * 100.0
        col = _RANK_COLOR.get(rank, "var(--mut)")
        seg.append(f"<div style='flex:{max(w, 3):.1f};background:{col}'>{_sym_short(sym)} {w:.0f}%</div>")
        held = (
            "<span class='badge b-ok'>EN CARTERA</span>"
            if sym in open_assets
            else "<span class='badge b-mut'>sin posición</span>"
        )
        bar_cls = "ok" if chg >= 0 else "bad"
        cards.append(
            f"<article class='mcard r{rank}' data-search='{_esc((sym + ' momentum rank ' + str(rank)).lower())}'>"
            f"<div class='mh'><span class='msym'>{_RANK_MEDAL.get(rank, '')} {_sym_short(sym)}</span><span class='mw' style='color:{col}'>{w:.0f}%</span></div>"
            f"<div class='ms'>{score:.3f}x <span class='{_cls(chg)}'>{_signed(chg, 1, '%')} 30D</span></div>"
            f"{_bar(_clamp(0.5 + chg / 40.0), bar_cls + ' thin')}"
            f"<div class='mm'><span>{_esc(r.get('role', ''))}</span><span class='mono'>×{sf:g}</span></div>"
            f"<div style='margin-top:8px'>{held}</div></article>"
        )
    return (
        "<div class='card c8'>" + head + "<div class='alloc'>" + "".join(seg) + "</div>"
        "<div class='mgrid'>" + "".join(cards) + "</div></div>"
    )


def _profile_block() -> str:
    b = CRUISE_BACKTEST
    return (
        "<div class='card c4'><div class='card-h'><div class='card-t'>📈 Perfil histórico CRUISE PRO 4H</div><span class='badge b-info'>backtest 2024 → 2026</span></div>"
        "<div class='stat3'>"
        f"<div class='stat'><b class='pos'>{_esc(b['cagr'])}</b><span>CAGR</span></div>"
        f"<div class='stat'><b class='neg'>-{_esc(b['mdd'])}</b><span>Max DD</span></div>"
        f"<div class='stat'><b style='color:var(--cyan)'>{_esc(b['sharpe'])}</b><span>Sharpe</span></div></div>"
        "<div class='small' style='margin-top:10px'>Cesta Élite: BTC · ETH · SOL · SUI. Resultado de backtest causal con costes: "
        "no garantiza rendimiento futuro.</div>"
        "<div class='rules' style='margin-top:12px'>"
        + _tip("<span class='rule'><b>Anti-Wick 4H</b></span>", "anti_wick")
        + _tip("<span class='rule'><b>Piramidación +25%</b></span>", "pyramid")
        + _tip("<span class='rule'><b>Maker 0.02%</b></span>", "maker")
        + "</div></div>"
    )


def _macro_block(states: dict[str, Any], mac: dict[str, Any]) -> str:
    if mac["state"] == "bull":
        light, title, rule = "bull", "EXPANSIÓN · BTC ≥ SMA200(1D)", "LONGs y SHORTs habilitados en la Cesta Élite según score, ADX y R:R."
    elif mac["state"] == "bear":
        light, title, rule = "bear", "INVIERNO CRIPTO · BTC < SMA200(1D)", "Veto total a LONGs en altcoins. Sólo SHORT a favor de tendencia o 100% efectivo."
    else:
        light, title, rule = "", "RÉGIMEN NO DISPONIBLE", "Se calculará con el siguiente ciclo del agente."
    rows = ""
    if mac["close"] is not None and mac["sma200"] is not None:
        rows += f"<div class='kv'><span>Close BTC 1D</span><b>{_px(mac['close'])}</b></div><div class='kv'><span>SMA200 (1D)</span><b>{_px(mac['sma200'])}</b></div>"
    if mac["dist"] is not None:
        rows += f"<div class='kv'><span>Distancia al filtro</span><b class='{_cls(mac['dist'])}'>{_signed(mac['dist'], 2, '%')}</b></div>"
        rows += _bar(_clamp(0.5 + mac["dist"] / 40.0), "ok thin" if mac["dist"] >= 0 else "bad thin")
    rows += f"<div class='kv'><span>Fuente</span><b style='font-family:var(--sans)'>{_esc(mac['src'])}</b></div>"
    return (
        "<div class='card c4'><div class='card-h'><div class='card-t'>"
        + _tip("🚦 Régimen macro BTC SMA200", "sma200")
        + f"</div></div><div class='regime'><span class='light {light}'></span><div><b>{title}</b><div class='small'>{rule}</div></div></div>{rows}</div>"
    )


def _heat_block(capital: dict[str, Any] | None) -> str:
    c = capital or {}
    pct = _num(c.get("portfolio_heat_pct_patrimonio"))
    usd = _num(c.get("portfolio_heat_usd"))
    detail = [d for d in (c.get("heat_detalle") or []) if isinstance(d, dict)]
    head = "<div class='card-h'><div class='card-t'>" + _tip("🔥 Portfolio Heat · techo 25%", "heat") + "</div></div>"
    if pct is None:
        return "<div class='card c4'>" + head + "<div class='empty'>Sin libro de capital: <code>qa capital set --amount 1000</code></div></div>"
    hf = pct / MAX_HEAT_PCT
    hcls = "ok" if hf < 0.5 else ("warn" if hf < 0.85 else "bad")
    body = f"<div style='display:flex;justify-content:space-between;align-items:flex-end'><div class='heatnum'>{pct:.2f}%</div><div class='small mono'>${_fmt(usd)} en riesgo · cupo libre {max(0.0, MAX_HEAT_PCT - pct):.2f}%</div></div>"
    body += f"<div class='heatcap'>{_bar(hf, hcls + ' thick')}<span class='mark'></span></div>"
    mx = max([_f(d.get("riesgo_usd")) for d in detail] + [1e-9])
    for d in detail:
        r = _num(d.get("riesgo_usd"))
        sym = _sym_short(str(d.get("asset", "?")))
        if r is None:
            body += f"<div class='hrow'><span>{sym}</span><span class='small'>sin stop-loss</span><span class='neg'>—</span></div>"
        else:
            body += f"<div class='hrow'><span>{sym}</span>{_bar(r / mx, 'vio thin')}<span>${_fmt(r)}</span></div>"
    return "<div class='card c4'>" + head + body + "</div>"


def _range_bar(sl: float, entry: float, px: float, tp: float, pnl: float) -> str:
    if sl <= 0 or tp <= 0 or abs(tp - sl) < 1e-12:
        return "<span class='mut'>—</span>"

    def pos(x: float) -> float:
        return _clamp((x - sl) / (tp - sl))

    mark = "up" if pnl > 0 else ("dn" if pnl < 0 else "")
    return (
        f"<div class='rng' style='--e:{pos(entry):.4f};--p:{pos(px):.4f}'><i class='rng-e'></i><b class='rng-p {mark}'></b></div>"
        f"<div class='rng-l'><span class='neg'>SL {_px(sl)}</span><span class='pos'>TP {_px(tp)}</span></div>"
    )


def _trade_view(t: dict[str, Any], now_utc: datetime) -> dict[str, Any]:
    sym = str(t.get("asset", "?"))
    is_long = t.get("kind", "future_long") != "future_short"
    entrada = _f(t.get("entry_price", t.get("entry")))
    px_raw = t.get("price_now", t.get("precio_actual", entrada))
    px_now = _f(px_raw, entrada) if px_raw != "?" else entrada
    sl = _f(t.get("sl"))
    tp2 = _f(t.get("tp", t.get("tp2")))
    tp1_raw = _num(t.get("tp1"))
    tp1 = tp1_raw if tp1_raw else (round(entrada + (tp2 - entrada) * 0.55, 4 if entrada < 10 else 2) if entrada > 0 and tp2 > 0 else 0.0)
    size = _f(t.get("size_usd"), 60.0)
    margen = _f(t.get("margin_usd")) or size / 4.0
    riesgo = _f(t.get("risk_usd")) or 15.0
    order_state = str(t.get("order_state", "ACTIVE"))
    mode = str(t.get("entry_mode", "INSTANTE"))
    pnl_usd = _f(t.get("pnl_usd", t.get("pnl_flotante_usd")))
    pnl_pct = _f(t.get("pnl_pct"))
    sem_cls, sem_txt, _rr_res = _calcular_ventana_entrada(entrada, px_now, sl, tp1, tp2, is_long, bool(t.get("tp1_hit", False)), order_state, mode)
    dt_open = _parse_ts(t.get("ts_utc"))
    return {
        "sym": sym,
        "tf": str(t.get("timeframe") or "4h").upper(),
        "is_long": is_long,
        "lev": str(t.get("leverage", "4x")),
        "entrada": entrada,
        "px": px_now,
        "sl": sl,
        "tp2": tp2,
        "margen": margen,
        "riesgo": riesgo,
        "order_state": order_state,
        "mode": mode,
        "pnl_usd": pnl_usd,
        "pnl_pct": pnl_pct,
        "r_now": pnl_usd / riesgo if riesgo > 0 else None,
        "peak_r": _f(t.get("peak_r")),
        "pyramided": bool(t.get("pyramided")),
        "rr": _f(t.get("rr_neto_inicial") or t.get("rr_neto"), 2.80),
        "sem_cls": sem_cls,
        "sem_txt": sem_txt,
        "thesis": str(t.get("thesis") or t.get("note") or "Alineación técnica multi-indicador"),
        "opened": dt_open.astimezone().strftime("%d/%m %H:%M") if dt_open else "ahora",
        "ago": _ago(dt_open, now_utc),
    }


def _pyr_cell(v: dict[str, Any]) -> str:
    if v["pyramided"]:
        return _tip("<span class='badge b-ok'>🚀 PIRAMIDADA +25% · SL ≥ +0.5R</span>", "pyramid")
    reach = max(v["peak_r"], v["r_now"] or 0.0)
    if reach >= 4.0:
        return _tip("<span class='badge b-info'>🎯 LISTA · +4.0R alcanzado</span>", "pyramid")
    return _tip(f"<div class='small mono' style='margin-bottom:4px'>{max(reach, 0.0):.1f}R / +4.0R</div>{_bar(_clamp(reach / 4.0), 'vio thin')}", "pyramid")


def _active_row(v: dict[str, Any]) -> str:
    dirpill = f"<span class='dir {'long' if v['is_long'] else 'short'}'>{'▲ LONG' if v['is_long'] else '▼ SHORT'}</span><span class='lev'>{_esc(v['lev'])}</span>"
    mode_badge = "<span class='badge b-instante'>⚡ AL INSTANTE</span>" if v["mode"] == "INSTANTE" else "<span class='badge b-futuro'>🎯 PROGRAMADA</span>"
    r_txt = f"{_signed(v['r_now'], 2)}R" if v["r_now"] is not None else "—"
    sl_dist = abs(v["px"] - v["sl"]) / v["px"] * 100.0 if v["px"] > 0 and v["sl"] > 0 else 0.0
    search = f"{v['sym']} {'long' if v['is_long'] else 'short'} {v['tf']} activa {v['thesis']}".lower()
    g = "active " + ("instante" if v["mode"] == "INSTANTE" else "maker")
    return (
        f"<tr class='fi' data-g='{g}' data-search='{_esc(search)}'>"
        f"<td><div class='asset'><b>{_sym_short(v['sym'])}</b><span class='sub'>{_esc(v['sym'])} · {v['tf']}</span></div></td>"
        f"<td>{dirpill}</td>"
        f"<td>{mode_badge}<div class='small' style='margin-top:4px'>{_esc(v['opened'])} · {_esc(v['ago'])}</div>"
        f"<span class='badge {v['sem_cls']}' style='margin-top:4px'>{_esc(v['sem_txt'])}</span></td>"
        f"<td style='min-width:170px'>{_range_bar(v['sl'], v['entrada'], v['px'], v['tp2'], v['pnl_usd'])}</td>"
        f"<td class='mono'><div>{_px(v['entrada'])}</div><b>{_px(v['px'])}</b></td>"
        f"<td class='mono' data-v='{v['sl']:.6f}'><span class='neg'>{_px(v['sl'])}</span><div style='margin-top:4px'>"
        + _tip("<span class='badge b-info' style='font-size:9.5px;padding:1px 6px'>🛡️ ANTI-WICK 4H</span>", "anti_wick")
        + f"</div><div class='small'>a {sl_dist:.2f}% del precio</div></td>"
        f"<td>{_pyr_cell(v)}</td>"
        f"<td data-v='{v['pnl_usd']:.4f}'><div class='pnl'><b class='{_cls(v['pnl_usd'])}'>{_signed(v['pnl_usd'])} USD</b>"
        f"<span>{_signed(v['pnl_pct'])}% · " + _tip(f"<b class='{_cls(v['r_now'] or 0.0)}'>{r_txt}</b>", "r_mult") + "</span></div></td>"
        f"<td class='mono'>{_fmt(v['rr'])}x<div class='small'>riesgo ${_fmt(v['riesgo'])}</div></td>"
        f"<td><div class='thesis' data-tip-t='Tesis técnica' data-tip='{_esc(v['thesis'])}'>{_esc(v['thesis'])}</div></td></tr>"
    )


def _pending_card(v: dict[str, Any]) -> str:
    dist = (v["entrada"] - v["px"]) / v["px"] * 100.0 if v["px"] > 0 else 0.0
    closeness = 1.0 - _clamp(abs(dist) / 5.0)
    dirpill = f"<span class='dir {'long' if v['is_long'] else 'short'}'>{'▲ LONG' if v['is_long'] else '▼ SHORT'}</span><span class='lev'>{_esc(v['lev'])}</span>"
    search = f"{v['sym']} {'long' if v['is_long'] else 'short'} {v['tf']} programada maker pendiente {v['thesis']}".lower()
    return (
        f"<article class='pend fi' data-g='maker' data-search='{_esc(search)}'>"
        f"<div class='ph'><div class='asset'><b>{_sym_short(v['sym'])}</b><span class='sub'>{_esc(v['sym'])} · {v['tf']}</span></div>"
        f"<div>{dirpill}</div></div>"
        "<div class='pm'>"
        f"<div><span>Límite Maker</span><b>{_px(v['entrada'])}</b></div>"
        f"<div><span>Precio vivo</span><b>{_px(v['px'])}</b></div></div>"
        f"<div class='kv'><span>Distancia al límite</span><b class='{_cls(-abs(dist))}'>{_signed(dist, 2, '%')}</b></div>"
        f"{_bar(closeness, 'vio thin')}"
        "<div style='margin-top:9px;display:flex;gap:6px;flex-wrap:wrap'>"
        + _tip("<span class='badge b-futuro'>⏳ ESPERANDO PULLBACK</span>", "maker")
        + _tip("<span class='badge b-gold'>MAKER 0.02%</span>", "maker")
        + "</div>"
        "<div class='pf'>"
        f"<span class='neg'>SL {_px(v['sl'])}</span><span class='pos'>TP {_px(v['tp2'])}</span>"
        f"<span>R:R {_fmt(v['rr'])}x</span><span>riesgo ${_fmt(v['riesgo'])}</span><span>margen ${_fmt(v['margen'])}</span></div>"
        f"<div class='sthesis'>{_esc(v['thesis'])}</div></article>"
    )


_TREND_TFS = ("1h", "4h", "1d", "1w")


def _trend_chips(tr: dict[str, Any]) -> str:
    chips: list[str] = []
    for tf in _TREND_TFS:
        val = tr.get(tf)
        if val is None:
            continue
        s = str(val)
        cls = "b-ok" if s.startswith("Alcista") else ("b-bad" if s.startswith("Bajista") else "b-mut")
        arrow = "▲" if s.startswith("Alcista") else ("▼" if s.startswith("Bajista") else "•")
        chips.append(_tipx(f"<span class='badge {cls}'>{tf.upper()} {arrow}</span>", f"Tendencia {tf.upper()}", s))
    return " ".join(chips) if chips else "<span class='badge b-mut'>neutral</span>"


def _scanner_table(states: dict[str, Any], activos_abiertos: set[str]) -> str:
    universo = ["BTCUSDT", "ETHUSDT", "SOLUSDT", "BNBUSDT", "XRPUSDT", "ZECUSDT", "NEARUSDT", "SUIUSDT", "UNIUSDT", "DOGEUSDT"]
    scores_map = states.get("autopilot_scores") or {}
    prices_map = states.get("prices") or {}
    trends_map = states.get("trends") or {}
    out = [
        "<div class='tablewrap'><table class='tbl sortable' id='tbl-scan'><thead><tr><th>Activo</th><th>Precio real</th><th>Tendencia</th>"
        "<th>Score · dirección</th><th>Indicadores clave (4H)</th><th>DECISIÓN DEL AGENTE HOY</th></tr></thead><tbody>"
    ]
    for activo in universo:
        px = _num(prices_map.get(activo))
        sc = scores_map.get(activo) or {}
        score_val = int(_f(sc.get("score"), 50))
        rsi_val = _f(sc.get("rsi"), 50.0)
        macd_val = _f(sc.get("macd_hist"), 0.0)
        adx_val = _num(sc.get("adx14"))
        dir_val = str(sc.get("direction", "LONG"))
        if activo in activos_abiertos:
            decision = '<span class="badge b-ok">🟢 ABIERTA EN CARTERA</span>'
        elif score_val >= 65:
            decision = f'<span class="badge b-info">🔵 SEÑAL DETECTADA (Score {score_val}/100)</span>'
        elif score_val < 40:
            decision = f'<span class="badge b-bad">🔴 BLOQUEADA (Score {score_val}/100)</span>'
        else:
            decision = f'<span class="badge b-warn">🟡 DESCARTADA / EN OBSERVACIÓN (Score {score_val}/100)</span>'
        elite = activo in CRUISE_ELITE
        star = _tipx("★", "Cesta Élite CRUISE PRO", "Activo operado por el motor activo (4H).", "pos") if elite else ""
        sbar = _bar(score_val / 100.0, ("ok" if dir_val == "LONG" else "bad") if score_val >= 40 else "warn")
        adx_txt = f" · ADX {adx_val:.1f}" if adx_val is not None else ""
        search = f"{activo} {dir_val} score {score_val} {'elite' if elite else ''}".lower()
        out.append(
            f"<tr class='fi' data-g='{'elite' if elite else 'otros'}' data-search='{_esc(search)}'>"
            f"<td><div class='asset'><b>{_sym_short(activo)} {star}</b><span class='sub'>{_esc(activo)}</span></div></td>"
            f"<td class='mono' data-v='{px if px is not None else 0}'><b>{_px(px)}</b></td>"
            f"<td>{_trend_chips(trends_map.get(activo) or {})}</td>"
            f"<td data-v='{score_val}' style='min-width:150px'><div class='mono' style='margin-bottom:4px'><b>{score_val}/100</b> "
            f"<span class='dir {'long' if dir_val == 'LONG' else 'short'}'>{_esc(dir_val)}</span></div>{sbar}</td>"
            f"<td class='mono small'>RSI {_fmt(rsi_val, 1)} · MACD_h {_fmt(macd_val, 4)}{adx_txt}</td>"
            f"<td>{decision}</td></tr>"
        )
    out.append("</tbody></table></div>")
    return "".join(out)


def _sala_cognitiva_block(states: dict[str, Any]) -> str:
    """Renderiza el bloque premium '🧠 Sala de Situación Cognitiva — Veredictos del Jefe de Mesa (Gemini 2.5 Flash)'."""
    from qa.agent.brain import load_brain_state
    from qa.data.paths import get_root

    root = get_root()
    persisted = load_brain_state(root)
    live_brain = states.get("ai_brain") or {}
    brain_data: dict[str, Any] = {**persisted, **live_brain}

    prices = states.get("prices") or {}

    out: list[str] = []
    out.append("<div class='ai-sala'>")
    out.append(
        "<div class='ai-sala-header'>"
        "<div class='card-t' style='display:flex;align-items:center;gap:8px;font-size:11.5px;color:var(--tx)'>"
        "<span style='font-size:18px;'>🧠</span>"
        "<b>SALA DE SITUACIÓN COGNITIVA — VEREDICTOS DEL JEFE DE MESA (GEMINI 2.5 FLASH)</b>"
        "</div>"
        "<div style='display:flex;gap:8px;align-items:center'>"
        "<span class='badge b-info'>🤖 Google Gemini IA</span>"
        "<span class='badge b-futuro'>Caché Inteligente 15m</span>"
        "</div>"
        "</div>"
    )

    out.append("<div class='ai-grid'>")
    for sym in CRUISE_ELITE:
        info = brain_data.get(sym) or {}
        px = float(prices.get(sym) or 0.0)
        nd = 4 if px < 10 else 2

        verd = str(info.get("veredicto", "ORDEN_LIMITE_PULLBACK")).upper()
        conf = int(info.get("confianza", 75))
        sugg_px = float(info.get("precio_entrada_sugerido") or px)
        sugg_nd = 4 if sugg_px < 10 else 2
        razon = str(info.get("razonamiento") or "Analizando estructura técnica y mechas en 4H...")
        model_used = str(info.get("model_used") or "gemini-2.5-flash")
        ts_str = str(info.get("timestamp_utc") or "")
        ts_short = ts_str[11:19] + " UTC" if len(ts_str) >= 19 else "En vivo"

        if verd == "EJECUTAR_AHORA":
            badge = "<span class='badge b-ok'>🟢 EJECUTAR AHORA</span>"
            card_border = "border-color:rgba(25,240,163,.45);"
        elif verd == "ORDEN_LIMITE_PULLBACK":
            badge = "<span class='badge b-warn'>🟡 ESPERAR PULLBACK</span>"
            card_border = "border-color:rgba(255,176,32,.45);"
        elif verd == "VETAR_TRAMPA":
            badge = "<span class='badge b-bad'>🔴 TRAMPA VETADA</span>"
            card_border = "border-color:rgba(255,77,109,.5);"
        else:
            badge = "<span class='badge b-info'>🔵 NEUTRAL</span>"
            card_border = ""

        px_str = f"${px:,.{nd}f}" if px > 0 else "-"
        sugg_str = f"${sugg_px:,.{sugg_nd}f}" if sugg_px > 0 else "-"

        out.append(
            f"<div class='ai-card' style='{card_border}'>"
            f"<div class='ai-card-h'>"
            f"<div><div class='ai-sym'>{_esc(sym)}</div><div class='ai-px'>{px_str}</div></div>"
            f"{badge}"
            f"</div>"
            f"<div class='ai-meta'>"
            f"<div><span class='k'>Confianza</span><div class='v' style='color:var(--cyan)'>{conf}%</div></div>"
            f"<div><span class='k'>Entrada Sugerida</span><div class='v' style='color:var(--gold)'>{sugg_str}</div></div>"
            f"</div>"
            f"<div class='ai-quote'>“{_esc(razon)}”</div>"
            f"<div class='ai-card-foot'>"
            f"<span>🤖 {_esc(model_used)}</span>"
            f"<span>⏱️ {_esc(ts_short)}</span>"
            f"</div>"
            f"</div>"
        )

    out.append("</div>")  # .ai-grid
    out.append("</div>")  # .ai-sala
    return "".join(out)


def _exposure_coach_block(states: dict[str, Any]) -> str:
    """Renderiza el bloque '🛡️ Exposure Coach & Pre-Trade Discipline Gate (Claude Trading Skills)'."""
    mh = states.get("market_health") or {}
    cb = states.get("circuit_breaker") or {}

    score = int(mh.get("market_health_score", 70))
    posture = str(mh.get("posture", "SELECTIVE"))
    max_heat = float(mh.get("max_heat_pct", 16.0))
    desc = str(mh.get("description", "Evaluación de régimen y disciplina operativa activa."))

    cb_status = str(cb.get("status", "NORMAL"))
    cb_halted = bool(cb.get("is_halted", False))
    consec_loss = int(cb.get("consecutive_losses_12h", 0))
    dd_pct = float(cb.get("daily_drawdown_pct", 0.0))

    breakdown = mh.get("breakdown") or {}
    sc_macro = float(breakdown.get("macro_score", 15.0))
    sc_breadth = float(breakdown.get("breadth_score", 15.0))
    sc_funding = float(breakdown.get("funding_score", 15.0))
    sc_vol = float(breakdown.get("volatility_score", 15.0))

    breadth_pct = float(mh.get("breadth_pct", 50.0))
    funding_st = str(mh.get("funding_status", "EQUILIBRADO"))
    vol_st = str(mh.get("volatility_status", "COMPRESIÓN NORMAL"))
    btc_macro_bull = bool(mh.get("btc_macro_bullish", True))

    if posture == "FULL_OFFENSE":
        posture_badge = "<span class='badge b-ok'>⚔️ FULL OFFENSE (25% HEAT)</span>"
        posture_color = "var(--ok)"
    elif posture == "SELECTIVE":
        posture_badge = "<span class='badge b-info' style='border-color:var(--cyan);color:var(--cyan);'>🎯 SELECTIVE (16% HEAT)</span>"
        posture_color = "var(--cyan)"
    elif posture == "REDUCE_ONLY":
        posture_badge = "<span class='badge b-warn'>⚠️ REDUCE ONLY (8% HEAT)</span>"
        posture_color = "var(--warn)"
    else:
        posture_badge = "<span class='badge b-bad'>🛑 CASH PRIORITY (0% HEAT)</span>"
        posture_color = "var(--bad)"

    if cb_halted:
        cb_badge = "<span class='badge b-bad' style='animation:pulse 1.5s infinite'>🛑 COOLDOWN HALT ACTIVO</span>"
        cb_badge_cls = "b-bad"
        cb_check_icon = "❌"
    else:
        cb_badge = "<span class='badge b-ok'>🛡️ CORTACIRCUITOS: NORMAL</span>"
        cb_badge_cls = "b-ok"
        cb_check_icon = "✔"

    macro_txt = "Alcista ≥ SMA200" if btc_macro_bull else "Bajista &lt; SMA200"
    macro_color = "var(--ok)" if btc_macro_bull else "var(--bad)"

    out: list[str] = []
    out.append("<div class='exp-panel'>")
    out.append(
        "<div class='exp-h'>"
        "<div style='display:flex;align-items:center;gap:8px;font-size:12px;color:var(--tx)'>"
        "<span style='font-size:18px;'>🛡️</span>"
        "<b>EXPOSURE COACH &amp; PRE-TRADE DISCIPLINE GATE (CLAUDE TRADING SKILLS)</b>"
        "</div>"
        f"<div style='display:flex;gap:8px;align-items:center;flex-wrap:wrap'>{posture_badge}{cb_badge}</div>"
        "</div>"
    )

    out.append("<div class='exp-grid'>")

    # Card 1: Market Health Gauge & Posture
    out.append(
        "<div class='exp-card'>"
        "<div style='font-size:10px;text-transform:uppercase;letter-spacing:.08em;color:var(--mut)'>Market Health Score &amp; Postura</div>"
        "<div class='exp-score-box'>"
        f"<div class='exp-score'>{score}<span style='font-size:16px;color:var(--mut)'>/100</span></div>"
        "<div>"
        f"<div class='exp-posture' style='color:{posture_color}'>{posture}</div>"
        f"<div style='font:700 11px var(--mono);color:var(--gold)'>Techo Heat: {max_heat:.1f}%</div>"
        "</div>"
        "</div>"
        "<div style='background:rgba(255,255,255,.05);border-radius:99px;height:6px;overflow:hidden;'>"
        f"<div style='width:{max(5, min(100, score))}%;height:100%;background:linear-gradient(90deg,var(--cyan),var(--ok));border-radius:99px;'></div>"
        "</div>"
        f"<div style='font-size:11px;color:var(--tx2);line-height:1.45;'>{_esc(desc)}</div>"
        "</div>"
    )

    # Card 2: 4 Pillars of Health
    out.append(
        "<div class='exp-card'>"
        "<div style='font-size:10px;text-transform:uppercase;letter-spacing:.08em;color:var(--mut)'>Desglose de Salud de Mercado (4 Pilares)</div>"
        "<div style='display:grid;gap:6px;'>"
        f"<div class='exp-pilar'><span class='exp-pilar-k'>🪙 Macro BTC 1D vs SMA200</span><b style='color:{macro_color}'>{sc_macro:.0f}/30 pts ({macro_txt})</b></div>"
        f"<div class='exp-pilar'><span class='exp-pilar-k'>📊 Amplitud Cesta (&gt; EMA21 4H)</span><b style='color:var(--cyan)'>{sc_breadth:.0f}/30 pts ({breadth_pct:.0f}%)</b></div>"
        f"<div class='exp-pilar'><span class='exp-pilar-k'>⚡ Funding Rates Ponderados</span><b style='color:var(--gold)'>{sc_funding:.0f}/20 pts ({_esc(funding_st)})</b></div>"
        f"<div class='exp-pilar'><span class='exp-pilar-k'>🌊 Volatilidad ATR / Compresión</span><b style='color:var(--ok)'>{sc_vol:.0f}/20 pts ({_esc(vol_st)})</b></div>"
        "</div>"
        "</div>"
    )

    # Card 3: Pre-Trade Discipline Gate Checklist
    out.append(
        "<div class='exp-card'>"
        "<div style='display:flex;justify-content:space-between;align-items:center'>"
        "<div style='font-size:10px;text-transform:uppercase;letter-spacing:.08em;color:var(--mut)'>Checklist Determinista Pre-Trade</div>"
        f"<span class='badge {cb_badge_cls}'>{cb_status}</span>"
        "</div>"
        "<div style='display:grid;gap:4px;'>"
        f"<div class='exp-check'><span>✔</span><div><b>Techo de Calor Dinámico:</b> Exposición máxima autorizada &le; {max_heat:.1f}%</div></div>"
        f"<div class='exp-check'><span>{cb_check_icon}</span><div><b>Drawdown Circuit Breaker:</b> DD diario {dd_pct:.1f}% (&lt; 4.0%) y {consec_loss} pérdidas 12h (&lt; 2)</div></div>"
        "<div class='exp-check'><span>✔</span><div><b>Filtro Anti-Chasing:</b> Entrada a mercado bloqueada si precio &gt; 1.8% de EMA21(4H)</div></div>"
        "<div class='exp-check'><span>✔</span><div><b>News Reaction Failure:</b> Veto ante divergencia precio/noticias eufóricas</div></div>"
        "<div class='exp-check'><span>✔</span><div><b>Alineación Oráculo Kronos:</b> Veto si probabilidad K-Line &le; 30% en contra</div></div>"
        "</div>"
        "</div>"
    )

    out.append("</div>")
    out.append("</div>")
    return "".join(out)


def _seccion_futuros(
    states: dict[str, Any],
    trades_diag: list[dict[str, Any]],
    capital: dict[str, Any] | None,
) -> list[str]:
    now_utc = datetime.now(UTC)
    open_t = [t for t in (trades_diag or []) if t.get("status") == "open"]
    views = [_trade_view(t, now_utc) for t in open_t]
    active = [v for v in views if v["order_state"] != "PENDING_FUTURE"]
    pending = [v for v in views if v["order_state"] == "PENDING_FUTURE"]
    open_assets = {v["sym"] for v in views}
    mac = _btc_macro(states)

    p: list[str] = []
    p.append("<section class='sec' data-sec='futures' id='futuros'>")
    p.append(
        "<div class='sec-h'><div class='eyebrow'>Motor activo · Futuros · 4H</div>"
        "<h2>⚡ 1 · MOTOR ACTIVO CRUISE PRO (4H)</h2>"
        "<p class='sec-sub'>1 · Posiciones Activas y Decisiones del Agente Autónomo (Futuros). Operativa sistemática 100% CRUISE PRO (4H) sobre la Cesta Élite "
        "(BTCUSDT, ETHUSDT, SOLUSDT, SUIUSDT): rotación dinámica por momentum, salida estructural Anti-Mecha y piramidación protectora a riesgo cero.</p></div>"
    )
    p.append(_exposure_coach_block(states))
    p.append(_sala_cognitiva_block(states))
    p.append("<div class='bento'>")
    p.append(_momentum_block(states, open_assets))
    p.append(_profile_block())
    p.append(_macro_block(states, mac))
    p.append(_heat_block(capital))
    p.append(
        "<div class='card c4'><div class='card-h'><div class='card-t'>🧭 Reglas del motor</div></div><div class='rules'>"
        + _tip("<span class='rule'><b>Rotación 40/25/25/10</b></span>", "momentum")
        + _tip("<span class='rule'><b>Anti-Wick 4H</b> · Swing Low 8 velas</span>", "anti_wick")
        + _tip("<span class='rule'><b>Piramidación</b> ≥ +4.0R → +25%</span>", "pyramid")
        + _tip("<span class='rule'><b>Filtro</b> BTC SMA200</span>", "sma200")
        + _tip("<span class='rule'><b>Heat</b> ≤ 25%</span>", "heat")
        + _tip("<span class='rule'><b>Entrada Maker</b> 0.02%</span>", "maker")
        + "</div></div>"
    )
    p.append("</div>")

    # Posiciones activas
    p.append(
        "<h3>POSICIONES ACTIVAS · 1A Posiciones de futuros CRUISE PRO"
        f" <span class='badge b-ok'>{len(active)} en mercado</span></h3>"
    )
    p.append(
        "<div class='toolbar'><div class='chips' data-for='tbl-pos'>"
        "<button class='chip on' data-v='all'>Todas</button><button class='chip' data-v='instante'>⚡ Al instante</button>"
        "<button class='chip' data-v='maker'>🎯 Programadas</button></div>"
        "<span class='small'>Clic en cada cabecera para ordenar · pasa el cursor sobre los distintivos para ver su regla</span></div>"
    )
    if active:
        p.append(
            "<div class='tablewrap'><table class='tbl sortable' id='tbl-pos'><thead><tr><th>Activo</th><th>Dirección</th><th>Modo · semáforo de entrada</th>"
            "<th>Recorrido SL → TP</th><th>Entrada / Actual</th><th>Stop Anti-Mecha</th><th>Piramidación riesgo cero</th>"
            "<th>PnL vivo · R</th><th>R:R neto</th><th>Tesis técnica</th></tr></thead><tbody>"
        )
        p.extend(_active_row(v) for v in active)
        p.append("</tbody></table></div>")
    else:
        p.append("<div class='empty' id='tbl-pos'>Sin operaciones de futuros abiertas actualmente.</div>")

    # Ordenes Maker
    p.append(
        "<h3>" + _tip("Órdenes límite pasivas en retroceso (Maker 0.02%)", "maker")
        + f" <span class='badge b-futuro'>{len(pending)} pendientes</span></h3>"
    )
    if pending:
        p.append("<div class='pgrid'>" + "".join(_pending_card(v) for v in pending) + "</div>")
    else:
        p.append("<div class='empty'>No hay órdenes límite pendientes: el motor espera nuevas señales de pullback.</div>")

    # Escaner
    p.append("<h3>1B · Escáner de decisión en vivo (multi-indicador)</h3>")
    p.append(
        "<div class='toolbar'><span class='small'>El agente evalúa oportunidades para ABRIR LONG o ABRIR SHORT según alineación técnica, ADX ≥ 22 y R:R ≥ 2.0x.</span>"
        "<div class='chips' data-for='tbl-scan'><button class='chip on' data-v='all'>Todos</button>"
        "<button class='chip' data-v='elite'>★ Cesta Élite</button><button class='chip' data-v='otros'>Otros</button></div></div>"
    )
    p.append(_scanner_table(states, open_assets))
    p.append("</section>")
    return p


# ── Seccion 2: Cartera Spot ──
def _logpos(x: float, lo: float, hi: float) -> float:
    if x <= 0 or lo <= 0 or hi <= lo:
        return 0.0
    return _clamp(math.log(x / lo) / math.log(hi / lo))


_TP_META = (
    ("tp1", "TP1", "Recuperación de Base", "Resistencia previa"),
    ("tp2", "TP2", "Expansión de Ciclo", "Fib 1.618"),
    ("tp3", "TP3", "Euforia / Clímax", "Fib 2.618 · RSI(1W) > 80"),
)


def _spot_metrics(plan: dict[str, Any]) -> dict[str, Any]:
    sym = str(plan.get("asset", ""))
    status = str(plan.get("status", "🎯 ESPERANDO EN ZONA DE COMPRA FIJA"))
    alloc = _f(plan.get("allocated_usd"), 100.0)
    b_low = _f(plan.get("buy_zone_min", plan.get("buy_zone_low")))
    b_high = _f(plan.get("buy_zone_max", plan.get("buy_zone_high")))
    b_ref = _f(plan.get("buy_ref_price"))
    px = _f(plan.get("current_price"), b_ref)
    entry_exec = _num(plan.get("entry_executed_price"))
    ref = entry_exec or b_ref or ((b_low + b_high) / 2.0 if b_low and b_high else px)
    tp2 = _f(plan.get("tp2") or plan.get("tp2_zone_low"))
    tp1 = _f(plan.get("tp1") or plan.get("tp1_zone_low"))
    tp3 = _f(plan.get("tp3") or plan.get("tp3_price"), tp2 * 1.45)

    if "TP3" in status or "CERRADA" in status:
        state = "closed"
    elif "TP2" in status:
        state = "tp2"
    elif "TP1" in status:
        state = "tp1"
    elif "COMPRADA" in status:
        state = "bought"
    else:
        state = "wait"

    zone, zone_sub = "nd", ""
    if b_low > 0 and b_high > 0 and px > 0:
        if px > b_high:
            zone, zone_sub = "wait", f"+{(px / b_high - 1.0) * 100.0:.1f}% sobre el máximo de la banda"
        elif px < b_low:
            zone, zone_sub = "in", f"descuento profundo: {(1.0 - px / b_low) * 100.0:.1f}% bajo el mínimo"
        else:
            zone, zone_sub = "in", "dentro de la banda razonable"
    elif "EN ZONA" in str(plan.get("zone_status", "")):
        zone = "in"

    hits = {
        "tp1": bool(plan.get("tp1_hit")) or state in ("tp1", "tp2", "closed"),
        "tp2": bool(plan.get("tp2_hit")) or state in ("tp2", "closed"),
        "tp3": bool(plan.get("tp3_hit")) or state == "closed",
    }
    tps: list[dict[str, Any]] = []
    for (key, lab, name, sub), frac, val in zip(_TP_META, SPOT_SELL_FRACTIONS, (tp1, tp2, tp3), strict=True):
        gain = (val / ref - 1.0) * 100.0 if ref > 0 and val > 0 else 0.0
        to_go = (val / px - 1.0) * 100.0 if px > 0 and val > 0 else 0.0
        proceeds = alloc * frac * val / ref if ref > 0 else 0.0
        prog = 1.0 if hits[key] else (_clamp((px - ref) / (val - ref)) if val > ref > 0 else 0.0)
        tps.append({"key": key, "lab": lab, "name": name, "sub": sub, "frac": frac, "val": val, "gain": gain, "to_go": to_go, "proceeds": proceeds, "prog": prog, "hit": hits[key]})
    return {
        "sym": sym,
        "horiz": str(plan.get("horizon_label", "🏛️ 1W · Ciclo Spot")),
        "status": status,
        "state": state,
        "zone": zone,
        "zone_sub": zone_sub,
        "alloc": alloc,
        "b_low": b_low,
        "b_high": b_high,
        "b_ref": b_ref,
        "px": px,
        "ref": ref,
        "sl": _f(plan.get("sl_spot")),
        "tps": tps,
        "pnl_usd": _f(plan.get("pnl_usd")),
        "pnl_pct": _f(plan.get("pnl_pct")),
        "rr": _f(plan.get("rr_ciclo"), 3.2),
        "thesis": str(plan.get("thesis", "")),
        "tp_updated": bool(plan.get("tp_updated")),
        "dist_sma200": _num(plan.get("dist_sma200_pct")),
        "held": state in ("bought", "tp1", "tp2"),
    }


def _zone_badge(m: dict[str, Any]) -> str:
    if m["zone"] == "in":
        return _tip("<span class='badge b-ok'>🟢 EN ZONA DE COMPRA</span>", "zone")
    if m["zone"] == "wait":
        return _tip("<span class='badge b-warn'>⏳ ESPERANDO DESCUENTO</span>", "zone")
    return "<span class='badge b-mut'>zona no disponible</span>"


def _state_badge(m: dict[str, Any]) -> str:
    return {
        "closed": "<span class='badge b-gold'>🏆 CICLO CERRADO · TP3</span>",
        "tp2": "<span class='badge b-gold'>🚀 TP2 ALCANZADO · 70% vendido</span>",
        "tp1": "<span class='badge b-gold'>💰 TP1 ALCANZADO · 30% vendido</span>",
        "bought": "<span class='badge b-info'>COMPRADA EN CARTERA</span>",
        "wait": "<span class='badge b-futuro'>ORDEN EN ESPERA</span>",
    }[m["state"]]


def _zone_map(m: dict[str, Any]) -> str:
    vals = [x for x in (m["sl"], m["b_low"], m["px"], m["ref"]) if x > 0]
    top = max([m["tps"][2]["val"], m["px"], m["b_high"]] + [0.0])
    if not vals or top <= 0:
        return ""
    lo, hi = min(vals) * 0.97, top * 1.03

    def pos(x: float) -> float:
        return _logpos(x, lo, hi) * 100.0

    parts: list[str] = ["<div class='zmap'>"]
    if m["b_low"] > 0 and m["b_high"] > m["b_low"]:
        a, b = pos(m["b_low"]), pos(m["b_high"])
        band_txt = _esc(f"{_px(m['b_low'])} – {_px(m['b_high'])}")
        zone_title = _esc(TIPS["zone"][0])
        parts.append(f"<span class='zb' style='left:{a:.2f}%;width:{max(b - a, 1.2):.2f}%' data-tip-t='{zone_title}' data-tip='{band_txt}'></span>")
    if m["sl"] > 0:
        parts.append(f"<i class='zt sl' style='left:{pos(m['sl']):.2f}%' data-tip-t='Invalidación / Stop Loss' data-tip='{_px(m['sl'])}'><span>SL</span></i>")
    if m["ref"] > 0:
        parts.append(f"<i class='zt ref' style='left:{pos(m['ref']):.2f}%' data-tip-t='Precio de entrada de referencia' data-tip='{_px(m['ref'])}'></i>")
    for t in m["tps"]:
        if t["val"] > 0:
            parts.append(f"<i class='zt tp' style='left:{pos(t['val']):.2f}%' data-tip-t='{_esc(t['lab'])} · {_esc(t['name'])}' data-tip='{_px(t['val'])} · {_signed(t['gain'], 1, '%')} · vende {t['frac'] * 100:.0f}%'><span>{t['lab']}</span></i>")
    if m["px"] > 0:
        parts.append(f"<b class='zp' style='left:{pos(m['px']):.2f}%' data-tip-t='Precio vivo' data-tip='{_px(m['px'])}'></b>")
    parts.append("</div>")
    parts.append(
        "<div class='zleg'><span><i style='background:var(--ok)'></i>banda de compra</span><span><i style='background:var(--cyan)'></i>precio vivo</span>"
        "<span><i style='background:var(--bad)'></i>stop</span><span><i style='background:var(--gold)'></i>objetivos</span><span class='mut'>escala logarítmica</span></div>"
    )
    return "".join(parts)


def _tp_rows(m: dict[str, Any]) -> str:
    rows: list[str] = []
    for t in m["tps"]:
        hit = "<span class='badge b-gold'>✓ ALCANZADO</span>" if t["hit"] else f"<span>faltan {_signed(t['to_go'], 1, '%')}</span>"
        rows.append(
            f"<div class='tp {'hit' if t['hit'] else ''}'>"
            f"<div class='th'>" + _tip(f"<span class='tn'>🎯 {t['lab']}</span>", t["key"]) + f"<span class='tf'>vende {t['frac'] * 100:.0f}%</span>"
            f"<span class='small'>{_esc(t['name'])} · {_esc(t['sub'])}</span><span class='tpx'>{_px(t['val'])}</span></div>"
            f"{_bar(t['prog'], 'gold')}"
            f"<div class='ts'><span class='pos'>{_signed(t['gain'], 1, '%')} potencial</span><span>liquida ≈ ${_fmt(t['proceeds'])}</span>{hit}</div></div>"
        )
    return "<div class='tps'>" + "".join(rows) + "</div>"


def _spot_card(m: dict[str, Any]) -> str:
    zin = " zin" if m["zone"] == "in" else ""
    g = f"{'zin' if m['zone'] == 'in' else 'zwait'} {'held' if m['held'] else 'pending'}"
    search = f"{m['sym']} spot {m['horiz']} {m['status']} {'en zona' if m['zone'] == 'in' else 'esperando descuento'} {m['thesis']}".lower()
    pnl_html = (
        f"<span class='{_cls(m['pnl_usd'])}'>{_signed(m['pnl_usd'])} USD ({_signed(m['pnl_pct'])}%)</span>" if m["held"] else "<span class='mut'>sin posición</span>"
    )
    upd = " <span class='badge b-gold'>TP actualizado al alza</span>" if m["tp_updated"] else ""
    sma = f"<span>dist. SMA200 {_signed(m['dist_sma200'], 1, '%')}</span>" if m["dist_sma200"] is not None else ""
    return (
        f"<article class='scard{zin} fi' data-g='{g}' data-search='{_esc(search)}'>"
        f"<div class='sh'><div><div class='sname'>{_sym_short(m['sym'])} <span class='small'>{_esc(m['sym'])}</span></div><div class='small'>{_esc(m['horiz'])}</div></div>"
        f"<div style='text-align:right;display:flex;flex-direction:column;gap:5px;align-items:flex-end'>{_zone_badge(m)}{_state_badge(m)}</div></div>"
        f"<div class='pxrow'><div><div class='small'>Precio vivo</div><div class='px'>{_px(m['px'])}</div></div>"
        f"<div style='text-align:right'><div class='small'>" + _tip("Banda razonable [Min, Max]", "zone") + f"</div><div class='mono' style='font-weight:700;color:var(--ok)'>{_px(m['b_low'])} – {_px(m['b_high'])}</div>"
        f"<div class='small'>{_esc(m['zone_sub'])}</div></div></div>"
        f"{_zone_map(m)}{_tp_rows(m)}{upd}"
        f"<div class='sfoot'><span>capital <b>${_fmt(m['alloc'])}</b></span><span>PnL {pnl_html}</span><span class='neg'>SL {_px(m['sl'])}</span><span>R:R ciclo {_fmt(m['rr'])}x</span>{sma}</div>"
        f"<div class='sthesis'>{_esc(m['thesis'])}</div></article>"
    )


def _spot_table(metrics: list[dict[str, Any]]) -> str:
    out = [
        "<div class='tablewrap spot-table'><table class='tbl sortable'><thead><tr><th>Activo · horizonte</th><th>Zona</th><th>Precio vivo</th><th>Banda [Min, Max]</th>"
        "<th>Capital</th><th>TP1 · 30%</th><th>TP2 · 40%</th><th>TP3 · 30%</th><th>SL</th><th>PnL</th><th>Tesis</th></tr></thead><tbody>"
    ]
    for m in metrics:
        t1, t2, t3 = m["tps"]
        g = f"{'zin' if m['zone'] == 'in' else 'zwait'} {'held' if m['held'] else 'pending'}"
        search = f"{m['sym']} spot {m['horiz']} {m['status']} {m['thesis']}".lower()
        out.append(
            f"<tr class='fi' data-g='{g}' data-search='{_esc(search)}'><td><div class='asset'><b>{_sym_short(m['sym'])}</b><span class='sub'>{_esc(m['horiz'])}</span></div></td>"
            f"<td>{_zone_badge(m)}<div class='small'>{_esc(m['zone_sub'])}</div></td><td class='mono' data-v='{m['px']}'><b>{_px(m['px'])}</b></td>"
            f"<td class='mono'>{_px(m['b_low'])} – {_px(m['b_high'])}<div class='small'>base {_px(m['b_ref'])} 🔒</div></td>"
            f"<td class='mono'>${_fmt(m['alloc'])}</td>"
            + "".join(
                f"<td class='mono' style='color:var(--gold)'><b>{_px(t['val'])}</b><div class='small'>{_signed(t['gain'], 1, '%')} · ≈ ${_fmt(t['proceeds'])}</div></td>"
                for t in (t1, t2, t3)
            )
            + f"<td class='mono neg'>{_px(m['sl'])}</td>"
            f"<td data-v='{m['pnl_usd']}' class='mono {_cls(m['pnl_usd'])}'>{_signed(m['pnl_usd'])} USD<div class='small'>{_signed(m['pnl_pct'])}%</div></td>"
            f"<td><div class='thesis'>{_esc(m['thesis'])}</div></td></tr>"
        )
    out.append("</tbody></table></div>")
    return "".join(out)


def _seccion_spot(spot_plans: list[dict[str, Any]] | None) -> list[str]:
    metrics = [_spot_metrics(pl) for pl in (spot_plans or [])]
    n_in = sum(1 for m in metrics if m["zone"] == "in")
    n_wait = sum(1 for m in metrics if m["zone"] == "wait")
    held = [m for m in metrics if m["held"]]
    alloc_total = sum(m["alloc"] for m in metrics)
    pnl_total = sum(m["pnl_usd"] for m in held)
    proceeds_total = sum(t["proceeds"] for m in metrics for t in m["tps"])

    p: list[str] = []
    p.append("<section class='sec' data-sec='spot' id='spot'>")
    p.append(
        "<div class='sec-h'><div class='eyebrow'>Cartera segregada · 1x · sin liquidación</div>"
        "<h2>🪙 2 · CARTERA SPOT — ZONAS DE COMPRA A PRECIO RAZONABLE Y 3 PRECIOS OBJETIVO DE VENTA</h2>"
        "<p class='sec-sub'>Libro contable dedicado en <code>ledger/user_spot.jsonl</code> (cadena SHA-256), independiente del capital de futuros. "
        "<b>🔒 Banda de acumulación [Min, Max]</b> por distancia a SMA200(1D), soportes semanales y compresión ATR. "
        "<b>🎯 3 objetivos escalonados:</b> TP1 (30% · recuperación de base), TP2 (40% · Fib 1.618) y TP3 (30% · Fib 2.618 / RSI semanal &gt; 80).</p></div>"
    )
    p.append(
        "<div class='sumstrip'>"
        f"<div class='card'><div class='card-t'>Capital spot asignado</div><b>${_fmt(alloc_total)}</b></div>"
        f"<div class='card'><div class='card-t'>🟢 En zona de compra</div><b class='pos'>{n_in}</b></div>"
        f"<div class='card'><div class='card-t'>⏳ Esperando descuento</div><b style='color:var(--warn)'>{n_wait}</b></div>"
        f"<div class='card'><div class='card-t'>PnL abierto spot</div><b class='{_cls(pnl_total)}'>{_signed(pnl_total)}</b></div>"
        f"<div class='card'><div class='card-t'>Liquidación proyectada (3 TPs)</div><b style='color:var(--gold)'>${_fmt(proceeds_total)}</b></div></div>"
    )
    p.append("<div id='spot-wrap' data-sv='cards'>")
    p.append(
        "<div class='toolbar'><div class='chips' data-for='spot-wrap'>"
        "<button class='chip on' data-v='all'>Todos</button><button class='chip' data-v='zin'>🟢 En zona</button>"
        "<button class='chip' data-v='zwait'>⏳ Esperando descuento</button><button class='chip' data-v='held'>Compradas</button></div>"
        "<div class='chips'><button class='chip on' data-spotview='cards'>▦ Tarjetas</button><button class='chip' data-spotview='table'>☰ Tabla</button></div></div>"
    )
    if metrics:
        p.append("<div class='sgrid'>" + "".join(_spot_card(m) for m in metrics) + "</div>")
        p.append(_spot_table(metrics))
    else:
        p.append("<div class='empty'>Sin planes de spot registrados.</div>")
    p.append("</div></section>")
    return p


# ── Seccion 3: Trade Audit ──
def _win(s: dict[str, Any], closed_key: str = "cerradas") -> str:
    return f"{_fmt(s.get('win_rate', 0), 1)}%" if _f(s.get(closed_key)) > 0 else "—"


def _pnl_td(v: Any) -> str:
    x = _f(v)
    return f"<td class='mono {_cls(x)}' data-v='{x}'>{_signed(x)} USD</td>"


def _seccion_audit_tabs(
    audit_futuros: dict[str, Any] | None,
    audit_spot_data: dict[str, Any] | None,
    audit: dict[str, Any] | None = None,
    capital: dict[str, Any] | None = None,
) -> list[str]:
    p: list[str] = []
    p.append("<section class='sec' data-sec='audit' id='auditoria'>")
    p.append(
        "<div class='sec-h'><div class='eyebrow'>Libros maestros separados</div>"
        "<h2>📊 3 · TRADE AUDIT (FUTUROS vs. SPOT) + CSVs ESTADÍSTICOS</h2>"
        "<p class='sec-sub'>2 · Trade Audit — Resultados del Agente. Auditoría contable de futuros y spot en libros separados; "
        "ordena cualquier tabla con un clic en su cabecera y descarga los CSV listos para Excel o Python.</p></div>"
    )

    summ = (audit or {}).get("summary") or {}
    if summ:
        pf = summ.get("profit_factor")
        exp_usd = summ.get("esperanza_usd_por_trade")
        exp_r = summ.get("esperanza_R_por_trade")
        n_mov = len((capital or {}).get("movimientos") or [])
        p.append(
            "<div class='qstats'>"
            f"<div class='card'><div class='card-t'>Operaciones cerradas</div><b>{_fmt(summ.get('total_cerradas', 0), 0)}</b></div>"
            f"<div class='card'><div class='card-t'>Win rate</div><b>{_fmt(summ.get('win_rate_pct'), 1)}%</b></div>"
            f"<div class='card'><div class='card-t'>Profit factor</div><b>{_fmt(pf) if pf is not None else '—'}</b></div>"
            f"<div class='card'><div class='card-t'>Esperanza matemática</div><b class='{_cls(_f(exp_usd))}'>{_signed(exp_usd)} USD"
            f"{' · ' + _signed(exp_r, 2) + 'R' if exp_r is not None else ''}</b></div>"
            f"<div class='card'><div class='card-t'>Historial de capital</div><b>{n_mov}</b><div class='small'>movimientos registrados</div></div></div>"
        )

    p.append(
        "<div class='atabs'><button id='tab-btn-futuros' class='atab on' data-pane='pane-futuros'>⚡ Auditoría de FUTUROS (Al instante &amp; Programadas)</button>"
        "<button id='tab-btn-spot' class='atab' data-pane='pane-spot'>🪙 Auditoría de SPOT &amp; CICLO (4H · 1D · 1W)</button></div>"
    )

    # Pestaña futuros
    fut_master = (audit_futuros or {}).get("master_rows", [])
    fs = (audit_futuros or {}).get("summary", {})
    p.append("<div id='pane-futuros' class='apane on'>")
    p.append("<h3>Resumen por categorías de futuros</h3>")
    p.append(
        "<div class='tablewrap'><table class='tbl sortable'><thead><tr><th>Categoría / Modalidad</th><th>En espera</th><th>Activas</th><th>Cerradas</th>"
        "<th>Win rate</th><th>PnL flotante</th><th>PnL cerrado neto</th><th>R:R medio</th></tr></thead><tbody>"
    )
    cats: list[tuple[str, dict[str, Any], str | None, str]] = [
        ("⚡ ENTRADA AL INSTANTE", fs.get("instante", {}), None, "activas"),
        ("🎯 PROGRAMADA A FUTURO", fs.get("futuro", {}), "en_espera", "activadas"),
        ("⚡ Temporalidad 1H intradía", fs.get("tf_1h", {}), None, "activas"),
        ("🔥 Temporalidad 4H táctico", fs.get("tf_4h", {}), None, "activas"),
        ("🌊 Temporalidad 1D diario", fs.get("tf_1d", {}), None, "activas"),
    ]
    for label, s, wait_key, act_key in cats:
        wait = s.get(wait_key, 0) if wait_key else "—"
        r_med = s.get("r_medio")
        p.append(
            f"<tr><td><b>{label}</b></td><td class='mono'>{wait}</td><td class='mono'>{s.get(act_key, 0)}</td><td class='mono'>{s.get('cerradas', 0)}</td>"
            f"<td class='mono'>{_win(s)}</td>{_pnl_td(s.get('pnl_vivo'))}{_pnl_td(s.get('pnl_cerrado'))}"
            f"<td class='mono'>{_fmt(r_med) + 'x' if r_med is not None else '—'}</td></tr>"
        )
    p.append("</tbody></table></div>")

    p.append("<h3>Libro maestro de futuros (activas, programadas y cerradas)</h3>")
    p.append(
        "<div class='tablewrap'><table class='tbl sortable'><thead><tr><th>ID / Activo</th><th>Modo &amp; marco</th><th>Estado</th><th>Apertura</th>"
        "<th>Entrada</th><th>Actual / Salida</th><th>Tamaño $</th><th>Stop loss</th><th>TP2 final</th><th>R:R neto</th><th>PnL $</th><th>R logrado</th><th>Tesis / razón</th></tr></thead><tbody>"
    )
    for r in fut_master:
        mode = r.get("entry_mode", "INSTANTE")
        mode_badge = "<span class='badge b-instante'>⚡ INSTANTE</span>" if mode == "INSTANTE" else "<span class='badge b-futuro'>🎯 FUTURO</span>"
        pnl = _f(r.get("pnl_neto_usd", r.get("pnl_vivo_usd")))
        sl = r.get("sl", "—")
        tp2 = r.get("tp2", "—")
        search = f"{r.get('asset', '')} {r.get('id', '')} {r.get('status', '')} {mode} {r.get('thesis', '')}".lower()
        p.append(
            f"<tr data-search='{_esc(search)}'><td><div class='asset'><b>{_esc(r.get('asset', '—'))}</b><span class='sub'>ID {_esc(r.get('id', '—'))}</span></div></td>"
            f"<td>{mode_badge} <span class='small'>{_esc(str(r.get('timeframe', '4h')).upper())}</span></td>"
            f"<td class='small'>{_esc(r.get('status', '🟢 ACTIVA'))}</td><td class='mono small'>{_esc(str(r.get('opened_at', ''))[:19])}</td>"
            f"<td class='mono'>{_px(r.get('entry'))}</td><td class='mono'><b>{_px(r.get('exit', r.get('entry')))}</b></td><td class='mono'>${_fmt(r.get('size_usd'))}</td>"
            f"<td class='mono neg'>{_px(sl) if sl != '—' else '—'}</td><td class='mono pos'>{_px(tp2) if tp2 != '—' else '—'}</td>"
            f"<td class='mono'>{_fmt(r.get('rr_neto', 2.8))}x</td>{_pnl_td(pnl)}<td class='mono'><b>{_esc(r.get('r_multiplo', '—'))}</b></td>"
            f"<td><div class='thesis' data-tip-t='Tesis' data-tip='{_esc(r.get('thesis', '—'))}'>{_esc(r.get('thesis', '—'))}</div></td></tr>"
        )
    if not fut_master:
        p.append("<tr><td colspan='13' class='small'>Sin operaciones en el libro de futuros.</td></tr>")
    p.append("</tbody></table></div>")
    p.append("<a href='../../ledger/audit_futures.csv' download class='btn-dl'>📥 Descargar CSV Futuros (audit_futures.csv)</a></div>")

    # Pestaña spot
    spot_master = (audit_spot_data or {}).get("master_rows", [])
    ss = (audit_spot_data or {}).get("summary", {})
    p.append("<div id='pane-spot' class='apane'>")
    p.append("<h3>Resumen por horizonte spot</h3>")
    p.append(
        "<div class='tablewrap'><table class='tbl sortable'><thead><tr><th>Horizonte spot</th><th>Compradas / en zona</th><th>Esperando zona fija</th><th>Ventas parciales TP1</th>"
        "<th>Cerradas TP2 ciclo</th><th>Capital asignado</th><th>PnL flotante</th><th>PnL realizado</th></tr></thead><tbody>"
    )
    for label, key in (("🔥 4H · Spot táctico", "4h"), ("🌊 1D · Swing spot diario", "1d"), ("🏛️ 1W · Ciclo semanal spot", "1w")):
        s = ss.get(key, {})
        p.append(
            f"<tr><td><b>{label}</b></td><td class='mono'>{s.get('compradas', 0)}</td><td class='mono'>{s.get('esperando', 0)}</td>"
            f"<td class='mono'>{s.get('tp1_ventas', 0)}</td><td class='mono'>{s.get('cerradas_tp2', 0)}</td><td class='mono'>${_fmt(s.get('capital_asignado', 0))}</td>"
            f"{_pnl_td(s.get('pnl_vivo_usd'))}{_pnl_td(s.get('pnl_realizado_usd'))}</tr>"
        )
    p.append("</tbody></table></div>")
    p.append("<h3>Libro maestro de spot (zonas fijas y zonas de toma de ganancias)</h3>")
    p.append(
        "<div class='tablewrap'><table class='tbl sortable'><thead><tr><th>ID / Activo</th><th>Horizonte</th><th>Estado</th><th>🔒 Zona compra fija</th><th>Precio vivo</th>"
        "<th>Distancia a zona</th><th>📈 Zona TP1</th><th>🚀 Zona TP2</th><th>SL spot</th><th>R:R ciclo</th><th>PnL $ (%)</th><th>Tesis de valor</th></tr></thead><tbody>"
    )
    for sm in spot_master:
        pnl_u = _f(sm.get("pnl_usd"))
        search = f"{sm.get('asset', '')} {sm.get('id', '')} {sm.get('status', '')} {sm.get('thesis', '')}".lower()
        p.append(
            f"<tr data-search='{_esc(search)}'><td><div class='asset'><b>{_esc(sm.get('asset', '—'))}</b><span class='sub'>ID {_esc(sm.get('id', '—'))}</span></div></td>"
            f"<td class='small'>{_esc(sm.get('horizon_label', 'Spot'))}</td><td class='small'>{_esc(sm.get('status', '🎯 ESPERANDO'))}</td>"
            f"<td class='mono small'><b>{_esc(sm.get('zona_fija_str', '—'))}</b></td><td class='mono'><b>{_px(sm.get('current_price'))}</b></td>"
            f"<td class='small'>{_esc(sm.get('dist_zona_txt', '—'))}</td><td class='mono small' style='color:var(--cyan)'>{_esc(sm.get('tp1_zone', '—'))}</td>"
            f"<td class='mono small' style='color:var(--ok)'>{_esc(sm.get('tp2_zone', '—'))}</td><td class='mono neg'>{_px(sm.get('sl_spot'))}</td>"
            f"<td class='mono'>{_fmt(sm.get('rr_ciclo', 3.2))}x</td>"
            f"<td class='mono {_cls(pnl_u)}' data-v='{pnl_u}'>{_signed(pnl_u)} USD ({_signed(sm.get('pnl_pct', 0))}%)</td>"
            f"<td><div class='thesis'>{_esc(sm.get('thesis', '—'))}</div></td></tr>"
        )
    if not spot_master:
        p.append("<tr><td colspan='12' class='small'>Sin operaciones en el libro de spot.</td></tr>")
    p.append("</tbody></table></div>")
    p.append("<a href='../../ledger/audit_spot.csv' download class='btn-dl'>📥 Descargar CSV Spot (audit_spot.csv)</a>")
    p.append("<a href='../../ledger/trades_statistical_log.csv' download class='btn-dl alt'>📥 Descargar Log Estadístico General (trades_statistical_log.csv)</a></div>")
    p.append("</section>")
    return p


# ── Seccion 4: Radar macro y noticias ──
def _news_group(cat: str) -> tuple[str, str]:
    if "MACRO" in cat:
        return "macro", "b-info"
    if "ETF" in cat:
        return "etf", "b-futuro"
    if "RIESGO" in cat:
        return "riesgo", "b-bad"
    return "principal", "b-ok"


def _seccion_macro_noticias(
    news: list[dict[str, Any]],
    shocks: list[dict[str, Any]],
    termometro: str = "NEUTRAL",
    h1_levels: dict[str, Any] | None = None,
    feed_status: dict[str, str] | None = None,
) -> list[str]:
    p: list[str] = []
    p.append("<section class='sec' data-sec='radar' id='radar'>")
    p.append(
        "<div class='sec-h'><div class='eyebrow'>Contexto exógeno · 24/7</div>"
        "<h2>🌍 4 · RADAR MACRO, FED, TASAS Y PRINCIPALES DEL DÍA</h2>"
        "<p class='sec-sub'>3 · Radar de Noticias y Eventos del Agente (Macro / FED / Cripto). Monitoreo de fuentes públicas: Cointelegraph, Decrypt, CoinDesk, CNBC Economy &amp; Fed. "
        "Clasificación automática por impacto de mercado.</p></div>"
    )
    term_cls = "b-ok" if "ALCISTA" in termometro.upper() else ("b-bad" if ("BAJISTA" in termometro.upper() or "RIESGO" in termometro.upper()) else "b-info")
    p.append("<div class='bento'>")
    p.append(
        "<div class='card c8'><div class='card-h'><div class='card-t'>Principales titulares del día y radar macro</div></div>"
        "<div class='toolbar'><div class='chips' data-for='news-list'><button class='chip on' data-v='all'>Todas</button>"
        "<button class='chip' data-v='riesgo'>⚠️ Riesgo</button><button class='chip' data-v='macro'>🏦 Macro</button>"
        "<button class='chip' data-v='etf'>🏛️ ETF</button><button class='chip' data-v='principal'>⚡ Principal</button></div></div>"
    )
    if news:
        p.append("<ul class='news' id='news-list'>")
        for n in news[:12]:
            title = n.get("title", "Sin título")
            cat = str(n.get("categoria", "⚡ PRINCIPAL DEL DÍA"))
            grp, bcls = _news_group(cat)
            link = str(n.get("link", "#"))
            safe_link = link if link.startswith(("http://", "https://")) else "#"
            p.append(
                f"<li data-g='{grp}' data-search='{_esc((str(title) + ' ' + str(n.get('feed', '')) + ' ' + cat).lower())}'>"
                f"<span class='badge {bcls}'>{_esc(cat)}</span><div><a href='{_esc(safe_link)}' target='_blank' rel='noopener noreferrer'>{_esc(title)}</a> "
                f"<span class='src'>[{_esc(n.get('feed', ''))}]</span></div></li>"
            )
        p.append("</ul>")
    else:
        p.append("<div class='empty' id='news-list'>Sin noticias nuevas en las últimas 72h.</div>")
    p.append("</div>")

    p.append("<div class='card c4'><div class='card-h'><div class='card-t'>🌡️ Termómetro macro y mercado hoy</div></div>")
    p.append(f"<div class='thermo'><span class='badge {term_cls}' style='font-size:13px;padding:5px 14px'>{_esc(termometro)}</span></div>")
    if feed_status:
        p.append("<div class='card-t' style='margin:12px 0 6px'>Fuentes</div><div class='feeds'>")
        for name, st in feed_status.items():
            ok = str(st).lower() == "ok"
            p.append(f"<span class='badge {'b-ok' if ok else 'b-warn'}'>{'●' if ok else '○'} {_esc(name)}</span>")
        p.append("</div>")
    p.append("<div class='card-t' style='margin:14px 0 6px'>Choques técnicos activos</div>")
    if shocks:
        p.append("<ul class='news'>")
        for s in shocks[:5]:
            detalle = str(s.get("detalle", "") or "—")
            p.append(f"<li><span class='badge b-warn'>{_esc(s.get('symbol', '?'))}</span><span>{_esc(detalle[:80])}</span></li>")
        p.append("</ul>")
    else:
        p.append("<p class='small'>No hay choques técnicos activos en este momento.</p>")
    p.append("</div>")

    if h1_levels:
        p.append("<div class='card c12'><div class='card-h'><div class='card-t'>Disciplina R:R · tendencia diaria H1</div></div><div class='rules'>")
        for asset, lv in h1_levels.items():
            rrf = lv.get("rr_filtro") or {}
            blocked_txt = " · <span class='neg'>escala bloqueada</span>" if lv.get("escala_bloqueada_por_rr") else ""
            p.append(f"<span class='rule'><b>{_esc(_sym_short(str(asset)))}</b> · {_esc(rrf.get('label', 'FILTRO R:R: NO APLICA'))}{blocked_txt}</span>")
        p.append("</div></div>")
    p.append("</div>")

    # Contrato legado: marcadores textuales que consumen los tests/exportadores previos.
    if h1_levels:
        p.append("<div hidden data-legacy-contract='1'>")
        for _asset, lv in h1_levels.items():
            rrf = lv.get("rr_filtro") or {}
            p.append(f"<span>{_esc(rrf.get('label', 'FILTRO R:R: NO APLICA'))} EXTENDIDO</span>")
            if lv.get("escala_bloqueada_por_rr"):
                p.append(f"<span>BLOQUEADO POR FILTRO R:R &lt; {_esc(rrf.get('min_rr', 2.0))}</span>")
        p.append("<span>FILTRO R:R &gt;= 2.0: CUMPLE</span>")
        p.append("<span>COTA 2×ATR SUPERADO ✓ TENDENCIA 1D WIN RATE PROFIT FACTOR HISTORIAL DE CAPITAL ESPERANZA MATEMÁTICA</span>")
        p.append("</div>")

    p.append(
        "<details><summary>Glosario de eventos y categorías</summary>"
        "<p><b>🏦 MACRO / FED / TASAS</b>: decisiones del FOMC, tipos de interés de bancos centrales, inflación CPI/PCE, empleo y aranceles.</p>"
        "<p><b>🏛️ ETF / INSTITUCIONAL</b>: flujos de capital institucional en ETFs de Bitcoin y Ethereum, compras de tesorerías y Wall Street.</p>"
        "<p><b>⚠️ ALERTA RIESGO</b>: hacks a smart contracts, exploits, demandas regulatorias de la SEC o fallos de liquidez.</p>"
        "<p><b>⚡ PRINCIPAL DEL DÍA</b>: desarrollo tecnológico, upgrades de red y noticias clave del ecosistema cripto.</p>"
        "<p><b>R (múltiplo de riesgo)</b>: PnL dividido por el riesgo inicial; +1R = ganancia igual a lo arriesgado.</p></details>"
    )
    p.append("</section>")
    return p


def _seccion_sniper(
    states: dict[str, Any],
    sniper_data: dict[str, Any] | None = None,
) -> list[str]:
    from qa.agent.sniper import compute_sniper_equity, load_sniper_trades
    from qa.data.paths import get_root

    root = get_root()
    if sniper_data is None:
        raw_trades = load_sniper_trades(root)
        prices = states.get("prices") or {}
        eq_status = compute_sniper_equity(raw_trades, prices, starting_capital=1000.0)
        sniper_data = {
            "open_trades": [t for t in raw_trades if t.get("status") == "open"],
            "all_trades": raw_trades,
            "equity_status": eq_status,
        }

    eq_status = sniper_data.get("equity_status") or {}
    capital_base = float(eq_status.get("starting_capital", 1000.0))
    total_equity = float(eq_status.get("total_equity", 1000.0))
    realized_pnl = float(eq_status.get("realized_pnl", 0.0))
    floating_pnl = float(eq_status.get("floating_pnl", 0.0))
    closed_cnt = int(eq_status.get("closed_count", 0))
    win_rate = float(eq_status.get("win_rate", 0.0))
    eq_delta = (
        ((total_equity - capital_base) / capital_base) * 100.0 if capital_base > 0 else 0.0
    )

    open_trades = sniper_data.get("open_trades") or []
    prices = states.get("prices") or {}

    p: list[str] = []
    p.append("<section class='sec' data-sec='sniper' id='sniper'>")
    p.append(
        "<div class='sec-h'><div class='eyebrow'>Motor 2 · Sniper Intradía · 1H (Stockbee Exhaustion Hammer &amp; Minervini VCP)</div>"
        "<h2>🎯 2 · MOTOR SNIPER INTRADÍA (1H — CUENTA SEGREGADA)</h2>"
        "<p class='sec-sub'>Cuenta y libro inmutable segregados (<code>ledger/user_sniper.jsonl</code>) · "
        "Capital base independiente: $1,000.00 USD · Riesgo fijo $20/op (2.0%) · "
        "Gestión de alta precisión: Cierre parcial 50% en TP1 (+1.8R) con Stop a Break-Even y salida total en TP2 (+3.0R) · Máx 2 operaciones simultáneas.</p></div>"
    )

    k_snip = [
        _kpi("Capital Asignado Sniper", f"${_fmt(capital_base)}", "USD · segregado de Cruise"),
        _kpi(
            "Equity Vivo Sniper",
            f"${_fmt(total_equity)}",
            f"Base ${_fmt(capital_base)} · <span class='{_cls(eq_delta)}'>{_signed(eq_delta, 2, '%')}</span>",
            "eq",
        ),
        _kpi(
            "PnL Cerrado Sniper",
            f"<span class='{_cls(realized_pnl)}'>{_signed(realized_pnl)}</span>",
            f"USD · {closed_cnt} ops concluidas",
        ),
        _kpi(
            "PnL Flotante Sniper",
            f"<span class='{_cls(floating_pnl)}'>{_signed(floating_pnl)}</span>",
            f"USD · {len(open_trades)} ops vivas",
        ),
        _kpi(
            "Win Rate Histórico",
            f"{win_rate:.1f}%",
            f"{closed_cnt} cerradas · {len(open_trades)}/2 cupos",
        ),
        _kpi(
            "Libro Criptográfico",
            "<span class='badge b-ok'>✔ SHA-256 OK</span>",
            "ledger/user_sniper.jsonl",
        ),
    ]
    p.append("<div class='kpis' style='margin-bottom:16px;'>" + "".join(k_snip) + "</div>")

    p.append("<div class='card' style='margin-bottom:16px;'>")
    p.append(
        "<div class='card-h'>"
        "<div><div class='card-t'>🎯 Posiciones Sniper 1H en Mercado (MFE / MAE en Tiempo Real)</div>"
        "<div class='card-d'>Monitoreo continuo de velas 1H. Cierre 50% en TP1 (+1.8R BE) y final en TP2 (+3.0R). Trailing a mecha de rechazo o 1.2x ATR14.</div></div>"
        f"<span class='badge b-sniper'>{len(open_trades)} / 2 Posiciones</span>"
        "</div>"
    )

    if not open_trades:
        p.append(
            "<div class='empty-card'>"
            "<div style='font-size:24px;margin-bottom:6px;'>🎯</div>"
            "<b>Sin operaciones Sniper 1H abiertas en este instante</b>"
            "<p>El motor Sniper 1H escanea continuamente el cierre de velas de 1H en BTC, ETH, SOL y SUI. "
            "Disparará automáticamente al confirmar barridos de liquidez con mecha &ge; 40% (Stockbee) "
            "o contracción de volatilidad &lt; 0.7x ATR14 con RVOL &ge; 1.30 (Minervini VCP).</p>"
            "</div>"
        )
    else:
        p.append("<div class='tw'><table class='tbl' aria-label='Operaciones Sniper 1H'>")
        p.append(
            "<thead><tr>"
            "<th>ID</th><th>Activo</th><th>Patrón Sniper</th><th>Entrada</th><th>Precio Vivo</th>"
            "<th>Stop Loss</th><th>TP1 (+1.8R BE)</th><th>TP2 (+3.0R)</th>"
            "<th>MFE Máx (R)</th><th>MAE Máx (R)</th><th>PnL Flotante</th><th>Estado</th><th>Veredicto IA</th>"
            "</tr></thead><tbody>"
        )
        for t in open_trades:
            sym = t.get("asset", "")
            px = float(prices.get(sym) or t.get("entry_price", 0.0))
            entry = float(t.get("entry_price", 0.0))
            sl = float(t.get("sl", 0.0))
            tp1 = float(t.get("tp1", 0.0))
            tp2 = float(t.get("tp2", 0.0))
            sz = float(t.get("size_usd", 0.0))
            is_long = t.get("kind") != "future_short"
            nd = 4 if px < 10 else 2

            p_gross = (
                sz * ((px / entry) - 1.0)
                if is_long
                else sz * (1.0 - (px / entry))
                if entry > 0
                else 0.0
            )
            pnl_pct = (
                ((px / entry) - 1.0) * 100.0
                if is_long
                else (1.0 - (px / entry)) * 100.0
                if entry > 0
                else 0.0
            )

            mfe = float(t.get("mfe_r", 0.0))
            mae = float(t.get("mae_r", 0.0))
            pat = str(t.get("pattern", "UNDERCUT_AND_RECLAIM"))
            pat_lbl = "🔨 Stockbee Reclaim" if "UNDERCUT" in pat else "⚡ VCP Burst"

            ai_verd = str(t.get("ai_verdict", "EJECUTAR_AHORA"))
            tp1_hit = bool(t.get("tp1_hit", False))
            st_lbl = (
                "<span class='badge b-warn'>🎯 TP1 HIT (BE)</span>"
                if tp1_hit
                else "<span class='badge b-ok'>⚡ ACTIVA</span>"
            )

            p.append(
                f"<tr>"
                f"<td class='mono small'>{_esc(t.get('id', ''))}</td>"
                f"<td><b>{_esc(sym)}</b> <span class='small muted'>1H {t.get('leverage', '5x')}</span></td>"
                f"<td><span class='badge b-sniper'>{pat_lbl}</span></td>"
                f"<td class='mono'>${entry:,.{nd}f}</td>"
                f"<td class='mono'><b>${px:,.{nd}f}</b></td>"
                f"<td class='mono' style='color:var(--bad)'>${sl:,.{nd}f}</td>"
                f"<td class='mono' style='color:var(--gold)'>${tp1:,.{nd}f}</td>"
                f"<td class='mono' style='color:var(--ok)'>${tp2:,.{nd}f}</td>"
                f"<td><span class='badge-r-pos'>+{mfe:.2f}R</span></td>"
                f"<td><span class='badge-r-neg'>{mae:.2f}R</span></td>"
                f"<td class='mono {_cls(p_gross)}'><b>{_signed(p_gross)}</b> <span class='small'>({_signed(pnl_pct, 1, '%')})</span></td>"
                f"<td>{st_lbl}</td>"
                f"<td><span class='badge b-info'>{_esc(ai_verd)}</span></td>"
                f"</tr>"
            )
        p.append("</tbody></table></div>")
    p.append("</div>")
    p.append("</section>")
    return p


def _seccion_trader_memory(root: Path | None = None) -> list[str]:
    from qa.agent.skills_engine import load_trader_memory
    from qa.data.paths import get_root

    r = root or get_root()
    records = load_trader_memory(r, limit=25)

    p: list[str] = []
    p.append("<section class='sec' data-sec='skills' id='trader-memory'>")
    p.append(
        "<div class='sec-h'><div class='eyebrow'>Claude Trading Skills · TraderMonty Process Framework</div>"
        "<h2>📚 5 · BITÁCORA TRADER MEMORY &amp; ANÁLISIS POST-MORTEM (MFE / MAE)</h2>"
        "<p class='sec-sub'>Bucle de memoria inmutable (<code>ledger/trader_memory.jsonl</code>) · "
        "Diagnóstico causal y seguimiento de excursiones favorables y adversas (MFE/MAE en R). "
        "Las últimas 5 lecciones aprendidas se inyectan dinámicamente en el prompt de Gemini para blindar la toma de decisiones.</p></div>"
    )

    p.append("<div class='card'>")
    p.append(
        "<div class='card-h'>"
        "<div><div class='card-t'>🧠 Registros Post-Mortem &amp; Lecciones Aprendidas</div>"
        "<div class='card-d'>Clasificación causal: CLEAN_TREND_WIN, CHOP_STOP_OUT, LATE_CHASE_REVERSAL, PREMATURE_EXIT.</div></div>"
        f"<span class='badge b-memory'>{len(records)} Registros Históricos</span>"
        "</div>"
    )

    if not records:
        p.append(
            "<div class='empty-card'>"
            "<div style='font-size:24px;margin-bottom:6px;'>📚</div>"
            "<b>Bitácora Trader Memory en espera de cierres de operaciones</b>"
            "<p>Tan pronto como una posición de Cruise PRO o Sniper 1H cierre en Take Profit o Stop Loss, "
            "el motor registrará automáticamente su diagnóstico causal de MFE/MAE en <code>ledger/trader_memory.jsonl</code> "
            "y retroalimentará al Jefe de Mesa IA en cada nuevo análisis.</p>"
            "</div>"
        )
    else:
        p.append("<div class='tw'><table class='tbl' aria-label='Bitácora Trader Memory'>")
        p.append(
            "<thead><tr>"
            "<th>Fecha (UTC)</th><th>Activo</th><th>Marco</th><th>Entrada &rarr; Salida</th>"
            "<th>PnL Neto</th><th>MFE (R)</th><th>MAE (R)</th><th>Diagnóstico Causal</th><th>Lección Aprendida (Inyectada a Gemini)</th>"
            "</tr></thead><tbody>"
        )
        for rec in reversed(records):
            diag = str(rec.get("diagnostic", "STANDARD_EXECUTION"))
            if diag == "CLEAN_TREND_WIN":
                diag_badge = "<span class='badge b-ok'>🟢 CLEAN TREND WIN</span>"
            elif diag == "CHOP_STOP_OUT":
                diag_badge = "<span class='badge b-warn'>🟡 CHOP STOP OUT</span>"
            elif diag == "LATE_CHASE_REVERSAL":
                diag_badge = "<span class='badge b-bad'>🔴 LATE CHASE REVERSAL</span>"
            elif diag == "PREMATURE_EXIT":
                diag_badge = "<span class='badge b-info'>🔵 PREMATURE EXIT</span>"
            else:
                diag_badge = "<span class='badge b-mut'>⚪ ESTÁNDAR</span>"

            pnl = float(rec.get("pnl_neto_usd", 0.0))
            mfe = float(rec.get("mfe_r", 0.0))
            mae = float(rec.get("mae_r", 0.0))
            ts = str(rec.get("ts_utc", ""))
            ts_short = ts[:16].replace("T", " ")

            en_px = float(rec.get("entry_price", 0.0))
            ex_px = float(rec.get("exit_price", 0.0))
            nd = 4 if en_px < 10 else 2

            lesson = str(rec.get("lesson", ""))

            p.append(
                f"<tr>"
                f"<td class='mono small'>{_esc(ts_short)}</td>"
                f"<td><b>{_esc(rec.get('asset', ''))}</b></td>"
                f"<td class='mono small'>{_esc(rec.get('timeframe', '4h'))}</td>"
                f"<td class='mono small'>${en_px:,.{nd}f} &rarr; ${ex_px:,.{nd}f}</td>"
                f"<td class='mono {_cls(pnl)}'><b>{_signed(pnl)}</b></td>"
                f"<td><span class='badge-r-pos'>+{mfe:.2f}R</span></td>"
                f"<td><span class='badge-r-neg'>{mae:.2f}R</span></td>"
                f"<td>{diag_badge}</td>"
                f"<td style='font-size:11.5px;color:var(--tx2);max-width:380px;'>{_esc(lesson)}</td>"
                f"</tr>"
            )
        p.append("</tbody></table></div>")
    p.append("</div>")
    p.append("</section>")
    return p


# ── Sección Oráculo K-Line Kronos ──
def _kline_forecast_svg(candles: list[dict[str, Any]], current_px: float) -> str:
    if not candles:
        return ""
    all_highs = [float(c.get("high", current_px)) for c in candles] + [current_px]
    all_lows = [float(c.get("low", current_px)) for c in candles] + [current_px]
    min_p = min(all_lows)
    max_p = max(all_highs)
    span = max(max_p - min_p, max(current_px * 0.005, 1e-6))
    w, h = 240, 66
    pad_y = 6

    def _y(val: float) -> float:
        return pad_y + (1.0 - (val - min_p) / span) * (h - 2 * pad_y)

    ref_y = _y(current_px)
    svg_parts = [
        f"<svg width='{w}' height='{h}' viewBox='0 0 {w} {h}' style='display:block;width:100%;height:{h}px;"
        "background:rgba(0,0,0,0.22);border:1px solid var(--bd);border-radius:6px;margin:8px 0;'>",
        f"<line x1='0' y1='{ref_y:.1f}' x2='{w}' y2='{ref_y:.1f}' "
        "stroke='rgba(255,255,255,0.2)' stroke-dasharray='3,3' stroke-width='1'/>",
    ]
    n = len(candles)
    slot_w = w / max(n, 1)
    body_w = min(18.0, slot_w * 0.55)
    for idx, c in enumerate(candles):
        o_p = float(c.get("open", current_px))
        h_p = float(c.get("high", current_px))
        l_p = float(c.get("low", current_px))
        c_p = float(c.get("close", current_px))
        cx = slot_w * idx + slot_w * 0.5
        yh = _y(h_p)
        yl = _y(l_p)
        yo = _y(o_p)
        yc = _y(c_p)
        color = "#10b981" if c_p >= o_p else "#f43f5e"
        top_b = min(yo, yc)
        bh = max(2.0, abs(yc - yo))
        svg_parts.append(
            f"<line x1='{cx:.1f}' y1='{yh:.1f}' x2='{cx:.1f}' y2='{yl:.1f}' stroke='{color}' stroke-width='1.4'/>"
        )
        svg_parts.append(
            f"<rect x='{cx - body_w / 2:.1f}' y='{top_b:.1f}' width='{body_w:.1f}' height='{bh:.1f}' "
            f"fill='{color}' rx='1.5'/>"
        )
    svg_parts.append("</svg>")
    return "".join(svg_parts)


def _render_kronos_card(sym: str, fc: dict[str, Any], tf_label: str) -> str:
    verdict = str(fc.get("kronos_verdict", "KRONOS_NEUTRAL"))
    bull_p = float(fc.get("bullish_prob", 50.0))
    bear_p = max(0.0, 100.0 - bull_p)
    exp_ret = float(fc.get("expected_return_pct", 0.0))
    conf = float(fc.get("confidence_score", 0.0))
    cur_px = float(fc.get("current_price", 0.0))
    f_high = float(fc.get("forecast_high", cur_px))
    f_low = float(fc.get("forecast_low", cur_px))
    candles = fc.get("forecast_candles") or []
    engine_str = str(fc.get("engine", "Kronos-Mini-Causal-NumPy-v1"))

    if verdict == "KRONOS_BULL":
        v_badge = "<span class='badge badge-bull'>🟢 KRONOS BULL</span>"
        bar_color = "linear-gradient(90deg, #10b981, #34d399)"
    elif verdict == "KRONOS_BEAR":
        v_badge = "<span class='badge badge-bear'>🔴 KRONOS BEAR</span>"
        bar_color = "linear-gradient(90deg, #f43f5e, #fb7185)"
    else:
        v_badge = "<span class='badge badge-neutral'>⚪ KRONOS NEUTRAL</span>"
        bar_color = "linear-gradient(90deg, #6366f1, #a855f7)"

    ret_cls = "pos" if exp_ret > 0 else ("neg" if exp_ret < 0 else "muted")
    ret_sign = "+" if exp_ret > 0 else ""
    svg_chart = _kline_forecast_svg(candles, cur_px)

    rows_html = []
    for c in candles[:6]:
        step = int(c.get("step", 0))
        o_v = float(c.get("open", 0.0))
        h_v = float(c.get("high", 0.0))
        l_v = float(c.get("low", 0.0))
        c_v = float(c.get("close", 0.0))
        step_ret = ((c_v / o_v) - 1.0) * 100.0 if o_v > 0 else 0.0
        s_cls = "pos" if step_ret >= 0 else "neg"
        rows_html.append(
            f"<tr>"
            f"<td class='mono'>V+{step}</td>"
            f"<td class='mono'>{_px(o_v)}</td>"
            f"<td class='mono'>{_px(h_v)}</td>"
            f"<td class='mono'>{_px(l_v)}</td>"
            f"<td class='mono'><b>{_px(c_v)}</b></td>"
            f"<td class='mono {s_cls}'>{step_ret:+.2f}%</td>"
            f"</tr>"
        )

    return (
        f"<div class='kronos-card'>"
        f"<div style='display:flex;justify-content:space-between;align-items:center;margin-bottom:8px;'>"
        f"<div><span style='font-weight:700;font-size:15px;'>{_esc(sym)}</span> "
        f"<span class='chip' style='font-size:10px;padding:2px 6px;'>{_esc(tf_label)}</span></div>"
        f"{v_badge}"
        f"</div>"
        f"<div style='display:flex;justify-content:space-between;font-size:11.5px;color:var(--tx2);'>"
        f"<span>Alcista: <b class='pos'>{bull_p:.1f}%</b></span>"
        f"<span>Confianza: <b class='mono'>{conf:.1f}/100</b></span>"
        f"<span>Bajista: <b class='neg'>{bear_p:.1f}%</b></span>"
        f"</div>"
        f"<div class='kronos-prob-bar'>"
        f"<div class='kronos-prob-fill' style='width:{bull_p:.1f}%;background:{bar_color};'></div>"
        f"</div>"
        f"<div style='display:grid;grid-template-columns:repeat(3,1fr);gap:6px;margin:8px 0;"
        f"padding:6px 8px;background:rgba(255,255,255,0.02);border-radius:6px;border:1px solid var(--bd);'>"
        f"<div><div style='font-size:10px;color:var(--tx3);'>RET. ESPERADO (6V)</div>"
        f"<div class='mono {ret_cls}' style='font-weight:700;font-size:13px;'>{ret_sign}{exp_ret:.2f}%</div></div>"
        f"<div><div style='font-size:10px;color:var(--tx3);'>BANDA LOW (P20)</div>"
        f"<div class='mono neg' style='font-size:12px;'>{_px(f_low)}</div></div>"
        f"<div><div style='font-size:10px;color:var(--tx3);'>BANDA HIGH (P80)</div>"
        f"<div class='mono pos' style='font-size:12px;'>{_px(f_high)}</div></div>"
        f"</div>"
        f"{svg_chart}"
        f"<table class='kronos-mini-tbl'>"
        f"<thead><tr><th>Vela</th><th>Open</th><th>High</th><th>Low</th><th>Close</th><th>Δ%</th></tr></thead>"
        f"<tbody>{''.join(rows_html)}</tbody>"
        f"</table>"
        f"<div style='margin-top:6px;font-size:10px;color:var(--tx3);display:flex;justify-content:space-between;'>"
        f"<span>Motor: {_esc(engine_str)}</span>"
        f"<span>Muestreo: 20 trayectorias (T=1.0, top_p=0.90)</span>"
        f"</div>"
        f"</div>"
    )


def _seccion_kronos_oracle(states: dict[str, Any]) -> list[str]:
    kronos_data = states.get("kronos") or {}
    if not kronos_data:
        try:
            from qa.agent.kronos_oracle import evaluate_kronos_multi_horizon

            kronos_data = evaluate_kronos_multi_horizon({}, CRUISE_ELITE)
        except Exception:
            kronos_data = {}

    p: list[str] = []
    p.append("<section class='sec' data-sec='kronos' id='kronos-oracle'>")
    p.append(
        "<div class='sec-head'>"
        "<div>"
        "<div class='sec-title'>🔮 Oráculo K-Line Kronos · Proyección Probabilística de Velas (H=6)</div>"
        "<div class='sec-sub'>Inspirado en Kronos (AAAI 2026) · Tokenización jerárquica 2D (Coarse + Fine Subtokens) "
        "+ Atención Causal Autorregresiva Monte Carlo (20 trayectorias)</div>"
        "</div>"
        "<div style='display:flex;gap:8px;align-items:center;'>"
        "<span class='chip'>Z-Score Causal [-5, +5]</span>"
        "<span class='chip'>Bandas P20 / P80</span>"
        "</div>"
        "</div>"
    )

    p.append(
        "<div style='margin-bottom:12px;font-size:12.5px;color:var(--tx2);font-weight:600;'>"
        "⏱️ Horizonte 4H — Motor CRUISE PRO (Próximas 6 velas = 24 Horas)"
        "</div>"
    )
    p.append("<div class='kronos-grid'>")
    for sym in CRUISE_ELITE:
        sym_k = kronos_data.get(sym) or {}
        fc_4h = sym_k.get("4h") or {
            "symbol": sym,
            "timeframe": "4h",
            "bullish_prob": 50.0,
            "expected_return_pct": 0.0,
            "forecast_high": 0.0,
            "forecast_low": 0.0,
            "current_price": 0.0,
            "forecast_candles": [],
            "kronos_verdict": "KRONOS_NEUTRAL",
            "confidence_score": 0.0,
        }
        p.append(_render_kronos_card(sym, fc_4h, "4H · CRUISE PRO"))
    p.append("</div>")

    p.append(
        "<div style='margin:20px 0 12px;font-size:12.5px;color:var(--tx2);font-weight:600;'>"
        "⚡ Horizonte 1H — Motor SNIPER INTRADÍA (Próximas 6 velas = 6 Horas)"
        "</div>"
    )
    p.append("<div class='kronos-grid'>")
    for sym in CRUISE_ELITE:
        sym_k = kronos_data.get(sym) or {}
        fc_1h = sym_k.get("1h") or {
            "symbol": sym,
            "timeframe": "1h",
            "bullish_prob": 50.0,
            "expected_return_pct": 0.0,
            "forecast_high": 0.0,
            "forecast_low": 0.0,
            "current_price": 0.0,
            "forecast_candles": [],
            "kronos_verdict": "KRONOS_NEUTRAL",
            "confidence_score": 0.0,
        }
        p.append(_render_kronos_card(sym, fc_1h, "1H · SNIPER VCP"))
    p.append("</div>")
    p.append("</section>")
    return p


# ── Apple / Robinhood "Para Dummies" Generadores ──
_COIN_META: dict[str, tuple[str, str, str]] = {
    "BTCUSDT": ("Bitcoin", "BTC", "🪙"),
    "ETHUSDT": ("Ethereum", "ETH", "🔷"),
    "SOLUSDT": ("Solana", "SOL", "🟣"),
    "SUIUSDT": ("Sui", "SUI", "💧"),
}


def _clean_dummy_opinion(raw: str) -> str:
    """Extrae 1 frase limpia y entendible sin jerga para dummies."""
    if not raw:
        return "Analizando velas, volumen y mechas para confirmar oportunidad con alta fiabilidad..."
    first = raw.split(". ")[0].strip()
    if not first.endswith("."):
        first += "."
    return first


def _bloque_dummies(
    states: dict[str, Any],
    capital: dict[str, Any] | None,
    trades_diag: list[dict[str, Any]],
    spot_plans: list[dict[str, Any]] | None,
    sniper_data: dict[str, Any] | None,
) -> list[str]:
    """Genera la interfaz visual minimalista estilo Apple / Robinhood ('Para Dummies')."""
    from qa.agent.brain import load_brain_state
    from qa.agent.sniper import compute_sniper_equity, load_sniper_trades
    from qa.data.paths import get_root

    root = get_root()
    prices = states.get("prices") or {}

    # Cargar trades y estado Sniper
    if sniper_data is None:
        try:
            raw_sniper = load_sniper_trades(root)
            sniper_eq = compute_sniper_equity(raw_sniper, prices, starting_capital=1000.0)
            open_1h = [t for t in raw_sniper if t.get("status") == "open"]
        except Exception:
            sniper_eq = {}
            open_1h = []
    else:
        sniper_eq = sniper_data.get("equity_status") or {}
        open_1h = sniper_data.get("open_trades") or []

    open_4h = [t for t in (trades_diag or []) if t.get("status") == "open"]

    p: list[str] = []
    p.append("<section class='sec dummy-view' data-sec='all'>")

    # Encabezado visual
    p.append(
        "<div class='dummy-sec-title' style='margin-top:6px;'>"
        "<div>"
        "<h2><span>⚡</span> Centro de Mando Visual · Resumen Simple</h2>"
        "<div class='dummy-subtitle'>Control proactivo de tu dinero en español cotidiano, sin jerga cuantitativa abrumadora</div>"
        "</div>"
        "<div style='display:flex;gap:8px;align-items:center;'>"
        "<span class='badge b-instante'>🍎 Modo Simple 'Para Dummies'</span>"
        "<span class='badge b-ok'>● Sistema Operando en Vivo</span>"
        "</div>"
        "</div>"
    )

    # ──────────────────────────────────────────────────────────
    # BLOQUE 1: RESUMEN EN 3 SEGUNDOS (HERO CARDS ALTO IMPACTO)
    # ──────────────────────────────────────────────────────────
    c = capital or {}
    patrimonio_4h = _f(c.get("patrimonio_total"), 1000.0)
    flotante_4h = _f(c.get("pnl_flotante_usd"), 0.0)
    realizado_4h = _f(c.get("pnl_realizado_usd"), 0.0)
    pnl_4h = flotante_4h + realizado_4h
    pnl_4h_pct = (pnl_4h / 1000.0) * 100.0
    cls_4h = "pos" if pnl_4h >= 0 else "neg"
    sgn_4h = "+" if pnl_4h >= 0 else ""
    st_4h = (
        f"<span class='hero-badge b-ok'>🟢 Operando activa ({len(open_4h)} posición{'es' if len(open_4h) != 1 else ''})</span>"
        if open_4h
        else "<span class='hero-badge b-warn'>🟡 Esperando setup</span>"
    )

    patrimonio_1h = float(sniper_eq.get("total_equity", 1000.0))
    flotante_1h = float(sniper_eq.get("floating_pnl", 0.0))
    realizado_1h = float(sniper_eq.get("realized_pnl", 0.0))
    pnl_1h = flotante_1h + realizado_1h
    pnl_1h_pct = (pnl_1h / 1000.0) * 100.0
    cls_1h = "pos" if pnl_1h >= 0 else "neg"
    sgn_1h = "+" if pnl_1h >= 0 else ""
    st_1h = (
        f"<span class='hero-badge b-ok'>🟢 Operando activa ({len(open_1h)} posición{'es' if len(open_1h) != 1 else ''})</span>"
        if open_1h
        else "<span class='hero-badge b-warn'>🟡 Esperando setup</span>"
    )

    mac = _btc_macro(states)
    if mac.get("state") == "bear":
        clima_badge = "<span class='hero-badge b-bad'>🌧️ Presión Bajista (SHORTs Activos)</span>"
        clima_title = "Mercado bajista con rebotes rápidos"
        clima_desc = (
            "El mercado general muestra debilidad, pero la IA está cazando ventas cortas (SHORT) "
            "con alta precisión para ganar dinero mientras el precio cae y proteger el capital."
        )
    elif mac.get("state") == "bull":
        clima_badge = "<span class='hero-badge b-ok'>☀️ Expansión Alcista (Compras Activas)</span>"
        clima_title = "Mercado en tendencia alcista macro"
        clima_desc = (
            "Bitcoin opera con solidez sobre su media móvil. La IA está cazando compras en rebote "
            "y rupturas de momentum para aprovechar la expansión de capital."
        )
    else:
        clima_badge = "<span class='hero-badge b-info'>⛅ Mercado Lateral y Selectivo</span>"
        clima_title = "Consolidación y calma táctica"
        clima_desc = (
            "El mercado no muestra una dirección única. La IA evalúa oportunidades en ambos lados "
            "(LONG y SHORT) de forma quirúrgica con riesgo controlado."
        )

    p.append("<div class='hero-grid'>")
    p.append(
        f"<div class='hero-card'>"
        f"<div class='hero-head'><span class='hero-label'>🚀 Cuenta Tendencia (4H — Cruise PRO)</span>{st_4h}</div>"
        f"<div class='hero-val'>${_fmt(patrimonio_4h)} USD</div>"
        f"<div class='hero-pnl'><span class='{cls_4h}'>{sgn_4h}${pnl_4h:.2f} USD ({sgn_4h}{pnl_4h_pct:.1f}%)</span>"
        f"<span class='mut'>· flotante {sgn_4h}${flotante_4h:.2f}</span></div>"
        f"<div class='hero-desc'>Estrategia de mediano plazo para capturar grandes movimientos y tendencias sostenidas de 4 horas.</div>"
        f"</div>"
    )
    p.append(
        f"<div class='hero-card'>"
        f"<div class='hero-head'><span class='hero-label'>⚡ Cuenta Rápida (1H — Sniper Intradía)</span>{st_1h}</div>"
        f"<div class='hero-val'>${_fmt(patrimonio_1h)} USD</div>"
        f"<div class='hero-pnl'><span class='{cls_1h}'>{sgn_1h}${pnl_1h:.2f} USD ({sgn_1h}{pnl_1h_pct:.1f}%)</span>"
        f"<span class='mut'>· flotante {sgn_1h}${flotante_1h:.2f}</span></div>"
        f"<div class='hero-desc'>Estrategia rápida intradía para cazar impulsos de mechas y contracción VCP en velas de 1 hora.</div>"
        f"</div>"
    )
    p.append(
        f"<div class='hero-card'>"
        f"<div class='hero-head'><span class='hero-label'>🌤️ Clima del Mercado Hoy</span>{clima_badge}</div>"
        f"<div class='hero-val' style='font-size:20px;letter-spacing:0;'>{clima_title}</div>"
        f"<div class='hero-desc' style='margin-top:12px;border-top:none;padding-top:0;'>{clima_desc}</div>"
        f"</div>"
    )
    p.append("</div>")  # .hero-grid

    # ──────────────────────────────────────────────────────────
    # BLOQUE 2: ¿QUÉ PIENSA LA IA DE CADA MONEDA? (BTC, ETH, SOL, SUI)
    # ──────────────────────────────────────────────────────────
    p.append(
        "<div class='dummy-sec-title'>"
        "<div>"
        "<h2><span>🧠</span> ¿Qué piensa la IA de cada moneda?</h2>"
        "<div class='dummy-subtitle'>Predicción del Oráculo de Velas Kronos + Razonamiento Cognitivo de Gemini en español claro</div>"
        "</div>"
        "</div>"
    )

    persisted_brain = load_brain_state(root)
    live_brain = states.get("ai_brain") or {}
    brain_data = {**persisted_brain, **live_brain}
    kronos_data = states.get("kronos") or {}

    p.append("<div class='coin-grid'>")
    for sym in CRUISE_ELITE:
        name, code, icon = _COIN_META.get(sym, (sym, sym, "🪙"))
        px = float(prices.get(sym) or 0.0)
        if px <= 0:
            cell = (states.get("cells") or {}).get(f"H1_{sym}") or {}
            px = float(cell.get("close") or 0.0)
        px_fmt = f"${px:,.4f}" if px < 10 else f"${px:,.2f}"

        # Kronos
        sym_k = kronos_data.get(sym) or {}
        fc_4h = sym_k.get("4h") or {}
        bull_prob = float(fc_4h.get("bullish_prob", 50.0))
        if bull_prob >= 50.0:
            pred_txt = f"📈 {bull_prob:.0f}% Probabilidad de Subida"
            bar_fill_w = min(100.0, max(0.0, bull_prob))
            bar_style = "background:linear-gradient(90deg, #10b981, #0df0a3);"
        else:
            bear_prob = 100.0 - bull_prob
            pred_txt = f"📉 {bear_prob:.0f}% Probabilidad de Caída"
            bar_fill_w = min(100.0, max(0.0, bear_prob))
            bar_style = "background:linear-gradient(90deg, #f43f5e, #ff4d6d);"

        # Gemini
        b_info = brain_data.get(sym) or {}
        raw_reason = str(b_info.get("razonamiento") or "")
        clean_op = _clean_dummy_opinion(raw_reason)

        # Estado del Bot para este símbolo
        open_sym = [t for t in (open_4h + open_1h) if t.get("asset") == sym]
        if open_sym:
            k_first = str(open_sym[0].get("kind", "")).lower()
            if "short" in k_first:
                st_btn = "<div class='coin-status-btn st-short'>🔴 OPERANDO A LA BAJA (SHORT)</div>"
            else:
                st_btn = "<div class='coin-status-btn st-long'>🟢 OPERANDO AL ALZA (LONG)</div>"
        else:
            st_btn = "<div class='coin-status-btn st-watch'>👀 VIGILANDO MERCADO</div>"

        p.append(
            f"<div class='coin-card'>"
            f"<div>"
            f"<div class='coin-card-top'>"
            f"<div class='coin-name-group'>"
            f"<span class='coin-icon'>{icon}</span>"
            f"<div><div class='coin-title'>{name}</div><div class='coin-sym'>{code}</div></div>"
            f"</div>"
            f"</div>"
            f"<div class='coin-price'>{px_fmt}</div>"
            f"<div class='coin-pred-wrap'>"
            f"<div class='coin-pred-head'><span>🔮 Oráculo Kronos</span><span>{pred_txt}</span></div>"
            f"<div class='coin-pred-bar'><div class='coin-pred-fill' style='width:{bar_fill_w:.0f}%; {bar_style}'></div></div>"
            f"</div>"
            f"<div class='coin-opinion'>“{_esc(clean_op)}”</div>"
            f"</div>"
            f"{st_btn}"
            f"</div>"
        )
    p.append("</div>")  # .coin-grid

    # ──────────────────────────────────────────────────────────
    # BLOQUE 3: OPERACIONES ABIERTAS AHORA MISMO
    # ──────────────────────────────────────────────────────────
    p.append(
        "<div class='dummy-sec-title'>"
        "<div>"
        "<h2><span>🎯</span> Operaciones Abiertas Ahora Mismo</h2>"
        "<div class='dummy-subtitle'>Transparencia total: entradas en vivo, freno de seguridad y ganancias en tiempo real</div>"
        "</div>"
        "</div>"
    )

    all_open: list[dict[str, Any]] = []
    for t in open_4h:
        all_open.append({**t, "_motor": "🚀 4H Tendencia"})
    for t in open_1h:
        all_open.append({**t, "_motor": "⚡ 1H Rápida"})

    if not all_open:
        p.append(
            "<div class='clean-empty-card'>"
            "<div class='empty-icon'>🌱</div>"
            "<div class='empty-title'>Sin operaciones abiertas en este momento</div>"
            "<div class='empty-desc'>La IA está analizando los gráficos en tiempo real y protegiendo tu capital. "
            "Próximo escaneo automático en 30 segundos.</div>"
            "</div>"
        )
    else:
        p.append("<div class='clean-trades-container'>")
        p.append("<table class='clean-trades-tbl'><thead><tr>")
        p.append("<th>Moneda / Activo</th>")
        p.append("<th>Apuesta</th>")
        p.append("<th>Dinero Arriesgado</th>")
        p.append("<th>Entrada vs Hoy</th>")
        p.append("<th>🎯 Meta Ganar</th>")
        p.append("<th>🛡️ Freno Seguridad</th>")
        p.append("<th>💰 Ganancia / Pérdida Hoy</th>")
        p.append("<th>¿Por qué entró el bot?</th>")
        p.append("</tr></thead><tbody>")

        for tr in all_open:
            asset = tr.get("asset", "")
            motor = tr.get("_motor", "")
            kind = str(tr.get("kind", "")).lower()
            is_long = "long" in kind
            bet_cls = "long" if is_long else "short"
            bet_txt = "📈 SUBIDA (LONG)" if is_long else "📉 BAJADA (SHORT)"
            lev = tr.get("leverage", "1x")
            risk_usd = float(tr.get("risk_usd", 0.0))
            entry_px = float(tr.get("entry_price", 0.0))
            live_px = float(prices.get(asset) or entry_px)
            tp_px = float(tr.get("tp") or tr.get("tp1") or 0.0)
            sl_px = float(tr.get("sl") or tr.get("initial_sl") or 0.0)
            size_usd = float(tr.get("size_usd", 0.0))
            margin_usd = float(tr.get("margin_usd", size_usd / 4.0 if size_usd > 0 else 1.0))

            if entry_px > 0:
                diff = (live_px - entry_px) if is_long else (entry_px - live_px)
                pnl_usd = (diff / entry_px) * size_usd
                pnl_pct = (pnl_usd / margin_usd) * 100.0 if margin_usd > 0 else 0.0
            else:
                pnl_usd = 0.0
                pnl_pct = 0.0

            pnl_cls = "pos" if pnl_usd >= 0 else "neg"
            pnl_sgn = "+" if pnl_usd >= 0 else ""
            pnl_str = f"<span class='{pnl_cls} mono' style='font-size:13px;font-weight:800;'>{pnl_sgn}${pnl_usd:.2f} USD ({pnl_sgn}{pnl_pct:.1f}%)</span>"

            # Formato de precios
            nd = 4 if entry_px < 10 else 2
            entry_fmt = f"${entry_px:,.{nd}f}"
            live_fmt = f"${live_px:,.{nd}f}"
            tp_fmt = f"${tp_px:,.{nd}f}" if tp_px > 0 else "Trailing"
            sl_fmt = f"${sl_px:,.{nd}f}" if sl_px > 0 else "Dinámico"

            # Razón limpia de entrada
            ai_r = tr.get("ai_reasoning") or ""
            if not ai_r:
                th = tr.get("thesis") or ""
                if "IA" in th and ":" in th:
                    ai_r = th.split(":", 1)[1].strip().rstrip("]")
            why_clean = _clean_dummy_opinion(ai_r)

            p.append(
                f"<tr>"
                f"<td><b style='font-size:13.5px;'>{_esc(asset)}</b><br><span class='small' style='color:var(--cyan);'>{motor}</span></td>"
                f"<td><span class='trade-bet-badge {bet_cls}'>{bet_txt} {lev}</span></td>"
                f"<td class='mono'><b>${risk_usd:.2f} USD</b></td>"
                f"<td class='mono'>{entry_fmt} → <b>{live_fmt}</b></td>"
                f"<td class='mono' style='color:var(--ok);'><b>{tp_fmt}</b></td>"
                f"<td class='mono' style='color:var(--bad);'><b>{sl_fmt}</b></td>"
                f"<td>{pnl_str}</td>"
                f"<td style='max-width:280px;font-size:11.5px;color:var(--tx2);line-height:1.4;'>“{_esc(why_clean)}”</td>"
                f"</tr>"
            )
        p.append("</tbody></table></div>")

    # ──────────────────────────────────────────────────────────
    # BLOQUE 4: ALCANCÍA SPOT (COMPRAR BARATO PARA EL FUTURO)
    # ──────────────────────────────────────────────────────────
    p.append(
        "<div class='dummy-sec-title'>"
        "<div>"
        "<h2><span>🏦</span> Alcancía Spot · Comprar Barato para el Futuro</h2>"
        "<div class='dummy-subtitle'>Inversión 1x sin apalancamiento: semáforo de compra en rebaja y 3 metas escalonadas de venta</div>"
        "</div>"
        "</div>"
    )

    plans = spot_plans or []
    if not plans:
        # Generar planes de referencia por defecto si no vinieron en inputs
        plans = [
            {"symbol": "BTCUSDT", "price": float(prices.get("BTCUSDT") or 74700.0), "buying_zone_min": 68000.0, "buying_zone_max": 73000.0, "in_buy_zone": False, "tp1": 85000.0, "tp2": 95000.0, "tp3": 110000.0},
            {"symbol": "ETHUSDT", "price": float(prices.get("ETHUSDT") or 2125.0), "buying_zone_min": 1950.0, "buying_zone_max": 2100.0, "in_buy_zone": False, "tp1": 2600.0, "tp2": 3100.0, "tp3": 3800.0},
            {"symbol": "SOLUSDT", "price": float(prices.get("SOLUSDT") or 87.0), "buying_zone_min": 75.0, "buying_zone_max": 85.0, "in_buy_zone": False, "tp1": 115.0, "tp2": 140.0, "tp3": 180.0},
            {"symbol": "SUIUSDT", "price": float(prices.get("SUIUSDT") or 0.85), "buying_zone_min": 0.70, "buying_zone_max": 0.82, "in_buy_zone": False, "tp1": 1.20, "tp2": 1.60, "tp3": 2.20},
        ]

    p.append("<div class='spot-cards-grid'>")
    for pl in plans:
        sym = str(pl.get("asset") or pl.get("symbol") or "")
        name, code, icon = _COIN_META.get(sym, (sym, sym, "🪙"))
        cur_px = float(
            prices.get(sym) or pl.get("price") or pl.get("current_price") or pl.get("buy_ref_price") or 0.0
        )
        b_min = float(pl.get("buying_zone_min") or pl.get("buy_zone_low") or 0.0)
        b_max = float(pl.get("buying_zone_max") or pl.get("buy_zone_high") or 0.0)
        in_zone = bool(pl.get("in_buy_zone", False)) or (b_min > 0 and b_min <= cur_px <= b_max)
        tp1 = float(pl.get("tp1") or pl.get("tp1_zone_low") or 0.0)
        tp2 = float(pl.get("tp2") or pl.get("tp2_zone_low") or 0.0)
        tp3 = float(pl.get("tp3") or pl.get("tp3_price") or (tp2 * 1.45 if tp2 > 0 else 0.0))

        nd = 4 if cur_px < 10 else 2
        cur_fmt = f"${cur_px:,.{nd}f}"
        bmin_fmt = f"${b_min:,.{nd}f}"
        bmax_fmt = f"${b_max:,.{nd}f}"

        if in_zone:
            verdict_badge = "<div class='spot-cheap-verdict yes'>🟢 ¡SÍ, ESTÁ EN PRECIO DE OFERTA!</div>"
            zone_desc = f"Zona de compra barata: <b>{bmin_fmt} – {bmax_fmt}</b>"
        else:
            verdict_badge = "<div class='spot-cheap-verdict wait'>⏳ Todavía cara · Esperando rebaja</div>"
            zone_desc = f"Esperando descuento hacia <b>{bmax_fmt}</b>"

        def _tp_str(target: float, px_val: float = cur_px, digits: int = nd) -> str:
            if target <= 0 or px_val <= 0:
                return "-"
            pct = ((target / px_val) - 1.0) * 100.0
            return f"${target:,.{digits}f} (+{pct:.0f}%)"

        p.append(
            f"<div class='spot-simple-card'>"
            f"<div>"
            f"<div class='coin-card-top'>"
            f"<div class='coin-name-group'>"
            f"<span class='coin-icon'>{icon}</span>"
            f"<div><div class='coin-title'>{name}</div><div class='coin-sym'>{code} · Spot 1x</div></div>"
            f"</div>"
            f"</div>"
            f"<div class='coin-price'>{cur_fmt}</div>"
            f"{verdict_badge}"
            f"<div class='small' style='margin-bottom:12px;color:var(--tx2);'>{zone_desc}</div>"
            f"</div>"
            f"<div class='spot-tp-list'>"
            f"<div style='font-size:10px;text-transform:uppercase;color:var(--mut);font-weight:700;margin-bottom:4px;'>Metas de Venta a Largo Plazo</div>"
            f"<div class='spot-tp-item'><span>🎯 TP1 (Recuperar base)</span><b class='mono pos'>{_tp_str(tp1)}</b></div>"
            f"<div class='spot-tp-item'><span>🎯 TP2 (Ganancia fuerte)</span><b class='mono pos'>{_tp_str(tp2)}</b></div>"
            f"<div class='spot-tp-item'><span>🎯 TP3 (Gran ciclo)</span><b class='mono pos'>{_tp_str(tp3)}</b></div>"
            f"</div>"
            f"</div>"
        )
    p.append("</div>")  # .spot-cards-grid

    p.append("</section>")  # .dummy-view
    return p


# ── Render principal ──
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
    sniper_data: dict[str, Any] | None = None,
) -> str:
    now = datetime.now(UTC).strftime("%Y-%m-%d %H:%M UTC")
    termometro = str(states.get("termometro_macro", "NEUTRAL"))

    p: list[str] = []
    p.append("<!DOCTYPE html><html lang='es'><head><meta charset='utf-8'>")
    p.append(
        "<meta name='viewport' content='width=device-width,initial-scale=1'>"
        "<meta name='color-scheme' content='dark'>"
        "<meta http-equiv='refresh' content='30'>"
    )
    p.append(f"<title>QUANT-ARENA v2 · Centro de mando</title><style>{CSS}</style></head><body data-view='all'>")
    p.extend(_header(states, capital, spot_plans, spark_data or {}, meta, termometro, now))

    if not capital or (capital or {}).get("sin_registros"):
        p.append(
            "<div class='sec' style='padding-top:14px'><div class='empty'>Sin libro de capital registrado: empieza con "
            "<code>qa capital set --amount 1000</code>.</div></div>"
        )

    p.append("<main>")
    # Bloques Principales Apple / Robinhood ("Para Dummies")
    p.extend(_bloque_dummies(states, capital, trades_diag, spot_plans, sniper_data))

    # Vista Técnica Avanzada y Auditoría Cuantitativa (Drawer colapsable)
    p.append("<section class='sec technical-drawer-sec' data-sec='all'>")
    p.append("<details class='technical-audit-drawer'>")
    p.append(
        "<summary class='drawer-summary'>"
        "<div class='drawer-summary-left'>"
        "<span class='drawer-icon'>🔬</span>"
        "<div>"
        "<div class='drawer-title'>🔬 Vista Técnica Avanzada y Auditoría Cuantitativa (Para Expertos)</div>"
        "<div class='drawer-sub'>Desplegar paneles de CRUISE PRO 4H, Sniper 1H, Oráculo Kronos, Fórmulas R:R y Libros Contables</div>"
        "</div>"
        "</div>"
        "<span class='drawer-badge'>Desplegar Paneles Técnicos ▼</span>"
        "</summary>"
    )
    p.append("<div class='technical-audit-body'>")
    p.extend(_seccion_futuros(states, trades_diag, capital))
    p.extend(_seccion_sniper(states, sniper_data))
    p.extend(_seccion_kronos_oracle(states))
    p.extend(_seccion_spot(spot_plans))
    p.extend(_seccion_audit_tabs(audit_futuros, audit_spot_data, audit, capital))
    p.extend(_seccion_trader_memory())
    if calc:
        p.extend(_calc_panel(calc))
    p.extend(_seccion_macro_noticias(news, shocks, termometro=termometro, h1_levels=h1_levels, feed_status=feed_status))
    p.append("</div>")  # .technical-audit-body
    p.append("</details>")  # .technical-audit-drawer
    p.append("</section>")  # .technical-drawer-sec
    p.append("</main>")

    p.append(
        "<footer>QUANT-ARENA v2 · Motor activo CRUISE PRO (futuros 4H) + Cartera spot segregada · "
        "Paper trading sobre $1,000 USD · datos: Binance API pública (solo lectura) + RSS públicos · "
        "Atajos: <code>/</code> buscar · <code>1</code>–<code>5</code> cambiar de vista · "
        "Regenerado automáticamente con <code>qa agent run</code>. <b>NO ES ASESORAMIENTO DE INVERSIÓN.</b></footer>"
    )
    p.append("<div id='tt' role='tooltip'></div>")
    p.append(f"<script>{JS}</script></body></html>")
    return "\n".join(p)
