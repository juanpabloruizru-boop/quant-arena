# PRERREGISTRO v1.1 — QUANT-ARENA v2

**Fecha v1.1:** 2026-10-26 (UTC) · **Estado:** registrado; v1.0 sellada en
`prereg-v1`/`prereg-v1-signed` (commit `82bf430`, intacta); v1.1 sellada en
`prereg-v1.1` + OpenTimestamps.
**Espejo máquina:** `config/hypotheses.yaml` v1.1 (este documento manda; si
divergen, es un bug y se corrige el YAML).

> Regla de oro: ninguna regla se implementa ni ejecuta si no está en este
> documento. Cambiar algo aquí **después** de ver resultados invalida la
> ejecución: se crea v1.x con fecha, motivo y `n_trials +=` celdas nuevas.
> **v1.1 se registra ANTES de ingerir ningún dato de mercado** (M1 no ha
> comenzado): incorpora las 4 condiciones del orquestador en el gate M0 y las
> resoluciones P1–P4. n_trials no cambia (38): no se añaden celdas.

---

## 1. Pregunta de investigación

¿Existe alguna regla simple, de baja frecuencia y pre-registrada que, en
criptomonedas líquidas de Binance y **neta de costes verificados**, supere a
sus benchmarks en términos riesgo-ajustados con evidencia estadística robusta
a la multiplicidad de pruebas?

Un resultado negativo bien documentado es un éxito. Un positivo mal validado
es un fracaso.

## 2. Alcance y prohibiciones

- Sin dinero real, sin claves de exchange, sin órdenes, sin listeners/daemons.
- Máximo 3 familias de hipótesis (H1, H2, H3). Nada fuera de esta rejilla.
- Prohibido: portar Confluenciómetro, Fibonacci, Mayer, proyecciones o
  dashboards del proyecto anterior; reportar solo la mejor celda; usar retorno
  absoluto sin benchmark; apalancamiento como fuente de "retorno"; reutilizar
  el holdout; editar el ledger.
- Toda cifra citada lleva `run_id` o hash de fichero; todo dato externo lleva
  URL + fecha de verificación o se marca `[NO VERIFICADO]`.

## 3. Datos y horizontes (fuentes verificadas en vivo el 2026-10-26)

Evidencia: `docs/evidence/binance_probes.json` (script: `scripts/probe_binance.py`).

| Dato | Fuente | Inicio verificado |
|---|---|---|
| Klines spot 1d y 4h | `api.binance.com/api/v3/klines` + dumps diarios `data.binance.vision` (bucket S3) | BTCUSDT: 2017-08-17 |
| Klines perp USDT-M 1d/4h | `fapi.binance.com/fapi/v1/klines` + dumps | BTCUSDT API: 2019-09-08; dumps diarios: 2019-12-31 |
| Funding histórico real | `fapi/v1/fundingRate` (paginado por startTime) + dumps **mensuales** `data/futures/um/monthly/fundingRate/` | BTCUSDT: primer registro 2019-09-10 |
| Unidades de timestamp | spot y futures: **ms** (13 dígitos), verificado empíricamente | — |
| Límites | `/api/v3/klines` tapa a **1000** filas (sin error); `fundingRate` ignora `startTime=0` (devuelve recientes) | — |

- **Unidades y timezone:** todo se normaliza a UTC y milisegundos. Test de
  unidad obligatorio en M1 (13 vs 16 dígitos) porque el prompt heredado avisa
  de mezclas ms/µs; hoy ambas APIs responden ms.
- **Congelación de datos:** en M1 se fija `data_freeze_date` (último día de
  datos curados) y se publica en el manifiesto.
- **Holdout sellado:** últimos **365 días** antes de `data_freeze_date`. Se
  bloquea al crear el dataset curado (M1), se evalúa **una sola vez** al final
  de M3 con reglas y celdas congeladas, y su resultado se reporta tal cual.
  Esperado con freeze ≈ 2026-10-25: holdout ≈ 2025-10-26 → 2026-10-25.
