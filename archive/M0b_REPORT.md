> **CORRECCIÓN POST-GATE (2026-10-26, dictamen del orquestador — defecto 1):**
> El titular de §9.3 y el riesgo R1 de este informe ("H1 probablemente NO PASA",
> potencia 1-2 %) quedan **RETIRADOS**. El benchmark exposure-matched (ē·r) está
> sesgado por Jensen (E[w²] ≥ ē²) contra toda regla de exposición variable bajo el
> nulo: el +14/+17 pp medido bajo GBM era el sesgo del benchmark, no una propiedad
> de H1; y los "mundos alternativos" no contenían habilidad plantada, así que la
> "potencia 1-2 %" no era potencia. Corrección completa en PRERREGISTRO v1.2
> (benchmark primario vol-matched + criterio permutado + potencia con drift AR(1)
> calibrado a ΔSharpe ∈ {0.1, 0.3, 0.5}: potencia real 17-43 %) y en
> `reports/M0_power_analysis.md` v1.2. El resto del informe permanece válido.

# M0b · Preregistro v1.1 y sellado (condiciones del gate M0) · 2026-10-26T18:43Z · git SHA `3f3fbb1562fe4aebde4b5764372a6955b297fbb6` (tag firmado `prereg-v1.1`)

## Resumen en 5 líneas

1. **Las 4 condiciones del gate M0 están incorporadas al PRERREGISTRO v1.1** (tag firmado `prereg-v1.1` + OTS): benchmark primario de H1 = B&H matched-exposure con nulo de permutación de timing; co-métricas Ulcer/Calmar/time-underwater + regla de subperíodos (≥2 de 3, en BTC y ETH); DSR deja de vetar H1 (SPA/Reality Check sobre ΔmaxDD matched pasa a ser su control de multiplicidad; DSR sigue siendo primario en H3); tabla de grados de libertad congelada (§4).
2. **P1–P4 resueltas:** rejilla disjunta ratificada (12 celdas, n_trials=38 sin cambios); horizonte 2017/2019 aprobado con declaración de régimen 2017-18 y PIT fino pre-2019; ETH se mantiene en H3 con MDE por activo y regla 2×; OTS ejecutado ya, OSF antes de M3 (a falta de la cuenta del usuario).
3. **Sellado ejecutado:** tag `prereg-v1-signed` (SSH ed25519, verificado "Good git signature") sobre el MISMO commit `82bf430` sin tocar `prereg-v1`; hashes normativos v1.0 y v1.1 anclados en OpenTimestamps (4 calendarios; *Pending confirmation in Bitcoin blockchain* — normal, se re-verifica en M1 con `make ots-check`).
4. **El análisis de potencia v1.1 da una noticia dura y honesta:** contra el benchmark matched-exposure, el mecanismo H1 no mejora el drawdown en media en NINGUNO de los 3 mundos sintéticos alternativos (E[ΔmaxDD] ≈ +6 a +10 pp; potencia 1–2 %; regla compuesta 7–19 %), aunque el test es conservador bajo el nulo (FPR 2–3 %). H1 solo pasará si el mercado real anticipa crashes mejor que esos mundos. Está pre-declarado en PREREGISTRO §9.3.
5. Hallazgo de diseño pre-datos: el vol targeting con rebalanceo diario sangra el drawdown vía turnover; se pre-registra **banda de rebalanceo de 10 pp** (los flips long↔flat siempre operan). Gates verdes: ruff ✓ mypy --strict ✓ pytest 10/10 ✓.

## Entregables

