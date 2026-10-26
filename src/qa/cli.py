"""CLI minima de QUANT-ARENA v2 (typer).

En M0 todos los comandos son stubs que salen con codigo 3 ("no implementado"):
el hito M0 es preregistro y diseno, sin codigo de datos. Los comandos se activan
segun el plan de hitos (M1: data; M2: stats; M3: research; M4: forward; M5: report).

Todo comando sera determinista (semillas fijas en config) y registrara sus
ejecuciones en el ledger correspondiente antes de devolver resultados.
"""

from __future__ import annotations

from typing import Annotated

import typer

app = typer.Typer(help="QUANT-ARENA v2 - laboratorio de investigacion (sin dinero real)")
data_app = typer.Typer(help="Ingesta y verificacion de datos (M1)")
research_app = typer.Typer(help="Ejecucion de hipotesis pre-registradas (M3)")
stats_app = typer.Typer(help="Estadistica y validacion anti-sobreajuste (M2)")
forward_app = typer.Typer(help="Forward-test en paper (M4)")
report_app = typer.Typer(help="Boletin informativo (M5)")

app.add_typer(data_app, name="data")
app.add_typer(research_app, name="research")
app.add_typer(stats_app, name="stats")
app.add_typer(forward_app, name="forward")
app.add_typer(report_app, name="report")

NOT_IMPLEMENTED_EXIT = 3


def _todo(milestone: str) -> None:
    typer.echo(
        f"NO IMPLEMENTADO: previsto en {milestone}. Estado actual: M0 (preregistro y diseno)."
    )
    raise typer.Exit(code=NOT_IMPLEMENTED_EXIT)


@data_app.command("sync")
def data_sync(
    phases: Annotated[
        str,
        typer.Option("--phases", help="meta,monthly,pool,daily,futures,funding o 'all'"),
    ] = "all",
) -> None:
    """Descarga datos crudos inmutables (resumible) + manifiestos SHA256. M1."""
    import json as _json

    from qa.data.paths import get_root
    from qa.data.sync import run_sync

    log = run_sync(get_root(), phases)
    typer.echo(_json.dumps(log, indent=2, default=str))


@data_app.command("curate")
def data_curate() -> None:
    """Curacion + universo PIT + holdout sellado + informe de calidad. M1."""
    import json as _json

    from qa.data.curate import run_curate
    from qa.data.paths import get_root, reports_dir
    from qa.data.pit import run_pit
    from qa.data.quality import render_quality_md, run_quality

    root = get_root()
    meta = run_curate(root)
    typer.echo(f"curate: {len(meta['files'])} ficheros, dups={meta['duplicates_removed']}")
    pit_meta = run_pit(root)
    typer.echo(f"pit: {_json.dumps(pit_meta, indent=2)}")
    result = run_quality(root)
    md = render_quality_md(result)
    (reports_dir(root) / "M1_data_quality.md").write_text(md, encoding="utf-8")
    typer.echo(f"quality: fallos de manifiesto={len(result['manifest_failures'])}")


@data_app.command("verify")
def data_verify() -> None:
    """Verifica manifiestos SHA256; falla (exit 1) si cualquier fichero cambia."""
    from qa.data.manifest import Manifest
    from qa.data.paths import get_root

    root = get_root()
    failures: list[str] = []
    total = 0
    for name in ("meta", "spot_monthly", "spot_daily", "futures_daily", "funding", "curated"):
        m = Manifest(root, name)
        total += len(m)
        failures.extend(m.verify())
    if failures:
        for f in failures[:50]:
            typer.echo(f"FAIL {f}")
        typer.echo(f"{len(failures)} fallo(s) de {total} ficheros")
        raise typer.Exit(code=1)
    typer.echo(f"OK: {total} ficheros verificados (SHA256)")


@research_app.command("run")
def research_run(
    hypothesis: Annotated[str, typer.Option("--hypothesis", "-h", help="H1 | H2 | H3")] = "H1",
) -> None:
    """Ejecuta una hipotesis pre-registrada (registro obligatorio en trials)."""
    _todo(f"M3 (hipotesis solicitada: {hypothesis})")


@stats_app.command("report")
def stats_report() -> None:
    """Informe estadistico agregado desde el ledger de trials."""
    _todo("M2")


@forward_app.command("run")
def forward_run() -> None:
    """Ejecucion one-shot del forward-test en paper (sin daemon)."""
    _todo("M4")


@report_app.command("daily")
def report_daily() -> None:
    """Genera el boletin diario (Telegram one-shot + HTML autocontenido)."""
    _todo("M5")


if __name__ == "__main__":
    app()
