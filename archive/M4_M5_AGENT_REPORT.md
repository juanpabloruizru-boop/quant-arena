# M4/M5 operativo · Agente de estados + tracker + vigilancia + dashboard · 2026-10-28T16:45Z · git SHA 643558e (ADR-008; este informe en el commit siguiente) · alcance conforme ADR-008

## Resumen en 5 líneas

1. **Construido y en vivo** el agente operativo dentro del alcance que la carta del proyecto permite: estados descriptivos de las **5 celdas congeladas** (`m3a-freeze`), **tracker de operaciones del usuario** con hash-chain, **vigilante de noticias/choques** sin claves, **dashboard autocontenido** con guard de lenguaje por construcción, y **forward paper v0** (registro diario encadenado + workflow de GitHub Actions, ADR-007). Gates: ruff ✓ mypy --strict (79 ficheros) ✓ **pytest 86/86** ✓.
2. **NO se construyó el generador de órdenes** (COMPRAR/VENDER, SL/TP por ATR, R:R, sizing por capital, motores 4H/semanal-táctico, señales sobre altcoins): son hipótesis no pre-registradas y heurísticas sin validar — choca con los principios 1/8, el PROHIBIDO explícito, los veredictos de M3b y la regla M5 de no recomendar sin PASA. Todo el razonamiento, lo construido y el **camino legítimo (preregistro v1.5)** están en **ADR-008**; se solicita ratificación (Q1).
3. **Estado en vivo de las reglas congeladas (2026-10-28):** H1 `sma50_s25` = **LONG** en BTC (posición de regla 60 %; close 83 322 vs SMA50 80 297, +3.8 %; vol20d 42.9 %) y **LONG** en ETH (65 %) — con badge *SIN VENTAJA DEMOSTRADA*; H3 carry **INACTIVA** en BTC (funding MA30 4.4 % < 5 %; MA7d 6.5 % subiendo) y ETH (4.1 %) — badges *VALIDADA (signo, edge frágil a ×2)* y *NO PASA*; H2 cesta teórica ZEC/NEAR/UNI/SOL — *SIN VENTAJA DEMOSTRADA*.
4. **Tracker demostrado con 2 operaciones EJEMPLO** (marcadas como tales en ledger y dashboard): PnL en vivo (+2.5 % / +12.6 USD la BTC), distancia a SL/TP **del usuario**, contexto de tendencia y estado `REVISAR (hechos observados, no es una orden)` cuando hay noticias con keyword de riesgo o choques técnicos del activo.
5. **Vigilancia funcionando**: 1 choque técnico y 27 titulares relevantes detectados en la corrida en vivo (Cointelegraph+Decrypt OK; CoinDesk 403 tolerado); el forward paper registró su primera línea encadenada; el dashboard (14 KB, sin recursos externos) se abre con un clic.

## Entregables

| Ítem | Ruta | Estado |
|---|---|---|
| ADR de alcance (conflicto directiva vs carta) | `docs/adr/ADR-008-alcance-m4m5-operativo.md` | ✅ |
| Ingesta viva (1h/4h/1d watchlist + diarias miembros PIT + funding + premiumIndex) | `src/qa/agent/live.py` | ✅ solo GET públicos |
| Estados de las 5 celdas congeladas (marcos investigados) | `src/qa/agent/signals.py` | ✅ con badges de veredicto |
| Tracker del usuario (hash-chain) + CLI | `src/qa/agent/tracker.py`, `qa trade open/close/status/list` | ✅ cadena verificada |
| Noticias RSS + choques técnicos | `src/qa/agent/news.py`, `config/watchlist.yaml` | ✅ 2 feeds OK, 1 tolerado |
| Dashboard autocontenido + guard de lenguaje | `src/qa/report/dashboard.py` → `reports/dashboard/index.html` | ✅ renderer lanza si aparece un imperativo; test dedicado |
| Forward paper v0 + workflow | `src/qa/forward/paper.py`, `qa forward run`, `.github/workflows/forward.yml` | ✅ 1ª línea encadenada; fills t+1 al congelar `forward-v1` (gate M4) |
| Tests del agente | `tests/unit/test_agent.py` (cadena, tampering, criba, choques, banda, estados, guard) | ✅ 86/86 |
| Bundle | `/home/user/quant-arena-M4.bundle` | ✅ |

