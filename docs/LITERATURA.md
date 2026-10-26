# Revisión de literatura — M0 (QUANT-ARENA v2)

**Fecha de consulta de todas las fuentes: 2026-10-26 (UTC).**
Ninguna referencia se cita de memoria: cada entrada fue verificada en vivo contra
Crossref (DOI), arXiv (API oficial) o la página del editor. La evidencia máquina
(respuestas API completas, títulos/autoría/año resueltos, estado HTTP) está en
[`evidence/sources.json`](evidence/sources.json) y se regenera con
`make verify-sources`.

Regla de lectura: `[V]` = verificado en vivo; `[X]` = intento de verificación
fallido (se declara y no se usa como evidencia).

---

## 1. Fuentes

### A. Sobreajuste y pruebas múltiples (el núcleo del diseño del laboratorio)

| # | Referencia | Estado |
|---|---|---|
| S01 | Bailey, D.H.; López de Prado, M. **The Deflated Sharpe Ratio: Correcting for Selection Bias, Backtest Overfitting, and Non-Normality.** *Journal of Portfolio Management* 40(5), 94–107 (2014). DOI: [10.3905/jpm.2014.40.5.094](https://doi.org/10.3905/jpm.2014.40.5.094) | [V] |
| S02 | Bailey, D.H.; Borwein, J.; López de Prado, M.; Zhu, Q.J. **The Probability of Backtest Overfitting.** SSRN 2326253 (2013/2014); versión publicada: *Journal of Computational Finance* 20(2) (2017). DOI: [10.2139/ssrn.2326253](https://doi.org/10.2139/ssrn.2326253) | [V] |
| S03 | White, H. **A Reality Check for Data Snooping.** *Econometrica* 68(5), 1097–1126 (2000). DOI: [10.1111/1468-0262.00152](https://doi.org/10.1111/1468-0262.00152) | [V] |
| S04 | Hansen, P.R. **A Test for Superior Predictive Ability.** *Journal of Business & Economic Statistics* 23(4), 365–380 (2005). DOI: [10.1198/073500105000000063](https://doi.org/10.1198/073500105000000063) | [V] |
| S05 | Harvey, C.R.; Liu, Y.; Zhu, H. **…and the Cross-Section of Expected Returns.** *Review of Financial Studies* 29(1), 5–68 (2016). DOI: [10.1093/rfs/hhv059](https://doi.org/10.1093/rfs/hhv059) | [V] |
| S06 | López de Prado, M. **The 10 Reasons Most Machine Learning Funds Fail.** SSRN 3104816 (2018); versión publicada: *IEEE Access* 6, 12050–12055. DOI: [10.2139/ssrn.3104816](https://doi.org/10.2139/ssrn.3104816) | [V] |
| S07 | López de Prado, M. **Advances in Financial Machine Learning.** Wiley (2018), ISBN 978-1-119-48208-6. | [X] Wiley bloquea la verificación automática desde este entorno (sin DOI Crossref resoluble); se cita como referencia canónica secundaria de CPCV/purging/embargo, cuyo contenido metodológico está cubierto por S06 [V]. No se usa como evidencia única de nada. |

**Qué aportan al diseño:** S01 da el DSR (deflacta el Sharpe observado por el
número de ensayos, la asimetría y la curtosis); S02 da el PBO vía CSCV
(probabilidad de que el backtest sobreajuste); S03/S04 dan Reality Check y SPA
(¿la mejor celda de la rejilla bate realmente al benchmark tras multiplicidad?);
S05 documenta que, con cientos de factores publicados, el umbral de evidencia
debe subir (proponen t>3 en acciones); S06 prescribe validación combinatoria
purgada con embargo (CPCV) y lista los fallos típicos (solapamiento de
muestras, selección del mejor backtest, etc.).

### B. Momentum / tendencia / volatilidad (H1 y H2)

| # | Referencia | Estado |
|---|---|---|
| S08 | Moskowitz, T.; Ooi, Y.H.; Pedersen, L.H. **Time Series Momentum.** SSRN 2089463 (2011); versión publicada: *Journal of Financial Economics* 104(2), 228–250 (2012). DOI: [10.2139/ssrn.2089463](https://doi.org/10.2139/ssrn.2089463) | [V] |
| S09 | Liu, Y.; Tsyvinski, A.; Wu, X. **Common Risk Factors in Cryptocurrency.** *The Journal of Finance* 77(2) (2022). DOI: [10.1111/jofi.13119](https://doi.org/10.1111/jofi.13119) | [V] |
| S10 | Fieberg, C.; Liedtke, G.; Poddig, T.; Walker, T.; Zaremba, A. **A Trend Factor for the Cross Section of Cryptocurrency Returns.** *Journal of Financial and Quantitative Analysis* 60(7), 3116–3153 (2025). DOI: [10.1017/s0022109024000747](https://doi.org/10.1017/s0022109024000747) | [V] |
| S11 | Borgards, O. **Dynamic time series momentum of cryptocurrencies.** *North American Journal of Economics and Finance* 58 (2021). DOI: [10.1016/j.najef.2021.101428](https://doi.org/10.1016/j.najef.2021.101428) | [V] |
| S12 | Moreira, A.; Muir, T. **Volatility-Managed Portfolios.** *Journal of Finance* 72(4), 1611–1644 (2017). DOI: [10.1111/jofi.12513](https://doi.org/10.1111/jofi.12513) | [V] |

**Qué aportan:** S08 es el fundamento de la tendencia temporal (el retorno
pasado a 12 meses predice el futuro en 58 instrumentos; base conceptual de H1).
S09 encuentra factores comunes en cripto (mercado, tamaño y un momentum de 1–4
semanas), con datos hasta ~2018. S10 construye un factor de tendencia
transversal para cripto y documenta que agrega información a tamaño y momentum
(JFQA 2025, muestra hasta 2023). S11 muestra que el TSMOM en cripto es
**dinámico/heterogéneo** (varía con el tiempo y por activo), no una constante.
S12 justifica el escalado por volatilidad realizada de H1 (en acciones mejora
el Sharpe porque la volatilidad es predecible y no proporcional al retorno
esperado; **no verificamos evidencia equivalente específica en cripto**).

### C. Carry / funding (H3)

| # | Referencia | Estado |
|---|---|---|
| S13 | Koijen, R.S.J.; Moskowitz, T.J.; Pedersen, L.H.; Vrugt, E.B. **Carry.** *Journal of Financial Economics* 127(2), 197–225 (2018). DOI: [10.1016/j.jfineco.2017.11.002](https://doi.org/10.1016/j.jfineco.2017.11.002) | [V] |
| S14 | He, S.; Manela, A.; Ross, O.; von Wachter, V. **Fundamentals of Perpetual Futures.** arXiv:2212.06888 (2022). URL: [arxiv.org/abs/2212.06888](https://arxiv.org/abs/2212.06888) | [V] |
| S15 | Franz, F.-C.; Schmeling, M. **Crypto Carry.** SSRN 3774118 (2021). DOI: [10.2139/ssrn.3774118](https://doi.org/10.2139/ssrn.3774118) | [V] |

**Qué aportan:** S13 establece el carry como fenómeno general entre activos.
S14 modela y analiza los perpetuals: el funding es el mecanismo que ancla el
precio del perp al spot y compensa a quien provee el anclaje. S15 mide la
estrategia de carry en cripto (long spot / short future-perp): primas
históricamente grandes, pero con **riesgo de crash** (reversiones bruscas del
basis/funding) y costes de ejecución que importan. Ninguna valida nuestra regla
concreta "media móvil de funding > umbral": eso lo trataremos como hipótesis
exploratoria bajo contabilidad estricta de ensayos.

### D. Costes y decaimiento de señales

| # | Referencia | Estado |
|---|---|---|
| S16 | McLean, R.D.; Pontiff, J. **Does Academic Research Destroy Stock Return Predictability?** *Journal of Finance* 71(1), 5–32 (2016). DOI: [10.1111/jofi.12365](https://doi.org/10.1111/jofi.12365) | [V] |

**Qué aporta:** en 97 anomalías de acciones, la rentabilidad cae ~26%
out-of-sample y ~58% tras la publicación (arbitraje + data snooping). Lección:
incluso efectos reales y publicados se erosionan; un backtest in-sample optimista
es el techo, no el suelo. En cripto no verificamos un estudio equivalente; se
marca como extrapolación.

---

## 2. Síntesis: qué está establecido, qué es controvertido, qué no tiene evidencia

**Establecido (evidencia fuerte, revisada por pares, replicada):**
1. El sobreajuste de backtests es medible y ubicuo: sin corregir por
   multiplicidad (n_trials), el "mejor" backtest es estadísticamente inútil
   (S01–S05). Un Sharpe observado alto con muchos ensayos detrás puede ser puro
   ruido: de ahí DSR>0.95 con n_trials real, PBO<0.2 y Reality Check/SPA.
2. La tendencia temporal (time-series momentum) existió y persistió en activos
   tradicionales durante décadas (S08).
3. En cripto hay evidencia revisada por pares de factores de mercado, tamaño y
   momentum de corto plazo (S09, *Journal of Finance*) y de un factor de
   tendencia transversal informativo (S10, *JFQA* 2025).
4. El carry de cripto (spot long / perp-futuro short) capturó primas grandes
   históricamente, con riesgo de crash (S13–S15). El funding de perpetuals está
   bien caracterizado (S14).
5. Las señales publicadas decaen out-of-sample y tras publicación (S16).

**Controvertido / con matices:**
1. **Persistencia del TSMOM en cripto:** S11 lo encuentra dinámico y
   dependiente de régimen/activo; S10 documenta utilidad del factor de
   tendencia pero en muestras concretas; no hay consenso sobre estabilidad
   temporal ni sobre magnitud neta de costes para un minorista.
2. **Volatility targeting en cripto:** funciona en acciones (S12); no
   verificamos evidencia específica en cripto dentro de este corpus. Se usa en
   H1 como mecanismo de control de riesgo (reducción de drawdown), no como
   generador de alpha — por eso el criterio primario de H1 es el drawdown.
3. **Magnitud utilizable del momentum transversal en cripto:** los spreads
   brutos publicados (S09/S10) no siempre sobreviven a costes realistas,
   límites de capacidad y al crowding posterior a publicación (S16 por
   analogía).

**Sin evidencia verificada (no asumir nada):**
1. Reglas minoristas tipo "confluenciómetro", Fibonacci, múltiplo de Mayer,
   proyecciones 1D/1W: **ninguna fuente académica verificada las respalda**.
   No se portan (prohibido en el prompt y coherente con la literatura).
2. Rentabilidad neta para capital <100 USD con mínimos y fees reales de
   exchange: ninguna fuente académica lo testea; lo verificamos nosotros en
   vivo (M0 ya tiene mínimos y fees, ver `config/costs.yaml`; M2 cuantifica el
   impacto).
3. Reglas de timing de funding con media móvil + umbral (nuestra H3): el carry
   está documentado (S13/S15), la regla concreta de timing no. Es exploratoria.

## 3. Implicaciones directas para el diseño (rastreo fuente → decisión)

| Decisión de diseño | Fuentes |
|---|---|
| DSR con n_trials leído del ledger (nunca manual) | S01, S05 |
| PBO (CSCV) < 0.20 por familia | S02 |
| Reality Check/SPA sobre TODAS las celdas vs benchmark | S03, S04 |
| CPCV purgado con embargo en vez de walk-forward ingenuo | S06 (y S07 como referencia canónica) |
| Criterio primario de H1 = reducción de drawdown (no alpha) | S12 + análisis de potencia propio |
| H3 asume riesgo de crash y exige neto tras costes ×2 | S15, S13 |
| Expectativas calibradas: solo efectos grandes pasarán los gates | S05, S16 + potencia M0 |
| Nada de heurísticas sin hipótesis pre-registrada | ausencia total de evidencia (sección 2) |

## 4. Cobertura mínima exigida por el prompt

≥10 fuentes verificadas con URL/DOI y fecha: **15 verificadas [V]** de 16
intentos (1 fallo declarado [X]). Cobertura temática: momentum/tendencia cripto
(S08–S12), carry/funding (S13–S15), sobreajuste/DSR/PBO/Reality Check/SPA
(S01–S05), validación purgada/CPCV (S06, S07[X] como secundaria), costes y
decaimiento (S16).
