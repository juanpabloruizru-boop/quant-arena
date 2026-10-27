# M2 (+ v1.3) · Motor de backtest, validación del laboratorio y correcciones pre-M3 · 2026-10-26T21:31Z · git SHA `9e82972b5c160f4d4be7307645e975d02e5c59b7`

Tags: `prereg-v1.3` (firmado SSH, commit `a67f6e5`) sobre PREREGISTRO v1.3 + hypotheses.yaml v1.3 + universe.yaml + adjudications.csv — **los 4 hashes re-verificados contra el tag coinciden**. v1.0/v1.1/v1.2 intactas.

## Resumen en 5 líneas

1. **v1.3 sellada y anclada**: las 6 correcciones pre-M3 del gate M1 están incorporadas (higiene mark-only con tabla de adjudicación evidenciada, exclusiones auditadas, nivel crítico de permutación t\*=0.025 calibrado con 5000 sims, FWER del pipeline simulado, cross-check de funding ampliado, regeneración byte-idéntica) — todo con evidencia **solo sintética o de calidad de datos**, ninguna métrica de estrategia sobre datos reales.
2. **Las 4 versiones del preregistro están ancladas en Bitcoin**: v1.0 bloque 973269 (18:26:10Z), v1.1 bloque 973272 (18:47:47Z), v1.2 bloque 973277 (19:20:35Z), v1.3 bloque 973290 (21:04:43Z) — anterioridad verificable por terceros.
3. **Motor M2 completo**: vectorizado, costes de `costs.yaml` (fees verificados + slippage por participación + mínimos + rechazos registrados), carry con **funding real y P&L de basis a dos piernas**, convención de funding 00/08/16 estricta con test de off-by-one, ledger `trials` DuckDB **obligatorio por construcción**, y stats: Sharpe/Sortino/maxDD/Calmar/Ulcer/time-underwater/expectancy-R, DSR, PBO (CSCV), CPCV purgado con embargo, walk-forward purgado, bootstrap estacionario, HAC, Reality Check/SPA.
4. **Las 3 pruebas sintéticas de aceptación pasan**: (1) batería de 48 estrategias aleatorias sobre paseo aleatorio con FPR ≤ nominal; (2) señal sembrada AR(1) persistente recuperada dentro de su IC bootstrap y detectada por el criterio permutado; (3) **B&H de BTC y ETH reproducido contra Kraken (XBTUSDT/ETHUSDT) con Δ = 0.025 % y 0.010 %** (tolerancia ±0.5 %).
5. **Holdout blindado en runtime**: movido fuera de `data/` a `holdout_sealed/`, carga rechazada sin `QA_HOLDOUT_UNLOCK=1`, y con unlock queda fila append-only (sha256 + git SHA + propósito) en `ledger/holdout_access.log` — con tests. Gates: ruff ✓, mypy --strict (56 ficheros) ✓, **pytest 65/65** ✓.

## Entregables

### Correcciones pre-M3 (condiciones 1-6 del gate M1) → v1.3