## Gates

| Gate | Comando | Resultado | Evidencia |
|---|---|---|---|
| Lint/format | `ruff check . && ruff format --check .` | ✅ | consola |
| Tipos | `mypy` (strict) | ✅ 79 ficheros | idem |
| Tests | `pytest` | ✅ **86 passed** | idem |
| Guard de lenguaje (regla M5 de la carta) | `pytest tests/unit/test_agent.py::test_dashboard_language_guard` | ✅ ningún imperativo de trading; badges SIN VENTAJA/NO PASA/VALIDADA presentes | test |
| Cadena de operaciones | `verify_chain` | ✅ "cadena valida" (2 líneas) + test de tampering | `ledger/user_trades.jsonl` |
| Cadena forward | `qa forward run` | ✅ ok=True líneas=1 | `ledger/forward.jsonl` |
| Holdout sigue intacto | `wc -l ledger/holdout_access.log` | ✅ 5 entradas (sin cambios desde M3b) | log |
| Research congelado intacto | tags `m3a-freeze`/`m3b-complete` + n_trials | ✅ 24/6/8 sin cambios | ledger |
| Dashboard sin recursos externos | inspección del HTML | ✅ 0 `src/href` externos, 0 JS | `reports/dashboard/index.html` |

## Resultados — corrida en vivo (2026-10-28T16:38Z)

| Celda congelada | Estado hoy | Detalle | Badge |
|---|---|---|---|
| H1 `sma50_s25` BTCUSDT | **LONG 60 %** | close 83 321.8 vs SMA50 80 296.8 (+3.8 %); vol20d 42.9 % → escala 0.25/0.429 ≈ 0.58, banda aplicada | SIN VENTAJA DEMOSTRADA (INCONTRASTABLE) |
| H1 `sma50_s25` ETHUSDT | **LONG 65 %** | idem | SIN VENTAJA DEMOSTRADA |
| H2 `L26_N10` | Cesta teórica: **ZEC, NEAR, UNI, SOL** | top-10 PIT vigente + formación 26w (saltando última) | SIN VENTAJA DEMOSTRADA |
| H3 `w30_t5` BTCUSDT | **INACTIVA** | funding MA30d 4.40 % < 5 %; MA7d 6.48 % (acercándose); último funding 0.009 %/8h | VALIDADA (PASA signo; costes ×2 ≈ 0) |
| H3 `w30_t5` ETHUSDT | **INACTIVA** | MA30d 4.07 % < 5 % | NO PASA (holdout) |

Vigilancia: 1 choque técnico en watchlist; 27 titulares relevantes (72 h). Operaciones ejemplo: BTC spot +2.5 % (+12.6 USD), SL a 9.2 %, TP a 16.6 %; ETH future_long con contexto 1D.

## Guía rápida para JP (5 comandos)

```bash
make install                    # 1) entorno (una vez)
qa trade open --asset BTCUSDT --kind spot --entry 79500 --size-usd 500 \
              --sl 74000 --tp 95000 --timeframe 1d   # 2) anota TUS operaciones
                                                    #    (kind: spot|future_long|future_short)
qa agent run                    # 3) estados + alertas + dashboard
                                #    -> abre reports/dashboard/index.html
qa trade status                 # 4) diagnóstico rápido de tus operaciones abiertas
qa trade close --id <ID> --exit 84000   # 5) cierra cuando vendas (registro append-only)
```
Extra: `qa forward run` (registro científico diario; en GitHub corre solo a las 00:30 UTC). Las 2 operaciones precargadas están marcadas `EJEMPLO`.

## Desviaciones del plan y su justificación

