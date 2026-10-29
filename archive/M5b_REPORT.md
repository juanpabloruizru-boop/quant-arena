# INFORME M5b — Contabilidad de capital, filtro R:R ≥ 2.0, Trade Audit, pre-print del dashboard y guía de modificación

**Fecha:** 2026-10-28 · **Commits:** `e9cb0e9` (código+docs+ejemplos) + commit de este informe ·
**CI local:** 110/110 tests · mypy --strict 86 ficheros · ruff limpio ·
**Hashes de entregables:** `docs/evidence/m5b_hashes.txt`

---

## Resumen (5 líneas)

1. Implementado el paquete M5b completo solicitado por JP: libro de capital con cadena de hashes y ecuación patrimonial (`qa capital set/add/status/reset-examples`), filtro de disciplina R:R Neto ≥ 2.0 en CLI/dashboard/watchlist, calculadora aritmética de riesgo (0.5/1/2 %, break-even neto, TP mín 2R/3R), Trade Audit del historial cerrado con tags, y mejoras de operaciones abiertas (break-even, cota 2×ATR, R:R residual).
2. Todo es contabilidad del usuario y geometría observable de precios conforme ADR-008 (addendum B añadido y trazable): el guard de lenguaje NO se relajó — de hecho detectó y obligó a corregir un imperativo propio ("Cierra con…") durante el desarrollo.
3. El filtro R:R ya discrimina en vivo: BTC diario NO CUMPLE (0.88x, extendido +3.6 % sobre SMA50 → escala teórica bloqueada a $0) mientras ETH diario CUMPLE (2.47x); la watchlist muestra ✓/✗ por marco 4H/1D/1W.
4. Datos EJEMPLO precargados y verificados aritméticamente: capital $1,000+$200, ganadora +2.4R ("Tendencia 1D"), perdedora −1.0R ("Ruptura 4H") y las 2 abiertas; `qa capital reset-examples` limpia todo de un golpe (con backup) cuando JP migre a su PC.
5. Guía de personalización `docs/GUIA_MODIFICACION_JP.md` (7 secciones) + pre-print completo del dashboard en este informe + bundle final regenerado.

---

## Entregables

| # | Entregable | Ruta | Verificación |
|---|---|---|---|
| 1 | Libro de capital append-only (cadena SHA-256) | `ledger/user_capital.jsonl` + `src/qa/agent/capital.py` + `src/qa/agent/chain.py` | `qa capital status` reverifica cadena; test `test_capital_ledger_chain_and_net` (tampering rompe cadena) |
| 2 | CLI capital: `set/add/status/reset-examples` | `src/qa/cli.py` | tests CLI offline (`test_cli_capital_set_add_status`, `test_cli_trade_audit_and_reset`) |
| 3 | Filtro R:R ≥ min_rr (geometría + trades) | `src/qa/agent/geometry.py`; `filtro_rr` en `config/watchlist.yaml` | tests `test_rr_neto_trade_formula`, `test_rr_tendencia_early_vs_extended_vs_below`, `test_cli_trade_open_rr_block_and_force` |
| 4 | Calculadora de riesgo (CLI + panel inline sin recursos externos) | `qa trade calc`; panel 4 del dashboard | test `test_cli_trade_calc` (fórmulas exactas) + `test_breakeven_and_tp_minimos` (coherencia inversa: con TP mín 2R el R:R neto = 2.000) |
| 5 | Trade Audit (CLI + panel) con `--tag/--note/--ts` | `src/qa/agent/audit.py`; `qa trade audit [--json]` | test `test_audit_metrics_and_tags` (+2.4R/−1.0R → PF 3.94, maxDD 12.50) |
| 6 | Operaciones abiertas mejoradas | `src/qa/agent/telemetry.py` (`trade_geometry`) | test `test_trade_geometry_breakeven_and_atr_bound` (long y short) |
| 7 | Dashboard M5b (barra patrimonio 5 tarjetas, paneles 4/5/6, glosario ampliado) | `src/qa/report/dashboard.py` → `reports/dashboard/index.html` | `test_dashboard_m5b_panels_and_guard` + `test_dashboard_language_guard` existente (sin cambios) |
| 8 | Guía de modificación para JP | `docs/GUIA_MODIFICACION_JP.md` | revisión humana (orquestador/JP) |
| 9 | ADR-008 addendum B + glosario M5b | `docs/adr/ADR-008-*.md`, `docs/GLOSARIO.md` | commit `e9cb0e9` |
| 10 | Ejemplos sembrados en libros | `ledger/user_capital.jsonl` (2), `ledger/user_trades.jsonl` (6 líneas: 2 abiertas M4 + 2 cerradas M5b) | salida `qa trade audit` reproducida abajo |
| 11 | Tests nuevos | `tests/unit/test_m5b_tools.py` (17 tests) | 110/110 suite completa |

