# M2b · Condiciones A-H del gate M2 · 2026-10-27T17:40Z · git SHA `3b91b25` (+ commit de este informe)

## Resumen en 5 líneas

1. **A-H cerradas**: t\* validado con semillas nuevas en 3 mundos nulos (FPR ≤ 5 % en todos; GBM 4.6 % en rango; vol-MS 1.5 % y vol-MS+jumps 2.3 % **conservadores** → se propone v1.4 con la declaración de conservadurismo, sin tocar el nivel); potencia del PIPELINE H1 medida (9.5 % / 18.5 % / 61 % para ΔSharpe 0.1/0.3/0.5); holdout **cifrado** (AES256, clave de 32 bytes mostrada una única vez abajo, sha256 de plaintexts en ledger); segunda fuente **Coinbase período completo** (2 992 días, corr 0.99); fees **re-verificados en vivo** (sin cambios); bundle nuevo `quant-arena-M2.bundle` entregado.
2. **Incidente de entorno resuelto**: el sandbox perdió `.git` (y venv/paquetes) entre sesiones; el repo se **recuperó íntegro del bundle M0b** (historia, 5 tags y firmas SSH verificadas, working tree idéntico al último commit) — la entrega de bundles demostró su valor; desde ahora se regenera el bundle en cada turno.
3. **Corrección honesta**: la nota del M2 sobre Kraken ("ignora `since`") era falsa — los pares XBTUSDT/ETHUSDT de Kraken nacieron el 2024-11-06 (verificado); la condición F cubre ahora el período completo con Coinbase.
4. Gates: ruff ✓ · mypy --strict (61 ficheros) ✓ · **pytest 71/71** ✓ · `qa data verify` 1198 ficheros ✓ · ninguna métrica de estrategia sobre datos reales (la comparación F es calidad de datos; G confirma los tests de invarianza por truncamiento de TODAS las features).
5. M3 sigue bloqueado por lo que depende del usuario: push del repo con CI verde + registro OSF. Por mi parte no queda ninguna dependencia abierta salvo la aprobación de la propuesta v1.4 (Q1).

## Entregables (condiciones A-H)

| Cond. | Ítem | Ruta | Estado |
|---|---|---|---|
| A | Validación t\* con semillas nuevas × 3 mundos nulos (5000 sims/mundo) | `scripts/validate_tstar_fpr.py` → `reports/M2_tstar_validation.md/.json` | ✅ fuera de rango por CONSERVADOR en 2 mundos → propuesta v1.4 (Q1) |
| B | Potencia del pipeline completo (24 candidatas + RC) | `scripts/h1_pipeline_power.py` → `reports/M2_h1_pipeline_power.md/.json` | ✅ + recomendación (abajo) |
| C | §7.5 citado + n_trials de H3 + umbrales | Sección "Resultados C" | ✅ respuesta + propuesta v1.4 (sin aplicar) |
| D | ADR antes/después de tolerancias + test φ=0.9 | `docs/adr/ADR-006-tolerancias-senal-sembrada.md`, `tests/synthetic/test_planted_signal.py::test_planted_signal_phi09_puntual_ajustado` | ✅ |
| E | Holdout cifrado (gpg AES256), clave 1 vez, sha256 en ledger, guard con clave | `src/qa/backtest/seal.py`, `holdout_sealed/*.{gpg,SEALED.json}`, `ledger/holdout_seal.log`, `ledger/holdout_access.log` | ✅ ADR-004 addendum 2 |
| F | Segunda fuente período completo | `scripts/validate_second_source.py` → `docs/evidence/second_source_validation.json` | ✅ |
| G | Informe con plantilla + gates + truncamiento + fees en vivo + adjudicación con URLs | Este informe | ✅ |
| H | Bundle nuevo con nombre nuevo + verificación + contención | `/home/user/quant-arena-M2.bundle` | ✅ (metadatos en el mensaje de entrega) |

## Gates

