# ADR-005 · Criterio primario de H1: B&H matched-exposure + permutación de timing

**Fecha:** 2026-10-26 (M0b) · **Estado:** aceptado — mandato del orquestador
(condición 1-3 del gate M0), diseño detallado y análisis de potencia propios.

## Contexto

En v1.0 el criterio primario de H1 era ΔmaxDD frente al B&H **crudo**. El
análisis de potencia mostró que ese test se pasa con potencia 77–99 % en TODOS
los mundos sintéticos, incluido GBM puro sin habilidad alguna: cualquier
estrategia que pase menos tiempo en el mercado tiene, casi por construcción,
menos drawdown que el activo crudo. Es decir, el test v1.0 medía sobre todo
"estar menos expuesto", no "elegir mejor los momentos".

## Decisión (v1.1)

1. **Benchmark primario de H1 = B&H con la misma exposición media** que la
   estrategia en cada periodo de evaluación: `r_bh_m[t] = ē · r[t]`. Aísla el
   *timing* (dónde se está expuesto) del *nivel* (cuánto se está expuesto).
2. **Nulo de permutación de timing**: misma serie de posiciones barajada en
   bloques circulares de 20 días (10 000 permutaciones, semilla fija). Si la
   estrategia no elige mejor los momentos que el azar con igual exposición, el
   p-valor será grande. Las permutaciones NO cuentan como trials (son parte del
   estadístico de una candidata).
3. **Regla de subperíodos** (2017-19 / 2020-22 / 2023-25): mejora exigida en
   el in-sample completo y en ≥2 de 3 subperíodos, en BTC y en ETH. Robustez
   temporal y entre activos, no un único número agregado.
4. **DSR deja de ser gate de H1** (sigue siendo gate de H3 y criterio completo
   de H2); la multiplicidad de H1 se controla con **SPA/Reality Check sobre el
   estadístico ΔmaxDD matched** en la rejilla de 12 celdas por activo. Motivo
   (condición 3 del orquestador): el DSR deflacta un Sharpe seleccionado; el
   claim de H1 es un drawdown relativo, y SPA/RC es el test de multiplicidad
   nativo para "la mejor de N reglas vs benchmark".
5. **Banda de rebalanceo de 10 pp** (los flips long↔flat siempre operan):
   hallazgo PRE-datos del propio análisis de potencia — sin banda, el vol
   targeting rearma la posición a diario y la sangría de costes empeora
   ΔmaxDD en ~1 pp de media. Parámetro de diseño congelado (no es dimensión de
   rejilla ni se optimizará con datos reales).

## Consecuencia honesta (pre-registrada en PREREGISTRO §9.3)

Bajo los tres DGPs alternativos simulados (vol MS, vol MS + crashes de
Poisson, deriva MS), el mecanismo H1 tal como está especificado NO mejora el
drawdown matched-exposure en media (E[ΔmaxDD_m] ≈ +6 a +10 pp; potencia del
test ≈ 1–2 %; regla compuesta ≈ 7–19 %). H1 solo pasará si el mercado real
tiene estructura anticipatoria de crashes superior a la sintética. Aceptamos
y declaramos de antemano que el resultado más probable de H1 es NO PASA o
INCONTRASTABLE — que es un resultado útil según la misión del proyecto.

## Alternativas descartadas

- Mantener B&H crudo como primario: premia la reducción de exposición, no el
  skill (motivo del mandato).
- Benchmark de volatilidad objetivo sobre B&H: empareja σ pero no exposición
  media; menos directo que el matched para el claim de H1.
- DSR como gate de H1: deflacta Sharpe, no estadísticos de drawdown; se usa
  donde el claim es retorno riesgo-ajustado (H2/H3).
- Rebalanceo diario sin banda: costes dominantes (ver §5).
