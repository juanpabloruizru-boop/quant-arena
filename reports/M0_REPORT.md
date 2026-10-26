# M0 · Preregistro y diseño · 2026-10-26T14:35Z · git SHA `82bf4309813d55c3e8dc534faff305a268634123` (tag `prereg-v1`)

## Resumen en 5 líneas

1. Literatura revisada con **15 fuentes verificadas en vivo** (Crossref/arXiv, evidencia en `docs/evidence/sources.json`); 1 intento fallido declarado (libro de Wiley bloquea bots).
2. **PREREGISTRO v1.0** congelado: 3 familias, 22 celdas de rejilla × activos = **n_trials mínimo 38**, criterios de éxito, holdout sellado de 365 días, y sellado con tag `prereg-v1` + SHA256.
3. **Análisis de potencia ejecutado** (script determinista): el test de Sharpe y H2 son **incontrastables para efectos típicos en el horizonte disponible**; el criterio primario de H1 se formula sobre **drawdown** (potencia 77–93 %) y H3 carry es la única familia con potencia holgada (MDE ≈ 1–2 %/año).
4. Fees, mínimos, unidades de timestamp, límites de paginación e historial de Binance **verificados en vivo hoy** (33 sondas, 0 fallos) — incluidos hallazgos que contradicen la documentación (klines spot tapa a 1000 filas; `fundingRate` ignora `startTime=0`).
5. Repo inicializado con los gates del prompt en verde local: ruff ✓, `mypy --strict` ✓ (15 ficheros), pytest **10/10** ✓ (incluye guard anti-clientes-de-trading/anti-listeners y congelación de la rejilla v1.0).

## Entregables

| Ítem | Ruta | Estado |
|---|---|---|
| Revisión de literatura (≥10 fuentes verificadas) | `docs/LITERATURA.md` | ✅ 15 [V] + 1 [X] declarado |
| Evidencia máquina de fuentes | `docs/evidence/sources.json` (+ `scripts/verify_sources.py`) | ✅ regenerable con `make verify-sources` |
| Evidencia máquina de endpoints/fees | `docs/evidence/binance_probes.json` (+ `scripts/probe_binance.py`) | ✅ 33 sondas, regenerable con `make verify-endpoints` |
| Preregistro v1.0 | `docs/PREREGISTRO.md` | ✅ SHA256 `e2029ea2…991c79` |
| Rejilla máquina-espejo v1.0 | `config/hypotheses.yaml` | ✅ SHA256 `d52b1817…a27c21` |
| Análisis de potencia (script + resultados) | `scripts/power_analysis.py` → `reports/M0_power_analysis.md/.json` | ✅ semilla 20261026, determinista |
| ADRs | `docs/adr/ADR-001…004` | ✅ stack, universo/horizonte, costes, sellado |
| Universo PIT (config) | `config/universe.yaml` | ✅ con sesgos no eliminables declarados |
| Costes (config) | `config/costs.yaml` | ✅ VERIFICADO/ASUNCION por campo |
| Repo + CI + calidad | `pyproject.toml`, `Makefile`, `.github/workflows/ci.yml`, `.pre-commit-config.yaml` | ✅ CI se estrenará al hacer push a GitHub; gates idénticos pasan en local |
| CLI mínima (stubs M0) | `src/qa/cli.py` (`qa data sync/verify`, `research run`, `stats report`, `forward run`, `report daily`) | ✅ exit code 3 "NO IMPLEMENTADO" |
| Guard de seguridad | `tests/unit/test_safety_no_trading_clients.py` | ✅ fallo si se importan clientes de trading o se abren listeners |
| Glosario (semilla) | `docs/GLOSARIO.md` | ✅ v0, se completa en M5 |
| Tag git `prereg-v1` | commit `82bf430` | ✅ anotado, con SHA256 de ambos ficheros normativos; **sin firma GPG** (no existe en el entorno, ver desviaciones) |

## Gates

