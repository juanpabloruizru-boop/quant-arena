# M3b · Evaluación ÚNICA del holdout sellado (2025-10-26 → 2026-10-25) · 2026-10-28 · freeze `m3a-freeze` (f834bfd) · resultados en HEAD

## Resumen en 5 líneas

1. **Apertura única ejecutada y auditada**: el holdout se descifró UNA vez por fichero (spot/futures/funding → `holdout_access.log` pasó de 2 a 5 entradas, sha256 verificados contra el sellado, git SHA registrado); las 5 celdas congeladas de `m3a-freeze` se evaluaron en la misma corrida en memoria (incluido el apéndice de capital), sin ninguna re-lectura posterior; los 5 ensayos quedaron registrados como `kind=holdout_evaluation` y **n_trials de estrategia sigue en 24/6/8**.
2. **Veredictos FINALES: H1 INCONTRASTABLE · H2 INCONTRASTABLE · H3 PASA (BTC) / NO_PASA (ETH) → PASA_PARCIAL.** Contexto del año holdout: mercado bajista fuerte (B&H BTC -30.0%, ETH -44.0%).
3. **H1** (descriptivo, no gate): la regla de tendencia esquivó la caída — BTC +9.98% neto vs B&H -30.03% (ΔmaxDD vs vol-matched -9.9 pp, MISMO signo que in-sample: C7 coherente); ETH +18.04% vs -43.97% (Δvm -17.8 pp, p permutación descriptivo 0.0077). Un año no convierte INCONTRASTABLE en PASA: la política pre-registrada se aplica como está escrita.
4. **H3**: BTC +0.949% neto (+0.26 pb/día, 6 episodios, 36 % del tiempo, MDD 0.38%) → signo coherente con IS ⇒ **PASA** (con aviso: costes ×2 lo dejan en ≈0 — año de funding bajo, señal casi siempre apagada). ETH -1.351% (-0.37 pb/día, 12 episodios, costes > funding capturado) → signo opuesto a IS ⇒ **NO_PASA** por C7.
5. **Corrección transparente**: la primera versión de la función mecánica de veredictos invertía el flag de signo en C7/H1; se detectó al contrastar el veredicto con las métricas ANTES de publicar, se corrigió con test unitario y se recalcularon los veredictos como función pura de las métricas ya extraídas (el holdout NO se releyó; el log de acceso no creció). Los veredictos iniciales erróneos quedan guardados en `M3b_results.json` (`verdicts_previos_con_bug`) como evidencia.

## Auditoría de la apertura única

| Comprobación | Valor |
|---|---|
| Entradas en `holdout_access.log` antes / después | 2 / **5** (3 descifrados: spot, futures, funding) |
| sha256 de plaintext vs `holdout_seal.log` | verificados por el guard en cada descifrado |
| Propósito registrado | "M3b evaluación única oficial (autorizada gate M3a, 2026-10-28)" |
| git SHA registrado en las 3 entradas | 95cd917… |
| Re-lecturas posteriores | **0** (la corrección de veredictos no toca los datos) |
| Trials registrados | 5 × `kind=holdout_evaluation` (no computan para n_trials) |
| n_trials strategy por familia tras M3b | H1 24 · H2 6 · H3 8 (sin cambios) |

## Resultados completos (5 celdas congeladas)

### H1 · sma50_s25 (long/flat SMA50 + vol target 25 %, banda 10 pp)

| Métrica | BTCUSDT | ETHUSDT |
|---|---|---|
| Retorno neto del año | **9.98%** | **18.04%** |
| B&H misma ventana (close-to-close) | -28.21% | -41.07% |
| B&H del activo en el holdout | -30.03% | -43.97% |
| Max drawdown | 13.7% | 10.7% |
| ΔmaxDD vs vol-matched (C7: signo) | **-9.9 pp** (IS: −4.4) ✓ coherente | **-17.8 pp** (IS: −20.2) ✓ coherente |
| ΔmaxDD vs B&H crudo | -35.1 pp | -51.6 pp |
| ΔSharpe vs B&H | +1.13 | +1.39 |
| p permutación (descriptivo, n=1 año) | 0.1295 | 0.0077 |
| Trades / exposición media | 11 / 35% | 4 / 23% |
| Costes ×2: Δvm / retorno | -8.7 pp / 7.80% | -17.6 pp / 17.13% |
| Posición el 2026-10-25 | 0% (objetivo 0%) | 0% (objetivo 0%) |
| Rechazos (mínimos / liquidez) | 0 / 0 | 0 / 0 |

**Veredicto final H1: INCONTRASTABLE** — C7 no degrada (signo coherente en ambos activos); la política de potencia pre-declarada (v1.4 §8) mantiene INCONTRASTABLE: un año descriptivamente bueno no es evidencia estadística. El forward (M4) ampliará la muestra.