**Modelo de comisiones usado (trazable a `config/costs.yaml`, VERIFICADO 2026-10-27):** taker spot 0.100 %/lado → ida y vuelta 0.200 %; taker perp 0.050 %/lado → ida y vuelta 0.100 %. PnL realizado = bruto − comisiones i/v estimadas sobre nocional de entrada. PnL flotante = bruto (las comisiones pendientes se muestran aparte). Break-even neto exacto: long `E×(1+f)/(1−f)`, short `E×(1−f)/(1+f)`.

---

## Gates

Condiciones heredadas del gate M5-final y su estado en M5b:

| Condición | Estado |
|---|---|
| Motor forward-v1 con fills t+1 (Q3) intacto | ✅ sin cambios (`qa forward run` y workflow pinned a tag `forward-v1` no se tocaron; suite completa verde) |
| ADR-008: cero imperativos de trading en el dashboard | ✅ guard `PROHIBIDOS` intacto + test dedicado; el guard **mordió de verdad** (ver "Qué aprendimos") |
| Escala aritmética etiquetada "teórica/informativo" | ✅ etiqueta mantenida en las dos rutas (patrimonio vivo y config) |
| Nada de órdenes/claves/dinero real/daemons | ✅ M5b solo añade contabilidad local, endpoints públicos de lectura y aritmética |
| Holdout sin re-abrir | ✅ `ledger/holdout_access.log` sin cambios (5 entradas, las mismas de M3b) |
| Sin señales nuevas no preregistradas | ✅ el filtro R:R es umbral de disciplina del USUARIO sobre geometría descriptiva; no se evalúa como hipótesis ni se presenta como alpha (etiquetas y addendum B explícitos) |

---

## Resultados

### A. Ecuación patrimonial en vivo (`qa capital status`, 2026-10-28)

Salida literal del comando (precios vivos de Binance, solo lectura):

```
═══ ECUACIÓN PATRIMONIAL (contabilidad del usuario · M5b) ═══
1) Capital Aportado Neto: 1,200.00 USD
   fecha            tipo          importe   acumulado  nota
   2026-09-15T10:00 inicial     +1,000.00    1,000.00  EJEMPLO: capital inicial [EJEMPLO]
   2026-10-01T10:00 flujo         +200.00    1,200.00  EJEMPLO: adición mensual [EJEMPLO]
2) PnL Realizado Acumulado: +36.73 USD (3.06% s/ aportado) · 2 cerradas · comisiones est. 1.10 USD descontadas
3) PnL Flotante: +13.08 USD (1.09% s/ aportado) · 2 abiertas · bruto de comisiones
4) PATRIMONIO TOTAL (Equity Vivo): 1,249.81 USD
   = aportado 1,200.00 + realizado +36.73 + flotante +13.08
5) Riesgo en Mesa (Portfolio Heat): 67.20 USD = 5.38% del patrimonio
   c3bc992c (BTCUSDT): riesgo aportado 34.59 USD
   024ee7dc (ETHUSDT): riesgo aportado 32.61 USD
```

Comprobaciones aritméticas (trazables): ganadora BTC 400×(87756/78000−1)=+50.03 bruto −0.80 fees = **+49.23 neto = +2.400R** (riesgo 400×4000/78000=20.51); perdedora ETH 300×(2302.40/2400−1)=−12.20 −0.30 = **−12.50 neto = −1.000R** (riesgo 12.50); heat BTC 500×(1−74000/79500)=34.59 + ETH 300×(1−2050/2300)=32.61 = **67.20**.

### B. Trade Audit en vivo (`qa trade audit`)

```
cierre     activo    tipo/marco      dur.       entrada    salida  tamaño$ RR ini  PnL neto$    PnL%      R  tag
2026-10-10 BTCUSDT   spot/1d         20d 3h   78,000.00 87,756.00      400  2.44x     +49.23  +12.51   2.4R  Tendencia 1D [EJEMPLO]
2026-10-14 ETHUSDT   future_long/4h  1d 22h    2,400.00  2,302.40      300   3.0x     -12.50   -4.07  -1.0R  Ruptura 4H [EJEMPLO]

operaciones cerradas: 2 · win rate: 50.0% · neta: +36.73 USD (3.06% s/ aportado · 5.25% s/ rotación)
profit factor: 3.94 · esperanza: +18.36 USD / 0.7R · R:R medio realizado: 0.7R
mejor/peor (USD): BTCUSDT +49.23 · ETHUSDT −12.50 · mejor/peor (R): +2.4 · −1.0
max drawdown realizado: 12.50 USD · operaciones sin SL: 0
por tag → Ruptura 4H: 1 op, 0.0%, −12.50 USD, R medio −1.0 · Tendencia 1D: 1 op, 100.0%, +49.23 USD, R medio +2.4
```