| # | Condición | Implementación | Estado |
|---|---|---|---|
| 1 | Higiene mark-only + adjudicación evidenciada | `config/adjudications.csv` (5 eventos = enumeración COMPLETA de \|log-ret\|>5 in-sample): LUNA 2022-05-31 → corporate_action (listing Terra 2.0, anuncio 2022-05-28); **LUNA 2022-05-12 → real_move conservado ÍNTEGRO** (colapso Terra, cobertura citada); VEN 2018-10-19 → corporate_action (swap VEN→VET 100:1); COCOS 2021-01-23 → corporate_action (redenominación 1000:1, anuncio 2021-01-18); SUN 2021-06-18 → corporate_action (migración 1:1000, anuncio 2021-06-08). Regla: corporate_action exige anuncio oficial (URL+fecha); sin anuncio → real_move por defecto. Exclusion PIT 30 d; sin imputación; deslistado = último precio observado. **Efecto en ranking top-40: no-op** (los 4 símbolos ya quedaban fuera por huecos/n_days<15/volumen) — documentado en PREREGISTRO §9.6 | ✅ sellado en v1.3 |
| 2 | Lista de exclusiones del universo | exchangeInfo USDT: 770 pares → 702 elegibles; excluidos en ingesta: **15 stablecoins/fiat** (TUSD, PAX, USDC, BUSD, EUR, GBP, DAI, USDP…), **50 tokens apalancados** (BULL/BEAR/UP/DOWN), **3 wrapped/pegged** (PAXG, WBTC, WBETH). Verificado: **0 colados** en spot_monthly, pool o PIT top-40 → el ranking de H2 NO cambia. Auditoría sellada en `universe.yaml` (`exclusions_audit`) y ahora leída por el sync (fuente única, sin duplicación) | ✅ |
| 3 | Nulo H1: rotación vs bloques, 5000 sims | block20: FPR(p<0.05)=6.68 %, potencia(ΔSharpe 0.3)=28.1 %; rotación completa: FPR=2.78 %, potencia=6.8 %. Ninguno cae en [3.5,6.5] a nivel 0.05 → **adoptado block20 con nivel crítico calibrado t\*=0.025** (FPR sintético 4.36 % ≤ 5 %; decisión solo con evidencia sintética, regla fijada antes de ver los números). C1 aclarado: **el estadístico de decisión es el p-valor permutado, no el ΔmaxDD puntual** (E[+4.4 pp] bajo nulo) | ✅ `reports/M0_null_scheme_comparison.md`, `M0_null_threshold_calibration.md` |
| 4 | FWER del pipeline H1 | 200 mundos GBM correlacionados (ρ=0.8), 24 candidatas (12 celdas × BTC/ETH), t\*=0.025, RC de White (B=200, bloque 20 d): P(alguna compuesta pasa) = **28.5 %**; P(RC rechaza) = 0.5 %; **P(pipeline: compuesta Y RC) = 0.5 %** → el gate C2' controla la multiplicidad familiar | ✅ `reports/M0_h1_fwer.md` |
| 5 | Cross-check funding ampliado | **14 meses** aleatorios (semilla fija) 2020-2025, BTC (7) y ETH (7): **1272 registros comunes, 0 discrepancias** (tolerancia exacta 1e-12) API vs dumps mensuales de data.binance.vision | ✅ `docs/evidence/funding_crosscheck_extended.json` |
| 6 | Prueba de regeneración | `run_sync(all)+run_curate+run_pit` en `/tmp/qa-regen` limpio (1621 peticiones, 156 s): **los 7 ficheros curados (in-sample + holdout + PIT) son byte-idénticos** (SHA256 coinciden con `dataset_meta.json`). Diferencias documentadas: `exchangeinfo_*.json.gz` (campo serverTime) y `sync_log.json` (timestamps) — no son datos de investigación | ✅ `docs/evidence/regeneration_test.json` |

### M2 · Motor y laboratorio

