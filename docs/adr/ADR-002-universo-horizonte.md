# ADR-002 · Universo de activos y horizonte de datos

**Fecha:** 2026-10-26 · **Estado:** aceptado (M0), pendiente ratificación del
orquestador sobre la extensión de horizonte (pregunta P2 del informe M0).

## Contexto

El proyecto anterior usó BTC/ETH/SOL/BNB/PEPE fijos, velas 4H, 2023-2026
(≈3.3 años) [HEREDADO, NO VERIFICADO]. El análisis de potencia de M0
(`reports/M0_power_analysis.md`) muestra que con 3.3 años el MDE de una
diferencia de Sharpe es ≈1.94: nada realista pasa. Extender el horizonte es la
única palanca disponible sin inventar datos.

Disponibilidad verificada en vivo (2026-10-26, `docs/evidence/binance_probes.json`):
- Spot diario y 4h desde **2017-08-17** (API y dumps de `data.binance.vision`).
- Perp USDT-M desde **2019-09-08** (API); dumps diarios desde 2019-12-31;
  funding: primer registro **2019-09-10**, dumps **mensuales** disponibles.
- Símbolos deslistados: el API actual lista 2 353 símbolos en estado BREAK y
  los dumps conservan historial completo (FTTUSDT, LUNABTC verificados).

## Decisión

1. **Horizonte máximo:** klines spot diarios desde el inicio de cada par
   (2017-08-17 para BTCUSDT); 4H solo si una hipótesis lo exige (ninguna de la
   rejilla v1.0 lo exige: H1 diario, H2 semanal, H3 diario+funding). Menos
   datos innecesarios = menos superficie de error.
2. **Universo H2 point-in-time:** top-N (N∈{10,20}) por volumen quote USDT
   trailing-30d, recalculado el primer día de cada mes usando solo el pasado;
   incluye deslistados (vía dumps); exclusiones de estables/wrapped/
   apalancados; edad mínima 60 días. `exchangeInfo` actual + dumps permiten
   reconstruir el listado histórico; donde no alcance, se documenta el hueco.
3. **H1 y H3 sobre BTC y ETH** (los dos con historia más larga y liquidez
   incuestionable; evita la selección post-hoc de "la alt que funcionó").
4. **Un solo venue (Binance):** el sesgo pro-Binance se declara; multi-venue
   está fuera del alcance de M0-M3.

## Alternativas descartadas

- Mantener 2023-2026: potencia nula para efectos realistas (MDE ≈ 1.94 Sharpe).
- Universe fijo tipo proyecto anterior (SOL/BNB/PEPE desde 2023): sesgo de
  selección de supervivientes — justo lo que PIT evita.
- Multi-venue (OKX/Bybit/Coingecko): más robustez, pero triplica el trabajo de
  ingesta/normalización; se deja como extensión si M3 encuentra algo.

## Consecuencias

- In-sample ≈8.2 años (H1), ≈6.8 (H2), ≈6.1 (H3): MDE de ΔSharpe no pareado
  baja a ≈1.23 y el criterio de drawdown de H1 gana potencia 77–93 %.
- H2 sigue siendo incontrastable para efectos típicos: se declara de antemano
  (PREREGISTRO §9.4) en vez de descubrirlo tras gastar el holdout.
- La ingesta de ~9 años × decenas de símbolos exige paginación cuidadosa
  (límite real de klines: 1000 filas) y reintentos; trabajo de M1.