- **In-sample esperado** (para planificación de potencia): H1 ≈ 8.19 años
  (2017-08-17→2025-10-25); H2 ≈ 6.8 años (universo PIT con profundidad desde
  ~2019-01, a confirmar en M1); H3 ≈ 6.1 años (funding desde 2019-09-10).
- **Declaración de régimen 2017-18 (condición P2):** el tramo 2017-08→2019-12
  (SP1) pertenece a la microestructura temprana de cripto: liquidez relativa
  baja, spreads más amplios que hoy, boom ICO y crash de enero 2018. Se
  conserva en H1 (más datos = más potencia) pero: (a) se reporta SIEMPRE por
  separado como subperíodo SP1; (b) ningún veredicto PASA puede apoyarse solo
  en SP1 (la regla de subperíodos exige consistencia); (c) los costes
  verificados en 2026 subestiman probablemente los de 2017-18 → el stress ×2
  es la protección pre-registrada.
- **Universo PIT fino pre-2019 (condición P2):** antes de 2019 Binance listaba
  menos pares líquidos; el top-N PIT de H2 empieza en ~2019-01 y los meses
  anteriores se excluyen de H2 (no se "rellenan" con menos símbolos de los que
  la regla exige). El informe de M1 documentará el número efectivo de
  candidatos por mes.

## 4. Universo point-in-time (ver ADR-002 y `config/universe.yaml`)

- Ranking mensual del top-N (N∈{10,20}) por volumen quote USDT (media diaria
  de los 30 días previos), usando **solo** datos anteriores al instante de
  ranking. Exclusión de estables, wrapped, tokens apalancados. Mínimo 60 días
  listado. Se incluyen símbolos deslistados mientras estuvieran en estado
  TRADING en su momento (los dumps de `data.binance.vision` los conservan:
  verificado FTTUSDT y LUNABTC el 2026-10-26).
- Sesgos no eliminables (se declaran en todo informe): solo existe lo que
  Binance listó (supervivencia del venue); el ranking usa el propio venue.

### Grados de libertad del investigador (condición 4 del gate M0)

Todo criterio de decisión tiene elecciones que un investigador podría retorcer
a posteriori. Las declaramos y las congelamos AHORA:

| Grado de libertad | Valor congelado | Comentario |
|---|---|---|
| N del top-N (H2) | {10, 20} como dimensión de rejilla | No es elección post-hoc: ambas se ejecutan y publican; la candidata se elige por la regla fija §7.6 |
| Métrica de ranking PIT | volumen quote USDT, media diaria trailing-30d | Alternativas (volume 7d, capitalización) NO se probarán |
| Cadencia de rebalanceo PIT | mensual (primer día UTC) | Fija |
| Edad mínima de listado | 60 días | Fija |
| Lista de exclusiones | la de `universe.yaml` v1.0 | Fija |
| Exposición media del benchmark H1 | ē calculado DENTRO de cada periodo de evaluación | Fijo (evita elegir el periodo que favorezca) |
| Bloque de permutación (H1) | circular, 20 días, 10 000 permutaciones, semilla 20261026 | Fijo |
| Banda de rebalanceo (H1) | 10 pp; los flips long↔flat siempre operan | Fija; justificada por el análisis de potencia PRE-datos (§9): sin banda, el turnover diario sangra el drawdown vía costes |
| Fronteras de subperíodos | SP1 2017-08-17→2019-12-31, SP2 2020-01-01→2022-12-31, SP3 2023-01-01→fin in-sample | Fijas (cubren regímenes: temprano, ciclo 2020-22, ciclo 2023-25) |
| Embargos CPCV | H1 20 d, H2 14 d, H3 7 d | Fijos |
| Bloque de bootstrap | estacionario, bloque esperado 20 d (diario) / 8 sem (semanal) | Fijo |

Cambiar CUALQUIERA de estos valores tras ver resultados = nueva versión del
preregistro + recuento de ensayos desde cero para esa familia.

