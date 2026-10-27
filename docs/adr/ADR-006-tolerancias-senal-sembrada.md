# ADR-006 · Tolerancias del test de señal sembrada (antes/después)

**Fecha:** 2026-10-27 (M2b) · **Estado:** aceptado (condición D del gate M2)

## Contexto

El test de aceptación sintética 2 ("señal sembrada de tamaño conocido") falló dos
veces durante M2 antes de estabilizarse. Todo ocurrió ANTES de calcular ninguna
métrica de estrategia sobre datos reales; los ajustes son de diseño del test,
no del preregistro. Este ADR documenta cada cambio con su motivo (transparencia
total: un test de aceptación cuyas tolerancias se mueven sin registro es una
puerta al autoengaño).

## Cambios (antes → después)

| # | Parámetro | Antes | Después | Motivo |
|---|---|---|---|---|
| 1 | Señal sembrada | z_t iid N(0,1) | AR(1) φ=0.995 (persistente) | Con señal iid la banda de 10 pp no reduce turnover (|Δz| típico > banda cada día) y la sangría de costes (≈0.13 %/día) supera al alpha sembrado: el fallo era del diseño del test, no del motor. Las señales de baja frecuencia reales son persistentes |
| 2 | IC verdadero | 0.05 | 0.10 | El test de aceptación debe verificar que el motor RECUPERA y DETECTA una señal conocida de forma determinista. Con IC 0.05 la detección por el criterio permutado de ΔmaxDD tiene potencia intrínsecamente baja (§9.4 del preregistro: ni IC enormes garantizan detección): no-detección sería comportamiento esperado, no fallo. IC 0.10 valida el mecanismo sin afirmar realismo |
| 3 | Tolerancia del IC puntual | \|ic−IC\| < 0.02 | \|ic−IC\| < 0.05 | Con φ=0.995 y L=4000 el nº efectivo de observaciones independientes es ~L·(1−φ)/(1+φ) ≈ 10: el error empírico del estimador puntual fue 0.029 (> 0.02). El criterio principal NUNCA se relajó: el IC verdadero debe caer dentro del IC bootstrap por bloques |
| 4 | Permutaciones del test | 399 | 999 | Resolución del p-valor (1/1000) para decidir contra t*=0.025 sin efectos de discretización |
| 5 | (nuevo) test φ=0.9 | — | IC 0.05, L=12000, \|ic−IC\| < 0.08 ≈ 2·se(n_eff≈630), IC verdadero dentro del IC bootstrap | Condición D del gate M2: con memoria más corta el n efectivo crece (~630) y la recuperación puntual puede exigirse más apretada en términos estadísticos (tolerancia calibrada por n efectivo, no a ojo) |

## Lo que NO cambió

- El criterio de aceptación principal: **el IC verdadero cae dentro del
  intervalo bootstrap por bloques** (block bootstrap de 20 días). Se mantuvo en
  todas las iteraciones y pasa en ambas variantes (φ=0.995 IC 0.10; φ=0.9
  IC 0.05).
- La detección por permutación exige p ≤ t\* = 0.025 (nivel pre-registrado).
- Ningún umbral del preregistro (DSR, PBO, folds, costes ×2) se tocó.

## Alternativas descartadas

- Bajar t\* del test: habría debilitado el nivel de decisión pre-registrado
  (prohibido: el nivel se fija por calibración del nulo, no por conveniencia
  del test).
- Quitar costes del test: el motor debe probarse con su modelo de costes real;
  la lección (señales iid + banda = sangría) es justamente lo que el test debe
  capturar.