1. **Reducción de alcance de la directiva ejecutiva (la importante)**: no se implementaron órdenes accionables, SL/TP/R:R/sizing, marcos 4H/1S ni señales de watchlist. Justificación completa en **ADR-008** (5 colisiones con la carta). Se implementó el 100 % de lo pedido que es compatible con la evidencia: seguimiento de operaciones, vigilancia, carry monitor, dashboard y forward. **Q1 solicita ratificación o directiva v1.5.**
2. **Dashboard estático sin JS interactivo** (principio 8 + preview del sandbox sin red): tablas/CSS/SVG inline; todo se regenera con `qa agent run`.
3. **CoinDesk RSS bloquea (403)**: declarado tolerable en config; 2 de 3 feeds operativos.
4. **Telegram pendiente del token del usuario** (`qa report daily` lo indica); el canal principal es el dashboard.
5. **Forward v0 = registro de estados** (no fills/PnL): el motor de fills t+1 se activa con la etiqueta `forward-v1` al aprobar el gate M4 — evita congelar código de P&L sin la revisión del orquestador.

## Limitaciones y sesgos conocidos

- Los estados en vivo reproducen las reglas congeladas sobre velas recientes de la API; la posición H1 usa banda con historial de 400 velas (estado converge al real salvo camino de banda en la primera semana tras arranque en frío).
- La cesta H2 "teórica" usa el top-10 PIT del mes vigente; el ranking real de los lunes puede diferir si el volumen mensual cambia el día 1.
- Los choques/noticias son vigilancia con umbrales descriptivos (config), no señales validadas; pueden dar falsos positivos (p. ej. titulares que solo mencionan el activo).
- El PnL del tracker no incluye comisiones de tu exchange real (las anotas tú); es contabilidad + contexto.
- Nada de esto es asesoramiento: es el espejo de un laboratorio que, tras 38 ensayos pre-registrados, solo pudo validar un carry frágil a nivel de signo.

## Riesgos abiertos

1. **R1 · Expectativas del usuario**: el mayor riesgo del producto es que un novato lea "LONG 60 %" como una recomendación. Mitigaciones: badges en cada fila, banner superior, guard de lenguaje, este informe y la pregunta Q1 explícita.
2. **R2 · Acciones de usuario pendientes**: push del remoto (CI + forward en Actions), OSF (v1.4), token de Telegram si se quiere el canal.
3. **R3 · Anclas OTS de m3a/m3b pendientes** de confirmación BTC (estampados; `make ots-check`).
4. **R4 · RSS inestables**: feeds públicos sin SLA; el sistema degrada con estado por feed visible en el dashboard.

## Preguntas para el orquestador (decisiones reales)

- **Q1 · Ratificación de alcance (ADR-008):** ¿confirmas el alcance conforme (agente descriptivo) o emites directiva de **preregistro v1.5** para investigar formalmente los marcos 4H/semanal, SL/TP por ATR y watchlist (semanas de trabajo, con probables INCONTRASTABLE según potencia de M0)? Yo no implementaré niveles accionables sin ese proceso.
- **Q2 · Sizing/capital:** cualquier cálculo de tamaño de posición sobre el capital real de JP es una decisión de capital que requiere (a) su instrucción explícita e informada y (b) una regla pre-registrada. ¿Se abre como hipótesis de v1.5 (p. ej. vol-targeting con límite de riesgo por operación) o se deja como entrada manual del usuario (estado actual)?
- **Q3 · Gate M4 formal:** ¿apruebas congelar `forward-v1` con el motor de fills t+1 (extensión directa del motor M2 ya testeado) para que el forward paper empiece a acumular PnL real-en-paper en GitHub Actions, con reglas día-30/día-90 de la carta?

## Qué aprendimos (lenguaje llano)

- **"Poder construirlo" no es "deber construirlo"**: el proyecto sabía generar un panel de señales de compra en una tarde; también sabía que sus propios datos no las respaldan. El valor del laboratorio está en esa segunda frase.
- **El guard de lenguaje es un test, no una opinión**: el renderer revienta si la palabra "COMPRAR" asoma en el HTML. La honestidad deja de ser buena voluntad cuando la ejecuta CI.
- **Tu tracker, tus reglas**: el agente mide TU operación contra TUS stops y te avisa de hechos (choques, noticias, tendencia); la decisión sigue siendo tuya — que es donde debe estar cuando la ciencia aún no demostró ventaja.
- **Cadenas de hash por todas partes**: operaciones del usuario, forward y holdout sellado — cada línea firma a la anterior; editar historia rompe el sello.

## Solicitud: GATE APROBADO M4M5 (alcance conforme ADR-008)
