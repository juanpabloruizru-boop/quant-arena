# PRERREGISTRO v1.0 — QUANT-ARENA v2

**Fecha:** 2026-10-26 (UTC) · **Estado:** registrado, sellado con tag `prereg-v1`
**Espejo máquina:** `config/hypotheses.yaml` v1.0 (este documento manda; si
divergen, es un bug y se corrige el YAML).

> Regla de oro: ninguna regla se implementa ni ejecuta si no está en este
> documento. Cambiar algo aquí **después** de ver resultados invalida la
> ejecución: se crea v1.1 con fecha, motivo y `n_trials +=` celdas nuevas.

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

## 4. Universo point-in-time (ver ADR-002 y `config/universe.yaml`)

- Ranking mensual del top-N (N∈{10,20}) por volumen quote USDT (media diaria
  de los 30 días previos), usando **solo** datos anteriores al instante de
  ranking. Exclusión de estables, wrapped, tokens apalancados. Mínimo 60 días
  listado. Se incluyen símbolos deslistados mientras estuvieran en estado
  TRADING en su momento (los dumps de `data.binance.vision` los conservan:
  verificado FTTUSDT y LUNABTC el 2026-10-26).
- Sesgos no eliminables (se declaran en todo informe): solo existe lo que
  Binance listó (supervivencia del venue); el ranking usa el propio venue.

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
- Rejilla: variante ∈ {sma, ret} × ventana ∈ {50, 100, 200} × σ_obj ∈ {15 %, 25 %}
  = **12 celdas**; cada celda se evalúa en BTCUSDT y ETHUSDT por separado →
  **24 trials**.
- *Decisión de interpretación:* el enunciado heredado "cierre > SMA(n) **o**
  retorno de L días > 0; n, L ∈ {50,100,200}" se registra como **dos variantes
  de señal disjuntas** (12 celdas), no como señal disyuntiva con producto
  cruzado n×L (18 celdas). Motivo: la disyunción cruzada prueba híbridos que
  nadie operaría e infla n_trials sin hipótesis detrás. **Pendiente de
  ratificación por el orquestador** (pregunta P1 del informe M0). Si se
  prefiere el producto cruzado: v1.1 y n_trials += 12.
- **Expectativa (como exige el prompt): reducción de drawdown con Sharpe ≥
  B&H; NO más retorno absoluto.**

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
   Calmar, expectancy en R, IC (cuando aplique señal continua).
3. **Incertidumbre**: bootstrap por bloques estacionario (bloque esperado 20 d
   en series diarias; 8 semanas en semanales; 10 000 remuestreos, semilla
   fija) para ICs de diferencias frente a benchmark; errores estándar HAC
   (Newey-West, lag = ventana de formación) para medias.
4. **Anti-sobreajuste**: DSR (Bailey–López de Prado) con n_trials del ledger,
   asimetría y curtosis empíricas; PBO vía CSCV sobre la rejilla de la familia;
   Reality Check/SPA sobre todas las celdas vs benchmark.
5. **Costes**: todo neto de costes verificados; repetición obligatoria con ×2.
6. **Selección de candidata**: por familia, la celda con mayor Sharpe neto
   medio en las 45 trayectorias CPCV **in-sample** (regla fijada ahora, antes
   de ver nada). Esa candidata —y solo esa— pasa al holdout.
7. **Holdout**: evaluación única al final de M3. Prohibido ajustar nada tras
   verlo. Su resultado se reporta tal cual, gane o pierda.

## 8. Criterios de éxito (ajustados por potencia — ver §9)

Una celdа candidata obtiene el veredicto **PASA** solo si cumple TODO:

| # | Criterio | Umbral |
|---|---|---|
| C1 | Métrica primaria de la familia (§6) con IC bootstrap 95 % favorable que excluya el 0 | H1: ΔmaxDD < 0 vs B&H; H2: ΔSharpe neto > 0 vs universo EW; H3: media diaria neta > 0 (t-HAC) |
| C2 | DSR con n_trials real del ledger | > 0.95 |
| C3 | PBO (CSCV de la familia) | < 0.20 |
| C4 | Neto positivo con costes ×2 | > 0 |
| C5 | Fracción de folds CPCV en positivo (métrica primaria) | ≥ 60 % |
| C6 | Reality Check/SPA de la familia vs benchmark | p < 0.05 |
| C7 | Holdout (una sola vez): signo de la métrica primaria coherente con in-sample | no requiere significación (n=1 año), pero un signo opuesto degrada a NO PASA |

- **H1, criterio secundario de Sharpe:** se reporta ΔSharpe anualizado vs B&H
  con IC bootstrap. Por potencia (§9), un IC que excluya 0 solo será posible
  para mejoras ≥ ~0.7; entre 0 y ~0.7 se reporta "compatible con no-inferioridad,
  sin potencia para concluir". El PASA de H1 NO exige Sharpe significativamente
  mayor: exige ΔmaxDD significativo **y** ΔSharpe puntual ≥ −0.10 (no-inferioridad
  práctica pre-registrada) — formulación honesta de "Sharpe ≥ B&H" dado que el
  test exacto de Sharpe≥B&H es incontrastable para efectos pequeños (§9).
