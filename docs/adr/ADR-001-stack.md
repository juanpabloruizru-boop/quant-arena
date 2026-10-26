# ADR-001 · Stack técnico y entorno de ejecución

**Fecha:** 2026-10-26 · **Estado:** aceptado (M0)

## Contexto

El prompt pide Python 3.12 + `uv`, Parquet+DuckDB, pandas o polars, pydantic v2,
typer, pytest/hypothesis, ruff, mypy --strict, pre-commit y CI. El entorno real
de trabajo (sandbox) tiene **Python 3.11.2**, `pip`/`venv` disponibles, y **sin
`uv`, sin `gpg` y sin `curl`** (verificado el 2026-10-26). Hay red saliente
(PyPI y APIs públicas de Binance responden).

## Decisión

- **Python:** `requires-python = ">=3.11"`. Local se desarrolla con 3.11.2;
  CI (GitHub Actions) corre con **3.12** (la versión objetivo del proyecto). El
  código debe pasar los gates en ambas (nada de sintaxis 3.12-only).
- **Gestor de entorno:** `venv + pip` local (Makefile `make install`); el
  `pyproject.toml` es estándar y compatible con `uv` (`uv pip install -e
  ".[dev]"` funciona igual) para cuando el entorno lo tenga. No se bloquea M0
  por la ausencia de `uv`.
- **DataFrame:** **pandas** (no polars). Motivos: (1) principio de simplicidad
  — el equipo/usuario es novato y pandas tiene más documentación y ejemplos;
  (2) el volumen de datos es pequeño (velas diarias/4H de decenas de activos:
  millones de filas como mucho), donde pandas sobra; (3) pyarrow+parquet y
  duckdb interoperan con ambas. Se pierde velocidad teórica; irrelevante aquí.
- **Almacenamiento:** Parquet inmutable (datos) + **DuckDB** (ledgers
  `trials`/`forward` append-only y consultas analíticas). DuckDB es embebido,
  sin servidor, transaccional y con SQL: encaja con "sin daemons".
- **CLI:** typer. **Esquemas:** pydantic v2. **HTTP:** httpx (tipado, timeouts
  explícitos, reintentos manuales con backoff).
- **Calidad:** ruff (lint+format, line-length 100), mypy --strict sobre
  `src/ scripts/ tests/`, pytest + hypothesis, pre-commit con los mismos gates
  que CI.
- **Sin dashboard:** informes en Markdown + HTML autocontenido (M5). Lección
  heredada: 80k LOC de dashboard no respondieron ninguna pregunta.

## Alternativas descartadas

- polars: más rápido, peor ratio documentación/complejidad para este tamaño.
- poetry/uv como requisito bloqueante: añadiría fricción sin valor en M0.
- SQLite para ledgers: DuckDB da mejor analítica (columnar) y SQL completo.
- Dashboards (Streamlit/Dash): prohibidos por el principio 8.

## Consecuencias

- Doble versión de Python (3.11 local / 3.12 CI): riesgo bajo, mitigado por CI.
- El tag `prereg-v1` no podrá ir firmado con GPG en este entorno (ver ADR-004).