### C. Filtro de disciplina en `qa trade open` / `qa trade calc` (ejemplos reales de la corrida)

Bloqueo (salida código 2, nada escrito en el libro):

```
⚠ ALERTA DE DISCIPLINA: R:R Neto = 0.92x (< mínimo 2.0x configurado por JP)
registro BLOQUEADO por tu filtro de disciplina (no se ha escrito nada).
Si aun asi quieres anotarla: repite con --force-low-rr (quedara marcada rr_forzado=true en el libro).
```

Paso del filtro (ejemplos sembrados): `✓ FILTRO R:R >= 2.0: CUMPLE (R:R Neto 2.31x)` (ganadora) y `… 2.91x` (perdedora). Calculadora en vivo (patrimonio base automático = equity vivo 1,253 USD en ese momento):

```
qa trade calc --entry 80848 --sl 78500 --tp 87000 --kind spot
 Riesgo % |   Riesgo $ |     Tamaño $ |   Unidades | % patrim.
     0.5% |       6.27 |       215.80 |   0.002669 |     17.2%
     1.0% |      12.53 |       431.59 |   0.005338 |     34.4%
     2.0% |      25.07 |       863.19 |   0.010677 |     68.9%
Precio Break-Even Neto (taker i/v): 81,009.86
TP que satisface R:R = 2.0x: 86,029.09 · R:R = 3.0x: 88,538.78
✓ FILTRO R:R >= 2.0: CUMPLE (Asimetría 2.39x)
```

Con `--tp 83000` la misma configuración da `0.79x` → ALERTA + NO CUMPLE + exit 2. La coherencia inversa está testeada: con el TP mín calculado, `rr_neto_trade` devuelve exactamente 2.000/3.000.

### D. PRE-PRINT COMPLETO DEL DASHBOARD (`reports/dashboard/index.html`)

Transcripción fiel del contenido renderizado el **2026-10-28 18:38 UTC** (datos vivos
`2026-10-28T18:38:17+00:00`, git `e9cb0e9`-pre, archivo autocontenido de ~39 KB: HTML+CSS+SVG+JS
inline, sin recursos externos). Los paneles se muestran en el orden del archivo.

**Cabecera y banner (siempre visibles):**

> QUANT-ARENA v2 · Centro de mando — Generado: 2026-10-28 18:38 UTC · herramienta de investigación, **no es asesoramiento de inversión**
> ⚠ Este panel muestra **estados descriptivos** de reglas investigadas y la CONTABILIDAD de tus propias operaciones. No da órdenes de compra/venta. H1 y H2 están **SIN VENTAJA DEMOSTRADA** (INCONTRASTABLE, preregistro v1.4); H3-BTC pasó a nivel de signo con edge frágil a costes ×2. El filtro R:R, la calculadora y el Trade Audit son aritmética sobre TUS niveles y TUS registros. Ningún número de aquí es una promesa de rentabilidad.

**Barra de Resumen de Cuenta (5 tarjetas):**

```
┌─────────────────────┬─────────────────────┬─────────────────────┬─────────────────────┬─────────────────────┐
│ CAPITAL APORTADO    │ PNL CERRADO (NETO)  │ PNL ABIERTO (VIVO)  │ PATRIMONIO TOTAL    │ RIESGO EN MESA      │
│ NETO                │                     │                     │ (EQUITY VIVO)       │ (PORTFOLIO HEAT)    │
│   1,200.00 USD      │   +36.73 USD        │   +13.08 USD        │   1,249.81 USD      │   67.20 USD         │
│ inicial+adiciones−  │ 3.06% s/ aportado · │ bruto de comisiones │ = aportado+cerrado  │ 5.38% del patrimonio│
│ retiros             │ fees 1.10 descont.  │ (se descuentan al   │ +abierto · base de  │ si TODOS los SL     │
│                     │                     │ cerrar) · precios   │ la escala teórica   │ saltaran hoy a la   │
│                     │                     │ públicos en vivo    │                     │ vez                 │
└─────────────────────┴─────────────────────┴─────────────────────┴─────────────────────┴─────────────────────┘
```

**Panel 1 · Mis operaciones abiertas (registro del usuario):**