## 5. Costes (ver ADR-003 y `config/costs.yaml`)

Verificados en vivo el 2026-10-26:
- Spot usuario regular: **0.100 % maker / 0.100 % taker**
  (binance.com/en/fee/schedule). No se asume descuento BNB.
- Perp USDT-M usuario regular: **0.020 % maker / 0.050 % taker**
  (binance.com/en/fee/futureFee). No se asume la promo vigente.
- Mínimos: spot `minNotional` 5 USDT (BTCUSDT/ETHUSDT; PEPEUSDT 1 USDT);
  perp BTCUSDT `minQty` 0.001 BTC y `MIN_NOTIONAL` 50 USDT.
- Funding: **histórico real** por símbolo (intervalo BTCUSDT verificado: 8 h).
- Slippage: tramos por participación sobre volumen diario (asunción
  pre-registrada, conservadora; se calibra contra evidencia en M2 sin
  relajarla tras ver resultados).
- **Stress obligatorio ×2** sobre fees+slippage en todo veredicto.
- Ejecución: señal en cierre de t → fill en t+1 (nunca en el mismo cierre).

## 6. Hipótesis y rejilla (congelada)

### H1 — Tendencia temporal long/flat con volatilidad objetivo (BTC, ETH)

- Señal A (`sma`): `close[t] > SMA(n)[t]` → long desde t+1.
- Señal B (`ret`): retorno acumulado de L días en t > 0 → long desde t+1.
- Tamaño: `min(1, σ_obj / σ_realizada_20d)`; flat = 0. Sin cortos, sin apalancar.
  **Banda de rebalanceo (v1.1):** la posición objetivo se recalcula a diario pero
  solo se ejecuta si cambia ≥ 10 pp o si la señal flipa (long↔flat). Parámetro de
  diseño congelado, justificado PRE-datos por el análisis de potencia (§9.2):
  sin banda, el turnover diario del vol targeting sangra el drawdown vía costes.
- Rejilla: variante ∈ {sma, ret} × ventana ∈ {50, 100, 200} × σ_obj ∈ {15 %, 25 %}
  = **12 celdas**; cada celda se evalúa en BTCUSDT y ETHUSDT por separado →
  **24 trials**.
- *Decisión de interpretación:* el enunciado heredado "cierre > SMA(n) **o**
  retorno de L días > 0; n, L ∈ {50,100,200}" se registra como **dos variantes
  de señal disjuntas** (12 celdas), no como señal disyuntiva con producto
  cruzado n×L (18 celdas). **Ratificada por el orquestador en el gate M0 (P1,
  2026-10-26).**
- **Benchmark primario (v1.1, condición 1 del gate M0): buy & hold con la MISMA
  exposición media que la estrategia** — `r_bh_matched[t] = ē · r_activo[t]`,
  con `ē` = media temporal de la posición de la estrategia DENTRO de cada
  periodo de evaluación (in-sample completo, subperíodo o fold). Benchmarks
  secundarios (siempre reportados): B&H crudo y caja. La comparación contra
  B&H crudo mide "estar menos expuesto"; la comparación matched mide **skill de
  timing**, que es lo que H1 afirma.
- **Nulo de permutación de timing (v1.1):** la misma serie de posiciones con la
  exposición preservada pero el timing barajado (permutación circular por
  bloques de 20 días, 10 000 permutaciones, semilla fija). p-valor = fracción
  de permutaciones con ΔmaxDD igual o mejor que el observado. Las permutaciones
  son parte del estadístico de una candidata, **no trials adicionales**
  (kind=`null` en el ledger).
- **Co-métricas obligatorias (v1.1, condición 2):** Ulcer Index, Calmar y
  tiempo bajo el agua (time underwater), además de Sharpe/Sortino/maxDD.
