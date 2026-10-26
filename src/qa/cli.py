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
def data_sync() -> None:
    """Descarga datos crudos inmutables + manifiestos SHA256."""
    _todo("M1")


@data_app.command("verify")
def data_verify() -> None:
    """Verifica manifiestos; falla si cualquier fichero cambia."""
    _todo("M1")


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
