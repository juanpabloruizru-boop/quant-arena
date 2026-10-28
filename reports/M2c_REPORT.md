# M2c · v1.4 sellada + condiciones H1-H6 del gate M2b · 2026-10-27T18:05Z · git SHA `a6df036` (+ commit de este informe) · tag `prereg-v1.4` (firmado SSH)

## Resumen en 5 líneas

1. **v1.4 sellada** (tag SSH `prereg-v1.4` sobre `d316232` + OTS estampado) con los 5 añadidos aprobados: t\* validado multi-mundo, DSR con n_trials **familiar** y sd **estimada del ledger** + nota FWER de programa, selección por **mediana CPCV** (una celda por familia y activo) sellada antes de ejecutar, **protocolo M3 en dos puertas** (M3a in-sample con n_perm=10 000 y RC B≥2 000 + congelación aprobada; M3b holdout único con clave del usuario) y **pre-declaración: resultado esperado de H1 = INCONTRASTABLE** (potencia pipeline 9.5-18.5 % para ΔSharpe 0.1-0.3).
2. **H1 reconciliada al detalle**: la diferencia 125 123 − 125 048 = **75 filas** = 25+25+25 velas de octubre-2026 (holdout) de los 3 símbolos huérfanos podados (GTC/HYPE/MSTRB, que en M1 se descargaron solo desde su primer mes top-60); in-sample sin cambios (los huérfanos aportaban 0 filas in-sample). sha256 de los 3 ficheros sellados coinciden con `ledger/holdout_seal.log`.
3. **H3 explicada**: la correlación global 0.990/0.993 es la mezcla de ≥0.9993 desde 2020 con **2017 = 0.948/0.941** (peores días: 2017-09-05, 2017-12-12/24 con discrepancias de 7-11 pp); los desfases ±1 día dan ≈ −0.05 (alineación temporal correcta, sin drift de huso).
4. **H4/H5/H6 cerradas**: justificación VEN en una línea (con evidencia de cobertura: 88 días de halt); tests de truncamiento nuevos para retorno-L-días, formación semanal de H2 (con semántica "salta la última semana" verificada), señal de carry de H3 y pertenencia PIT en t; ADR-007 con el diseño M4 en GitHub Actions (ledger JSONL hash-chain commiteado por el runner; sandbox fuera del estado).
5. Gates: ruff ✓ · mypy --strict (62 ficheros) ✓ · **pytest 74/74** ✓ · bundle nuevo `quant-arena-M3pre.bundle`. Incidente de entorno: el sandbox perdió otra vez `.git`/venv; **recuperación íntegra desde el bundle M2** (5 tags + firmas verificadas) — la política de bundle por turno vuelve a justificarse.

## Entregables

| Ítem | Ruta | Estado |
|---|---|---|
| v1.4 añadidos 1-5 | `docs/PREREGISTRO.md` §7.3/§7.5/§7.7/§7.9/§8-H1/§10/§12 · `config/hypotheses.yaml` v1.4 (`selection_rule`, `m3_protocol`, `dsr_n_trials_scope: family`, `dsr_sd_trials_source: ledger`, `program_fwer_note`, `expected_verdict_predeclared`) | ✅ sellado (tag+OTS) |
| H1 reconciliación holdout | este informe + re-descarga API de los 3 huérfanos (25+25+25=75) | ✅ |
| H3 correlaciones año/desfase | `scripts/second_source_correlation.py` → `docs/evidence/second_source_correlation.json` | ✅ |
| H4 justificación VEN | Resultados H4 (una línea) + `reports/M1_coverage_by_symbol.csv` | ✅ |
| H5 tests de truncamiento | `src/qa/features/indicators.py` (`ret_L_days`, `formation_return_weekly`, `carry_signal`) · `src/qa/data/pit.py` (`membership_at`) · `tests/unit/test_features_truncation.py` | ✅ 74 tests |
| H6 diseño M4 | `docs/adr/ADR-007-forward-github-actions.md` | ✅ |
| Bundle | `/home/user/quant-arena-M3pre.bundle` | ✅ (metadatos en mensaje de entrega) |

## Gates

| Gate | Comando | Resultado | Evidencia |
|---|---|---|---|
| Lint | `ruff check . && ruff format --check .` | ✅ | consola 2026-10-27 |
| Tipos | `mypy` (strict) | ✅ 62 ficheros | idem |
| Tests | `pytest` | ✅ **74 passed** (nuevos: ret_L_days, formación semanal, carry signal, φ=0.9) | idem |
| Firma v1.4 | `git tag -v prereg-v1.4` | ✅ Good signature `SHA256:SyPjyq…OyYQ` | consola |
| Hashes v1.4 vs tag | `sha256sum` de los 4 normativos | ✅ coinciden con el mensaje del tag (universe/adjudications sin cambios desde v1.3, como corresponde a "solo texto") | este informe |
| OTS v1.4 | `ots stamp` (4 calendarios) + `ots upgrade`/`info` | estampado ✅; ancla BTC: ver "Sellado" abajo | `docs/evidence/normative_hashes_v1.4.txt.ots` |
| Datos intactos | `qa data verify` | ✅ 1198 ficheros | salida CLI |
| Holdout sin tocar | `ledger/holdout_access.log` | 2 entradas técnicas (M2b), **0 en M2c** | log |