| Op | Activo/Tipo/Marco | PnL | Dist. SL/TP (tuyos) | Tiempo | R:R inic.→residual | Break-even neto | Cota 2×ATR (tu marco) | SMA50 de tu marco | Contexto tendencia | Seguimiento |
|---|---|---|---|---|---|---|---|---|---|---|
| `c3bc992c` EJEMPLO | BTCUSDT · spot · 1d | +1.572 % (+7.86 USD) | 8.36 % / 17.65 % | 0d 2h | 2.82 → 2.11 | 79,659.16 · superado ✓ | 76,858.03 · marco 1d, estadística no stop | SMA50(1d) 80,296.84 — por encima (+3.77 %) | 1D close +3.8 % vs SMA50; regla en LONG | SIN ALERTAS |
| `024ee7dc` EJEMPLO | ETHUSDT · future_long · 4h | +1.739 % (+5.22 USD) | 12.39 % / 23.93 % | 0d 2h | 2.4 → 1.93 | 2,302.30 · superado ✓ | 2,278.58 · marco 4h | SMA50(4h) 2,391.10 — por debajo (−3.19 %) | 1D close +1.1 % vs SMA50; regla en LONG | SIN ALERTAS |
| `97f22a6d` EJEMPLO | BTCUSDT · spot | — | — | — | — | — | n/d | — | — | CERRADA por el usuario |
| `6fe34f81` EJEMPLO | ETHUSDT · future_long | — | — | — | — | — | n/d | — | — | CERRADA por el usuario |

Nota al pie del panel: break-even neto = precio con PnL 0 tras comisiones taker i/v; cota 2×ATR = precio ∓ 2×ATR(14) del marco (referencia estadística, NO un stop propuesto); R:R residual = dist. TP / dist. SL desde el precio de hoy.

**Panel 2 · Reglas congeladas (m3a-freeze) — estados de hoy:**

| Regla | Veredicto del preregistro | Estado hoy | Detalle |
|---|---|---|---|
| H1 tendencia BTCUSDT (sma50_s25 · diario) | ⚠ SIN VENTAJA DEMOSTRADA (INCONTRASTABLE) | **LONG** | close 83,321.81 vs SMA50 80,296.84 (+3.8 %) · vol20d 42.9 % · posición de la regla 60 % (0.598) |
| H1 tendencia ETHUSDT (sma50_s25 · diario) | ⚠ SIN VENTAJA DEMOSTRADA (INCONTRASTABLE) | **LONG** | close 2,574.14 vs SMA50 2,547.03 (+1.1 %) · vol20d 44.5 % · posición de la regla 65 % (0.647) |
| H2 momentum (L26_N10 · semanal) | ⚠ SIN VENTAJA DEMOSTRADA (INCONTRASTABLE) | CESTA TEÓRICA | ZEC, NEAR, UNI, SOL · top-10 PIT: BTC, ETH, ZEC, SOL, XRP, NEAR, BNB, SUI, UNI, DOGE |
| H3 carry BTCUSDT (w30_t5 · delta-neutral) | ✅ VALIDADA (PASA in-sample + holdout signo) — con costes ×2 el edge es ~0 | INACTIVA (MA30 ≤ 5 % anual) | MA30d 4.4 % · MA7d 6.48 % (subiendo) · último funding 0.01 %/8h · próximo 2026-10-29T00:00Z |
| H3 carry ETHUSDT (w30_t5 · delta-neutral) | ✖ NO PASA (holdout) | INACTIVA (MA30 ≤ 5 % anual) | MA30d 4.07 % · MA7d 5.96 % · último funding 0.01 %/8h · próximo 2026-10-29T00:00Z |

*Niveles observables de H1 (diario) — estadística descriptiva del precio, no hipótesis ni señal:*

| Activo | Precio | Nivel SMA50 (dist.) | ATR14 | Rango estadístico [−2×ATR, +3×ATR] | Filtro R:R ≥ 2.0 (entrada nueva hoy) | Exposición regla | Escala teórica s/ capital de referencia |
|---|---|---|---|---|---|---|---|
| BTCUSDT | 83,321.81 | 80,296.84 (+3.77 %) | 1,945.87 (2.34 %) | [79,430.06 ; 89,159.43] | ✖ **FILTRO R:R >= 2.0: NO CUMPLE (Asimetría 0.88x < 2.0 — Extendido)** · Reward 2,812.65 / Risk 3,191.61 · extensión +3.63 % | 60 % | **0 USD — BLOQUEADO por filtro R:R < 2.0** (entrada nueva hoy no cumpliría tu asimetría mínima; sin filtro la aritmética sería 60 % × 1,249.81 = 747.39 USD, informativo) |
| ETHUSDT | 2,574.14 | 2,547.03 (+1.06 %) | 74.76 (2.90 %) | [2,424.61 ; 2,798.43] | ✓ **FILTRO R:R >= 2.0: CUMPLE (Asimetría 2.47x)** · Reward 197.18 / Risk 79.91 · extensión +1.05 % | 65 % | 808.63 USD (= 65 % × 1,250 USD [patrimonio vivo — tu contabilidad M5b]; escala teórica/informativo) |