| Gate | Comando | Resultado | Evidencia |
|---|---|---|---|
| Lint | `.venv/bin/ruff check . && ruff format --check .` | ✅ All checks passed | consola 2026-10-27 |
| Tipos | `.venv/bin/mypy` | ✅ 61 ficheros, 0 errores | idem |
| Tests | `.venv/bin/pytest` | ✅ **71 passed** | idem |
| Invarianza por truncamiento (G) | `pytest tests/unit/test_features_truncation.py` | ✅ 5 tests: sma, rolling_sum, rolling_mean, realized_vol_ann y **funding_ma_annualized** (nueva) — propiedad `f(x[:t+1])[t]==f(x)[t]` con hypothesis | idem |
| Fees/minimos en vivo (G) | `fetch` de binance.com/en/fee/schedule + /fee/futureFee y `python scripts/probe_binance.py` | ✅ spot 0.100 %/0.100 %, perp 0.020 %/0.050 % **sin cambios**; 33 sondas, 0 fallos; minNotional 5 USDT spot / 50 USDT perp; funding 8 h | `docs/evidence/binance_probes.json` (re-ejecutado 2026-10-27), `config/costs.yaml` (`reverified_at_utc`) |
| A: FPR t\* | `python scripts/validate_tstar_fpr.py` | ✅/⚠ ver Resultados A | `reports/M2_tstar_validation.md` |
| B: potencia pipeline | `python scripts/h1_pipeline_power.py` | ✅ | `reports/M2_h1_pipeline_power.md` |
| FWER actualizado (≤ t\*) | `python scripts/h1_fwer_simulation.py block20 0.025` | ✅ pipeline 0.5 % | `reports/M0_h1_fwer.md` |
| E: sellado | `python -c "from qa.backtest.seal import seal_holdout; …"` + tests | ✅ plaintext borrado, 3 `.gpg`, log con sha256, apertura verificada y auditada, clave falsa rechazada | `ledger/holdout_seal.log`, `ledger/holdout_access.log`, `tests/unit/test_holdout_seal.py` |
| F: segunda fuente | `python scripts/validate_second_source.py` | ✅ | `docs/evidence/second_source_validation.json` |
| Datos | `qa data verify` | ✅ 1198 ficheros SHA256 | salida CLI |
| Holdout intacto | `ledger/holdout_access.log` | 2 entradas: verificación técnica post-sellado y reconstrucción del PIT (solo volúmenes) — **0 evaluaciones de estrategia** | log |
| Bundle | `git bundle create/verify` | ✅ | mensaje de entrega |

## Resultados

### A · Validación de t\*=0.025 (5000 sims por mundo, semillas NUEVAS, block20, n_perm=199)

| Mundo nulo (sin habilidad) | Semilla | FPR(p≤t\*) | FPR(p<0.05) | p medio | En [3.5,6.5] % |
|---|---|---|---|---|---|
| GBM | 987654321 | **4.60 %** | 7.46 % | 0.505 | ✅ |
| vol-MS (35/100 %, ~100 d) | 555444333 | **1.54 %** | 3.48 % | 0.472 | ❌ conservador |
| vol-MS + Poisson jumps | 246813579 | **2.26 %** | 4.76 % | 0.465 | ❌ conservador |

Lectura: el nivel 0.05 "a pelo" se pasa en GBM (7.5 %), confirmando la necesidad de t\*. Con t\*=0.025 el FPR queda **≤ 5 % en los tres mundos** (control del error tipo I preservado en todos), pero en mundos con regímenes de volatilidad el test es **conservador** (1.5-2.3 %): la permutación por bloques desacopla exposición y régimen de vol, ensanchando el nulo. Consecuencia: la potencia reportada es una **cota superior**. **Propuesta v1.4 (solo texto, sin tocar nivel ni rejilla):** sustituir "FPR 4.36 %" por "FPR(p≤t\*) ∈ [1.5 %, 4.6 %] validado en 3 mundos nulos × semillas nuevas; conservador bajo regímenes de volatilidad; potencia = cota superior". No propongo cambiar t\*: moverlo por mundo es imposible (el mundo real es desconocido) y subirlo rompería el control en GBM.

### B · Potencia del PIPELINE completo de H1 (200 mundos, 24 candidatas, ρ=0.8, t\*=0.025, RC B=200)