### H2 · L26_N10 (momentum transversal 26 semanas, top-10 PIT, tercil superior)

| Métrica | Valor |
|---|---|
| Retorno neto del año (52 semanas) | **-38.09%** |
| Benchmark universo EW | -45.11% |
| ΔSharpe vs EW | +0.36 (Sharpe -0.5002 vs -0.8616) |
| Max drawdown | 49.3% |
| Win rate semanal | 38% |
| Cesta final (2026-10-19) | NEARUSDT, ZECUSDT, UNIUSDT, SOLUSDT |

**Veredicto final H2: INCONTRASTABLE** — el año holdout fue descriptivamente favorable en términos RELATIVOS (batió a su universo EW por ~7 pp en un año de −45 %) pero la familia carecía de potencia in-sample y n=1 año no concluye nada. Trazabilidad del preregistro cerrada.

### H3 · w30_t5 (carry delta-neutral, funding MA 30d > 5 % anual)

| Métrica | BTCUSDT | ETHUSDT |
|---|---|---|
| Retorno neto del año | **0.949%** | **-1.351%** |
| Media diaria neta | +0.26 pb | -0.37 pb |
| HAC t / p una cola | 1.1894 / 0.11715 | -1.6185 / 0.05278 |
| Max drawdown | 0.38% | 1.54% |
| % tiempo dentro / episodios | 3644% / 6 | 1644% / 12 |
| Funding total del periodo (referencia) | 3.42% | 2.52% |
| Costes ×2 (media pb/día) | -0.02 | -0.93 |
| Señal el 2026-10-25 | FLAT (funding MA 3.78% < 5 %) | FLAT (funding MA 3.85% < 5 %) |

**Veredicto final H3: BTCUSDT = PASA · ETHUSDT = NO_PASA · familia = PASA_PARCIAL**

- BTC: signo coherente con IS (+) ⇒ PASA según C7 (que no exige significación con n=1 año). **Aviso honesto**: con costes ×2 la media queda en ≈0 pb/día — el año holdout tuvo funding débil (MA 3-4 %, señal activa solo 36 % del tiempo); el PASA es regulatorio (signo), no una afirmación de rentabilidad robusta en cualquier régimen.
- ETH: signo opuesto a IS (−0.37 pb/día) ⇒ NO_PASA por C7. Causa visible: 12 episodios (cruces frecuentes del umbral) cuyos costes (~32 pb por episodio, ambas piernas taker) superaron al funding capturado; el funding total de ETH del período fue positivo (+2.5 %) pero la regla solo estuvo dentro 16 % del tiempo.
- Nota de programa (v1.4 §7.5): todo PASA se reporta con FWER de programa ≤ ~3× el familiar.

## Tabla ejecutiva para JP (lenguaje claro) — el último año (oct-2025 → oct-2026) vs el histórico in-sample

| Regla | Año holdout: retorno neto | Año: máx. caída | Año: ops | Año: vs comprar y aguantar | Histórico IS 2017-2025 (CAGR / MDD) | ¿Qué hace EXACTAMENTE el 2026-10-25? | Estado final |
|---|---|---|---|---|---|---|---|
| H1 tendencia BTC (sma50_s25) | **9.98%** | 13.7% | 11 | B&H -30.0% → **+40.0% de diferencia** | 31.8 % / 33.9 % | **FLAT (0 %)**: precio bajo SMA50 | SIN VENTAJA DEMOSTRADA (INCONTRASTABLE) |
| H1 tendencia ETH (sma50_s25) | **18.04%** | 10.7% | 4 | B&H -44.0% → diferencia 62% | 27.2 % / 24.7 % | **FLAT (0 %)**: precio bajo SMA50 | SIN VENTAJA DEMOSTRADA (INCONTRASTABLE) |
| H2 momentum (L26_N10) | **-38.09%** | 49.3% | ~9 cambios/año | universo EW -45.11% (batió a su universo, perdió en absoluto) | 6.0 % / 90.4 % | Cesta: NEARUSDT, ZECUSDT, UNIUSDT, SOLUSDT (equiponderada) | SIN VENTAJA DEMOSTRADA (INCONTRASTABLE) |
| H3 carry BTC (w30_t5) | **0.95%** | 0.38% | 6 entradas | vs B&H BTC -30.0%: el carry no depende de la dirección | 11.2 % / 2.1 % | **FLAT**: funding MA 3.78% < umbral 5 % | **PASA** (BTC); riesgo: con costes ×2 ≈ 0 |
| H3 carry ETH (w30_t5) | **-1.35%** | 1.54% | 12 entradas | — | 14.4 % / 1.7 % | **FLAT**: funding MA 3.85% < umbral 5 % | **NO PASA** (costes > funding) |

