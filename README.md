# QUANT-ARENA v2

Laboratorio de investigación **reproducible** para responder una pregunta con rigor
estadístico: ¿existe alguna regla simple y de baja frecuencia con **ventaja neta de
costes** en criptomonedas líquidas?

> Un resultado negativo bien documentado es un resultado exitoso.
> Un resultado positivo mal validado es un fracaso.

## Reglas del proyecto

- **Sin dinero real**: ni claves de exchange, ni órdenes, ni webhooks/daemons. Solo
  endpoints públicos de lectura y paper trading (M4+).
- **Hipótesis antes que código**: todo está pre-registrado en
  [`docs/PREREGISTRO.md`](docs/PREREGISTRO.md) antes de ejecutarse.
- **Cero look-ahead**: invarianza por truncamiento en cada feature.
- **Todo backtest se registra solo** en el ledger `ledger/trials.duckdb`
  (append-only); el DSR lee `n_trials` de ahí, nunca de un número manual.
- **Holdout sellado**: los últimos 12 meses se evalúan una sola vez, al final de M3.
- **Ningún número sin trazabilidad**: `run_id`, hash de fichero o `[NO VERIFICADO]`.

## Estructura

```
quant-arena/
  docs/{adr/, LITERATURA.md, PREREGISTRO.md, GLOSARIO.md, evidence/}
  config/{universe.yaml, costs.yaml, hypotheses.yaml}
  src/qa/{data/, features/, strategies/, backtest/, stats/, forward/, report/, cli.py}
  scripts/{verify_sources.py, probe_binance.py, power_analysis.py}
  tests/{unit/, property/, integration/, synthetic/}
  data/{raw/, curated/, manifests/}
  reports/  ledger/
```

## Uso

```bash
make install          # crea .venv e instala el paquete + herramientas dev
make ci               # ruff + mypy --strict + pytest (mismos gates que CI)
make power            # re-genera el analisis de potencia (v1.2)
make verify-sources   # re-verifica la bibliografia contra Crossref/arXiv
make verify-endpoints # re-verifica endpoints/fees/minimos de Binance en vivo
make reproduce        # ci + power (reproduccion completa del hito actual)

qa data sync          # M1: ingesta cruda resumible (meta,monthly,pool,daily,futures,funding)
qa data curate        # M1: curacion + universo PIT + holdout sellado + informe de calidad
qa data verify        # M1: verifica SHA256 de los 1204+ ficheros (falla si algo cambia)
```

CLI (typer): `qa data sync | qa data curate | qa data verify | qa research run
--hypothesis H1 | qa stats report | qa forward run | qa report daily`. Los
comandos de research/stats/forward/report siguen siendo stubs hasta M2-M5.

## Hitos y Archivo Histórico

El proyecto avanzó a través de los hitos M0 a M6:
- **M0 preregistro** → **M1 datos** → **M2 validación estadística** → **M3 investigación** → **M4 forward paper** → **M5 boletín y dashboard** → **M6 Agente Autónomo Conquistador**.
- Los reportes, datos de holdout y bundles de hitos pasados han sido organizados en [`archive/`](archive/).
- Para más información sobre la estructura de directorios y la trazabilidad histórica, consulta [`docs/TRAZABILIDAD_PROYECTO.md`](docs/TRAZABILIDAD_PROYECTO.md).