**Panel 3 · Telemetría watchlist 4H·1D·1W** (descriptiva; no constituye hipótesis evaluada ni señal):

| Símbolo | Precio | 24 h | Choque | 4H vs SMA50 | 1D vs SMA50 | 1W vs SMA50 | ATR14 % 4H/1D/1W | Filtro R:R ≥ 2.0 (4H·1D·1W) |
|---|---|---|---|---|---|---|---|---|
| BNBUSDT | 772.45 | −0.9 % | no | encima +0.21 % | encima +5.0 % | debajo −4.11 % | 1.07/2.54/7.2 | ✓ 2.363x · ✗ 0.577x · no aplica |
| BTCUSDT | 83,321.81 | −2.6 % | no | debajo −2.18 % | encima +3.77 % | debajo −3.55 % | 0.89/2.34/7.09 | no aplica · ✗ 0.881x · no aplica |
| ETHUSDT | 2,574.14 | −4.57 % | no | debajo −3.19 % | encima +1.06 % | debajo −1.34 % | 1.33/2.9/8.44 | no aplica · ✓ 2.468x · no aplica |
| SOLUSDT | 116.30 | −3.65 % | no | debajo −3.41 % | encima +8.36 % | debajo −7.72 % | 1.42/3.82/10.18 | no aplica · ✗ 0.472x · no aplica |
| XRPUSDT | 1.4215 | −5.05 % | no | debajo −0.91 % | debajo −0.29 % | debajo −16.73 % | 1.44/4.65/12.15 | no aplica · no aplica · no aplica |
| ZECUSDT | 1,187.02 | −10.61 % | no | n/d | encima +0.95 % | n/d | —/9.96/— | n/d · ✓ 2.848x · n/d |
| NEARUSDT | 4.464 | −16.33 % | no | n/d | encima +38.31 % | n/d | —/13.31/— | n/d · ✗ 0.439x · n/d |
| SUIUSDT | 1.0408 | −7.76 % | no | n/d | encima +15.58 % | n/d | —/9.88/— | n/d · ✗ 1.182x · n/d |
| UNIUSDT | 7.12 | −9.99 % | no | n/d | encima +1.06 % | n/d | —/9.32/— | n/d · ✓ 2.827x · n/d |
| DOGEUSDT | 0.08404 | −5.62 % | no | n/d | debajo −5.66 % | n/d | —/5.73/— | n/d · no aplica · n/d |

Leyenda del panel: ✓ = `FILTRO R:R >= 2.0: CUMPLE (Asimetría X.Xx)` · ✗ = `NO CUMPLE (Asimetría X.Xx < 2.0 — Extendido)` · «no aplica» = precio bajo SMA50 (sin tendencia alcista en el marco) · «n/d» = marco no descargado para miembros PIT fuera de la watchlist config (solo tienen 1D). El tooltip de cada celda muestra la etiqueta completa. Lectura didáctica en vivo: NEAR (+38 % sobre su SMA50 diaria) es el caso textbook de «extendido» (0.44x); BNB recién cruzando su SMA50 en 4H tiene la mejor asimetría (2.36x). **Ninguna de estas etiquetas es una señal de entrada: es la regla de disciplina de JP aplicada a geometría observable.**

**Panel 4 · Calculadora de riesgo por operación (simulador aritmético):**

Cabecera del panel: «Aritmética sobre TUS propios números — no es sizing recomendado ni señal. Evaluación para 0.5 %, 1.0 % y 2.0 % de riesgo sobre el patrimonio, break-even neto y TP que satisface tu regla R:R (2.0x/3.0x). Idéntico a `qa trade calc`». Línea de contexto renderizada: *Patrimonio de referencia: **1,249.81 USD** (patrimonio vivo — tu contabilidad M5b) · comisiones taker por lado: spot 0.1 %, perp 0.05 % (costs.yaml VERIFICADO) · R:R mínimo de tu disciplina: **2.0x***. Controles: entradas numéricas (Entrada / SL / TP / Patrimonio), selector de instrumento (spot · perp long · perp short) y botón «Calcular»; la tabla de resultados (3 filas de riesgo + break-even + TP mín 2R/3R + badge del filtro con `ALERTA DE DISCIPLINA` si incumple) se calcula en JavaScript inline con las constantes inyectadas desde la config (una sola fuente de verdad; mismas fórmulas que el CLI, verificado por tests). Ejemplo de salida con los inputs de la sección C: filas 6.27/215.80 · 12.53/431.59 · 25.07/863.19 USD; BE 81,009.86; TP2R 86,029.09; TP3R 88,538.78; badge CUMPLE 2.39x.