Lectura para JP: en un año en que comprar y aguantar perdió 30 % (BTC) y 44 % (ETH), las reglas defensivas brillaron en RELATIVA (H1 esquivó la caída), pero el laboratorio solo otorga PASA a lo que sobrevive a todos los filtros: el carry de BTC, y con el aviso de que en regímenes de funding bajo (como este) su edge neto es frágil a costes. Ninguna fila es una recomendación de inversión; M4 (paper forward) es el siguiente examen.

## Apéndice pre-registrado · escalado de capital (mismas celdas, año holdout)

| Capital | H1 BTC ret/MDD/trades/rechazos | H3 BTC ret/eps | H2 ret/MDD |
|---|---|---|---|
| $100 | 9.98% / 14% / 11 / min:0 liq:0 | 0.95% / 6 | -38.05% / 49% |
| $500 | 9.98% / 14% / 11 / min:0 liq:0 | 0.95% / 6 | -38.05% / 49% |
| $1000 | 9.98% / 14% / 11 / min:0 liq:0 | 0.95% / 6 | -38.05% / 49% |
| $10000 | 9.98% / 14% / 11 / min:0 liq:0 | 0.95% / 6 | -38.09% / 49% |

Notas de factibilidad (mínimos verificados en vivo 2026-10-26/27): spot minNotional 5 USDT; perp BTCUSDT minNotional 50 USDT y minQty 0.001 BTC (≈90-110 USDT a precios 2025-26). Con 100 USDT: H1 opera sin rechazos (band trades ≥10 USDT); H3 queda dentro de mínimos PERO la pierna perp solo admite múltiplos de ~0.001 BTC → granularidad ~90 % del capital (el motor no simula minQty: caveat declarado); H2 reparte 10 USDT/nombre (≥5 ✓). El motor solo impone mínimos en run_positions (H1); en H2/H3 el análisis de mínimos es la nota anterior. El claim heredado 'comisiones consumen 40-75 % del objetivo con <100 USD' no se reproduce en estas celdas de baja frecuencia (H1: ~11 ops/año): el coste anualizado a $100 es ~0.4-0.7 %/año para H1 — la diferencia con el claim heredado es la FRECUENCIA de operación.

## Limitaciones

- n = 1 año (365 días) y un régimen concreto (bajista, funding débil): los veredictos C7 son de signo, no de magnitud; nada de lo anterior estima rendimientos futuros.
- H1 'INCONTRASTABLE con año descriptivo bueno' puede leerse como oportunidad perdida: es el precio pre-aceptado de la honestidad estadística (potencia 9.5-18.5 % declarada en v1.4).
- H3 BTC PASA con stress ×2 ≈ 0: el margen de seguridad de costes en el año holdout fue mínimo; el forward M4 lo vigilará con la regla de día-30/90.
- El ETH H3 NO_PASA no invalida el carry como fenómeno (funding ETH del período fue +2.5 %): invalida ESTA parametrización (umbral 5 % con 12 cruces) net de costes en este año.
- Corrección del bug de veredicto documentada arriba; el incidente no afectó a los datos ni a las métricas, solo a la regla mecánica de combinación de signos.

## Implicaciones para M4 (forward paper)

- Se implementan las 5 reglas congeladas en forward (ADR-007: GitHub Actions, hash-chain en repo): **H3-BTC con etiqueta 'validada in-sample + holdout (signo)'** y las demás como **'informativas, sin ventaja demostrada'** (H1/H2) o **'no pasa'** (H3-ETH). El boletín (M5) mostrará `SIN VENTAJA DEMOSTRADA (n=…, IC=…)` donde corresponda.
- Reglas de decisión M4 pre-registradas: día 30 solo calidad/bugs; evaluación estadística al n de potencia; cierre a día 90.

## Qué aprendimos (lenguaje llano)

- **El sobre se abrió una sola vez, y se notó**: 3 descifrados auditados, cero re-lecturas; la disciplina del holdout es lo que permite que un 'PASA' valga algo.
- **Un buen año no es prueba**: H1 esquivó una caída del 30-44 % y aun así su veredicto sigue siendo 'no contrastable'. Suena ingrato; es exactamente lo que firmamos en el preregistro.
- **El carry pasa, pero con la lengua fuera**: BTC gana el examen por signo con +0.26 pb/día; con comisiones dobles se queda en cero. En trading, 'pasar' por poco es información valiosa, no victoria.
- **Los bugs se cazan leyendo, no ejecutando**: el veredicto erróneo de H1 se detectó porque no cuadraba con sus propias métricas; corregir la función (no los datos) y dejar rastro es la forma honesta de arreglarlo.

## Solicitud: GATE APROBADO M3b (cierre de M3)