- **Regla de subperíodos (v1.1, condición 2):** la mejora de ΔmaxDD (frente al
  benchmark matched) debe darse en el in-sample completo **y** en ≥ 2 de los 3
  subperíodos: SP1 2017-08-17→2019-12-31, SP2 2020-01-01→2022-12-31,
  SP3 2023-01-01→fin del in-sample. Se exige por activo (BTC y ETH).
- **Expectativa (formulación exigida por el prompt y afinada en v1.1):**
  reducción de drawdown **a igual exposición media** con Sharpe no inferior al
  de B&H; NO se espera más retorno absoluto.

### H2 — Momentum transversal semanal en universo PIT

- Formación: retorno acumulado de L semanas **excluyendo la última semana**.
- Cartera: long del tercil superior, equiponderado, rebalanceo semanal, sin cortos.
- Rejilla: L ∈ {4, 12, 26} × N ∈ {10, 20} = **6 celdas → 6 trials**.
- Benchmark directo: universo equiponderado (no B&H de BTC).

### H3 — Carry spot-perp delta-neutral (BTC, ETH)

- Señal: media móvil de `window_days` del funding anualizado > `threshold`
  (anualización con el intervalo real del símbolo) → entrar en t+1; salir al
  cruzar por debajo.
- Posición: 1× spot long + 1× perp short del mismo nocional. Sin apalancamiento
  neto. Funding real cobrado/pagado en cada intervalo.
- Rejilla: window ∈ {7, 30} d × umbral ∈ {5 %, 10 %} anual = **4 celdas**;
  en BTCUSDT y ETHUSDT → **8 trials**.
- Benchmark: caja (USDT). Riesgos pre-registrados: crash de basis, cambio de
  régimen de funding, ejecución asíncrona de piernas (se modela el peor orden).
- **Regla por activo (P4, gate M0):** ETH se MANTIENE en H3. Cada activo se
  evalúa con su propia historia real (el funding de ETHUSDT puede empezar más
  tarde que el de BTCUSDT; M1 lo verifica) y su propio MDE con su n real.
  **Si MDE_ETH > 2 × MDE_BTC → ETH se declara INCONTRASTABLE por separado**;
  BTC sigue evaluado con todos los criterios y el veredicto de familia se toma
  sobre BTC, dejando constancia explícita del estado de ETH.

### Contabilidad de ensayos (no negociable)

- `n_trials` por familia = filas en `ledger/trials.duckdb` de configuraciones
  de estrategia ejecutadas (incluidas diagnósticos y fallos), con **suelo** =
  rejilla pre-registrada (H1: 24, H2: 6, H3: 8; total 38).
- Escribir en `trials` es obligatorio por diseño: el motor no devuelve métricas
  sin haber registrado (decorador/contexto en M2). DSR y Reality Check/SPA leen
  n_trials de la tabla, **nunca** de un número escrito a mano.
- Benchmarks y pruebas sintéticas no cuentan como trials de hipótesis, pero sí
  se registran con etiqueta `kind` distinta.

## 7. Pipeline de evaluación (idéntico para las 3 familias)

1. **CPCV purgado con embargo**: N=10 splits, 2 splits de test → C(10,2)=45
   trayectorias. Purge: fuera del train toda muestra cuya ventana de formación
   solape el test. Embargo posterior al test: H1 20 d, H2 14 d, H3 7 d.
2. **Métricas por fold y agregadas**: Sharpe y Sortino anualizados, max DD,
   Calmar, expectancy en R, IC (cuando aplique señal continua). **Co-métricas
   H1 (v1.1):** Ulcer Index y tiempo bajo el agua, por periodo de evaluación.
3. **Benchmarks H1 (v1.1):** B&H matched-exposure (primario; ē dentro de cada
   periodo de evaluación) + B&H crudo y caja (secundarios). **Nulo de
   permutación de timing:** permutación circular por bloques de 20 días de la
   serie de posiciones, 10 000 permutaciones, semilla 20261026; p-valor =
   fracción de permutaciones con ΔmaxDD igual o mejor que el observado.
   **Subperíodos:** SP1/SP2/SP3 con fronteras fijas (§4, grados de libertad).