| Ítem | Ruta | Estado |
|---|---|---|
| Features causales + invarianza por truncamiento (hypothesis) | `src/qa/features/indicators.py`, `tests/unit/test_features_truncation.py` | ✅ propiedad verificada para sma/rolling_sum/rolling_mean/realized_vol |
| Motor vectorizado: costes por tramos de participación, minNotional, rechazos registrados, banda 10 pp | `src/qa/backtest/engine.py` (`run_positions`) | ✅ + tests de fixture B&H exacto |
| Carry delta-neutral: funding real, **basis a dos piernas**, convención `entry_ts < fundingTime < exit_ts` (estricto, conservador: se pierde el evento 00:00 del día de entrada) | `run_carry` + `tests/unit/test_engine.py` (off-by-one: 5 de 7 eventos capturados, exacto) | ✅ |
| Costes desde `costs.yaml` + stress ×2 (`CostModel.stressed` via `stress=True`) | `src/qa/backtest/costs.py` | ✅ |
| Ledger `trials` DuckDB append-only; **registro obligatorio** (evaluar sin contexto de trial → RuntimeError); run_id determinista; fallos también se registran; `n_trials` se lee de la tabla | `src/qa/backtest/trials.py` + tests | ✅ |
| Stats: Sharpe, Sortino, maxDD, Calmar, Ulcer, time-underwater, expectancy-R | `src/qa/stats/metrics.py` | ✅ valores conocidos testeados |
| DSR (Bailey–LdP), PBO (CSCV), CPCV purgado con embargo (45 paths), walk-forward purgado, bootstrap estacionario, HAC (Newey-West), Reality Check/SPA | `src/qa/stats/{dsr,spa,cpcv,bootstrap}.py` | ✅ monotonicidad DSR, purga/embargo verificados, RC mini-calibrado (≤2/10 rechazos bajo ruido) |
| Benchmarks vol-matched/exposure-matched + permutaciones (bloque y rotación) | `src/qa/stats/benchmarks.py` | ✅ identidades: exposición constante ⇒ Δ=0 exacto; signo Δ>0=peor |
| **Holdout: guard en RUNTIME** — fuera de `data/` (en `holdout_sealed/`), sin carga salvo `QA_HOLDOUT_UNLOCK=1` + fila append-only (sha256, git SHA, propósito) en `ledger/holdout_access.log` | `src/qa/backtest/data_access.py` + tests | ✅ |
| Prueba sintética 1: paseo aleatorio deriva 0 — batería de 48 estrategias aleatorias: FPR permutación ≤ 0.10, FPR DSR(n_trials=48) ≤ 0.05, ICs bootstrap incluyen 0 | `tests/synthetic/test_random_walk_battery.py` | ✅ |
| Prueba sintética 2: señal sembrada AR(1) φ=0.995, IC verdadero 0.10 → IC recuperado dentro del IC bootstrap y detectada (p ≤ t\*, Δ = mejora) | `tests/synthetic/test_planted_signal.py` | ✅ |
| Prueba sintética 3: B&H BTC/ETH contra fuente independiente citada | `scripts/validate_bh.py` → `docs/evidence/bh_validation.json` | ✅ Δ=0.025 % / 0.010 % |
| CLI `qa stats report` (lee ledger) | `src/qa/cli.py` | ✅ |

### Sellado y persistencia

| Ítem | Detalle | Estado |
|---|---|---|
| Tag `prereg-v1.3` | firmado SSH (Good signature, clave `SHA256:SyPjyq…OyYQ`), 4 hashes en el mensaje, re-verificados contra el working tree | ✅ |
| Anclajes OTS (ots verify/info + blockstream) | **v1.0 → bloque 973269 @ 2026-10-26T18:26:10Z** · **v1.1 → 973272 @ 18:47:47Z** · **v1.2 → 973277 @ 19:20:35Z** · **v1.3 → 973290 @ 21:04:43Z** (`docs/evidence/ots_block_anchors.json` con hashes de bloque) | ✅ las 4 ancladas |
| Bundle actualizado | `/home/user/quant-arena-M0b.bundle` (historia completa + 4 tags; `git bundle verify` OK). Clave pública: `docs/keys/prereg_signer_ed25519.pub` (+ copia en `/home/user/`). **Clave privada: solo en `/home/user/.ssh/qa_prereg_ed25519` del sandbox** — no viaja en el bundle ni en git | ✅ |

## Gates

| Gate | Comando | Resultado | Evidencia |
|---|---|---|---|
| Lint + formato | `ruff check . && ruff format --check .` | ✅ | consola 21:29Z |
| Tipos estrictos | `mypy` | ✅ 56 ficheros, 0 errores | idem |
| Tests completos | `pytest` | ✅ **65 passed** | idem |
| Identidades del estadístico H1 | `pytest tests/unit/test_benchmark_identities.py` | ✅ (Δ=0 exacto con exposición constante; signo) | idem |
| Calibración del nulo | `pytest tests/synthetic/test_null_calibration.py` | ✅ p̄≈0.52, FPR≤0.10 | idem |
| Off-by-one de funding | `pytest tests/unit/test_engine.py::test_funding_off_by_one_convention` | ✅ 5/7 eventos, exacto | idem |
| Guard de holdout | `pytest tests/unit/test_holdout_guard.py` | ✅ niega sin env; log append-only con sha256+git SHA | idem |
| Registro obligatorio de trials | `pytest tests/unit/test_trials_ledger.py` | ✅ RuntimeError sin contexto; fallo registrado; idempotente | idem |
| Manifiestos de datos | `qa data verify` | ✅ 1201 ficheros | salida CLI |
| B&H vs fuente independiente | `python scripts/validate_bh.py` | ✅ overall_passed=true | `docs/evidence/bh_validation.json` (Kraken `/0/public/OHLC`, consultado 2026-10-26, ventana 2024-12-01→2025-06-30, 212 días) |
| Anclajes OTS | `ots upgrade/verify/info` + blockstream.info | ✅ 4/4 versiones con altura y hora de bloque | `docs/evidence/ots_block_anchors.json` |