**Panel 5 · Trade Audit — historial de operaciones cerradas:**

| Cierre | Activo/Tipo/Marco | Duración | Entrada | Salida | Tamaño | R:R inic. (bruto) | PnL neto $ | PnL % | R logrado | Tag | Nota |
|---|---|---|---|---|---|---|---|---|---|---|---|
| 2026-10-10 EJEMPLO | BTCUSDT · spot · 1d | 20d 3h | 78,000.00 | 87,756.00 | 400.00 | 2.44x | **+49.23** (bruto 50.03 − fees 0.80) | +12.508 % | **+2.4R** | Tendencia 1D | EJEMPLO: ganadora +2.4R · cierre en TP |
| 2026-10-14 EJEMPLO | ETHUSDT · future_long · 4h | 1d 22h | 2,400.00 | 2,302.40 | 300.00 | 3.0x | **−12.50** (bruto −12.20 − fees 0.30) | −4.067 % | **−1.0R** | Ruptura 4H | EJEMPLO: perdedora −1.0R · stop alcanzado |

| Métrica global | Valor |
|---|---|
| Operaciones cerradas | 2 |
| Win Rate | 50.0 % |
| Ganancia/Pérdida Neta | +36.73 USD · 3.06 % s/ capital aportado · 5.25 % s/ rotación desplegada |
| Profit Factor | 3.94 |
| Esperanza matemática por operación | +18.36 USD · 0.700 R |
| R:R medio realizado | 0.700 R |
| Mejor / peor operación ($) | mejor BTCUSDT +49.23 · peor ETHUSDT −12.50 |
| Mejor / peor operación (R) | mejor BTCUSDT +2.40 · peor ETHUSDT −1.00 |
| Max Drawdown realizado (sobre PnL acumulado) | 12.50 USD |
| Operaciones sin SL (R no computable) | 0 |

| Tag (diario de trading) | Ops | Win Rate | PnL neto | R medio |
|---|---|---|---|---|
| Ruptura 4H | 1 | 0.0 % | −12.50 USD | −1.000 R |
| Tendencia 1D | 1 | 100.0 % | +49.23 USD | +2.400 R |

*Aviso de honestidad incorporado al panel: con 2 operaciones de ejemplo estas métricas no significan nada estadísticamente; el audit existe para que JP mida SU disciplina (tags, R:R forzado, expectancy) a lo largo de meses, no para celebrar rachas.*

**Panel 6 · Historial de capital (libro contable del usuario):**

| Fecha (UTC) | Tipo | Importe | Acumulado | Nota |
|---|---|---|---|---|
| 2026-09-15T10:00 EJEMPLO | inicial | +1,000.00 USD | 1,000.00 USD | EJEMPLO: capital inicial |
| 2026-10-01T10:00 EJEMPLO | flujo | +200.00 USD | 1,200.00 USD | EJEMPLO: adición mensual |

**Panel 7 · Choques técnicos y noticias (vigilancia):**

Sin choques técnicos activos en la corrida (umbrales en `config/watchlist.yaml`). Titulares relevantes de las últimas 72 h (10 de 27; sólo se listan, las alertas de riesgo por keyword aparecen además en el seguimiento de tus operaciones):

| Titular | Keyword/Activo · Fecha | Fuente |
|---|---|---|
| Fed Stands Pat, Bitcoin Holds Steady—But a December Rate Hike Is in Play | BTC · 10-28 18:25 | Decrypt |
| Crypto PAC spending before midterms possibly obscured after reported FEC hack | [hack] · 10-28 17:05 | Cointelegraph |
| Bitcoin price bounce rejected at 50-day trend line ahead of FOMC, earnings | BTC · 10-28 16:53 | Cointelegraph |
| Wall Street's Fast Money Fled Bitcoin ETFs, Sovereign Funds Stepped In | BTC · 10-28 16:15 | Decrypt |
| Fed Rate Decision: What Markets and Bitcoin Traders Can Expect | BTC · 10-28 15:15 | Decrypt |
| Google Cloud outlines MPC service for institutional Bitcoin custody | BTC · 10-28 13:47 | Cointelegraph |
| Moody's Rates Ripple's $2.6B RLUSD Stablecoin A2, a Day After OCC Bank Approval | [ban] XRP · 10-28 12:16 | Decrypt |
| Settlement concerns prompt Euronext to halt CoinShares' Zcash ETP ahead of debut | [halt] · 10-28 11:24 | Cointelegraph |
| Mirae Asset Securities issues tokenized notes on Solana | [sec] SOL · 10-28 11:05 | Cointelegraph |
| Bithumb Says Hackers Accessed Internal System, Leaking Personal Data | [hack] · 10-28 10:57 | Decrypt |