4. **Incertidumbre**: bootstrap por bloques estacionario (bloque esperado 20 d
   en series diarias; 8 semanas en semanales; 10 000 remuestreos, semilla
   fija) para ICs de diferencias frente a benchmark; errores estándar HAC
   (Newey-West, lag = ventana de formación) para medias.
5. **Anti-sobreajuste**: PBO vía CSCV sobre la rejilla de la familia;
   Reality Check/SPA sobre todas las celdas vs benchmark — **en H1 el
   estadístico de SPA/RC es la mejora de ΔmaxDD matched (criterio primario de
   multiplicidad, condición 3 del gate M0)**; en H2/H3 el estadístico es el
   retorno/Sharpe neto. DSR (Bailey–López de Prado) con n_trials del ledger,
   asimetría y curtosis empíricas: **criterio de gate en H2 y H3; en H1 se
   computa y reporta, sin poder tumbar un PASA**.
6. **Costes**: todo neto de costes verificados; repetición obligatoria con ×2.
7. **Selección de candidata**: por familia, según su métrica primaria — H1:
   mayor mejora media de ΔmaxDD matched en las 45 trayectorias CPCV
   in-sample; H2/H3: mayor Sharpe neto medio en las 45 trayectorias. Regla
   fijada ahora, antes de ver nada. Esa candidata —y solo esa— pasa al holdout.
8. **Holdout**: evaluación única al final de M3. Prohibido ajustar nada tras
   verlo. Su resultado se reporta tal cual, gane o pierda.

## 8. Criterios de éxito (v1.1 — diferenciados por familia; potencia en §9)

Veredictos por familia sobre la candidata seleccionada en §7.7.

### H1 (v1.1: el gate primario mide *timing skill* contra matched-exposure)

| # | Criterio | Umbral |
|---|---|---|
| C1a | ΔmaxDD vs B&H matched-exposure (in-sample completo): mejora (ΔmaxDD < 0) **en BTC y en ETH**, con p-valor del test de permutación de timing | p < 0.05 por activo |
| C1b | Subperíodos: mejora (ΔmaxDD < 0) en ≥ 2 de 3 (SP1/SP2/SP3) | por activo (BTC y ETH) |
| C2' | Multiplicidad: **SPA/Reality Check** sobre el estadístico ΔmaxDD matched, rejilla completa de 12 celdas por activo (condición 3 del gate M0: DSR NO es criterio primario de H1; se computa y reporta, sin veto) | p < 0.05 |
| C3 | PBO (CSCV de la familia) | < 0.20 |
| C4 | Costes ×2: ΔmaxDD matched mantiene la mejora **y** ΔSharpe matched ≥ −0.10 | ambos |
| C5 | Folds CPCV con ΔmaxDD matched < 0 | ≥ 60 % |
| C7 | Holdout (una sola vez): signo de ΔmaxDD matched coherente con in-sample | no exige significación (n = 1 año); signo opuesto en ambos activos → NO PASA |

- Co-métricas (Ulcer Index, Calmar, tiempo bajo el agua) y ΔSharpe vs B&H
  crudo: se reportan SIEMPRE, no hacen gate.
- ΔSharpe matched con IC bootstrap: se reporta con nota explícita de potencia
  (MDE pareado ≈ 0.67 a 8.2 años, §9.1). La no-inferioridad práctica
  (ΔSharpe matched ≥ −0.10) forma parte de C4.

### H2 (criterios v1.0, sin cambios)

| # | Criterio | Umbral |
|---|---|---|
| C1 | ΔSharpe neto anualizado vs universo equiponderado, IC bootstrap 95 % | excluye 0 y > 0 |
| C2 | DSR con n_trials real del ledger | > 0.95 |
| C3 | PBO (CSCV) | < 0.20 |
| C4 | Sharpe neto con costes ×2 | > 0 |
| C5 | Folds CPCV en positivo | ≥ 60 % |
| C6 | Reality Check/SPA de la familia vs benchmark | p < 0.05 |
| C7 | Holdout: signo coherente | signo opuesto → NO PASA |

