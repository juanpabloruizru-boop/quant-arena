# ADR-003 · Modelo de costes

**Fecha:** 2026-10-26 · **Estado:** aceptado (M0)

## Contexto

Ningún veredicto vale nada sin costes realistas. El prompt exige fees y
mínimos verificados en vivo y stress ×2. Lección heredada: con capital <100 USD
los mínimos y comisiones pueden consumir gran parte del objetivo.

## Datos verificados en vivo (2026-10-26)

- Spot Regular User: **0.100 % maker / 0.100 % taker**; con BNB −25 %
  (0.075 %). Fuente: https://www.binance.com/en/fee/schedule
- Perp USDT-M Regular User: **0.020 % maker / 0.050 % taker**; con BNB −10 %;
  promo vigente de 0 % maker en perps U-margined (no se asume). Fuente:
  https://www.binance.com/en/fee/futureFee
- Mínimos (API `exchangeInfo`): spot `minNotional` 5 USDT (BTCUSDT/ETHUSDT),
  1 USDT (PEPEUSDT); perp BTCUSDT `minQty` 0.001 BTC y `MIN_NOTIONAL` 50 USDT.
- Funding BTCUSDT: intervalo **8 h** (spacing verificado entre registros).
- Precios de referencia: BTC ≈ 79 740 USDT, ETH ≈ 2 305 USDT.
- Evidencia completa: `docs/evidence/binance_probes.json`.

## Decisión

1. **Conservadurismo:** todo backtest usa **taker en ambos lados** y SIN
   descuentos (ni BNB ni promos). Quien opera reglas de baja frecuencia con
   market orders paga eso; si algún día se usan limit orders, el resultado con
   taker sigue siendo cota válida.
2. **Slippage por tramos de participación** sobre el volumen quote del día
   (1 pb ≤0.01 %, 3 pb ≤0.1 %, 15 pb ≤1 %, 60 pb ≤5 %, >5 % = trade
   RECHAZADO y registrado). Valores = **asunción pre-registrada** (no
   verificables sin datos de libro); en M2 se comparan contra el spread
   observado y se documenta; nunca se relajan tras ver resultados.
3. **Funding real:** en H3 se aplica el funding histórico real por símbolo e
   intervalo (nunca una tasa modelada). En M2 el motor carga el histórico y un
   test verifica cobertura y signo.
4. **Stress ×2** obligatorio (fees+slippage) en todo veredicto (C4).
5. **Mínimos operativos como restricción dura:** el motor de backtest rechaza
   (y registra) toda orden por debajo del mínimo vigente del símbolo; el
   forward paper (M4) igual. Para cuentas pequeñas esto se reporta como
   factibilidad, no se ignora.
6. `config/costs.yaml` es la única fuente de costes; cada campo lleva `status:
   VERIFICADO|ASUNCION` + URL + fecha. Re-verificación obligatoria en M1 y M4
   (los fees cambian).

## Alternativas descartadas

- Fees fijos en bps sin mínimos: subestima el coste real en capital pequeño.
- Asumir maker/BNB/promo: sesga a favor de la estrategia (prohibido).
- Modelar funding como constante 0.01 %/8h: destruye la hipótesis H3 (el
  funding es justo la señal y el ingreso).

## Consecuencias

- Aritmética de capital pequeño (con precios del 2026-10-26): round-trip spot
  de 100 USDT ≈ 0.26 USDT (fees 0.2 + slippage ~0.06) ≈ 26 % de un objetivo
  mensual del 1 % sobre 100 USDT **por cada trade**; en perp BTC el mínimo de
  50 USDT obliga a concentrar. El claim heredado 40–75 % es plausible para
  frecuencias de varios trades/mes; M2 publica la tabla exacta coste/objetivo
  por frecuencia.