Feeds: Cointelegraph ok (13 relevantes/72 h) · Decrypt ok (14/72 h) · CoinDesk no disponible (bloqueado; `tolerar_fallo: true`).

**Panel 8 · Evidencia científica (resumen M0-M3)** — sin cambios respecto a M5: tabla de las 4 filas de veredictos (H1/H2 INCONTRASTABLE; H3-BTC PASA signo con caveat costes ×2; H3-ETH NO PASA) + sparklines SVG de 90 velas diarias BTC/ETH + nota de rigor (n_trials=38, DSR/PBO/CPCV/RC, holdout abierto UNA vez, potencia H1 9.5-18.5 %).

**Panel 9 · Glosario para JP** (desplegable) — ampliado en M5b con: Cota 2×ATR, Break-even neto, R:R Neto, Filtro R:R ≥ 2.0, Múltiplo R, Portfolio Heat, Equity Vivo, Profit Factor/Esperanza, y la nota de que la Escala teórica usa el patrimonio vivo y se bloquea cuando el filtro no cumple.

**Footer:** «QUANT-ARENA v2 · M4/M5 operativo + M5b contabilidad del usuario (alcance conforme ADR-008 + addendum B) · holdout usado una única vez en M3b · datos: Binance API pública (solo lectura) + RSS públicos · se regenera con `qa agent run`».

### E. Resumen de la Guía de Modificación (`docs/GUIA_MODIFICACION_JP.md`)

7 secciones en lenguaje llano: **(0)** instalación en su PC desde el bundle (git init/fetch/reset + `make git-config` + `make install`); **(1)** operación diaria desde cero en 6 pasos (reset-examples → capital set/add → status → calc → open/close con tag → `qa agent run`), con rutina diaria sugerida de 5 minutos; **(2)** cómo cambiar `min_rr_ratio`, la watchlist y los feeds RSS/keywords en `config/watchlist.yaml` (y por qué `costs.yaml` no se edita a mano); **(3)** tabla "quiero hacer X → archivo → función" para indicadores/columnas/estilos, con advertencia explícita de NO tocar `signals.py` (celdas congeladas); **(4)** qué hace el guard de lenguaje, cómo editarlo bajo su responsabilidad en una copia local y por qué le recomendamos no hacerlo (divergencia de hashes de evidencia); **(5)** flujo seguro de 3 comandos (`pytest` → `qa agent run` → `git commit`); **(6)** tabla de problemas comunes (cadena rota, sin precio vivo, exit 2 del filtro…); **(7)** lo que la guía NO enseña (órdenes reales, señales de altcoins, leer el forward antes de 30 días) y por qué.

---

## Desviaciones

1. **Etiqueta compacta en la watchlist**: la etiqueta completa `FILTRO R:R >= 2.0: CUMPLE (Asimetría X.Xx)` se renderiza íntegra en el panel H1 y en los tooltips (atributo `title`) de cada celda de la watchlist; en la columna visible de la watchlist se usa la forma compacta `✓ 2.363x / ✗ 0.439x / no aplica` con leyenda que reproduce las etiquetas completas (una tabla con 3 etiquetas largas por fila × 10 símbolos sería ilegible). Desviación de formato, no de contenido.
2. **`qa trade calc` con configuración incumplidora sale con código 2** tras mostrar toda la información (incluida la ALERTA). El pedido decía "muestra un aviso destacado"; el código de salida adicional facilita guiones y no oculta nada. `qa trade open` sí bloquea la ESCRITURA (nada se registra) salvo `--force-low-rr`, exactamente como se pidió.
3. **PnL flotante bruto** (las comisiones pendientes se muestran como dato aparte en tarjetas/CLI) para no mezclar convenciones: el realizado sí es neto. Documentado en las propias tarjetas.
4. **`reset-examples` reescribe las cadenas** (única mutación permitida del libro): solo elimina registros `example=true`, con backup previo en `ledger/backup/` (gitignored) y re-verificación posterior. Añadido al ADR-008 addendum B para que quede constancia del alcance exacto.
5. Las operaciones cerradas siguen apareciendo en el panel 1 marcadas «CERRADA por el usuario» (comportamiento heredado de M4); su detalle completo vive en el panel 5 (Trade Audit).

## Limitaciones