## Resultados

### H1 · Reconciliación de filas del holdout (125 123 vs 125 048)

| Fichero sellado | Filas | sha256 (ledger `holdout_seal.log` = dataset_meta) |
|---|---|---|
| `spot_daily_holdout.parquet` | **125 048** | `8c8218ba5da47715…` ✅ |
| `futures_daily_holdout.parquet` | **730** | `7fcc06265f5d799c…` ✅ |
| `funding_holdout.parquet` | **2 190** | `ffd2de9cbfb1b56e…` ✅ |

Explicación de la diferencia (75 filas): en M1, `phase_daily` descarga cada
símbolo **desde su primer mes en el top-60 mensual**. GTCUSDT, HYPEUSDT y
MSTRBUSDT entraron en el pool de 488 solo por el mes 2026-10 (vela mensual
parcial, luego corregida) → sus ficheros crudos tenían únicamente velas de
octubre-2026: **25 filas cada uno, todas en ventana holdout, 0 in-sample**
(verificado hoy re-descargando los 3 símbolos: 25+25+25 = 75 = 125 123 −
125 048; in-sample 479 954 en ambos casos, consistente). Tras la poda
pre-determinista (pool 485) y la re-curación, el holdout sellado es el de
125 048 filas. El número de M1 (125 123) corresponde al pool-488 pre-poda;
ambos quedan documentados y reconciliados.

### H3 · Correlación Binance-Coinbase por año y desfases

| Año | corr BTC | corr ETH |
|---|---|---|
| 2017 (parcial) | 0.9483 | 0.9414 |
| 2018 | 0.9857 | 0.9918 |
| 2019 | 0.9954 | 0.9969 |
| 2020 | 0.9995 | 0.9994 |
| 2021 | 0.9999 | 0.9999 |
| 2022 | 0.9999 | 1.0000 |
| 2023 | 0.9997 | 0.9998 |
| 2024 | 0.9999 | 0.9999 |
| 2025 (oct) | 0.9999 | 1.0000 |

- Desfases: corr(lag −1, Coinbase lidera) = −0.054/−0.064; corr(lag +1,
  Binance lidera) = −0.043/−0.061 → **la alineación lag-0 es la correcta**
  (sin drift de huso horario ni de cierre de vela).
- **Explicación del 0.990/0.993 global:** es la mezcla ponderada de una era
  moderna con correlación ≥ 0.9993 (2020+) y un 2017 con microestructura
  temprana (spreads anchos, fragmentación entre venues, prima USDT volátil):
  los 5 peores días son todos de 2017 (2017-09-05: 8.0/9.0 pp; 2017-12-12:
  6.4/10.7 pp; 2017-12-24: 7.2/7.6 pp de discrepancia diaria). |diff| media
  diaria = 14.9/16.0 pb, dominada por 2017-18. Diferencia de quote
  (USDT vs USD) incluida sin ajustar, como se pidió.

### H4 · VEN 2018-10-19 (una línea)

Es `corporate_action` porque la vela del −9.82 log-ret no es una sesión
negociada del mismo activo: es la **reanudación tras 88 días de halt** por el
mainnet swap VEN→VET 100:1 (anunciado el 2018-06-22 —fecha de la PRIMERA vela
del par— y completado el 2018-07-24), cotizando al valor residual post-swap
(0.0001 vs ≈1.8 pre-halt): la ruptura refleja la redenominación, no el
mercado (evidencia de cobertura: `reports/M1_coverage_by_symbol.csv`, fila
VENUSDT: 33 velas en 120 días, max_gap 88).

### H5 · Tests de invarianza por truncamiento añadidos

- `ret_L_days` (variante `ret` de H1): propiedad hypothesis ✅.
- `formation_return_weekly` (H2, L semanas saltando la última): propiedad
  hypothesis + verificación explícita de la semántica `f[w] = x[w−2]/x[w−2−L] − 1` ✅.
- `carry_signal` (H3, umbral sobre MA anualizada): truncamiento + warmup nunca
  enciende + semántica de umbral ✅.
- Ranking H2 / pertenencia PIT en t: `build_pit_from_frame` (propiedad
  hypothesis ya existente) + `membership_at(pit, ts, n)` que solo consulta el
  último mes-start ≤ ts (causal por construcción) ✅.

### H6 · Diseño M4 (ADR-007)