| Gate | Comando | Resultado | Evidencia |
|---|---|---|---|
| ≥10 fuentes verificadas (URL/DOI+fecha) | `make verify-sources` | ✅ 15 OK, 1 fallo esperado declarado, exit 0 | `docs/evidence/sources.json` (`checked_at_utc 2026-10-26`) |
| Potencia calculada y declarada | `make power` | ✅ 6 tablas + veredictos por hipótesis | `reports/M0_power_analysis.md` (semilla 20261026) |
| Lint | `.venv/bin/ruff check . && ruff format --check .` | ✅ All checks passed / 24 files formatted | salida de consola 2026-10-26 |
| Tipos estrictos | `.venv/bin/mypy` | ✅ Success: no issues in 15 source files | idem |
| Tests | `.venv/bin/pytest` | ✅ 10 passed | idem |
| Rejilla congelada y consistente | `tests/unit/test_configs_valid.py` | ✅ 12+6+4 celdas × activos = 38 trials | idem |
| Preregistro sellado | `git tag -n99 prereg-v1` | ✅ hashes en mensaje del tag | tag sobre `82bf430` |
| Endpoints/fees/mínimos verificados en vivo | `make verify-endpoints` | ✅ 33 sondas, 0 errores | `docs/evidence/binance_probes.json` |

## Resultados

### Verificación en vivo de Binance (2026-10-26, 33 sondas públicas de lectura)

| Hecho | Valor verificado | Impacto |
|---|---|---|
| Timestamps spot y futures klines/funding | **ms (13 dígitos)** ambos | La normalización ms/µs del prompt sigue siendo obligatoria como test, pero hoy todo llega en ms |
| `/api/v3/klines` límite | pedidos 1500/1501 → devuelve **1000** filas, sin error | M1 debe paginar a 1000, no fiarse del "1500" documentado |
| `/fapi/v1/fundingRate` con `startTime=0` | devuelve los **más recientes** (ignora el 0) | M1 debe paginar desde fecha explícita |
| Historia spot BTCUSDT | primera vela **2017-08-17** (API y dump) | H1 con ~8.2 años in-sample |
| Historia perp BTCUSDT | primera vela 2019-09-08; primer funding **2019-09-10**; dumps diarios desde 2019-12-31; funding en dumps **mensuales** | H3 con ~6.1 años |
| Funding BTCUSDT | intervalo **8 h** (spacing real entre registros) | anualización correcta en H3 |
| Fees spot | **0.100 %/0.100 %** Regular User (página oficial) | `costs.yaml` |
| Fees perp USDT-M | **0.020 %/0.050 %** Regular User (página oficial; promo vigente NO asumida) | `costs.yaml` |
| Mínimos | spot minNotional **5 USDT** (BTC/ETH), 1 USDT (PEPE); perp BTCUSDT **minQty 0.001 BTC + MIN_NOTIONAL 50 USDT** | factibilidad de capital pequeño |
| Deslistados | 2 353 símbolos BREAK en exchangeInfo; dumps conservan FTTUSDT y LUNABTC completos | universo PIT con deslistados |
| Precios ref. | BTC 79 739.64 / ETH 2 304.86 USDT | aritmética de mínimos (0.001 BTC ≈ 80 USD) |

### Potencia (resumen ejecutivo; tablas completas en `reports/M0_power_analysis.md`)

| Pregunta | Respuesta con datos de hoy |
|---|---|
| ¿Cuántos años para detectar ΔSharpe=0.5 vs B&H (80 % potencia)? | **~50 años** (no pareado). Con test pareado (MC de H1): MDE ≈ **0.67** a 8.2 años → mejoras pequeñas de Sharpe son **incontrastables** |
| ¿Y ΔSharpe=0.3? | ~137 años. Descartado |
| ¿Puede H1 demostrar reducción de drawdown? | **Sí, para efectos grandes**: sd(ΔmaxDD) ≈ 13 pp → detectable al 5 % desde ~21 pp; potencia 77–93 % para mejoras de 35–42 pp (las que produce el montaje simulado) |
| ¿Qué Sharpe exige DSR>0.95 con n_trials=38 y 8.2 años? | **≈1.66–2.22** según dispersión entre celdas (sd 0.5–0.75) |
| ¿H2 momentum semanal es contrastable? | n≈354 semanas → MDE ≈ **0.46–0.77 %/sem** (24–40 % anualizado). Para spreads típicos (10–20 %/año): **INCONTRASTABLE en el horizonte** (declarado de antemano) |
| ¿H3 carry es contrastable? | **Sí**: n≈2 237 días → MDE ≈ 1.0–2.1 %/año (σ diaria 5–10 pb). Carry ≥4 %/año: potencia >80 % con ~1.7 años de datos |
| ¿Cuántos trades para discriminar WR 45 % vs 40 %? | **n≈600** (42 % vs 40 %: ~3 729). H1 genera decenas → ningún criterio basado en win-rate (lección heredada corregida) |