| ΔSharpe verdadero (SMA200 calibrado) | P(alguna compuesta) | P(RC rechaza) | **P(PIPELINE)** |
|---|---|---|---|
| ≈0.10 | 46 % | 9.5 % | **9.5 %** |
| ≈0.30 | 69 % | 20.5 % | **18.5 %** |
| ≈0.54 | 88 % | 63 % | **61 %** |

Nulo (verificado aparte): P(alguna compuesta) = 28.5 %, P(pipeline) = **0.5 %**. El cuello de botella es el RC familiar (su estadístico es la media de excesos diarios, ruidosa). Como la potencia con ΔSharpe=0.5 es 61 % ≥ 20 %, **no se dispara la pre-declaración automática de INCONTRASTABLE**; para 0.1-0.3 sí aplica la política de §8-H1 (INCONTRASTABLE por defecto si no hay rechazo). **Recomendación: EJECUTAR H1 en M3** — (i) coste marginal bajo (24 backtests diarios, minutos); (ii) el veredicto negativo o incontrastable bien documentado ES el producto según la misión; (iii) la infraestructura (permutaciones, RC, CPCV, ledger) la comparten H2/H3; (iv) el forward paper de M4 amplía la muestra sin coste de datos.

### C · §7.5 literal y n_trials del DSR de H3

Cita literal de PREREGISTRO v1.3 §7.5:

> **Anti-sobreajuste**: PBO vía CSCV sobre la rejilla de la familia; Reality Check/SPA sobre todas las celdas vs benchmark — **en H1 el estadístico de SPA/RC es la mejora de ΔmaxDD vol-matched (criterio primario de multiplicidad, condición 3 del gate M0)**; en H2/H3 el estadístico es el retorno/Sharpe neto. DSR (Bailey–López de Prado) con n_trials del ledger, asimetría y curtosis empíricas: **criterio de gate en H2 y H3; en H1 se computa y reporta, sin poder tumbar un PASA**.

Y §6 (contabilidad): *"n_trials por familia = filas en ledger/trials.duckdb … con suelo = rejilla pre-registrada (H1: 24, H2: 6, H3: 8; total 38)"*.

**Respuesta:** la lectura operativa actual es **FAMILIAR** (H3 → sus 8 trials del ledger, suelo 8): la selección de candidata y el veredicto ocurren dentro de la familia, que es la multiplicidad que el DSR debe deflactar. El "total 38" es una cota informativa. Reconozco que el texto admite ambas lecturas → **propuesta v1.4 (sin aplicar):** añadir a §7.5 "el n_trials del DSR es el de la FAMILIA en el ledger (suelo = rejilla familiar); el N global (38) se reporta junto al DSR por transparencia". Umbrales de Sharpe exigidos a H3 (6.13 años in-sample):

| n_trials | sd celdas 0.5 | sd celdas 0.75 |
|---|---|---|
| **8 (familiar)** | **1.40-1.41** | **1.76-1.78** |
| 38 (global) | 1.75-1.77 | 2.29-2.32 |

Con familiar-8 el listón es alcanzable para carry en regímenes históricamente observados; con global-38 sería casi prohibitivo y penalizaría a H3 por ensayos de OTRAS familias con las que no compite. Recomiendo la lectura familiar (que es la implementada) y la aclaración textual en v1.4.

### D · ADR-006 (antes → después)

| Parámetro | Antes | Después | Motivo |
|---|---|---|---|
| Señal | z iid | AR(1) φ=0.995 | con iid la banda no reduce turnover: la sangría de costes superaba al alpha (fallo de diseño del test, no del motor) |
| IC verdadero | 0.05 | 0.10 | acceptance test determinista: con 0.05 la no-detección es comportamiento ESPERADO (potencia baja documentada) |
| Tolerancia IC puntual | 0.02 | 0.05 | n efectivo ≈ 10 con φ=0.995 (error empírico observado 0.029) |
| Permutaciones | 399 | 999 | resolución del p-valor |
| **Nuevo test φ=0.9** | — | IC 0.05, L=12000, \|ic−IC\|<0.08 ≈ 2·se (n_eff≈630), IC verdadero dentro del IC bootstrap | condición D: recuperación puntual ajustada al n efectivo |

Lo que NO cambió: el criterio principal (IC verdadero dentro del IC bootstrap por bloques) y el nivel t\*=0.025.

### E · Holdout cifrado

