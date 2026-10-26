# M1 (+ PRERREGISTRO v1.2) · Datos y corrección del defecto 1 · 2026-10-26T19:52Z · git SHA `8a0c3b5952941da73af5b0a0fda22778102e5510`

Tags: `prereg-v1.2` (firmado SSH, commit `d8d864d`) · `prereg-v1-signed`/`prereg-v1` (commit `82bf430`, intactos) · `prereg-v1.1` (commit `3f3fbb1`).
Anclajes OpenTimestamps: **v1.0 → bloque Bitcoin 973269 ✓**, **v1.1 → bloque 973272 ✓**, v1.2 pendiente (<1 h, checklist M2).

## Resumen en 5 líneas

1. **v1.2 sellada** con las 6 enmiendas: benchmark primario vol-matched (f = σ_strat/σ_B&H por periodo), exposure-matched degradado a diagnóstico, criterio y subperíodos basados en la permutación del vector de exposición, tests de identidad/calibración en verde, bandas {0,2,5,10,20} pp simuladas, titular "H1 NO PASA" retirado formalmente.
2. **Potencia real con habilidad plantada** (drift AR(1) calibrado a ΔSharpe verdadero ∈ {0.1, 0.3, 0.5}): potencia de la regla compuesta = **17 % / 24-27 % / 39-42 %** → <50 % en todos los casos ⇒ veredicto pre-declarado de H1 = **INCONTRASTABLE** si el test no rechaza (enmienda 4 cumplida). El nulo calibra bien: FPR 6.6 % vs 5 % nominal, p medio 0.52.
3. **M1 completo sin tocar métricas de estrategia**: 703 símbolos mensuales, pool top-60 de 488, diarias spot de 427 símbolos in-sample (479 954 filas) + holdout sellado en ficheros separados (125 123 filas), futures y funding BTC/ETH con **0 registros faltantes**, cross-check funding API vs dump independiente **93/93 coincidencias, 0 discrepancias**.
4. **Universo PIT reconstruido**: 109 meses (2017-11→2026-11), primer mes con ≥20 candidatos: **2019-04** (H2 arranca ahí, como anticipaba el preregistro); 135 símbolos deslistados/BREAK incluidos; invarianza por truncamiento verificada con test de propiedad (hypothesis).
5. **Entregados para el usuario**: `quant-arena-M0b.bundle` (243 KB, historia completa + 4 tags, verificado), clave pública de firma (repo y junto al bundle); clave privada declarada: solo vive en `/home/user/.ssh/qa_prereg_ed25519` del sandbox, no viaja en el bundle ni en git.

## Entregables

| Ítem | Ruta | Estado |
|---|---|---|
| v1.2: benchmark vol-matched + permutación (enmiendas 1-2) | `docs/PREREGISTRO.md` §6-H1/§7.3/§8 · `config/hypotheses.yaml` | ✅ sellado (tag+OTS) |
| v1.2: tests de identidad y calibración (enmienda 3) | `src/qa/stats/benchmarks.py` · `tests/unit/test_benchmark_identities.py` · `tests/synthetic/test_null_calibration.py` | ✅ 32 tests verdes |
| v1.2: potencia con habilidad plantada (enmienda 4) | `scripts/power_analysis.py` → `reports/M0_power_analysis.md` S3/S4 | ✅ determinista |
| v1.2: retirada del titular §9.3/R1 (enmienda 5) | PREREGISTRO §9 (bloque "Retirado") + banner de corrección en `reports/M0b_REPORT.md` | ✅ |
| v1.2: bandas documentadas (enmienda 6) | PREREGISTRO §4 + `reports/M0_power_analysis.md` S6 | ✅ |
| Ingesta spot mensual (703 símbolos) | `data/raw/spot_monthly/` (702 API + NBTUSDT vía vision) | ✅ manifestado |
| Ingesta spot diaria pool (488) | `data/raw/spot_daily/` (54 MB) | ✅ 0 vacíos |
| Futures diarios + funding real BTC/ETH | `data/raw/futures_daily/`, `data/raw/funding/` | ✅ + cross-check vision |
| Curación + holdout sellado | `data/curated/*_in_sample.parquet` / `*_holdout.parquet` + `dataset_meta.json` | ✅ separación física |
| Universo PIT | `data/curated/pit_universe.parquet` (sha256 `9a4feb16…`) | ✅ 109 meses |
| Manifiestos SHA256 | `data/manifests/*.jsonl` | ✅ **1204 ficheros verificados** (`qa data verify`) |
| Informe de calidad | `reports/M1_data_quality.md/.json` + `M1_coverage_by_symbol.csv` | ✅ |
| Bundle para el usuario | `/home/user/quant-arena-M0b.bundle` | ✅ `git bundle verify` OK |
| Clave pública de firma | `docs/keys/prereg_signer_ed25519.pub` (+ copia en `/home/user/`) | ✅ |