### H3 (criterios v1.0; DSR como criterio primario de multiplicidad — condición 3)

| # | Criterio | Umbral |
|---|---|---|
| C1 | Media diaria neta > 0 tras costes y funding real (t-HAC una cola), por activo | p < 0.05 |
| C2 | **DSR con n_trials real del ledger (criterio primario)** | > 0.95 |
| C3 | PBO (CSCV) | < 0.20 |
| C4 | Media diaria neta con costes ×2 | > 0 |
| C5 | Folds CPCV en positivo | ≥ 60 % |
| C6 | Reality Check/SPA de la familia vs caja | p < 0.05 |
| C7 | Holdout: signo coherente | signo opuesto → NO PASA |

- **Regla P4 (ETH):** MDE por activo con su n real; si MDE_ETH > 2 × MDE_BTC →
  ETH = INCONTRASTABLE por separado (no penaliza a BTC); ver §6 H3.

### Veredictos (todas las familias)

- **PASA**: todos los criterios de su tabla.
- **NO PASA**: C1 falla, o fallan C2'–C5 con potencia ≥ 50 % para el efecto
  observado (§9).
- **INCONTRASTABLE**: efecto observado < MDE del horizonte (§9) con potencia
  < 50 %. El boletín (M5) no emitirá recomendación; reportará
  `SIN VENTAJA DEMOSTRADA (n=…, IC=…)`.
- Regla anti-jardinería: veredictos por familia, TODAS las celdas publicadas
  siempre (tabla completa + distribución), ninguna re-ejecación "para
  comprobar" tras el holdout.

## 9. Análisis de potencia (resumen v1.1; detalle en `reports/M0_power_analysis.md/.json`)

Script: `scripts/power_analysis.py` (semilla 20261026; α una cola 5 %, potencia
objetivo 80 %, K = 2.4866; Monte Carlo con 1 200 trayectorias por config).

1. **Diferencia de Sharpe (no pareada):** MDE = 1.94 con 3.3 años; **1.23 con
   8.2 años**. Detectar ΔSharpe = 0.5 exigiría ~50 años; Δ = 0.3, ~137 años.
   Monte Carlo pareado de H1 (sd(ΔSharpe) ≈ 0.27 a 8.2 años): MDE pareado
   ≈ 0.67 (potencia 80 %) o ≈ 0.44 (nivel 5 %). → El test "Sharpe ≥ B&H" es
   incontrastable para mejoras pequeñas; el Sharpe entra como co-métrica y
   como no-inferioridad práctica (≥ −0.10) en C4.
2. **H1 vs B&H CRUDO (comparación v1.0, ya no primaria):** la mejora de
   maxDD aparece con potencia 77–99 % en TODOS los mundos simulados (incluso
   bajo GBM sin skill): es casi pura consecuencia de estar menos expuesto.
   Justifica la condición 1 del gate M0 (benchmark matched-exposure).