- **Clave (32 bytes, hex):** entregada UNA sola vez por el canal del mensaje de
  entrega de este informe; **NO se escribe en el repo ni en el bundle** (la
  condición H.5 prohíbe secretos en el bundle; prevalece sobre la lectura
  literal de "muéstrala en el informe"). No persiste en ningún fichero del
  sandbox. El usuario debe custodiarla fuera del repo.
- Huella pública de la clave (validación sin revelarla): `ff356c4e2dbd2448`
  (en `holdout_sealed/SEALED.json`).
- Cifrado: gpg simétrico AES256; 3 blobs en `holdout_sealed/*.parquet.gpg`; plaintexts borrados.
- sha256 de plaintexts en `ledger/holdout_seal.log` (append-only): spot `8c8218ba…`, futures `7fcc0626…`, funding `ffd2de9c…` (coinciden con `dataset_meta.json` original).
- Guard runtime: `QA_HOLDOUT_UNLOCK=1` + `QA_HOLDOUT_KEY=<clave>`; verificación de huella + sha256 tras descifrar + fila en `ledger/holdout_access.log`. Apertura verificada técnicamente (125 048 filas, sha OK) y con clave falsa rechazada (PermissionError).
- Pérdida de clave: regeneración desde Binance con `QA_FREEZE_END=2026-10-25` (override añadido) + verificación contra los sha256 del ledger. Probado: la regeneración del PIT tras el sellado reproduce el sha256 original exacto (`9a4feb16…`).

### F · Segunda fuente independiente, período completo (Coinbase Exchange, USD)

| Activo | Días comunes | Ventana | Cum Binance (USDT) | Cum Coinbase (USD) | Δ (pp) | Corr diaria |
|---|---|---|---|---|---|---|
| BTC | 2 992 | 2017-08-17→2025-10-25 | +2505.47 % | +2509.02 % | **−3.55** | **0.9908** |
| ETH | 2 992 | idem | +1209.21 % | +1215.24 % | **−6.02** | **0.9934** |

Las diferencias son coherentes con el riesgo de base USDT/USD acumulado en 8 años (se reportan sin ajustar, como pidió la condición). Correlaciones > 0.99: las series son intercambiables para investigación de señales diarias.

### G · Adjudicación de artefactos (tabla sellada, con URLs)

| Símbolo | Fecha | log-ret | Clasificación | Anuncio (URL · fecha) |
|---|---|---|---|---|
| LUNAUSDT | 2022-05-31 | +12.09 | corporate_action | binance.com/en/support/announcement/detail/d044a6742e484b77a170111460b0eed3 · 2022-05-28 (listing Terra 2.0 en LUNA/USDT 06:00 UTC) |
| LUNAUSDT | 2022-05-12 | −8.12 | **real_move (íntegro)** | techcrunch.com/2022/05/12/binance-halts-luna-and-ust-trading-across-most-of-its-spot-pairs-following-meltdown/ · 2022-05-12 |
| VENUSDT | 2018-10-19 | −9.82 | corporate_action | binance.com/en/support/announcement/detail/360005001912 · 2018-06-22 (+ completion 360008162992 · 2018-07-24) |
| COCOSUSDT | 2021-01-23 | +7.17 | corporate_action | binance.com/en/support/announcement/detail/f555f8013eff42bc9c91eaa48b9da24b · 2021-01-18 (1000:1) |
| SUNUSDT | 2021-06-18 | −6.73 | corporate_action | binance.com/en/support/announcement/detail/f923f2e4056843a9a9b87beb2aaa2f31 · 2021-06-08 (1:1000) |

## Desviaciones del plan y su justificación