| Ítem (condición del gate) | Ruta | Estado |
|---|---|---|
| (1) Benchmark primario H1 = matched-exposure + permutación | `docs/PREREGISTRO.md` §6-H1/§7.3, `config/hypotheses.yaml` (`benchmark_primary`, `permutation_null`) | ✅ v1.1 |
| (2) Co-métricas + subperíodos ≥2/3 en BTC y ETH | PREREGISTRO §6-H1/§8-C1b, hypotheses.yaml (`co_metrics`, `subperiods_utc`, `composite_rule`) | ✅ v1.1 |
| (3) DSR no gatea H1; SPA/RC sobre ΔmaxDD matched; DSR primario en H3 | PREREGISTRO §7.5/§8, hypotheses.yaml (`dsr_gating_for: [H2,H3]`) | ✅ v1.1 |
| (4) Grados de libertad documentados y congelados | PREREGISTRO §4 (tabla de 11 grados de libertad) | ✅ v1.1 |
| P1 rejilla disjunta ratificada | PREREGISTRO §6-H1 (nota "Ratificada… P1") | ✅ |
| P2 régimen 2017-18 + PIT fino pre-2019 | PREREGISTRO §3; ADR-002 addendum | ✅ |
| P3 OpenTimestamps YA | `docs/evidence/normative_hashes_v1.{0,1}.txt(.ots)` + logs | ✅ estampado; ancla BTC pendiente (horas) → `make ots-check` en M1 |
| P3 OSF antes de M3 | ADR-004 addendum §3 + checklist M3 | ⏳ requiere cuenta del usuario |
| P4 ETH en H3 + MDE por activo + regla 2× | PREREGISTRO §6-H3/§8-H3; hypotheses.yaml (`per_asset_mde_rule`) | ✅ |
| Tag SSH `prereg-v1-signed` (mismo commit `82bf430`) | `git tag -v prereg-v1-signed` → Good signature; `docs/evidence/ssh_signature_log.txt`; clave pública `docs/keys/prereg_signer_ed25519.pub` | ✅ prereg-v1 intacto |
| Tag v1.1 firmado | `prereg-v1.1` (SSH, verificado) sobre `3f3fbb1`, hashes en mensaje | ✅ |
| Remoto git para CI | prueba de push a remoto-bare local OK (`docs/evidence/remote_push_test_log.txt`); remoto real pendiente de URL/credenciales del usuario | ⚠️ ver P5 |
| Potencia v1.1 (matched-exposure, 4 DGPs, subperíodos, banda) | `scripts/power_analysis.py` → `reports/M0_power_analysis.md/.json` (T3/T3b) | ✅ determinista, semilla 20261026 |
| ADR-005 (criterio primario H1) | `docs/adr/ADR-005-h1-matched-exposure.md` | ✅ |
| Glosario ampliado | `docs/GLOSARIO.md` (+7 términos v1.1) | ✅ |

## Gates

| Gate | Comando | Resultado | Evidencia |
|---|---|---|---|
| Lint | `ruff check . && ruff format --check .` | ✅ All checks passed | consola 2026-10-26T18:40Z |
| Tipos | `mypy` (strict) | ✅ Success: 15 files | idem |
| Tests (incluye congelación rejilla v1.1 + guards de seguridad) | `pytest` | ✅ 10 passed | idem |
| Potencia v1.1 regenerada | `make power` | ✅ T3/T3b con 4 DGPs | `reports/M0_power_analysis.json` (semilla 20261026) |
| Firma SSH v1.0 | `git tag -v prereg-v1-signed` | ✅ Good "git" signature ED25519 `SHA256:SyPjyq4EimJ2X48XuJRQgHiIh/5XFHYqhC/Sd86OyYQ` | `docs/evidence/ssh_signature_log.txt` |
| Firma SSH v1.1 | `git tag -v prereg-v1.1` | ✅ Good signature (misma clave) | salida de consola; tag sobre `3f3fbb1` |
| OTS v1.0 / v1.1 | `ots stamp` + `ots verify` | ✅ estampado en 4 calendarios; verify = *Pending confirmation in Bitcoin blockchain* (esperado) | `docs/evidence/ots_stamp_log_v1.{0,1}.txt`, ficheros `.ots` |
| prereg-v1 intacto | `git for-each-ref refs/tags` | ✅ `prereg-v1` y `prereg-v1-signed` → `82bf430`; `prereg-v1.1` → `3f3fbb1` | idem |
| Push limpio (ramas+tags) | `git push mirror main --tags` (bare local) | ✅ 3 tags + main viajan | `docs/evidence/remote_push_test_log.txt` |

## Resultados

### v1.1 — cambios normativos (resumen; detalle en el diff de PREREGISTRO §12)

- H1: primario = ΔmaxDD vs **matched-exposure** (`ē·r[t]`, ē por periodo de evaluación) con **p de permutación < 0.05** (bloques circulares 20 d, 10 000, semilla fija) **en BTC y ETH**, + mejora en **≥2 de 3 subperíodos** por activo; SPA/RC sobre ΔmaxDD matched como control de multiplicidad; DSR informativo; banda de rebalanceo 10 pp; co-métricas Ulcer/Calmar/time-underwater siempre reportadas.
- H2/H3: criterios v1.0 sin cambios (DSR gate); H3 añade regla P4 (MDE por activo; ETH INCONTRASTABLE en solitario si MDE_ETH > 2×MDE_BTC).
- n_trials: **38** (sin cambios; permutaciones y benchmarks se registran con `kind` ≠ trial).