## Gates

| Gate | Comando | Resultado | Evidencia |
|---|---|---|---|
| Lint | `ruff check . && ruff format --check .` | ✅ | consola 19:49Z |
| Tipos | `mypy` (strict, 34 ficheros) | ✅ Success | idem |
| Tests (identidad, calibración nulo, PIT invarianza, paginación, timestamps, manifiestos, guard M1, configs v1.2, seguridad) | `pytest` | ✅ **32 passed** | idem |
| Identidad: exposición constante ⇒ ΔmaxDD = 0 | `pytest tests/unit/test_benchmark_identities.py` | ✅ exacto (<1e-12) | test |
| Nulo: E[Δ vol-matched] ≈ 0 y p uniforme | `pytest tests/synthetic/test_null_calibration.py` | ✅ p̄=0.52±, FPR≤0.10 | test + S3 |
| Manifiestos | `qa data verify` | ✅ OK: 1204 ficheros | salida CLI |
| Tampering detectado | `tests/unit/test_manifest.py` | ✅ HASH DISTINTO / FALTA | test |
| Invarianza por truncamiento PIT | `tests/property/test_pit_invariance.py` (hypothesis) | ✅ | test |
| Prohibición M1: sin métricas de estrategia | `tests/unit/test_m1_no_strategy_metrics.py` (AST sobre `src/qa/data/`) | ✅ | test |
| Firma SSH v1.2 | `git tag -v prereg-v1.2` | ✅ Good signature `SHA256:SyPjyq…OyYQ` | consola |
| OTS | `ots upgrade` + `ots verify` | ✅ v1.0 bloque **973269**, v1.1 bloque **973272**; v1.2 pending | `docs/evidence/ots_verify_log.txt` |
| Bundle | `git bundle verify` | ✅ historia completa | `/home/user/quant-arena-M0b.bundle` |
| Funding contra 2ª fuente | dump mensual vision vs API (BTCUSDT 2020-01) | ✅ 93 comunes, **0 discrepancias** | `data/raw/funding/crosscheck_BTCUSDT_2020-01.json` |

## Resultados

### v1.2 · Potencia corregida (tablas S3/S4 de `reports/M0_power_analysis.md`)

| Comprobación | Resultado | Lectura |
|---|---|---|
| E[ΔmaxDD vol-matched] bajo GBM (nulo) | +4.4 pp (sd 12.9) | ≈0 relativo; el sesgo residual de mezcla de escalas lo absorbe la permutación |
| E[ΔmaxDD exposure-matched] bajo GBM (diagnóstico) | **+17.2 pp** | sesgo de Jensen confirmado: inhabilitado como criterio |
| E[ΔmaxDD vs B&H crudo] bajo GBM | −40.2 pp | puro efecto de exposición, no skill |
| p medio de permutación / FPR(p<0.05) / FPR compuesta | 0.520 / 6.6 % / 6.6 % | nulo calibrado (≈ nominal 5 %) |
| Potencia compuesta con ΔSharpe verdadero ≈ 0.1 | 16.5–17.5 % | — |
| Potencia compuesta con ΔSharpe verdadero ≈ 0.3 | 23.5–26.5 % | — |
| Potencia compuesta con ΔSharpe verdadero ≈ 0.5 | 39–41.5 % | **<50 % ⇒ veredicto por defecto INCONTRASTABLE** (enmienda 4) |
| Bandas {0,2,5,10,20} pp: sangría de costes | 1.06 / 0.99 / 0.92 / 0.85 / 0.80 %/año | 10 pp = rodilla (motivo registrado en §4) |

