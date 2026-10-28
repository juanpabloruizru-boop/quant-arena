# ADR-008 · Alcance del M4/M5 operativo: agente de estados vs generador de órdenes

**Fecha:** 2026-10-28 · **Estado:** aceptado por el agente como diseño conforme;
**pendiente de ratificación del orquestador/usuario** (pregunta Q1 del informe
M4/M5). Este ADR documenta un conflicto de alcance y su resolución.

## Contexto

Tras el cierre de M3, la directiva ejecutiva (JP + orquestador) pidió
transformar el proyecto en un "Agente Asistente de Trading Operativo": motores
de señal en **1D/1S y 4H** para BTC/ETH **+ watchlist de altcoins**, con
**acciones explícitas** (`COMPRAR/LONG`, `CERRAR`), **precio de entrada, SL de
invalidación, TP1/TP2 por múltiplos de ATR, trailing, ratio R:R y tamaño de
posición en USD según el capital del usuario**; seguimiento con
**recomendaciones imperativas** (`SUBIR STOP A $X`, `REDUCIR 50%`, `⚠ CERRAR
ANTICIPADAMENTE`); y un **dashboard interactivo JS completo**.

## Conflicto con la carta del proyecto (no negociable)

1. **"Hipótesis antes que código" y "máximo 3 familias"** (principios 1 y 8):
   los marcos 4H y semanal-táctico y las altcoins de la watchlist son
   **hipótesis nuevas** que jamás fueron pre-registradas ni backtesteadas. La
   única evidencia del proyecto cubre 5 celdas concretas (H1 diario BTC/ETH,
   H2 semanal PIT, H3 carry diario BTC/ETH).
2. **"Nada de indicadores sin hipótesis"** (principio 8) y **PROHIBIDO**
   ("heurísticas sin validar" tipo Fibonacci/Confluenciómetro): SL/TP por
   múltiplos de ATR, trailing stops y R:R serían exactamente ese tipo de
   heurística inventada, con el agravante de presentarse junto a la marca
   "evidencia científica" del proyecto.
3. **M5 de la carta original**: "el boletín **nunca afirme más confianza de la
   que la evidencia permite**" y test obligatorio que impida lenguaje de
   recomendación cuando el veredicto no es PASA. Veredictos finales de M3b:
   H1 **INCONTRASTABLE**, H2 **INCONTRASTABLE**, H3-BTC **PASA a nivel de
   signo** (con stress ×2 ≈ 0), H3-ETH **NO PASA**. Un panel de órdenes
   COMPRAR/VENDER contradice frontalmente estos veredictos.
4. **Lección heredada explícita**: "proyecciones 1D/2-3D/1W no superan su
   baseline" y "80k LOC de dashboard" fueron fallos del proyecto anterior que
   la carta manda NO repetir.
5. **El usuario es novato en trading** (carta original): niveles accionables
   con barniz científico para un novato, incluyendo sizing de su capital, es
   el escenario de máximo daño que el proyecto se diseñó para evitar. Las
   decisiones de capital requieren aprobación explícita e informada.

## Decisión (alcance conforme implementado)

**Se construye** (todo DESCRIPTIVO, con etiquetas de veredicto):

1. **Estados en vivo de las 5 celdas congeladas** (`m3a-freeze`), en sus
   marcos investigados (diario/semanal): posición de la regla H1 (LONG x% /
   FLAT), cesta teórica H2, señal H3 (funding MA30 vs 5 %). Cada uno con su
   badge: `SIN VENTAJA DEMOSTRADA`, `VALIDADA (signo) + caveat costes ×2`,
   `NO PASA`.
2. **Tracker de operaciones del USUARIO** (`qa trade open/close/status/list`,
   `ledger/user_trades.jsonl` append-only con hash-chain): el agente registra
   las decisiones de JP (entrada, tamaño, SL y TP **puestos por él**) y
   devuelve PnL, distancia a SUS niveles, contexto de tendencia (solo donde
   hay regla investigada) y alertas de riesgo. Formato de seguimiento:
   `SIN ALERTAS — contexto: …` o `REVISAR (hechos observados, no es una
   orden): …`.
3. **Vigilante de noticias y choques** (RSS públicos sin claves: Cointelegraph,
   Decrypt; CoinDesk tolera fallo — 403 verificado) + choques técnicos
   (movimiento vs ATR14 1h/4h, spike de volumen, funding extremo) con umbrales
   documentados en `config/watchlist.yaml`. Cruce con posiciones del usuario y
   watchlist. Descriptivo: "motivos para revisar", nunca "CIERRE ANTICIPADO".
4. **Dashboard autocontenido** (`reports/dashboard/index.html`, HTML+CSS+SVG
   inline, sin recursos externos): operaciones + alertas, estados de reglas
   con veredictos, monitor carry, evidencia científica resumida, sparklines.
   **Guard de lenguaje por construcción**: el renderer lanza excepción si el
   HTML contiene imperativos de trading (`PROHIBIDOS` en
   `qa/report/dashboard.py`) + test `test_dashboard_language_guard`.
5. **Forward paper v0** (ADR-007): `qa forward run` registra el estado diario
   de las 5 celdas en `ledger/forward.jsonl` con hash-chain; workflow
   `.github/workflows/forward.yml` (cron 00:30 UTC) lo commitea al remoto.
   El motor de fills t+1 con P&L paper completo se activará al congelar
   `forward-v1` (gate M4).

**Se RECHAZA / difiere** (requiere preregistro v1.5 + aprobación explícita):

