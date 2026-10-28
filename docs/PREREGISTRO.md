# PRERREGISTRO v1.4 — QUANT-ARENA v2

**Fecha v1.4:** 2026-10-27 (UTC) · **Estado:** registrado. v1.4 = solo texto
(añadidos 1-5 del gate M2b, aprobados por el orquestador): validación
multi-mundo de t\*, n_trials familiar del DSR con sd estimada del ledger,
selección de candidata por MEDIANA CPCV (una celda por familia y activo),
protocolo M3 en dos puertas (M3a in-sample + congelación aprobada; M3b
holdout único con clave del usuario) y pre-declaración de veredicto esperado
para H1. Sin cambios en rejilla, sizing ni criterios numéricos. v1.0 (`prereg-v1`,
`prereg-v1-signed`, commit `82bf430`), v1.1 (`prereg-v1.1`) y v1.2
(`prereg-v1.2`) intactas. v1.3 sellada en `prereg-v1.3` + OpenTimestamps.
Incorpora las correcciones pre-M3 del gate M1: (1) la higiene de datos SOLO
MARCA — tabla de adjudicación de artefactos con evidencia (anuncio+fecha),
los real_moves se conservan íntegros; (2) auditoría de exclusiones del
universo; (3) nivel crítico del test de permutación CALIBRADO en el nulo
sintético (t* = 0.025, FPR 4.4 %; rotación completa descartada con
evidencia); (4) FWER del pipeline H1 simulado (0.5 %); (5) prueba de
regeneración byte-idéntica. Sigue sin calcularse ninguna métrica de
estrategia sobre datos reales.
**Espejo máquina:** `config/hypotheses.yaml` v1.4 (este documento manda; si
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
| Factor del benchmark vol-matched H1 | f = σ_estrategia/σ_B&H, ex-post DENTRO de cada periodo de evaluación (solo para el benchmark) | Fijo; exposure-matched (ē) degradado a diagnóstico por sesgo de Jensen |
| Bloque de permutación (H1) | bloques circulares 20 días, 10 000 permutaciones, semilla 20261026, nivel crítico t* = 0.025 | Fijo. t* calibrado PRE-datos con 5000 sims del nulo (FPR 4.36 % ≤ 5 %; con 0.05 se iba a 6.7 %). Rotación circular completa descartada por evidencia sintética (FPR 2.8 %, potencia 6.8 %) |
| Banda de rebalanceo (H1) | 10 pp; los flips long↔flat siempre operan | Fija. Bandas simuladas PRE-datos {0, 2, 5, 10, 20} pp (§9.5): sangría 1.06/0.99/0.92/0.85/0.80 %/año. 10 pp = rodilla: captura casi todo el ahorro sin ralentizar la reacción ante crashes (20 pp ahorra 0.05 %/año más pero duplica el retardo de salida). Ninguna banda se optimizará con datos reales |
| Fronteras de subperíodos | SP1 2017-08-17→2019-12-31, SP2 2020-01-01→2022-12-31, SP3 2023-01-01→fin in-sample | Fijas (cubren regímenes: temprano, ciclo 2020-22, ciclo 2023-25) |
| Embargos CPCV | H1 20 d, H2 14 d, H3 7 d | Fijos |
| Adjudicación de artefactos | `config/adjudications.csv` (5 eventos \|log-ret\|>5 in-sample; enumeración completa) | Protocolo: corporate_action exige anuncio oficial (URL+fecha); sin anuncio → real_move por defecto. Sellada en v1.3 |
| Convención de deslistado | último precio observado (sin imputación) | Fija |
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
- **Benchmark primario (v1.2, corrección del defecto 1 del gate M0b): B&H
  VOL-MATCHED** — `r_bh_vm[t] = f · r_activo[t]`, con
  `f = σ(retornos netos de la estrategia) / σ(retornos del activo)` calculado
  ex-post DENTRO de cada periodo de evaluación (in-sample completo, subperíodo
  o fold) y usado SOLO para construir el benchmark. Bajo el nulo de timing,
  E[ΔmaxDD] ≈ 0 (§9.3, verificado). El **exposure-matched de v1.1 (ē·r) queda
  degradado a diagnóstico**: por Jensen (E[w²] ≥ ē²) penaliza sistemáticamente
  a toda regla de exposición variable bajo el nulo; no puede ser criterio.
  Benchmarks reportados: vol-matched (primario), exposure-matched, B&H crudo y
  caja (diagnósticos). Nota: Sharpe(f·r) = Sharpe(r) ⇒ ΔSharpe vs vol-matched
  ≡ ΔSharpe vs B&H crudo.
- **Criterio de permutación (v1.3):** nulo = el PROPIO vector de posiciones de
  la estrategia, permutado por bloques circulares de 20 días (10 000
  permutaciones en evaluación real; 199 en simulaciones; semilla fija
  20261026). Para cada permutación se recalcula el estadístico COMPLETO
  (estrategia neta de costes frente a SU vol-matched con f propio). p-valor =
  (1 + #{Δ_perm ≤ Δ_obs}) / (1 + n_perm). **Nivel crítico calibrado: p ≤ t\* =
  0.025** (FPR sintético 4.36 % ≤ 5 %; a 0.05 daba 6.7 %). La rotación
  circular completa se evaluó y descartó con evidencia sintética: FPR 2.8 %
  pero potencia 6.8 % (con exposición persistente de meses, rotar apenas cambia
  la alineación de baja frecuencia). **El estadístico de decisión es el p-valor
  permutado, NO el ΔmaxDD puntual** (bajo el nulo E[ΔmaxDD vol-matched] ≈ +4 pp
  por mezcla de escalas: el punto no decide, la permutación sí). También se
  computa el p-valor adverso (#{Δ_perm ≥ Δ_obs}) para el veredicto NO PASA. Las
  permutaciones son parte del estadístico de una candidata, **no trials
  adicionales** (kind=`null` en el ledger).
- **Co-métricas obligatorias (v1.1, condición 2):** Ulcer Index, Calmar y
  tiempo bajo el agua (time underwater), además de Sharpe/Sortino/maxDD.
- **Regla de subperíodos (v1.2):** usa el MISMO estadístico — ΔmaxDD frente
  al vol-matched con f calculado DENTRO de cada subperíodo (nunca el punto
  contra una fracción constante): mejora (Δ < 0) exigida en el in-sample
  completo **y** en ≥ 2 de los 3 subperíodos: SP1 2017-08-17→2019-12-31, SP2
  2020-01-01→2022-12-31, SP3 2023-01-01→fin del in-sample. Por activo (BTC y
  ETH).
- **Expectativa (v1.2):** reducción de drawdown **a igual volatilidad** (skill
  de timing) con Sharpe no inferior al de B&H; NO se espera más retorno
  absoluto.

### H2 — Momentum transversal semanal en universo PIT

- Formación: retorno acumulado de L semanas **excluyendo la última semana**.
- Cartera: long del tercil superior, equiponderado, rebalanceo semanal, sin cortos.
- Rejilla: L ∈ {4, 12, 26} × N ∈ {10, 20} = **6 celdas → 6 trials**.
- Benchmark directo: universo equiponderado (no B&H de BTC).
- **Higiene de datos (v1.3, mark-only):** los eventos |log-ret diario| > 5 se
  MARCAN, no se borran (`config/adjudications.csv`, sellada). `real_move`
  (p. ej. colapso LUNA 2022-05-12) se conserva ÍNTEGRO — borrar crashes reales
  favorece a las carteras long-only. `corporate_action` (ruptura con anuncio
  oficial: LUNA2 2022-05-31, VEN→VET 2018, COCOS 1000:1, SUN 1:1000): excluye
  al símbolo del ranking PIT 30 días y **toda ventana de formación que cruce la
  ruptura invalida al símbolo para ese rebalanceo** (slot a caja esa semana;
  cada activación se audita). Convención de deslistado: último precio
  observado, sin imputación.

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
3. **Benchmarks H1 (v1.2):** vol-matched (primario; f = σ_strat/σ_BH dentro de
   cada periodo de evaluación) + exposure-matched, B&H crudo y caja
   (diagnósticos). **Nulo de permutación:** bloques circulares de 20 días
   sobre el vector de posiciones, 10 000 permutaciones, semilla 20261026;
   estadístico completo recalculado por permutación; p-valor con corrección
   +1. \1
   **Validación de t\* (v1.4):** FPR(p≤t\*) ∈ [1.5 %, 4.6 %] en 3 mundos nulos
   × semillas nuevas (5000 sims cada uno): GBM 4.6 %, vol-MS 1.5 %, vol-MS +
   jumps 2.3 % — siempre ≤ 5 % nominal y **conservador bajo regímenes de
   volatilidad**; la potencia sintética reportada debe leerse como **cota
   superior** (`reports/M2_tstar_validation.md`).
4. **Incertidumbre**: bootstrap por bloques estacionario (bloque esperado 20 d
   en series diarias; 8 semanas en semanales; 10 000 remuestreos, semilla
   fija) para ICs de diferencias frente a benchmark; errores estándar HAC
   (Newey-West, lag = ventana de formación) para medias.
5. **Anti-sobreajuste**: PBO vía CSCV sobre la rejilla de la familia;
   Reality Check/SPA sobre todas las celdas vs benchmark — **en H1 el
   estadístico de SPA/RC es la mejora de ΔmaxDD vol-matched (criterio primario
   de multiplicidad, condición 3 del gate M0)**; en H2/H3 el estadístico es el
   retorno/Sharpe neto. DSR (Bailey–López de Prado): **n_trials = FAMILIA**
   (filas `kind=strategy` de esa familia en el ledger, con suelo = rejilla
   familiar: H2 = 6, H3 = 8; en H1 se computa con 24, informativo) y el
   **N global (38) se reporta junto al DSR por transparencia**. La **sd entre
   celdas se ESTIMA del ledger** (distribución empírica de los Sharpe de los
   trials de la familia), no se supone. Asimetría y curtosis empíricas.
   **Criterio de gate en H2 y H3; en H1 se computa y reporta, sin poder
   tumbar un PASA.** Nota de programa (v1.4): un PASA en cualquier familia se
   reportará con la nota de FWER a nivel programa ≤ ~3× el FWER de una familia
   (cota de unión sobre las 3 familias evaluadas de forma independiente;
   FWER familiar medido en §9.4b: 0.5 %).
6. **Costes**: todo neto de costes verificados; repetición obligatoria con ×2.
7. **Selección de candidata (v1.4, sellada antes de cualquier ejecución):**
   **UNA celda por familia y activo**, elegida por la **MEDIANA** (no la
   media) del criterio primario de la familia en las 45 trayectorias CPCV
   in-sample:
   - H1: mediana de ΔmaxDD vol-matched (más negativa = mejor); BTCUSDT y
     ETHUSDT pueden seleccionar celdas distintas.
   - H2: mediana del Sharpe neto anualizado vs universo equiponderado.
   - H3: mediana del Sharpe neto del carry diario (por activo).
   La mediana es más robusta que la media frente a folds extremos. La tabla
   completa de medianas de TODAS las celdas se publica en el informe M3a.
   Esas candidatas —y solo esas— pasan al holdout.
8. **Holdout**: evaluación única al final de M3 (puerta M3b). Prohibido
   ajustar nada tras verlo. Su resultado se reporta tal cual, gane o pierda.
9. **Protocolo M3 en dos puertas (v1.4, condición 4 del gate M2b):**
   - **M3a — SOLO in-sample:** ejecución completa de la rejilla (24 + 6 + 8 =
     38 trials `kind=strategy` en el ledger; diagnósticos/benchmarks con
     `kind` propio), permutaciones con **n_perm = 10 000**, Reality Check con
     **B ≥ 2 000**, CPCV(10,2), costes ×2. Se publican TODAS las celdas. Al
     terminar: **congelación de las celdas elegidas** (§7.7) en un fichero
     `reports/M3a_selected_cells.json` con commit + SHA256 + ancla OTS, y
     **ESPERA de la aprobación del orquestador**. Ningún acceso al holdout.
   - **M3b — evaluación única del holdout:** solo las celdas congeladas y
     aprobadas; desbloqueo con la clave del usuario (`QA_HOLDOUT_UNLOCK=1` +
     `QA_HOLDOUT_KEY`, queda auditado en `ledger/holdout_access.log`);
     resultado tal cual; veredictos finales PASA / NO PASA / INCONTRASTABLE
     según §8. Todo ajuste posterior está prohibido.

## 8. Criterios de éxito (v1.3 — diferenciados por familia; potencia en §9)

Veredictos por familia sobre la candidata seleccionada en §7.7.

### H1 (v1.3: gate primario = p-valor permutado vs vol-matched, nivel t* = 0.025)

| # | Criterio | Umbral |
|---|---|---|
| C1a | ΔmaxDD vs B&H **vol-matched** (in-sample completo): mejora (Δ < 0) **en BTC y en ETH**, con p-valor de permutación del vector de exposición | p < 0.05 por activo |
| C1b | Subperíodos: ΔmaxDD vol-matched < 0 (f propio del subperíodo) en ≥ 2 de 3 (SP1/SP2/SP3) | por activo (BTC y ETH) |
| C2' | Multiplicidad: **SPA/Reality Check** sobre el estadístico ΔmaxDD vol-matched, rejilla completa de 12 celdas por activo (DSR se computa y reporta, sin veto — condición 3 del gate M0) | p < 0.05 |
| C3 | PBO (CSCV de la familia) | < 0.20 |
| C4 | Costes ×2: ΔmaxDD vol-matched mantiene la mejora (Δ < 0) **y** ΔSharpe (≡ vs B&H crudo) ≥ −0.10 | ambos |
| C5 | Folds CPCV con ΔmaxDD vol-matched < 0 | ≥ 60 % |
| C7 | Holdout (una sola vez): signo de ΔmaxDD vol-matched coherente con in-sample | no exige significación (n = 1 año); signo opuesto en ambos activos → NO PASA |

- Co-métricas (Ulcer Index, Calmar, tiempo bajo el agua), benchmarks
  diagnóstico (exposure-matched, B&H crudo, caja) y ΔSharpe con IC bootstrap:
  se reportan SIEMPRE, no hacen gate.
- **Pre-declaración (v1.4, condición 5 del gate M2b):** para ΔSharpe en el
  rango plausible según literatura (0.1–0.3), la potencia del PIPELINE
  completo (compuesta ∧ RC sobre 24 candidatas) es **9.5–18.5 %** → el
  resultado ESPERADO de H1 es **INCONTRASTABLE**. Un rechazo del nulo sería un
  resultado extraordinario y exigiría la batería completa de gates.
- **Política de veredicto por potencia (enmienda 4 del gate M0b, ratificada
  en v1.3):** la potencia medida con habilidad plantada al nivel t\* (§9.4) es
  < 50 % para todo efecto ΔSharpe ≤ 0.5 (10-12 % / 18-20 % / 29-30 %). Por tanto, para H1 se pre-declara: si los tests no rechazan
  el nulo, el veredicto por defecto es **INCONTRASTABLE** (no NO PASA).
  **NO PASA** solo si (a) el p-valor adverso de permutación ≤ t* (la
  estrategia es significativamente PEOR que su propio timing aleatorizado), o
  (b) C7 con signo opuesto en ambos activos, o (c) C4/C5 fallan claramente
  con el efecto observado en dirección contraria.

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

## 9. Análisis de potencia (v1.3; detalle en `reports/M0_power_analysis.md/.json`)

Script: `scripts/power_analysis.py` v1.3 (semilla 20261026; α una cola 5 %,
potencia objetivo 80 %, K = 2.4866). Tests de identidad/calibración:
`tests/unit/test_benchmark_identities.py`, `tests/synthetic/test_null_calibration.py`.
Evidencia de calibración del nulo: `reports/M0_null_scheme_comparison.md`,
`reports/M0_null_threshold_calibration.md`, `reports/M0_h1_fwer.md`.

**Retirado (v1.1 → v1.2, confirmado en v1.3):** el titular "H1 probablemente
NO PASA" y el riesgo R1 de M0b siguen RETIRADOS (benchmark sesgado por Jensen
y mundos sin habilidad). La política de veredicto de H1 es la de §8.

### 9.1 Analítico (sin cambios desde v1.2)

1. **ΔSharpe no pareado:** MDE = 1.94 (3.3 años) / **1.23** (8.2 años);
   ΔSharpe 0.5 exigiría ~50 años. Pareado (MC): MDE ≈ 0.67.
2. **DSR ≥ 0.95** (gate de H2/H3): n_trials = 38 y 8.2 años ⇒ Sharpe
   observado ≈ 1.66–2.22.
3. **H2** (n ≈ 340 semanas desde 2019-04, confirmado por M1): MDE ≈ 0.47–0.79
   %/sem → **INCONTRASTABLE para spreads típicos**; declarado.
4. **H3:** n_BTC = 2 237 d, n_ETH = 2 169 d (M1) → MDE ≈ 1.0–2.1 %/año;
   **contrastable** ≥ ~2-4 %/año. Regla P4: MDE_ETH/MDE_BTC = 1.015 ≪ 2 →
   ambos contrastables.
5. **WR:** 45 % vs 40 % exige ~600 trades → ningún criterio WR.

### 9.2 H1 vs B&H crudo (diagnóstico)

Mejora de 35-48 pp con potencia 77-99 % incluso bajo GBM sin habilidad: es
efecto de exposición. No es criterio.

### 9.3 Calibración del nulo y elección de esquema (v1.3, 5000 sims por esquema)

| Esquema | FPR a p<0.05 | FPR regla compuesta | Potencia (ΔSharpe 0.3) | Decisión |
|---|---|---|---|---|
| Bloques circulares 20 d | 6.68 % | 6.14 % | 26.1 % | **ADOPTADO con t\* = 0.025** (FPR 4.36 %) |
| Rotación circular completa | 2.78 % | 2.58 % | 6.7 % | Descartado: sobre-conservador y casi sin potencia |

Con t\* = 0.025: FPR de la compuesta bajo el nulo = 2.8 % (500 sims,
`reports/M0_power_analysis.md` S3); p medio del nulo = 0.52 (uniforme);
E[ΔmaxDD vol-matched] = +4.4 pp (sesgo residual de mezcla de escalas: por eso
el punto NO decide; el p-valor permutado sí — aclarado en C1). Identidades
verificadas por tests: exposición constante ⇒ Δ = 0 exacto; signo Δ>0 = peor.

### 9.4 Habilidad plantada (drift AR(1) φ=0.995 calibrado; potencia al nivel t*)

| ΔSharpe verdadero | vent. 100: pot. compuesta | vent. 200: pot. compuesta | E[ΔmaxDD vm] |
|---|---|---|---|
| ≈ 0.11-0.14 | 10.5 % | 11.5 % | −7 pp |
| ≈ 0.28-0.34 | 19.0 % | 17.8 % | −13/−14 pp |
| ≈ 0.50-0.57 | 29.5 % | 28.5 % | −21 pp |

**Potencia < 50 % para TODO efecto ≤ 0.5** ⇒ política pre-declarada (§8-H1):
si el test no rechaza, el veredicto es **INCONTRASTABLE**, no NO PASA.

### 9.4b FWER del pipeline H1 completo (condición 4 del gate M1)

200 mundos GBM correlacionados (ρ_BTC,ETH = 0.8), 24 candidatas (12 celdas × 2
activos), umbral t\*=0.025, n_perm=99, RC de White (B=200, bloque 20 d):

| Evento bajo el nulo | Probabilidad |
|---|---|
| ALGUNA candidata pasa la regla compuesta | **28.5 %** (por activo: BTC 19.5 %, ETH 16.5 %) |
| RC/SPA rechaza (p<0.05) | 0.5 % |
| **Pipeline completo (compuesta Y RC)** | **0.5 %** |

Lectura: la compuesta por candidata NO controla la multiplicidad familiar
(28.5 % con 24 candidatas); el gate C2' (RC/SPA) la reduce a ~0.5 % — el
pipeline conjunto está por debajo del 5 % nominal. Los gates C3-C5 sólo pueden
reducirlo más. (Con 10 000 permutaciones reales la resolución de t* mejora;
n_perm=99 en la simulación es una aproximación documentada.)

### 9.5 Banda de rebalanceo (grados de libertad, §4)

Bandas simuladas {0, 2, 5, 10, 20} pp: sangría 1.06/0.99/0.92/0.85/0.80 %/año;
10 pp = rodilla. Tabla completa en S6.

### 9.6 Higiene de datos y adjudicación (v1.3)

Enumeración completa in-sample de |log-ret diario| > 5: **5 eventos**
(LUNA 2022-05-31 y 2022-05-12, VEN 2018-10-19, COCOS 2021-01-23, SUN
2021-06-18). Adjudicados con anuncio oficial (URL+fecha) SIN mirar P&L:
4 corporate_action (rupturas por swap/redenominación/relistado) y 1 real_move
(colapso Terra 2022-05-12, conservado íntegro). Efecto sobre el ranking PIT:
las 4 exclusiones de 30 días resultaron **no-op para el top-40** (los símbolos
ya quedaban fuera por huecos de cotización/n_days<15 o volumen insuficiente en
la ventana); la maquinaria queda sellada y su efecto operativo será sobre las
ventanas de formación de H2 en M3. Tabla: `config/adjudications.csv`.

### 9.7 Consecuencia pre-registrada

Con 38 ensayos, t\*=0.025 y 8.2 años, el laboratorio solo confirma efectos
grandes de timing; todo efecto menor se reportará INCONTRASTABLE con su MDE.
El FWER del pipeline completo está medido y controlado (≤0.5 % bajo el nulo).

## 10. Sellado del preregistro (estado v1.4)

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
- **v1.2:** tag `prereg-v1.2` (anotado y firmado SSH) sobre el commit que
  congela este documento + `config/hypotheses.yaml` v1.2, con SHA256 en el
  mensaje + anclaje OTS (`normative_hashes_v1.2.txt`). Corrección del defecto
  1 del gate M0b: benchmark vol-matched + criterio permutado + potencia con
  habilidad plantada.
- **v1.3:** tag `prereg-v1.3` (anotado y firmado SSH) sobre el commit que
  congela este documento + `config/hypotheses.yaml` v1.3 +
  `config/universe.yaml` + `config/adjudications.csv` (los CUATRO hashes en
  el mensaje del tag) + anclaje OTS (`normative_hashes_v1.3.txt`).
- **v1.4:** tag `prereg-v1.4` (anotado y firmado SSH) sobre el commit que
  congela este documento + `config/hypotheses.yaml` v1.4 +
  `config/universe.yaml` + `config/adjudications.csv` (4 hashes en el mensaje
  del tag) + anclaje OTS (`normative_hashes_v1.4.txt`). Solo texto: sin
  cambios de rejilla, sizing ni umbrales numéricos.

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
| 1.2 | 2026-10-26 | Corrección del defecto 1 del gate M0b (benchmark exposure-matched sesgado por Jensen): benchmark primario H1 = B&H vol-matched; exposure-matched degradado a diagnóstico; criterio y subperíodos basados en permutación del vector de exposición; tests de identidad/calibración del nulo como requisito previo; potencia recalculada con drift AR(1) plantado (ΔSharpe ∈ {0.1,0.3,0.5}) → potencia <50 % ⇒ política de veredicto INCONTRASTABLE por defecto en H1; bandas simuladas {0,2,5,10,20} pp documentadas en §4/§9.5; retirado el titular "H1 probablemente NO PASA" (M0b §9.3/R1). Sin cambios en rejilla ni sizing. | 38 |
| 1.3 | 2026-10-26 | Correcciones pre-M3 del gate M1: (1) higiene mark-only + tabla de adjudicación sellada (`config/adjudications.csv`, 5 eventos, 4 corporate_action con anuncio oficial, 1 real_move conservado íntegro) + convención de deslistado (último precio observado); (2) auditoría de exclusiones del universo (68 pares excluidos en ingesta, 0 colados en pool/PIT); (3) nivel crítico del test de permutación calibrado en nulo sintético: t* = 0.025 (5000 sims; FPR 4.36 %; rotación completa descartada: FPR 2.8 %/potencia 6.8 %); el estadístico de decisión de C1 es el p-valor permutado, no el ΔmaxDD puntual; (4) FWER del pipeline H1 simulado (24 candidatas: compuesta-any 28.5 %, pipeline con RC 0.5 %); (5) cross-check de funding ampliado (14 meses BTC/ETH 2020-2025, 1272 registros, 0 discrepancias); (6) prueba de regeneración byte-idéntica en directorio limpio. Sin cambios en rejilla ni sizing. | 38 |
| 1.4 | 2026-10-27 | Añadidos 1-5 del gate M2b (solo texto, pre-datos): (1) validación multi-mundo de t* (FPR ∈ [1.5 %, 4.6 %], conservador bajo regímenes de vol; potencia = cota superior); (2) §7.5: n_trials del DSR = FAMILIA (H3=8, H2=6, H1=24 informativo) + N global 38 reportado; sd entre celdas ESTIMADA del ledger; nota de FWER de programa (≤ ~3× familiar) en todo PASA; (3) §7.7: selección = UNA celda por familia y activo por MEDIANA CPCV del criterio primario (H1: ΔmaxDD vol-matched; H2/H3: Sharpe neto), sellada antes de ejecutar; (4) §7.9: protocolo M3 en dos puertas (M3a in-sample, n_perm=10 000, RC B≥2 000, congelación commit/hash/OTS + aprobación; M3b holdout único con clave del usuario); (5) §8-H1: pre-declaración de veredicto esperado INCONTRASTABLE (potencia pipeline 9.5-18.5 % para ΔSharpe 0.1-0.3). | 38 |