## Resultados

### Potencia v1.3 al nivel calibrado t\*=0.025 (regla compuesta, 8.2 años)

| ΔSharpe verdadero | Potencia compuesta (ventana 100/200) |
|---|---|
| ≈0.11-0.14 | 10.5 % / 11.5 % |
| ≈0.28-0.34 | 19.0 % / 17.8 % |
| ≈0.50-0.57 | 29.5 % / 28.5 % |

Potencia < 50 % para todo efecto ≤ 0.5 ⇒ **veredicto por defecto INCONTRASTABLE** si el test no rechaza (política §8-H1, enmienda 4 del gate M0b ratificada). Bajo el nulo: FPR compuesta 2.8 % (conservador); FWER del pipeline completo con RC: 0.5 %.

### Validación del motor contra fuente independiente (prueba de aceptación 3)

| Activo | Ventana (in-sample) | engine_bh | Kraken (XBTUSDT/ETHUSDT) | Δ |
|---|---|---|---|---|
| BTCUSDT | 2024-12-01→2025-06-30 (212 d) | +10.2498 % | +10.2248 % | **0.025 %** |
| ETHUSDT | idem | −32.9630 % | −32.9730 % | **0.010 %** |

Identidad interna engine↔close-ratio exacta (<1e-9). Fuente: `https://api.kraken.com/0/public/OHLC?pair=XBTUSDT|ETHUSDT&interval=1440`, consultado 2026-10-26T21:2xZ. Ventana corta por limitación documentada de Kraken (devuelve como máximo las últimas 720 velas diarias; `since` no pagina hacia atrás — verificado empíricamente); misma quote USDT en ambos venues ⇒ sin riesgo de base.

## Desviaciones del plan y su justificación

1. **Ventana de validación B&H acortada** (2024-12→2025-06 en vez de multi-año): el endpoint de Kraken no pagina más allá de 720 velas diarias (quirk verificado en vivo). La prueba sigue cumpliendo su propósito (reproducción ±0.5 % contra fuente independiente citada) con 212 días. Alternativa multi-año (Coinbase/CoinGecko USD) descartada por riesgo de base USD/USDT.
2. **Señal sembrada con IC=0.10 y banda 10 pp**: el test de aceptación valida que el motor RECUPERA y DETECTA una señal conocida grande; con IC=0.05 y rebalanceo continuo, los costes se comen la señal (documentado en el test) y con IC=0.05 la detección no es determinista (potencia baja por diseño, §9.4). No es una estimación de efectos reales.
3. **FWER con n_perm=99** (vs 10 000 de la evaluación real): aproximación documentada; el umbral t\* es ligeramente conservador con menos permutaciones.
4. **Adjudicación de VENUSDT**: el halt de 88 días y la reanudación al valor post-swap se anotan al anuncio del swap VEN→VET (junio-julio 2018); no se localizó anuncio específico de reanudación del 2018-10-19 → clasificado corporate_action por la ruptura de serie documentada en los anuncios del swap (la razón del movimiento es el swap, no el mercado).
5. **`pandas 3.1.0` sin `py.typed`** → `pandas-stubs` en dev-deps (CI idéntico).
6. El motor de carry incluye la pierna de basis desde M2 (no estaba explícito en el plan): sin ella el carry quedaría sobreestimado; convención documentada en el docstring y testeada.

## Limitaciones y sesgos conocidos