Forward en GitHub Actions (cron 00:30 UTC + dispatch), código congelado en tag
`forward-v1`, datos públicos de Binance, ledger `ledger/forward.jsonl` con
**hash-chain** (`prev_hash` por línea) commiteado por el runner (sello temporal
de GitHub + OTS semanal del head), `qa forward verify-chain` como auditoría,
rellenos tardíos con flag `late_fill` sin reescritura, sandbox fuera del
estado, sin secretos para el forward.

### Sellado v1.4 y anclajes OTS (estado al cierre)

| Versión | Bloque BTC | Hora bloque (UTC) |
|---|---|---|
| v1.0 | 973269 | 2026-10-26T18:26:10 |
| v1.1 | 973272 | 2026-10-26T18:47:47 |
| v1.2 | 973277 | 2026-10-26T19:20:35 |
| v1.3 | 973290 | 2026-10-26T21:04:43 |
| v1.4 | *(estampado 2026-10-27T18:0x; upgrade/verificación en curso — se reporta la altura en el mensaje de entrega y queda en `docs/evidence/ots_block_anchors.json`)* | |

## Desviaciones del plan y su justificación

1. **Segunda pérdida de estado del sandbox** (`.git`, venv, apt): recuperación
   íntegra desde `quant-arena-M2.bundle` (HEAD 573bc81, 5 tags, firmas SSH
   verificadas, working tree idéntico). Política consolidada: bundle nuevo
   cada turno + datos regenerables + `make git-config`/`make install`.
2. **La cifra de holdout de M1 (125 123) quedó desactualizada por la poda
   pre-determinista**: reconciliada en H1 con evidencia de re-descarga; los
   informes M1/M2b no se reescriben (historial), la reconciliación vive aquí.
3. `phase_daily` descarga desde el primer mes top-60 (no desde el listado):
   limitación de cobertura ya documentada en M1 (limitación 2) y relevante
   solo para símbolos fuera del pool estable; los 3 huérfanos podados no
   afectan al universo PIT (nunca fueron top-40 en meses completados).

## Limitaciones y sesgos conocidos

- t\* conservador bajo regímenes de vol → potencia real ≤ potencia sintética
  reportada (pre-declarado en v1.4 §7.3).
- La sd entre celdas del DSR se estimará del ledger en M3a: si la dispersión
  empírica es mayor que 0.5-0.75 (rango de las tablas de planificación), el
  Sharpe mínimo exigible sube — se reportará el valor real usado.
- Coinbase cotiza en USD: las correlaciones/diferencias incluyen base risk
  USDT/USD (declarado).

## Riesgos abiertos

1. **R1 · Acciones del usuario (bloquean M3):** push del bundle
   `quant-arena-M3pre.bundle` al repo privado con CI verde + registro OSF de
   v1.4 + custodia de la clave del holdout (entregada una vez en M2b).
2. **R2 · Cómputo de M3a:** 38 trials × CPCV45 × (permutaciones 10 000 + RC
   B≥2 000) es pesado; se ejecutará por familias con checkpoints en el ledger
   (nada se pierde si se interrumpe) y semillas fijas.
3. **R3 · Volatilidad del sandbox:** mitigada (bundle por turno, regeneración
   verificada, holdout cifrado con recuperación por hash).

## Preguntas para el orquestador

Ninguna nueva: las condiciones A-H y los añadidos 1-5 de v1.4 están cerrados o
asignados al usuario. (Q1/Q2 del M2b quedaron resueltas por el gate: v1.4
aprobada con añadidos, H1 se ejecuta.)

## Qué aprendimos (lenguaje llano)

- **Mediana para elegir, no media:** la celda que pasa al examen final se
  elige por su mediana en 45 trayectorias: un fold extremo ya no puede
  "comprar" la selección.
- **Dos puertas mejor que una:** M3a mira solo el pasado y congela sus
  elecciones ante notario (commit+hash+OTS+aprobación); M3b abre el sobre del
  holdout UNA vez con la clave del usuario. Entre ambas, imposible autoengañarse.
- **75 filas fantasma:** la discrepancia de conteos no era un bug misterioso:
  eran 3 símbolos de octubre-2026 descargados "a medias" por una regla de
  eficiencia. Reconciliar al detalle (25+25+25) es lo que separa auditoría de
  contabilidad creativa.
- **La correlación 0.99 tiene apellido:** por año se ve que el "ruido" está
  casi todo en 2017 (0.94) — la era de los exchanges fragmentados. Desde 2020,
  Binance y Coinbase se mueven como un solo mercado (≥0.9993).
- **El estado que importa vive fuera del sandbox:** dos pérdidas en una semana
  no son mala suerte, son arquitectura: bundle por turno, ledger en el repo,
  sellos en Bitcoin.

## Solicitud: GATE APROBADO M2c