- **NO PASA**: no se cumple C1, o C2–C6 fallan con potencia suficiente para el
  efecto observado (≥ 50 % según §9).
- **INCONTRASTABLE**: el efecto observado es menor que el MDE del horizonte
  (§9) con potencia < 50 %. El boletín (M5) no emitirá recomendación; se
  reportará `SIN VENTAJA DEMOSTRADA (n=…, IC=…)`.
- Regla anti-jardinería: veredictos por familia, todas las celdas publicadas
  siempre (tabla completa + distribución), ninguna re-ejecución "para
  comprobar" tras el holdout.

## 9. Análisis de potencia (resumen; detalle en `reports/M0_power_analysis.md/.json`)

Script: `scripts/power_analysis.py` (semilla 20261026; α una cola 5 %, potencia
objetivo 80 %, K = 2.4866). Cifras clave:

1. **Diferencia de Sharpe (no pareada):** MDE = 1.94 con 3.3 años; **1.23 con
   8.2 años**. Detectar ΔSharpe = 0.5 exigiría ~50 años de datos; Δ = 0.3, ~137
   años. Monte Carlo pareado de H1 (mismo camino, sd(ΔSharpe) ≈ 0.27 a 8.2
   años): MDE pareado ≈ 0.67 (potencia 80 %) o ≈ 0.44 (nivel 5 %).
   → **El test "Sharpe ≥ B&H" es incontrastable en el horizonte para mejoras
   pequeñas (< ~0.5).** Por eso C1 de H1 es el drawdown y el Sharpe entra como
   no-inferioridad práctica.
2. **Reducción de max drawdown (H1, MC pareado):** sd(ΔmaxDD) ≈ 13 pp a 8.2
   años → mejoras detectables al 5 % desde ~21 pp y con potencia 80 % desde
   ~32 pp. Las mejoras típicas simuladas del montaje long/flat+vol target son
   de 35–42 pp → **potencia estimada 77–93 %**. C1 de H1 es contrastable para
   efectos grandes (que son los que la regla promete).
3. **DSR ≥ 0.95:** con n_trials = 38 y 8.2 años, exige Sharpe observado
   ≈ **1.66–2.22** según dispersión entre celdas (sd 0.5–0.75) y colas. Con
   3.3 años: ≈ 2.0–2.6. El listón es alto a propósito: solo efectos grandes y
   estables pasan.
4. **H2 (spread semanal, n ≈ 354 semanas):** MDE ≈ 0.46–0.77 %/sem
   (σ 3–5 %/sem, ρ 0–0.15) ≈ 24–40 % anualizado. Detectar 0.2 %/sem exigiría
   ~64 años. → **H2 es incontrastable en el horizonte para spreads típicos
   (10–20 %/año); solo un spread bruto extraordinario (> ~25–30 %/año) sería
   detectable.** Se ejecutará igual (rejilla congelada) y, si el efecto es
   menor que el MDE, el veredicto será INCONTRASTABLE, no NO PASA.
5. **H3 (carry diario, n ≈ 2 237 días):** MDE ≈ 1.0–4.2 %/año según σ diaria
   (5–20 pb) y ρ. Un carry neto de 2 %/año es marginal (potencia ~50 % a
   6.1 años); ≥ 4 %/año es claramente contrastable (potencia > 80 % con
   ~1.7 años de datos). → **H3 es la única familia con potencia suficiente
   para efectos plausibles** (el carry cripto histórico documentado es mayor).
6. **Tasas de acierto:** discriminar WR 45 % vs 40 % exige **n ≈ 600 trades**
   (42 % vs 40 %: ~3 729). H1 genera O(decenas) de cambios de posición en 8
   años → ningún criterio basado en WR (lección heredada: n=30 no discrimina).
7. **Consecuencia pre-registrada:** con 38 ensayos y estos horizontes, el
   laboratorio solo puede confirmar **efectos grandes**. Todo lo demás se
   reportará como INCONTRASTABLE con su MDE explícito. Esto no es un fallo del
   diseño: es la honestidad que exige el principio 9.

## 10. Sellado del preregistro

- Tag git anotado `prereg-v1` sobre el commit que congela este documento +
  `config/hypotheses.yaml`. Entorno sin GPG → el tag no lleva firma criptográfica
  (desviación documentada, ver ADR-004); el mensaje del tag incluye el SHA256
  de ambos ficheros.
- **Sello externo recomendado (pendiente de decisión del usuario/orquestador):**
  registro del PDF/markdown en **OSF** (osf.io, gratuito, timestamp de tercero,
  inmutable) o, alternativamente, OpenTimestamps. Razón: un tag git local es
  autoatestiguado — quien posee el repo puede reescribir la historia y
  re-fecharla; un sello de un tercero con reloj independiente es la única
  prueba de que la rejilla existía **antes** de ver resultados.

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
| 1.0 | 2026-10-26 | Registro inicial | 38 |