- Las 3 pruebas sintéticas validan el motor y el protocolo de decisión, no la presencia de edge en el mercado real.
- `run_positions` usa el quote_volume del día de ejecución para la participación (el trade forma parte de ese volumen); con capital grande el test de participación rechazará trades (correcto: documenta la capacidad limitada).
- La permutación por bloques de 20 d subestima la persistencia multimes de la exposición (por eso FPR 6.7 % a nivel 0.05 → corregido con t\* calibrado). La evaluación real usa 10 000 permutaciones (mejor resolución de t\*).
- CPCV/PBO/RC están implementados y testeados en sintético, pero el pipeline integrado de M3 (rejilla completa × CPCV × costes ×2) aún no se ha ejecutado — es el trabajo de M3.
- El holdout sigue intacto: 0 accesos (`ledger/holdout_access.log` no existe todavía).

## Riesgos abiertos

1. **R1 · M3 BLOQUEADO por OSF**: condiciones del orquestador = v1.3 sellada ✅ + OTS v1.2 anclado ✅ + **OSF registrado ✗ (requiere cuenta del usuario)**. Todo lo demás está listo para M3.
2. **R2 · CI sin estrenar**: el bundle está entregado y verificado; en cuanto el usuario lo empuje al remoto, GitHub Actions correrá los mismos gates (python 3.12).
3. **R3 · Runtime de M3**: 24 candidatas H1 × 45 paths CPCV × bootstrap 10k + RC por familia — se ejecutará por fases con checkpoints en el ledger (nada se pierde si se interrumpe).
4. **R4 · Clave de firma en el sandbox**: si se pierde, las firmas antiguas siguen verificables (clave pública committeada) y se emitiría clave nueva con addendum en ADR-004.

## Preguntas para el orquestador (solo decisiones reales)

- **Q1 · Confirmación de bloqueo M3**: con v1.3 sellada y OTS anclado, ¿confirmas que M3 arranca en cuanto el usuario registre OSF (acción 2) y empuje el bundle (acciones 1/3)? No hay ninguna otra dependencia abierta por mi parte.
- (Recordatorio de acciones del usuario, no bloquean M2: crear repo privado vacío + cuenta OSF + `git clone quant-arena-M0b.bundle qa && cd qa && git remote add origin <URL> && git push -u origin main --tags`.)

## Qué aprendimos (lenguaje llano)

- **Un test también se calibra:** si tu examen suspende al 6.7 % de los inocentes cuando debería suspender al 5 %, subes la nota de corte (t\*=0.025 → 4.4 %). Calibrar con simulaciones antes de examinar datos reales es lo que separa un laboratorio de una lotería.
- **Rotar vs barajar:** para medir si tu timing vale algo, comparar contra tu propia exposición barajada por bloques resulta más informativo que contra la misma exposición rotada en bloque (que apenas cambia nada cuando las posiciones duran meses). Probamos las dos y nos quedamos con la que calibra bien Y conserva potencia.
- **El error familiar (FWER):** con 24 intentos, la probabilidad de que ALGUNO parezca bueno por azar era 28.5 %; el Reality Check sobre toda la familia la baja a 0.5 %. Por eso ningún veredicto mira una sola celda.
- **El carry tiene dos piernas:** cobrar funding no es todo — si la prima entre perp y spot se mueve en tu contra, pierdes. El motor ya contabiliza ambas (funding + basis), con la convención de horarios (00/08/16) testeada evento a evento para que no haya "off-by-one" que regale dinero ficticio.
- **Borrar el crash de LUNA habría sido trampa:** el −99.97 % de mayo 2022 fue real (mismo token); la trampa de datos está en el +178.000 % del 31 (cuando el par se re-asignó al token nuevo). La tabla de adjudicación distingue uno de otro con el anuncio oficial delante, sin mirar nunca el P&L.

## Solicitud: GATE APROBADO M2


---

## Corrección (M2b, 2026-10-27)

La Desviación 1 de este informe atribuía la ventana corta de validación B&H a
que "Kraken ignora `since` y no pagina más allá de 720 velas". **Es
incorrecto**: la causa real es que los pares **XBTUSDT/ETHUSDT de Kraken
nacieron el 2024-11-06** (verificado en vivo el 2026-10-27: primera vela de
ambos pares). Las 721 velas devueltas son la historia completa del par. La
validación de período completo contra segunda fuente independiente se cubrió
en M2b condición F con Coinbase Exchange (BTC-USD/ETH-USD, 2 992 días,
2017-08-17→2025-10-25): ver `docs/evidence/second_source_validation.json`.