Consecuencia pre-registrada (PREREGISTRO §8-§9): C1 de H1 = reducción de maxDD; Sharpe entra como no-inferioridad práctica (ΔSharpe ≥ −0.10); H2 se ejecutará pero su veredicto probable, si el efecto es típico, será INCONTRASTABLE **por diseño conocido de antemano**, no por sorpresa.

### n_trials

Pre-registrado: **38** (H1 24 = 12 celdas × 2 activos; H2 6; H3 8 = 4 × 2). Suelo mínimo: el ledger `trials` puede hacerlo crecer, nunca reducirlo. Todavía no existe `trials.duckdb` (nace en M2 con el motor).

## Desviaciones del plan y su justificación

1. **Python 3.11.2 local en vez de 3.12** (el sandbox no tiene 3.12): `requires-python >=3.11`; CI en GitHub Actions usa **3.12** (objetivo del prompt). El código pasa los gates en 3.11 y no usa sintaxis 3.12-only. ADR-001.
2. **`uv` no disponible en el entorno**: se usa `venv+pip` con pyproject estándar compatible con uv. ADR-001.
3. **`gpg` no disponible → tag `prereg-v1` anotado pero NO firmado**: mitigado con SHA256 de los dos ficheros normativos dentro del mensaje del tag + recomendación de sello externo OSF/OpenTimestamps. ADR-004. Es la desviación más relevante del hito: sin sello externo, la anterioridad del preregistro es autoatestiguada.
4. **S07 (libro AFML, Wiley) no verificable en vivo** (la editorial bloquea peticiones automáticas; no tiene DOI Crossref resoluble): se declara `[X]` y se usa solo como referencia secundaria; su contenido metodológico (CPCV/purging) está cubierto por S06 [V].
5. **Dos referencias heredadas resultaron inciertas al verificar**: "Common Cryptocurrency Risk Factors" es en realidad *"Common Risk Factors in Cryptocurrency"* (JF 2022), y la referencia a Kołodziejczyk et al. (RQFA) no fue localizable en Crossref → sustituida por Fieberg et al. (JFQA 2025, DOI verificado). Evidencia de por qué no se cita de memoria.
6. **Extensión del horizonte de datos** (2017→ frente al 2023-2026 heredado): decisión de alcance motivada por la potencia (con 3.3 años, MDE ΔSharpe ≈ 1.94 — nada pasa). ADR-002, pregunta P2.
7. **GitHub Actions no ejecutado** (no hay remoto en M0): los gates idénticos se ejecutan en local (`make ci`) y el workflow queda commiteado; se estrenará con el primer push.

## Limitaciones y sesgos conocidos

- **Velas y fees de un solo venue (Binance)**: sesgo pro-Binance; multi-venue fuera de alcance M0-M3.
- **Slippage por tramos = asunción** pre-registrada (no verificable sin libro de órdenes histórico); se contrastará con spreads observados en M2 y nunca se relajará tras ver resultados.
- **Monte Carlo de potencia bajo GBM log-normal**: cuantifica la potencia del *test*, no predice signos reales (bajo GBM puro, filtrar tendencia no añade alpha; los mercados reales tienen colas y regímenes). Sensibilidades de σ/ρ incluidas en las tablas.
- **H2 depende de profundidad real de altcoins líquidas** (inicio efectivo ~2019 por confirmar en M1): si el universo PIT solo es profundo desde 2020, el MDE de H2 empeora (ya declarado incontrastable para efectos típicos).
- **Universo PIT reconstruido desde dumps + exchangeInfo actual**: puede haber huecos de símbolos muy antiguos; se documentará símbolo a símbolo en M1.
- El sello externo (OSF) está pendiente de decisión/credenciales → la prueba de anterioridad es, por ahora, interna.