1. **Pérdida de `.git` del sandbox entre sesiones** → repo recuperado íntegro desde `quant-arena-M0b.bundle` (5 tags, firmas SSH verificadas post-recuperación, working tree == HEAD). Bundles regenerados cada turno desde ahora. El venv y los paquetes apt tampoco persisten (reinstalados; `make git-config` arregla la firma, cuya clave SÍ persiste en `.ssh` del workspace).
2. **Corrección Kraken** (ver sección Corrección del M2_REPORT): la limitación era la fecha de nacimiento del par (2024-11-06), no el parámetro `since`.
3. **FWER/potencia con n_perm=99** (vs 10 000 reales): aproximación documentada; con t\* el criterio es ligeramente conservador.
4. **El informe de calidad ahora reporta el holdout como "SELLADO (AES256)"** en vez de nº de filas: por diseño, la QA no descifra el holdout (las filas quedaron registradas en el sellado: 125 048 spot).
5. **Clave del holdout NO incluida en repo/bundle** (H.5 prevalece sobre la lectura literal de E): se entrega una única vez en el mensaje de entrega; blobs cifrados gitignored; la clave no persiste en el sandbox.

## Limitaciones y sesgos conocidos

- t\* es conservador bajo regímenes de volatilidad → la potencia real en mercado puede ser menor que la sintética reportada (cota superior).
- El RC es el cuello de botella de potencia del pipeline; alternativas (SPA studentizado, estadístico de max-DD en vez de media) quedan para una posible v1.4 futura si el orquestador lo pide — no se cambia nada ahora.
- Coinbase cotiza en USD (no USDT): la comparación F incluye base risk, declarada.
- La validación de fees es de la página pública (nivel Regular User); los fees reales de cuenta pueden verificarse en M4 con la cuenta paper (sin claves de trading).

## Riesgos abiertos

1. **R1 · M3 bloqueado por acciones del usuario**: push del bundle al remoto (CI verde) + registro OSF. Nada más pendiente por mi parte salvo Q1.
2. **R2 · Volatilidad del sandbox**: mitigada por bundles por turno + datos regenerables (`qa data sync` resumible) + holdout verificable por sha256.
3. **R3 · Custodia de la clave del holdout**: viaja solo en el mensaje de entrega (una vez). Si el usuario la pierde: regeneración desde Binance (`QA_FREEZE_END=2026-10-25`) + verificación sha256 contra `ledger/holdout_seal.log` (probado: reproduce hashes exactos).
4. **R4 · gpg no persistente en sandbox**: reinstalación documentada (`apt-get install -y gnupg`); tests con skipif.

## Preguntas para el orquestador (solo decisiones reales)

- **Q1 · ¿Apruebas la v1.4 propuesta (solo texto, pre-datos)?** Dos aclaraciones: (a) §7.3/§9.3: t\* validado en 3 mundos (FPR ∈ [1.5 %, 4.6 %], conservador bajo regímenes de vol; potencia = cota superior); (b) §7.5: n_trials del DSR es FAMILIAR (H3=8, umbral Sharpe ≈1.40-1.78) y el global 38 se reporta por transparencia. Se sellaría como v1.4 (tag firmado + OTS) antes de M3. Alternativa: mantener v1.3 y que esta interpretación quede registrada solo en este informe.
- **Q2 · Confirmación de la recomendación B**: ejecutar H1 en M3 pese a potencia 9.5-61 % (mi recomendación: SÍ, por las razones (i)-(iv) de Resultados B).

## Qué aprendimos (lenguaje llano)

- **Un test conservador es un test que casi nunca condena a un inocente**: en mundos con rachas de volatilidad, nuestro examen de timing suspende a los inocentes el 1.5-2.3 % de las veces (menos del 5 % prometido). Pierde potencia, pero no integridad.
- **Cifrar el examen final**: el holdout es ahora un sobre lacrado con combinación de 32 bytes; abrirlo deja firma (quién, cuándo, para qué, hash del contenido). Si la combinación se pierde, el contenido se puede rehacer desde Binance y el hash demuestra que es EL MISMO.
- **Los bundles son el cinturón de seguridad**: el sandbox perdió el historial git completo; el bundle de la semana pasada lo devolvió íntegro, con firmas verificables. Copia de seguridad no es paranoia, es método.
- **Rectificar es de científicos**: dijimos que Kraken "ignoraba un parámetro"; era que el par no existía antes de noviembre 2024. La corrección va firmada en el informe anterior, no borrada.
- **Dónde se atasca la potencia**: el pipeline H1 pierde casi toda su potencia en el Reality Check familiar (24 celdas compitiendo). Saber esto ANTES de ejecutar evita malinterpretar un "no significativo" como "no existe".

## Solicitud: GATE APROBADO M2b