- Órdenes imperativas (COMPRAR/VENDER/CERRAR/SUBIR STOP/REDUCIR).
- SL/TP/trailing/R:R "sugeridos" por ATR u otra heurística no validada.
- Tamaño de posición calculado sobre el capital del usuario.
- Motores de señal 4H y semanal-táctico, y señales sobre altcoins de la
  watchlist (la watchlist solo recibe vigilancia de riesgos).
- Dashboard JS interactivo pesado (principio 8).

**Camino legítimo para lo diferido**: v1.5 definiría las nuevas hipótesis
(p. ej. "SL por ATR(14)×2 mejora el expectancy de H1-BTC tras costes"), con su
análisis de potencia, rejilla congelada, ejecución de una sola pasada y gates
DSR/PBO/RC/holdout. Solo una celda que llegue a PASA podría producir niveles
"accionables", y aun entonces como estado de regla pre-registrada, no como
consejo personalizado.

## Alternativas descartadas

- **Cumplir la directiva tal cual**: viola 5 cláusulas de la carta; habría
  convertido un laboratorio honesto en un generador de consejos no validados
  para un novato. Inaceptable para el agente en su rol de revisor escéptico.
- **No construir nada y solo escalar**: deja a JP sin las partes legítimas y
  útiles que sí pidió (seguimiento de sus operaciones, vigilancia, visibilidad
  del carry). Se construye lo conforme y se escala lo demás.
- **Construir los niveles "solo como educación"**: un nivel SL numérico junto
  a un badge científico ES una recomendación para un novato, diga lo que diga
  la letra pequeña.

## Consecuencias

- JP obtiene hoy: tracker fiable de SUS operaciones, contexto de tendencia
  validado donde existe, monitor de carry, vigilancia de noticias/choques y un
  panel único — sin que el proyecto finja confianza que no tiene.
- El orquestador puede revertir esta decisión mediante directiva explícita
  v1.5 (proceso científico), no mediante re-etiquetado del dashboard.
- Los entregables de investigación siguen sellados e intactos
  (`m3a-freeze`, `m3b-complete`, prereg v1.0-v1.4).

---

## Addendum B (M5b, 2026-10-28): contabilidad del usuario y filtro geométrico R:R

**Ratificado por directiva del orquestador/JP (M5b, 2026-10-28)**, se añaden las
siguientes herramientas, todas dentro del régimen descriptivo de este ADR
(contabilidad del usuario y hechos matemáticos observables de precios/niveles):

1. **Libro de capital** (`ledger/user_capital.jsonl`, `qa capital
   set/add/status/reset-examples`): contabilidad append-only con cadena de
   hashes de los aportes/retiros del usuario, ecuación patrimonial (equity
   vivo = aportado + PnL realizado neto + PnL flotante bruto) y portfolio
   heat (pérdida sobre capital aportado si todos los SL saltaran a la vez;
   SL en zona de ganancia/break-even aporta $0; sin SL no es computable y se
   lista aparte). El equity vivo sustituye a `capital_ref_usd` como base de
   la columna *Escala teórica* (etiqueta "escala teórica/informativo"
   obligatoria, igual que en la decisión Q2 original).
2. **Filtro de asimetría R:R ≥ min_rr** (regla de disciplina del PROPIO
   usuario; `min_rr_ratio: 2.0` en `config/watchlist.yaml`): (a) sobre los
   niveles de sus trades, R:R Neto = (|TP−Entry|−fees)/(|Entry−SL|+fees), con
   `ALERTA DE DISCIPLINA` y bloqueo en `qa trade open` salvo
   `--force-low-rr` (queda marcado `rr_forzado` en el libro, auditable);
   (b) sobre la geometría observable SMA50/ATR14 del precio (H1 y watchlist
   4H/1D/1W): Risk = max(Close−SMA50, 1×ATR14) + comisión i/v; Reward =
   3×ATR14 − extensión desde SMA50. Etiquetas descriptivas CUMPLE/NO CUMPLE
   (Asimetría X.Xx); si NO CUMPLE, la escala teórica de H1 se muestra
   bloqueada ($0). Las comisiones salen de `costs.yaml` (VERIFICADO):
   spot 0.20 % i/v, perp 0.10 % i/v.
3. **Calculadora aritmética de riesgo** (`qa trade calc` + panel inline sin
   recursos externos): riesgo $, tamaño equivalente (USD/unidades), break-even
   neto taker y TP que satisface R:R 2.0x/3.0x de los niveles del usuario,
   para 0.5/1.0/2.0 % del equity. Etiquetada "informativo, no es sizing
   recomendado": replica la excepción de escala aritmética ya ratificada.
4. **Trade Audit** (`qa trade audit` + panel): métricas contables del
   historial CERRADO del usuario (win rate, profit factor, esperanza $/R,
   R:R medio realizado, mejor/peor, maxDD realizado, desglose por tag) y
   soporte `--tag`/`--note`/`--ts` en open/close.

**El guard de lenguaje y `test_dashboard_language_guard` NO se relajan**:
durante el desarrollo de M5b el guard detectó y obligó a corregir un
imperativo ("Cierra con …") en el panel de auditoría — evidencia de que el
test sigue mordiendo. Sigue sin exigirse v1.5: nada de esto genera órdenes,
sugiere niveles propios del sistema ni evalúa hipótesis nuevas; el filtro
R:R es el umbral de disciplina que JP se configura a sí mismo, aplicado a
su propia contabilidad y a geometría estándar del precio.

`reset-examples` reescribe las cadenas SOLO para eliminar registros
`example: true`, con backup previo en `ledger/backup/` (gitignored) y
re-verificación posterior; los registros reales nunca se tocan.