### Potencia v1.1 (T3b, 8.2 años, 1 200 sims/config, σ_obj 25 %, coste 13 pb/lado, banda 10 pp)

| Mundo sintético | E[ΔmaxDD vs crudo] | potencia (crudo) | E[ΔmaxDD vs matched] | potencia (matched) | P(regla compuesta) |
|---|---|---|---|---|---|
| GBM iid (nulo, sin habilidad) | −36 a −41 pp | 82–93 % | **+14 a +17 pp** | 0.2–0.3 % | 2–3 % |
| Vol MS (35 %/100 %, ~100 d) | −44 a −47 pp | 97 % | **+7.6 a +8.3 pp** | 1.5–1.6 % | 16–17 % |
| Vol MS + crashes Poisson (2/año altos) | −44 a −48 pp | 98–99 % | **+6.4 a +6.9 pp** | ≈2 % | 16–19 % |
| Deriva MS (bull +80 %/bear −40 %) | −45 a −48 pp | 98 % | **+10.2 a +10.4 pp** | <1 % | 7–8 % |

Lecturas pre-registradas (PREREGISTRO §9.2-9.3):
1. Contra B&H **crudo**, la mejora de DD sale "significativa" hasta en el mundo sin habilidad → confirma que la condición 1 del orquestador era necesaria: ese test medía exposición, no timing.
2. Contra **matched-exposure**, el mecanismo H1 (tal como está especificado) NO mejora el drawdown en media en ningún mundo probado; el test es conservador bajo el nulo (2–3 % < 5 % nominal). Conclusión honesta: **H1 solo pasará si el mercado real tiene estructura anticipatoria de crashes superior a la de estos mundos sintéticos**. El espectro de veredictos probables (NO PASA / INCONTRASTABLE) queda declarado ANTES de ver datos.
3. ΔSharpe matched: E ≈ −0.10 a +0.07 (potencia 1–8 %) → coherente con mantener Sharpe solo como no-inferioridad práctica (≥ −0.10) dentro de C4.
4. Hallazgo de diseño: sin banda de rebalanceo, el turnover diario del vol targeting empeora ΔmaxDD matched ~1 pp de media por sangría de costes → banda 10 pp pre-registrada (grado de libertad congelado, §4).

### Sellado (estado al cierre de M0b)

- `prereg-v1` → `82bf430` (intacto) · `prereg-v1-signed` → `82bf430` (SSH, verify OK) · `prereg-v1.1` → `3f3fbb1` (SSH, verify OK).
- OTS: v1.0 y v1.1 estampados (4 calendarios). Ancla BTC *pending* (horas); checklist M1: `make ots-check` hasta `success` con altura de bloque, y guardar el log.
- OSF: pendiente de cuenta del usuario (deadline: antes de M3).

## Desviaciones del plan y su justificación

1. **Banda de rebalanceo 10 pp añadida a H1** (no estaba en v1.0): cambio de diseño PRE-datos descubierto por el propio análisis de potencia (turnover diario ⇒ sangría de costes). Legítimo: no se ha visto ningún dato real; queda congelado como grado de libertad (§4) y registrado en el changelog v1.1.
2. **`openssh-client` instalado vía apt en el sandbox** para poder firmar (no existía). Los paquetes del sandbox no persisten entre sesiones: `make git-config` re-aplica la configuración de firma, y la verificación por terceros solo necesita la clave pública committeada.
3. **OTS en estado "Pending confirmation in Bitcoin blockchain"**: es el estado normal inmediato al estampado (los calendarios agregan al ancla BTC en horas). No es un fallo; la verificación definitiva entra en el checklist M1.
4. **Remoto git real todavía no configurado**: no existen URL/credenciales en el entorno (y el prompt prohíbe inventarlas). Se validó el flujo completo contra un remoto-bare local (main + 3 tags viajan limpios) y se dejaron las instrucciones exactas. Ver P5.
5. **`.git/config` no persiste en snapshots del entorno**: documentado en ADR-004 addendum; mitigado con `make git-config`.

## Limitaciones y sesgos conocidos

