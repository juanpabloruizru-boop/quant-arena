# GLOSARIO (v0 — semilla de M0; se completa en M5)

Lenguaje llano + ejemplo numérico cuando ayuda. Términos usados en los
documentos de M0.

- **Retorno**: cuánto gana o pierde algo en un período. Ej.: compras a 100 y
  vendes a 110 → +10 %.
- **Buy & hold (B&H)**: comprar y no hacer nada. Nuestro rival a batir.
- **Sharpe (ratio)**: retorno extra por unidad de riesgo (volatilidad). Sharpe
  anual 1 = decente; 2 = muy bueno; 3+ en backtests = sospecha de error o
  sobreajuste.
- **Sortino**: como el Sharpe pero solo castiga la volatilidad "mala" (caídas).
- **Volatilidad (σ)**: cuánto se mueve el precio. BTC suele tener σ anual
  40–80 %.
- **Max drawdown (MDD)**: la peor caída desde un máximo hasta el siguiente
  mínimo, en %. Ej.: de 100 a 55 → MDD 45 %. Duele más que lo que sugiere:
  para volver de 55 a 100 hace falta +82 %.
- **Calmar**: retorno anualizado / MDD.
- **Expectancy en R**: ganancia media por operación medida en múltiplos del
  riesgo inicial (R). 0.5R = ganas medio riesgo por trade en promedio.
- **IC (information coefficient)**: correlación entre lo que predice la señal y
  lo que pasó después. IC 0.05 ya es relevante en finanzas; 0.5 sería magia.
- **Funding**: pago periódico (en Binance cada 8 h en BTCUSDT perp) entre
  largos y cortos de un perpetual para pegar su precio al spot. Positivo: los
  largos pagan a los cortos. Es el "cupón" del carry (H3).
- **Perpetual (perp)**: futuro sin vencimiento que replica el spot vía funding.
- **Carry delta-neutral**: comprar spot y vender el perp a la vez: no te
  importa si sube o baja (posición neutral), cobras el funding. Riesgo: que la
  prima se dé la vuelta bruscamente (crash de basis).
- **Slippage**: diferencia entre el precio que ves y el que consigues. Ej.:
  quieres comprar a 100.00 y tu orden se llena a 100.03 → 3 pb de slippage.
- **Fee maker/taker**: comisión por poner liquidez (maker, más barata) o por
  quitarla (taker, más cara). Verificado 2026-10-26: spot 0.1 %/0.1 %;
  perp 0.02 %/0.05 % (usuario regular).
- **Mínimo notional**: importe mínimo por orden. Verificado: 5 USDT spot
  BTCUSDT; 50 USDT perp BTCUSDT. Con capital pequeño, esto manda.
- **PIT (point-in-time)**: reconstruir el pasado usando solo lo que se sabía
  entonces. Evita el sesgo de "elegir hoy a los ganadores de ayer".
- **Sesgo de supervivencia**: estudiar solo los que sobrevivieron (monedas que
  siguen listadas) y concluir que todo sube. Mitigado incluyendo deslistadas.
- **Look-ahead**: usar en el día t información que solo existió en t+1.
  Prohibido; se testea con invarianza por truncamiento.
- **Holdout sellado**: trozo final de datos (últimos 12 meses) que se guarda
  bajo llave y se mira UNA sola vez, con las reglas ya congeladas.
- **n_trials**: cuántas variantes probaste (aunque sea "solo para mirar").
  Cuanto mayor, más probable que tu mejor resultado sea chiripa. Se cuenta
  solo (ledger), nunca a mano.
- **DSR (Deflated Sharpe Ratio)**: probabilidad de que tu Sharpe sea real tras
  descontar n_trials, asimetría y colas. Pedimos > 0.95.
- **PBO (Probability of Backtest Overfitting)**: probabilidad de que la mejor
  celda del backtest quede por debajo de la mediana fuera de muestra. Pedimos
  < 0.20.
- **Reality Check / SPA**: test de "¿la mejor de N reglas bate de verdad al
  benchmark tras contar la búsqueda?".
- **CPCV**: cross-validation combinatorio purgado — repartir la historia en
  bloques, entrenar/validar en muchas combinaciones, **purgando** solapes y
  dejando **embargo** (días de cuarentena) para que nada del test contamine el
  train.
- **Bootstrap por bloques**: remuestrear trozos de serie (no días sueltos) para
  no romper la autocorrelación y obtener intervalos de confianza honestos.
- **HAC (Newey-West)**: errores estándar corregidos por autocorrelación.
- **Potencia**: probabilidad de detectar un efecto si existe. 80 % es el
  estándar. Sin potencia, "no significativo" ≠ "no existe".
- **MDE (minimum detectable effect)**: el efecto más pequeño que tu test puede
  ver con la potencia objetivo. Nuestro MDE de ΔSharpe con 8.2 años ≈ 1.23
  (no pareado): por eso H1 se juzga por drawdown, no por Sharpe.
- **Walk-forward**: entrenar en una ventana, probar en la siguiente, deslizar y
  repetir.
- **B&H matched-exposure (misma exposición media)**: benchmark que invierte en
  el activo la MISMA fracción media de capital que la estrategia (ē), todos los
  días. Si tu estrategia pasa menos tiempo dentro, este benchmark también: así
  la comparación mide *cuándo* estuviste dentro (timing), no *cuánto*
  (exposición). Ej.: estrategia expuesta 60 % del tiempo → benchmark = 0.6 ×
  retorno diario del activo.
- **Test de permutación (de timing)**: barajamos CUÁNDO estuvo puesta la
  posición (conservando cuánto) miles de veces y miramos cuántas veces el azar
  lo hace igual o mejor que la regla real. Si el azar lo iguala el 20 % de las
  veces, no hay skill demostrable (p = 0.20).
- **Ulcer Index**: promedio de cuánto "duele" la cartera bajo el agua
  (caída media cuadrática desde máximos). Cuanto más bajo, menos sufrimiento.
- **Tiempo bajo el agua (time underwater)**: cuántos días pasa la cartera sin
  recuperar su máximo histórico. Ej.: 400 días bajo el agua = más de un año
  sin ver un nuevo máximo.
- **Banda de rebalanceo**: solo se toca la posición si el objetivo cambia más
  de X puntos (nosotros: 10 pp). Sin banda, los micro-ajustes diarios
  acumulan comisiones que se comen el beneficio.
- **OpenTimestamps (OTS)**: servicio gratuito que ancla el hash de un fichero
  en la blockchain de Bitcoin vía calendarios públicos: prueba de que el
  fichero existía en una fecha, verificable por cualquiera sin confiar en
  nosotros. Tarda horas en confirmar (el ancla entra en un bloque BTC).
- **Subperíodos**: trozos fijos de la historia (2017-19, 2020-22, 2023-25)
  para exigir que un resultado no dependa de un único régimen de mercado.
- **Volatilidad objetivo (vol targeting)**: dimensionar la posición para que la
  cartera tenga una σ fijada (p. ej. 25 % anual): si el activo se desboca, se
  reduce posición; si se calma, se sube (tope 1×, sin apalancar).
- **Ledger append-only**: libro de registros que solo sabe añadir filas (con
  cadena de hashes): ni borrar ni editar sin dejar evidencia.