3. **H1 vs B&H MATCHED-EXPOSURE (criterio primario v1.1), espectro de DGPs:**
   - GBM iid (nulo sin habilidad): la regla compuesta pasa en ~2–3 % de los
     mundos → el test es **conservador** (por debajo del 5 % nominal).
   - Vol Markov-switching (σ 35 %/100 %, duraciones ~100 d): E[ΔmaxDD_m]
     ≈ +7.6/+8.3 pp (PEOR que el matched), potencia ≈ 1.5–1.6 %, regla
     compuesta ≈ 16–17 %.
   - Vol MS + crashes de Poisson (2/año en estado alto vs 0.2/año en bajo,
     tamaño N(−15 %, 8 %)): E[ΔmaxDD_m] ≈ +6.4/+6.9 pp, potencia ≈ 2 %,
     regla compuesta ≈ 16–19 %.
   - Deriva MS (bull +80 % / bear −40 %, duraciones ~200 d): E[ΔSharpe_m]
     ≈ +0.04/+0.07, E[ΔmaxDD_m] ≈ +10 pp, compuesta ≈ 7–8 %.
   **Lectura honesta:** en los mundos sintéticos ensayados, el mecanismo H1
   pre-registrado NO mejora el drawdown a igual exposición media (el vol
     targeting con σ_real 20d reacciona tarde a los saltos y la SMA llega
   tarde a los giros). Solo pasaría C1a/C1b si el mercado real contiene
   estructura anticipatoria de crashes mayor que la de estos mundos. H1 tiene
   pues una probabilidad sustancial de terminar en **NO PASA o
   INCONTRASTABLE**; se declara AHORA, antes de ver datos. No se relaja el
   criterio por eso: es exactamente el claim de skill que debe demostrarse.
   **Hallazgo de diseño pre-datos:** sin banda de rebalanceo, el turnover
   diario del vol targeting añade ~1 pp de sangría a ΔmaxDD_m; la banda de
   10 pp (§6 H1) queda pre-registrada.
4. **DSR ≥ 0.95 (gate de H2/H3; informativo en H1):** con n_trials = 38 y
   8.2 años exige Sharpe observado ≈ **1.66–2.22** según dispersión entre
   celdas (sd 0.5–0.75) y colas; con 3.3 años: ≈ 2.0–2.6.
5. **H2 (spread semanal, n ≈ 354 semanas):** MDE ≈ 0.46–0.77 %/sem
   (σ 3–5 %/sem, ρ 0–0.15) ≈ 24–40 % anualizado. Detectar 0.2 %/sem exigiría
   ~64 años. → **INCONTRASTABLE en el horizonte para spreads típicos
   (10–20 %/año)**; solo un spread bruto extraordinario (> ~25–30 %/año) sería
   detectable. Declarado de antemano.
6. **H3 (carry diario):** n_BTC ≈ 2 237 días → MDE ≈ 1.0–2.1 %/año
   (σ diaria 5–10 pb, ρ 0–0.1). Carry ≥ 4 %/año: potencia > 80 % con ~1.7
   años. **P4:** n_ETH se verifica en M1; si el funding de ETHUSDT empieza
   ~2019-11, n_ETH ≈ 0.95·n_BTC → MDE_ETH ≈ 1.03·MDE_BTC ≪ 2× → ambos
   contrastables. La regla P4 (§6 H3) protege contra sorpresas mayores.
7. **Tasas de acierto:** discriminar WR 45 % vs 40 % exige **n ≈ 600 trades**
   (42 % vs 40 %: ~3 729). H1 genera decenas → ningún criterio basado en WR.
8. **Consecuencia pre-registrada (v1.1):** con 38 ensayos y estos horizontes,
   el laboratorio solo confirma **efectos grandes**; H1 exige además skill de
   timing pura (matched-exposure), que los mundos sintéticos sugieren que el
   mecanismo no posee por construcción. Todo efecto menor que el MDE se
   reportará como INCONTRASTABLE con su MDE explícito. Esto no es un fallo del
   diseño: es la honestidad que exige el principio 9.

## 10. Sellado del preregistro (estado v1.1)

- **v1.0 (intacto, no se modifica):** tag anotado `prereg-v1` + tag FIRMADO
  `prereg-v1-signed` (SSH ed25519, clave pública en `docs/keys/`) sobre el
  MISMO commit `82bf430`. Verificación: `git tag -v prereg-v1-signed`
  (evidencia: `docs/evidence/ssh_signature_log.txt`).
- **OpenTimestamps (condición P3, "ya"):** hashes normativos v1.0 anclados
  mediante `ots stamp` en 4 calendarios públicos
  (`docs/evidence/normative_hashes_v1.0.txt.ots`, log en
  `docs/evidence/ots_stamp_log_v1.0.txt`). Estado al sellar: *Pending
  confirmation in Bitcoin blockchain* (normal: los calendarios agregan al ancla
  BTC en horas). **Checklist M1:** `ots upgrade` + `ots verify` → debe dar
  success con altura de bloque. Lo mismo se hace con v1.1.