### M1 · Datos (todo en `reports/M1_data_quality.md/.json`)

| Concepto | Valor |
|---|---|
| Freeze / holdout sellado | 2026-10-25 23:59:59.999Z · holdout 2025-10-26→2026-10-25 (365 d, ficheros separados) |
| Universo mensual descargado | 703 símbolos USDT (702 vía API —incluidos 254 BREAK— + NBTUSDT vía dumps) |
| Pool de ingesta (top-60 mensual ∪ {BTC,ETH}) | 488 símbolos |
| Spot diario in-sample | 427 símbolos · 479 954 filas · 2017-08-17→2025-10-25 · duplicados 0 · precios imposibles 0 · 415/427 sin huecos |
| Coberturas peores | VENUSDT 72.5 % faltante (halt VEN→VET, max gap 88 d), FTTUSDT 14.5 % (max gap 311 d) — documentadas, no se imputan |
| Outliers (z robusto \|z\|>8, QA de datos) | 1 672 filas; top: LUNAUSDT 2022-05-31 (+12.1 log), SUNUSDT 2021-06-18 (−6.7), LUNAUSDT 2022-05-12 (−8.1), VENUSDT 2018-10-19 (−9.8), COCOSUSDT 2021-01-23 (+7.2) → redenominaciones/token-swaps ⇒ **regla de higiene pre-registrada** (ver Desviaciones 5) |
| Funding real | BTCUSDT 7 808 regs (2019-09-10→2026-10-25), **0 faltantes**, 0 huecos >8.5 h; ETHUSDT 7 574 (2019-11-27→), **0 faltantes** |
| Regla P4 (gate M0b) | n_ETH/n_BTC = 0.97 ⇒ MDE_ETH ≈ 1.02 × MDE_BTC ≪ 2× → **ambos contrastables** |
| Futures diario | BTC/ETH desde 2019-09-08, 4 400 filas in-sample |
| PIT | 109 meses; candidatos min 2 (2017-18, régimen declarado) / mediana 40; **primer mes con ≥20: 2019-04**; ≥40: 2019-07; 172 símbolos distintos en top-20 alguna vez |
| Deslistados incluidos | 135 símbolos BREAK/ausentes en el pool (AGIX, AMB, ANT, BCC, FTT, …) |
| Manifiestos | 1204 ficheros con SHA256 verificados; 0 fallos |

## Desviaciones del plan y su justificación

1. **ExchangeInfo comprimido (gz, 30 MB→0.4 MB)**: evidencia idéntica, hash SHA256 del `.gz` en manifiesto. Motivo: presupuesto de persistencia del workspace.
2. **Pool top-60 mensual como filtro de ingesta** (en vez de descargar diarias de los 703): el ranking PIT se reconstruye dentro del pool; margen 3× sobre N=20; auditado en `ingest_pool.json` (primer mes top-60 por símbolo). Riesgo residual declarado en el informe de calidad (limitación 2).
3. **H2 arranca 2019-04** (no 2019-01 como estimación): lo confirma el primer mes con ≥20 candidatos. El preregistro ya lo dejaba "a confirmar en M1". Efecto en potencia: n≈340 semanas vs 354 → MDE ≈ invariado; H2 sigue INCONTRASTABLE para efectos típicos.
4. **`pandas 3.1.0` no trae `py.typed`** → añadido `pandas-stubs` a dev-deps (CI igual).
5. **Regla de higiene de datos (NUEVA, pre-cómputo de estrategia)**: guard de redenominación `|log-ret| > 5` en `config/universe.yaml` (secciones `data_hygiene`), motivada por los artefactos documentados hoy (LUNA/VEN/SUN/COCOS). Umbral genérico, no afinado contra resultados; aplicado uniformemente; activaciones auditables. **No modifica PREREGISTRO v1.2 (ya sellado)**: universe.yaml es el fichero normativo del universo referenciado por §4. Se solicita ratificación (Q1).
6. **v1.2 OTS aún pending** (<1 h desde el estampado): checklist M2 re-ejecutar upgrade/verify y commitear `.ots` + log ANTES de M3 (condición ya cumplida para v1.0/v1.1 con altura de bloque).
7. **CI de GitHub aún no ejecutada**: el push lo hace el usuario con el bundle (decisión P5 del gate). Los gates idénticos corren en local.