## Riesgos abiertos

1. **R1 · Sellos**: sin OSF, un escéptico podría dudar de la fecha del preregistro. Mitigación: hashes en tag + publicar hashes en un canal fechado en cuanto se apruebe (P3).
2. **R2 · API en evolución**: hoy klines spot tapa a 1000 y existe una línea "TradFi Futures" nueva en el site de fees; la semántica de los endpoints puede cambiar durante el proyecto. Mitigación: `make verify-endpoints` re-ejecutable + tests de contrato en M1.
3. **R3 · H2 nace muerta para efectos típicos**: riesgo de gastar tiempo en algo incontrastable. Mitigación: veredicto INCONTRASTABLE pre-definido; el forward (M4) ampliaría muestra si el orquestador lo ve útil.
4. **R4 · Criterios exigentes (DSR>0.95 ⇒ Sharpe ≳1.7)**: posible "todo NO PASA". Aceptado por diseño: resultado negativo bien documentado = éxito (misión).
5. **R5 · Entorno local ≠ CI** (3.11 vs 3.12): riesgo bajo, mitigado por doble matrix mental y código conservador.

## Preguntas para el orquestador (solo decisiones reales)

- **P1 · Interpretación de la rejilla H1 (pre-registro).** Registré "cierre>SMA(n) **o** retorno L>0" como **dos variantes disjuntas** (12 celdas × 2 activos = 24 trials). La lectura alternativa (señal disyuntiva con producto cruzado n×L) daría 18×2=36 celdas y más n_trials. ¿Ratificas la lectura disjunta (v1.0) o exiges v1.1 con producto cruzado?
- **P2 · Horizonte de datos (alcance).** Extiendo el in-sample a **desde 2017** (spot) / 2019 (funding) en vez del 2023-2026 heredado, por potencia (ADR-002). ¿Lo apruebas? Afecta al volumen de ingesta de M1 (~9 años × universo PIT).
- **P3 · Sello externo.** ¿Autorizas registrar PREREGISTRO v1.0 en OSF (necesitaría una cuenta) u OpenTimestamps, o prefieres mantener solo tag+hash con la limitación declarada? (ADR-004)
- **P4 · H3 en ETHUSDT.** El funding de ETHUSDT perp existe desde ~2019-11/2020 (a verificar en M1). Si su historia resultara materialmente más corta que BTC, ¿mantengo ETH en H3 con la muestra reducida (y lo declaro) o reduzco H3 a solo BTC (n_trials 8→4)?

## Qué aprendimos (lenguaje llano)

- **La potencia manda:** con pocos años de datos, hasta la mejor estrategia del mundo puede "no significar nada" estadísticamente. Calcular antes *qué tamaño de efecto podemos ver* evita montar un laboratorio que no puede responder (el fallo heredado de n=30). MDE = "el bulto más pequeño que nuestra balanza detecta".
- **Cada prueba extra cuenta:** si pruebas 38 variantes y eliges la mejor, el azar ya te regala un Sharpe aparente de ~1.1-1.6. El DSR descuenta ese "premio por buscar". Por eso el ledger cuenta los ensayos solo, sin fiarse de nadie.
- **Las fuentes se verifican o no valen:** dos referencias "seguras" de memoria resultaron tener títulos/DOIs distintos al verificarlas contra Crossref. Regla del proyecto: URL+fecha o `[NO VERIFICADO]`.
- **La documentación oficial miente (a veces):** el API de spot aceptó `limit=1501` y devolvió 1000 filas sin quejarse; `fundingRate` ignora `startTime=0`. Probar en vivo > leer docs.
- **Drawdown y Sharpe no se miden igual de bien:** con los mismos datos, demostrar "cae un 30 % menos" es mucho más fácil que demostrar "Sharpe 0.3 mejor". H1 se juzgará por lo primero.

## Solicitud: GATE APROBADO M0