- **El R:R geométrico de la watchlist NO es una hipótesis evaluada**: es la regla de disciplina de JP aplicada a geometría estándar SMA50/ATR14. El proyecto mantiene que ninguna de las 3 familias demostró ventaja; el filtro no cambia eso ni "bendice" entradas (etiquetas y addendum B lo dicen en el propio panel).
- Comisión modelada como taker ida y vuelta sobre nocional de entrada: si JP usa órdenes limit (maker) o BNB descuento, el break-even real será algo mejor; el modelo es el conservador.
- La cota 2×ATR de un trade perp usa el ATR del spot del mismo marco (el agente solo descarga velas spot de la watchlist): diferencia despreciable para una referencia estadística, documentada.
- Portfolio heat asume SL efectivos al precio exacto del stop (sin gap ni slippage): en un crash con huecos la pérdida real puede ser mayor. Las operaciones sin SL se listan como "riesgo no acotado" y NO computan (subestiman el heat si JP las mantiene).
- La calculadora inline del dashboard necesita JavaScript habilitado (inline, sin red); el CLI `qa trade calc` cubre el mismo cálculo sin JS.
- Métricas de auditoría sobre 2-4 operaciones de ejemplo: sin poder estadístico alguno (ilustración de la mecánica contable).

## Riesgos

- **Riesgo de lectura como consejo** (el de siempre, ahora con más números): mitigado con etiquetas en cada panel, banner, glosario, guard intacto y sección 7 de la guía. El filtro R:R puede "sentirse" como una señal de entrada cuando dice CUMPLE: las etiquetas repiten "entrada nueva hipotética HOY" y "no es señal".
- **`--force-low-rr` normaliza la indisciplina**: mitigado dejando marca permanente `rr_forzado=true` en el libro (el audit futuro puede desglosarla; hoy la columna existe en el JSONL).
- **Reset accidental**: mitigado con confirmación interactiva (o `--yes`), backups automáticos y alcance limitado a registros EJEMPLO.
- **Deriva de la copia local de JP** (si edita el guard o las reglas): la guía explica que divergir rompe la comparabilidad de hashes; los sellos científicos (prereg, m3a-freeze, m3b-complete) no se ven afectados porque viven en tags firmados.

## Preguntas

1. **Q1 (menor, no bloqueante):** ¿el orquestador quiere que `reset-examples` también purgue los backups tras N días, o los conservamos indefinidamente (postura actual: indefinidamente, gitignored)? No requiere respuesta para el gate.
2. Sin más preguntas: el paquete M5b se implementó literalmente según la solicitud; no se necesitó ninguna decisión de capital/alcance/preregistro nueva (la ratificación ADR-008 addendum B ya venía dada en la directiva).

## Qué aprendimos

- **El guard de lenguaje demostró su valor en desarrollo real**: el primer borrador del panel de auditoría decía "Cierra con `qa trade close …`" y `render_dashboard` reventó con `AssertionError: lenguaje prohibido: CIERRA`. Se reformuló en voz pasiva ("Los cierres se anotan con…"). El test no es decorativo: muerde incluso al agente que lo escribió.
- **El filtro R:R discrimina de verdad en el mercado actual**: misma sesión, mismos datos → BTC extendido (0.88x, escala bloqueada) vs ETH cerca de su media (2.47x, cumple). Es exactamente la semántica que JP pidió ("entrada temprana con stop corto vs entrada tardía con stop lejano") y se valida sola contra la intuición geométrica.
- **Testear la inversa de las fórmulas es barato y potente**: `tp_minimo_para_rr(k)` alimentado de vuelta a `rr_neto_trade` debe devolver exactamente k — un test de 2 líneas que blindó la calculadora contra errores algebraicos de signo (long/short) que las pruebas manuales no habrían visto.
- **La contabilidad obliga a decidir convenciones** (flotante bruto vs neto, heat sobre aportado vs sobre equity, R sin SL): todas quedaron explícitas en docstrings, tarjetas del dashboard y limitaciones de este informe; ninguna es "la obvia" sin documenting.

## Solicitud GATE

**Solicito `GATE APROBADO M5b`** sobre:

- 110/110 tests (17 nuevos), mypy --strict 86 ficheros, ruff limpio;
- entregables 1-11 de la tabla con hashes en `docs/evidence/m5b_hashes.txt`;
- ADR-008 addendum B (contabilidad + geometría del usuario; guard intacto; sigue sin requerirse v1.5);
- holdout SIN tocar (log con las mismas 5 entradas de M3b); motor forward-v1 y workflow sin cambios;
- bundle final `quant-arena-M5.bundle` regenerado tras este commit (historial completo + 9 tags; se reporta tamaño y verificación en el mensaje de entrega).

Tras la aprobación (o correcciones), el siguiente paso sigue siendo la decisión ya elevada en M5-final: **M6 = operación y revisión** (30 días de forward antes de la primera lectura, ~2026-11-27) o cierre definitivo del proyecto con el veredicto negativo documentado. Quedo a la espera; no inicio M6 ni toco el holdout sin gate.