- Los DGPs sintéticos (GBM, vol MS, vol MS + Poisson jumps, deriva MS) son **planos por construcción**: no capturan todo lo que podría dar skill real a H1 (p. ej., subida de vol semanas ANTES de los crashes, cascadas de apalancamiento, microestructura). La potencia reportada es una cota inferior informativa, no una predicción del veredicto real.
- Las potencias de la regla compuesta/permutación se aproximan con el ensemble MC (sd entre trayectorias), no simulando la distribución de permutación completa por trayectoria (coste computacional); la aproximación es conservadora en el nulo (FPR 2–3 % < 5 %).
- `ē` del benchmark matched se calcula dentro de cada periodo de evaluación (in-sample completo/subperíodo/fold): es ex-post por definición de benchmark; se congela así en §4 para evitar grados de libertad.
- La firma SSH acredita control de la clave del proyecto, no identidad civil; la anterioridad frente a terceros la aporta OTS (y OSF en cuanto exista cuenta).

## Riesgos abiertos

1. **R1 · H1 probablemente NO PASA/INCONTRASTABLE** (declarado): riesgo de "gastar" M3 en una familia con baja probabilidad de éxito. Mitigación: es barato (12 celdas × 2 activos, datos diarios) y su resultado negativo bien documentado vale según la misión; además la infraestructura (permutaciones, matched benchmark, subperíodos) la reutilizan H2/H3.
2. **R2 · Ancla OTS pendiente**: si los calendarios fallaran, re-stamp y log. Verificación obligatoria en M1.
3. **R3 · Sin remoto real**: la CI no se estrena hasta que el usuario proporcione el repo (P5). Los gates se ejecutan en local idénticos.
4. **R4 · Clave de firma en el sandbox**: quien controle el workspace controla la clave (autoatestiguado). OSF antes de M3 cierra este flanco (reloj de tercero).
5. **R5 · ETH funding más corto de lo esperado**: cubierto por la regla P4 (MDE por activo; umbral 2×).

## Preguntas para el orquestador (solo decisiones reales)

- **P5 · Remoto git (capital/alcance técnico):** configurar la CI real requiere un remoto GitHub (u otro) con credenciales aportadas por el usuario. ¿Quién lo crea y cuándo? Instrucciones listas: `git remote add origin <URL> && git push -u origin main --tags`. Sin esto, los gates siguen corriendo en local (mismos comandos que el workflow).
- **P6 · Confirmación de no-relajación de H1 (pre-registro):** la potencia v1.1 indica que el mecanismo H1 tal como está especificado tiene baja probabilidad de superar el criterio matched-exposure en mundos sintéticos plausibles. Por defecto **NO tocamos nada** (la rejilla y el sizing quedan como están; cualquier cambio ahora sería v1.2 pre-datos y legítimo, pero debe pedirlo el orquestador, no yo). ¿Se confirma ejecutar H1 exactamente como está pre-registrada?

## Qué aprendimos (lenguaje llano)

- **"Estar menos expuesto" no es habilidad.** Contra el B&H crudo, casi cualquier filtro que te sane del mercado "mejora" el drawdown. El benchmark matched-exposure pone al rival la misma exposición media que tú: si entonces no mejoras, no había timing, solo menos tamaño. Es como comparar a dos conductores con el mismo número de kilómetros: gana quien frene mejor, no quien conduzca menos.
- **Un test bueno también se mide por sus falsos positivos:** bajo el mundo-nulo (GBM), nuestra regla compuesta solo "aprueba" el 2–3 % de las veces (por debajo del 5 % nominal): el test es conservador, no tramposo.
- **Las comisiones castigan el retocar a diario:** ajustar la posición todos los días (vol targeting sin banda) cuesta más de lo que aporta; una banda de 10 puntos porcentuales lo arregla. Lo descubrimos simulando, ANTES de tocar datos reales — para eso sirve la potencia pre-datos.
- **OpenTimestamps = notario con reloj de Bitcoin:** mandas el hash de tu documento a calendarios públicos que lo agregan a un bloque de Bitcoin; desde entonces nadie (ni nosotros) puede borrar esa fecha. Tarda horas en confirmarse.
- **Firmar con SSH vs "sellar en Git":** un tag normal lo puede reescribir el dueño del repo; un tag firmado con una clave cuya parte pública está publicada permite a cualquiera verificar que nadie lo alteró, y OTS prueba CUÁNDO existía.

## Solicitud: GATE APROBADO M0b