- **OSF (condición P3): antes de M3.** El usuario crea la cuenta; se registran
  PREREGISTRO v1.x vigente + hashes. Motivo (ADR-004): un tag git es
  autoatestiguado; OSF aporta timestamp de tercero con reloj independiente.
- **v1.1:** tag `prereg-v1.1` (anotado y firmado SSH) sobre el commit que
  congela este documento + `config/hypotheses.yaml` v1.1, con SHA256 de ambos
  en el mensaje del tag + anclaje OTS de los hashes (`normative_hashes_v1.1.txt`).

## 11. Hechos heredados del proyecto anterior (estado de verificación)

| Hecho heredado | Estado | Plan |
|---|---|---|
| Universo anterior BTC/ETH/SOL/BNB/PEPE, velas 4H 2023-2026, Binance | [HEREDADO, NO VERIFICADO] | M1 reconstruye universo PIT real (no se reutiliza) |
| Baseline EMA21/55+RSI+Donchian −39 % vs B&H +211 %, DSR≈0.07 | [HEREDADO, NO VERIFICADO] | No se porta (fuera de rejilla). Solo como motivación |
| Pullback MTF+SMA200 ≈ 0 ventaja (PF 0.99); filtro SMA200 empeora | [HEREDADO, NO VERIFICADO] | No se porta |
| Macro Momentum EMA12/26 diario PF 4.46 con n=20, DSR≈0 | [HEREDADO, NO VERIFICADO] | No se porta. Nota: n=20 y DSR≈0 es exactamente el fallo que este preregistro evita (potencia §9.6) |
| Proyecciones 1D/2-3D/1W no superan baseline | [HEREDADO, NO VERIFICADO] | Fuera de alcance |
| Confluenciómetro/Fibonacci/Mayer sin validar | Confirmado: sin evidencia en literatura (§2 de LITERATURA.md) | Prohibido portar |
| Capital <100 USD: fees consumen 40–75 % del objetivo 1–2 %/mes | [PARCIALMENTE VERIFICADO] mínimos y fees en vivo 2026-10-26 (`config/costs.yaml`); la horquilla 40–75 % depende de frecuencia | M2 informa el número exacto por frecuencia de operación |
| Fallos de diseño a no repetir (n_trials manual, sin sello externo, potencia insuficiente, clase vacía por guarda, señales correlacionadas como independientes, duplicados, dashboard 80k LOC) | Mitigados por diseño: §6 (ledger), §10 (sello), §9 (potencia), tests de no-vacío en M3, bootstrap de bloque/HAC (ρ entre activos), repo único sin duplicados, sin dashboard | Tests de aceptación en M2/M3 |

## 12. Versionado

| Versión | Fecha | Cambio | n_trials |
|---|---|---|---|
| 1.0 | 2026-10-26 | Registro inicial (tag `prereg-v1`, commit `82bf430`) | 38 |
| 1.1 | 2026-10-26 | Condiciones 1-4 del gate M0 (orquestador): benchmark primario H1 = B&H matched-exposure + permutación de timing; co-métricas Ulcer/Calmar/time-underwater y regla de subperíodos (≥2 de 3) por activo; DSR deja de ser gate de H1 (SPA/RC sobre ΔmaxDD matched lo sustituye) y sigue siéndolo de H3; grados de libertad documentados (§4). Resoluciones P1 (rejilla disjunta ratificada), P2 (horizonte 2017/2019 + declaración de régimen 2017-18 y PIT fino), P3 (OTS ya, OSF antes de M3), P4 (ETH se mantiene; MDE por activo; regla 2×). Banda de rebalanceo 10 pp añadida por hallazgo PRE-datos del análisis de potencia (§9.3). Sin celdas nuevas. | 38 |