## Limitaciones y sesgos conocidos

- Supervivencia del venue (solo lo que Binance listó); pool top-60 (limitación 2); régimen 2017-18 con costes 2026 (protegido con stress ×2); PIT fino pre-2019; redenominaciones menores que el umbral 5 (p. ej. swaps 1:10, |log|≈2.3) no quedan filtradas — riesgo residual documentado, las activaciones del guard y las semanas |log|∈(2.3,5) se auditarán en M3.
- La potencia v1.2 se mide sobre mundos sintéticos (GBM/AR1/MS): cuantifican el test, no predicen el mercado real.
- FTTUSDT muestra actividad hasta 2026 en el API (con un hueco de 311 días): la cobertura real de cada símbolo queda en `M1_coverage_by_symbol.csv`; el PIT lo trata mes a mes según datos disponibles.

## Riesgos abiertos

1. **R1 · OTS v1.2 pending** → se completa en M2 (compromiso antes de M3).
2. **R2 · CI sin estrenar** hasta el push del usuario (bundle listo).
3. **R3 · Workspace ~100 MB de datos**: si el snapshot del sandbox los perdiera, `qa data sync` (resumible, ~3 min) + `qa data curate` los regeneran idénticos; los hashes de los manifiestos detectarían cualquier diferencia.
4. **R4 · Clave de firma vive solo en el sandbox** (`/home/user/.ssh/qa_prereg_ed25519`, declarada; no incluida en bundle ni git). Si se pierde, las firmas antiguas siguen verificables (clave pública committeada) y se emitiría una clave nueva con addendum en ADR-004.

## Preguntas para el orquestador (solo decisiones reales)

- **Q1 · Ratificación de la regla de higiene** (Desviación 5): guard genérico `|log-ret|>5` añadido a `universe.yaml` ANTES de cualquier cómputo de estrategia, motivado por artefactos documentados en el informe de calidad. ¿Se ratifica como regla de capa de datos, o prefieres que se incorpore formalmente a la próxima versión del preregistro (v1.3) antes de M3?
- Recordatorio de acciones del usuario (no bloquean M2): (a) clonar el bundle y empujarlo al repo privado de GitHub para estrenar la CI; (b) crear la cuenta OSF (registro obligatorio antes de M3).

## Qué aprendimos (lenguaje llano)

- **El rival debe correr la misma carrera.** Comparar tu drawdown contra el de "comprar y aguantar" premia simplemente estar menos invertido; compararlo contra una copia del activo con TU misma volatilidad (vol-matched) aísla la habilidad real de esquivar caídas. Y si barajas CUÁNDO estuviste dentro (permutación) y aun así ganas, entonces sí hay timing.
- **La potencia se mide plantando el efecto.** Para saber si la balanza funciona, se pesa una manzana de peso conocido (ΔSharpe 0.1/0.3/0.5 simulados): la nuestra solo detecta manzanas muy gordas (<50 % de acierto incluso con ΔSharpe 0.5). Conclusión honesta: si H1 no resulta significativa, el veredicto será "no contrastable", no "falso".
- **Las monedas a veces cambian de escala.** LUNA, VEN o SUN tuvieron días de ±1000× por migraciones de token: no es información, es contabilidad. Un guard genérico (|log-ret|>5) las aparta antes de que contaminen nada.
- **Un ancla en Bitcoin es un notario global:** el hash del preregistro v1.0/v1.1 está ya escrito en los bloques 973269/973272 de Bitcoin. Nadie —tampoco nosotros— puede borrar esa fecha.
- **Point-in-time de verdad:** el test de "truncamiento" demuestra que el ranking de cada mes se puede reconstruir con la historia cortada en ese mes: la máquina no puede hacer trampa mirando el futuro.

## Solicitud: GATE APROBADO M1
