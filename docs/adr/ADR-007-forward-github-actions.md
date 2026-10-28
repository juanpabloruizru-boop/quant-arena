# ADR-007 · M4 forward-test en GitHub Actions con ledger hash-chain en el repo

**Fecha:** 2026-10-27 (M2c) · **Estado:** aceptado (condición H6 del gate M2b) ·
Diseño; la implementación es M4.

## Contexto

El forward-test en paper (M4) debe ejecutarse a diario sin intervención, con
estado append-only verificable y sellado temporal externo. El sandbox del
agente es **volátil por evidencia empírica**: perdió `.git`, el venv y los
paquetes apt entre sesiones (recuperados dos veces desde bundles). Cualquier
estado que viva solo en el sandbox puede desaparecer. El orquestador exige:
forward en GitHub Actions, ledger en el repo, sandbox fuera del camino del
estado.

## Decisión

1. **Ejecución:** workflow de GitHub Actions `forward.yml`:
   - `schedule` cron diario a las 00:30 UTC (tras el cierre de la vela diaria
     y los fundings de 00:00) + `workflow_dispatch` para one-shot manuales.
   - Sin daemons ni listeners: cada run nace, ejecuta, commitea y muere
     (one-shot, como exige el prompt).
   - Checkout del código **congelado en el tag `forward-v1`** (cualquier
     cambio de lógica = nuevo tag + nuevo preregistro + ledger reiniciado,
     según M4 del prompt).
2. **Datos:** el runner descarga de los endpoints públicos de Binance (solo
   lectura, sin secretos) las velas y el funding del día; valida unidades de
   timestamp (ms/µs) con los tests de M1.
3. **Ledger append-only con hash-chain, en el repo:**
   - `ledger/forward.jsonl`: una línea JSON por ejecución con
     `{ts_utc, run_id, git_sha, data_hashes, positions, fills, cash_virtual,
     prev_hash}` donde `prev_hash = sha256(línea anterior)` — cadena tipo
     blockchain: editar o borrar una línea histórica rompe todas las
     siguientes.
   - El propio workflow hace `git commit && git push` de la nueva línea con el
     `GITHUB_TOKEN` (permiso `contents: write`); el timestamp del commit en el
     remoto es un sello temporal de tercero (GitHub), y la historia del repo
     protegida hace el resto.
   - `qa forward verify-chain` recalcula la cadena completa (test de aceptación
     de M4).
   - DuckDB (`ledger/forward.duckdb`) se regenera DERIVADO del JSONL para
     consultas (el JSONL es la fuente de verdad versionada; nunca al revés).
4. **Reglas de decisión:** día 30 solo calidad de datos/bugs; evaluación
   estadística solo al n requerido por la potencia de M0; informe de cierre al
   día 90 (tal como exige M4 del prompt). Rellenos tardíos (runner caído):
   línea nueva con flag `late_fill` y hash del hueco documentado — nunca
   reescribir líneas anteriores.
5. **Snapshot diario comiteado = sello externo** (el remoto GitHub hace de
   tercero fechador); adicionalmente, anclaje OTS semanal del head de la
   cadena (automatizable en el mismo workflow).
6. **Sandbox:** solo desarrollo y pruebas; ningún estado de forward vive aquí.
7. **Secretos:** ninguno para el forward (datos públicos + paper). El token de
   Telegram (M5) irá como secret del repo, inyectado al workflow, nunca
   logueado ni commiteado.

## Alternativas descartadas

- Cron en el sandbox: volatilidad demostrada (dos pérdidas de estado en una
  semana); sin sello de tercero.
- VM/nube del usuario: coste y secretos de más; GitHub Actions ya está en el
  stack (CI) y es gratuito para repos privados con minutos suficientes.
- Ledger solo en DuckDB binario commiteado: diffs ilegibles y cadena de hash
  menos auditable; JSONL línea a línea es verificable por cualquiera con `jq`.
- Firmar cada commit con la clave del preregistro: posible (runner con clave
  dedicada), pero expone una clave firmante en CI; se prefiere hash-chain +
  timestamps del remoto + OTS semanal.

## Consecuencias

- El usuario debe crear el repo privado y activar Actions (ya necesario para
  la CI). Permisos del workflow: `contents: write`.
- La cadena es verificable por el orquestador en cualquier momento clonando
  el repo (independiente del sandbox).
- M4 añadirá: `forward.yml`, `src/qa/forward/` (motor paper, verify-chain),
  tests de cadena (append, detección de edición histórica) y el tag
  `forward-v1`.
