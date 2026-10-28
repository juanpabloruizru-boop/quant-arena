"""CLI minima de QUANT-ARENA v2 (typer).

En M0 todos los comandos son stubs que salen con codigo 3 ("no implementado"):
el hito M0 es preregistro y diseno, sin codigo de datos. Los comandos se activan
segun el plan de hitos (M1: data; M2: stats; M3: research; M4: forward; M5: report).

Todo comando sera determinista (semillas fijas en config) y registrara sus
ejecuciones en el ledger correspondiente antes de devolver resultados.
"""

from __future__ import annotations

from datetime import UTC
from typing import Annotated, Any

import typer

app = typer.Typer(help="QUANT-ARENA v2 - laboratorio de investigacion (sin dinero real)")
data_app = typer.Typer(help="Ingesta y verificacion de datos (M1)")
research_app = typer.Typer(help="Ejecucion de hipotesis pre-registradas (M3)")
stats_app = typer.Typer(help="Estadistica y validacion anti-sobreajuste (M2)")
forward_app = typer.Typer(help="Forward-test en paper (M4)")
report_app = typer.Typer(help="Boletin informativo (M5)")
agent_app = typer.Typer(help="Agente operativo M4/M5 (estados + tracker + vigilancia)")
trade_app = typer.Typer(help="Registro de operaciones del USUARIO (el agente no abre nada)")

app.add_typer(data_app, name="data")
app.add_typer(research_app, name="research")
app.add_typer(stats_app, name="stats")
app.add_typer(forward_app, name="forward")
app.add_typer(report_app, name="report")
app.add_typer(agent_app, name="agent")
app.add_typer(trade_app, name="trade")

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
    hypothesis: Annotated[
        str, typer.Option("--hypothesis", "-h", help="H1 | H2 | H3 | all | stats")
    ] = "H1",
) -> None:
    """Ejecuta una familia pre-registrada (M3a in-sample; registro obligatorio en trials)."""
    import sys as _sys
    from pathlib import Path as _Path

    _sys.argv = ["run_m3a", "--family", hypothesis.lower()]
    _repo = _Path(__file__).resolve().parents[2]
    exec(
        compile((_repo / "scripts" / "run_m3a.py").read_text(), "run_m3a", "exec"),
        {"__name__": "__main__", "__file__": str(_repo / "scripts" / "run_m3a.py")},
    )


@stats_app.command("report")
def stats_report() -> None:
    """Informe agregado desde el ledger de trials (M2: registros y n_trials)."""
    import json as _json

    from qa.backtest.trials import TrialLedger
    from qa.data.paths import get_root

    root = get_root()
    ledger_path = root / "ledger" / "trials.duckdb"
    if not ledger_path.exists():
        typer.echo("Ledger de trials vacio (todavia no se ha ejecutado ningun backtest).")
        raise typer.Exit(code=0)
    led = TrialLedger(root)
    rows = led.all_trials()
    typer.echo(f"trials registrados: {len(rows)}")
    for h in ("H1", "H2", "H3"):
        typer.echo(f"  n_trials[{h}] (kind=strategy): {led.n_trials(h)}")
    for r in rows[-10:]:
        m = _json.loads(r["metrics"]) if r["metrics"] else {}
        typer.echo(
            f"  {r['ts_utc']} {r['hypothesis']}/{r['cell_id']}/{r['asset']} "
            f"[{r['kind']}] sharpe={m.get('sharpe_ann')} mdd={m.get('max_drawdown')}"
        )
    led.close()


@forward_app.command("run")
def forward_run(
    capital: Annotated[
        float, typer.Option("--capital", help="Capital paper inicial (USDT), solo al crear estado")
    ] = 10_000.0,
) -> None:
    """Forward paper v1 (ADR-007): fills t+1 sobre las 5 celdas congeladas.

    Usa SOLO velas diarias cerradas (fetch_live descarta la vela en formación):
    la señal se computa con datos <= D-1 y el fill se ejecuta al cierre de
    D-1 — la misma convención del backtest de investigación. Contabilidad
    simulada con costes nivel estrés y funding real; cada paso se encadena en
    ledger/forward.jsonl. Ninguna orden real sale de este proceso.
    """
    import json as _json
    from datetime import datetime

    import pandas as _pd

    from qa.agent.live import fetch_extra_daily, fetch_live
    from qa.agent.signals import compute_states
    from qa.data.paths import get_root
    from qa.data.pit import membership_at
    from qa.forward.paper import (
        append_record,
        init_state,
        load_state,
        run_step,
        save_state,
        verify_forward_chain,
    )

    root = get_root()
    now = datetime.now(UTC)
    pit = _pd.read_parquet(root / "data" / "curated" / "pit_universe.parquet")
    members = membership_at(pit, _pd.Timestamp.now(tz=UTC), 10)
    live = fetch_live(sorted({"BTCUSDT", "ETHUSDT"} | set(members)))
    extra = fetch_extra_daily([m for m in members if m not in live["klines"]])
    for sym, df in extra.items():
        live["klines"].setdefault(sym, {})["1d"] = df
    states = compute_states(live, members)
    cells = states["cells"]
    h3_active = {
        a: bool(cells.get(f"H3_{a}", {}).get("senal_activa", False)) for a in ("BTCUSDT", "ETHUSDT")
    }
    basket = list(cells.get("H2_L26_N10", {}).get("cesta_teoretica", []) or [])
    weights = {sym: 1.0 / len(basket) for sym in basket} if basket else {}
    daily = {sym: frames.get("1d") for sym, frames in live["klines"].items()}
    funding = live.get("funding", {})

    state = load_state(root)
    if state is None:
        state = init_state(capital, now)
        typer.echo(f"Estado forward-v1 inicializado: {capital:,.0f} USDT paper (4 sleeves x 25 %).")
    record, equities = run_step(state, cells, weights, daily, funding, now, h3_active)
    append_record(root, record)
    save_state(root, state)
    typer.echo(
        f"Paso forward-v1: fills={len(record['fills'])} · "
        f"funding={record['funding_usd']:+.2f} USD · H3 activa={h3_active}"
    )
    typer.echo(
        f"Patrimonios paper (USDT): {_json.dumps(equities)} · TOTAL "
        f"{record['total_equity_usdt']:,} ({record['total_return_pct']:+.3f} %)"
    )
    ok, n, msg = verify_forward_chain(root)
    typer.echo(f"Cadena forward: {'OK' if ok else 'ROTO'} · {n} registros ({msg})")
    if not ok:
        raise typer.Exit(code=1)


@report_app.command("daily")
def report_daily() -> None:
    """Boletin: el canal principal es el dashboard (`qa agent run`).

    Telegram queda pendiente del token del usuario (.env); hasta entonces este
    comando regenera el dashboard y lo indica.
    """
    typer.echo("Canal Telegram pendiente de TELEGRAM_BOT_TOKEN (.env). Usa `qa agent run`.")
    raise typer.Exit(code=0)


@agent_app.command("run")
def agent_run() -> None:
    """One-shot: ingesta viva -> estados + tracker + vigilancia -> dashboard."""
    import json as _json

    import pandas as _pd
    import yaml as _yaml

    from qa.agent.live import fetch_extra_daily, fetch_live, last_price
    from qa.agent.news import detect_shocks, fetch_news
    from qa.agent.signals import compute_states
    from qa.agent.telemetry import h1_levels, trade_geometry, watchlist_telemetry
    from qa.agent.tracker import diagnose, load_trades, verify_chain
    from qa.data.paths import get_root, reports_dir
    from qa.data.pit import membership_at
    from qa.report.dashboard import render_dashboard

    root = get_root()
    cfg = _yaml.safe_load((root / "config" / "watchlist.yaml").read_text(encoding="utf-8"))
    watchlist = list(cfg["watchlist"])
    pit = _pd.read_parquet(root / "data" / "curated" / "pit_universe.parquet")
    members = membership_at(pit, _pd.Timestamp.now(tz=UTC), 10)

    live = fetch_live(sorted(set(watchlist) | {"BTCUSDT", "ETHUSDT"}))
    extra = fetch_extra_daily([m for m in members if m not in live["klines"]])
    for sym, df in extra.items():
        live["klines"].setdefault(sym, {})["1d"] = df
    states = compute_states(live, members)

    trades = load_trades(root)
    ok, n_lines, msg = verify_chain(root)
    if not ok:
        typer.echo(f"CADENA DE OPERACIONES ROTA: {msg}")
        raise typer.Exit(code=1)

    bases = sorted(
        {t["asset"].replace("USDT", "") for t in trades}
        | {w.replace("USDT", "") for w in watchlist}
    )
    news_cfg = cfg["noticias"]
    news_items, feed_status = fetch_news(
        news_cfg["feeds"],
        list(news_cfg["keywords_riesgo"]),
        bases,
        int(news_cfg.get("max_age_hours", 72)),
    )
    shocks = detect_shocks(live["klines"], live["premium"], cfg.get("choques", {}))

    # telemetria descriptiva (ADR-008 ratificado: hechos matematicos del precio, no senales)
    tele = watchlist_telemetry(dict(live["klines"]))
    capital_ref = float(cfg.get("capital_ref_usd", 0.0))
    h1_lv: dict[str, Any] = {}
    for asset in ("BTCUSDT", "ETHUSDT"):
        st = states["cells"].get(f"H1_{asset}")
        d1 = live["klines"].get(asset, {}).get("1d")
        if st and d1 is not None and not d1.empty:
            h1_lv[asset] = h1_levels(d1, float(st["posicion_regla"]), capital_ref)

    diags = []
    for t in trades:
        if t.get("status") != "open":
            diags.append({**diagnose(t, None, "", []), "example": t.get("example", False)})
            continue
        px = last_price(live, t["asset"])
        if px is None:
            d1 = live["klines"].get(t["asset"], {}).get("1d")
            px = float(d1["close"].iloc[-1]) if d1 is not None and not d1.empty else None
        base = t["asset"].replace("USDT", "")
        st = states["cells"].get(f"H1_{t['asset']}")
        if st:
            ctx = (
                f"1D close {st['close_vs_sma50_pct']:+.1f}% vs SMA50; "
                f"regla investigada en estado {st['estado']}"
            )
        else:
            ctx = "sin regla validada para este activo (ver ADR-008)"
        alerts = [
            f"choque {s['tipo']}: {s['detalle']}" for s in shocks if s["symbol"] == t["asset"]
        ]
        # solo noticias CON keyword de riesgo disparan REVISAR; la mera mencion
        # del activo es contexto (ya aparece en el panel de noticias)
        alerts += [
            f"noticia de riesgo [{','.join(n.keywords)}] {n.title[:90]}"
            for n in news_items
            if n.keywords and base.upper() in [a.upper() for a in n.assets]
        ]
        d = diagnose(t, px, ctx, alerts[:4])
        d.update(trade_geometry(t, px))
        tf_key = {"1w": "1w", "1s": "1w", "4h": "4h"}.get(
            (t.get("timeframe") or "1d").lower(), "1d"
        )
        tl = tele.get(t["asset"], {}).get(tf_key) or {}
        if tl.get("disponible"):
            d["sma50_marco_txt"] = (
                f"SMA50({tf_key}) {tl['sma50']} — precio {tl['lado_sma50']} "
                f"({tl['dist_sma50_pct']:+}%)"
            )
        d["example"] = t.get("example", False)
        diags.append(d)

    spark = {}
    for sym in ("BTCUSDT", "ETHUSDT"):
        d1 = live["klines"].get(sym, {}).get("1d")
        if d1 is not None and not d1.empty:
            spark[sym] = [float(x) for x in d1["close"].tail(90)]

    import subprocess as _sp

    try:
        sha = _sp.run(
            ["git", "rev-parse", "HEAD"], cwd=root, capture_output=True, text=True, timeout=10
        ).stdout.strip()
    except Exception:
        sha = "unknown"
    meta = {
        "git_sha": sha,
        "evidencia": {
            "filas": [
                [
                    "H1 tendencia BTC/ETH (sma50_s25)",
                    "IS 8.2a: CAGR 31.8%/27.2%, MDD 33.9%/24.7%",
                    "Holdout 25-26: +10.0%/+18.0% vs B&H -30%/-44%",
                    "INCONTRASTABLE (sin ventaja demostrada)",
                ],
                [
                    "H2 momentum (L26_N10)",
                    "IS: CAGR 6.0%, MDD 90.4%",
                    "Holdout: -38.1% vs EW -45.1%",
                    "INCONTRASTABLE",
                ],
                [
                    "H3 carry BTC (w30_t5)",
                    "IS: CAGR 11.2%, MDD 2.1%, Sharpe 7.3",
                    "Holdout: +0.95%, MDD 0.4%",
                    "PASA a nivel de signo (costes x2 ~ 0: edge fragil)",
                ],
                [
                    "H3 carry ETH (w30_t5)",
                    "IS: CAGR 14.4%, MDD 1.7%",
                    "Holdout: -1.35% (costes>funding)",
                    "NO PASA",
                ],
            ]
        },
    }
    html_out = render_dashboard(
        states,
        diags,
        [n.__dict__ for n in news_items],
        feed_status,
        shocks,
        spark,
        meta,
        telemetry=tele,
        h1_levels=h1_lv,
        capital_ref=capital_ref,
    )
    outdir = reports_dir(root) / "dashboard"
    outdir.mkdir(parents=True, exist_ok=True)
    (outdir / "index.html").write_text(html_out, encoding="utf-8")
    typer.echo(f"dashboard -> {outdir / 'index.html'}")
    typer.echo(f"operaciones: {len(trades)} (cadena: {n_lines} lineas, {msg})")
    typer.echo(f"choques: {len(shocks)} | noticias relevantes: {len(news_items)}")
    typer.echo(
        "estados: "
        + _json.dumps(
            {
                k: (v.get("estado") or v.get("cesta_teoretica") or v.get("senal_activa"))
                for k, v in states["cells"].items()
            },
            default=str,
        )
    )


@trade_app.command("open")
def trade_open(
    asset: Annotated[str, typer.Option("--asset")],
    kind: Annotated[str, typer.Option("--kind", help="spot|future_long|future_short")],
    timeframe: Annotated[str, typer.Option("--timeframe")] = "1d",
    entry: Annotated[float, typer.Option("--entry")] = 0.0,
    size_usd: Annotated[float, typer.Option("--size-usd")] = 0.0,
    sl: Annotated[float, typer.Option("--sl")] = 0.0,
    tp: Annotated[float, typer.Option("--tp")] = 0.0,
    note: Annotated[str, typer.Option("--note")] = "",
    example: Annotated[bool, typer.Option("--example")] = False,
) -> None:
    """Registra una operacion ABIERTA POR TI (el agente nunca abre nada)."""
    from qa.agent.tracker import open_trade
    from qa.data.paths import get_root

    rec = open_trade(
        get_root(),
        asset,
        kind,
        timeframe,
        entry,
        size_usd,
        sl or None,
        tp or None,
        note,
        example,
    )
    typer.echo(
        f"registrada: id={rec['id']} {asset} {kind} entrada={entry} tam=${size_usd} "
        f"SL={sl or '—'} TP={tp or '—'}{' [EJEMPLO]' if example else ''}"
    )


@trade_app.command("close")
def trade_close(
    id: Annotated[str, typer.Option("--id")],
    exit: Annotated[float, typer.Option("--exit")],
    note: Annotated[str, typer.Option("--note")] = "",
) -> None:
    """Registra el cierre de una operacion."""
    from qa.agent.tracker import close_trade
    from qa.data.paths import get_root

    close_trade(get_root(), id, exit, note)
    typer.echo(f"cerrada {id} a {exit}")


@trade_app.command("list")
def trade_list() -> None:
    """Lista operaciones (abiertas y cerradas)."""
    import json as _json

    from qa.agent.tracker import load_trades
    from qa.data.paths import get_root

    for t in load_trades(get_root()):
        typer.echo(_json.dumps(t, default=str))


@trade_app.command("status")
def trade_status() -> None:
    """Diagnostico descriptivo de las operaciones abiertas (precios vivos)."""
    from qa.agent.live import fetch_live, last_price
    from qa.agent.news import detect_shocks, fetch_news
    from qa.agent.telemetry import trade_geometry
    from qa.agent.tracker import diagnose, load_trades
    from qa.data.paths import get_root

    root = get_root()
    trades = [t for t in load_trades(root) if t.get("status") == "open"]
    if not trades:
        typer.echo("sin operaciones abiertas")
        return
    assets = sorted({t["asset"] for t in trades} | {"BTCUSDT", "ETHUSDT"})
    live = fetch_live(assets)
    shocks = detect_shocks(live["klines"], live["premium"], {})
    bases = sorted({t["asset"].replace("USDT", "") for t in trades})
    news, _ = fetch_news([], [], bases)
    for t in trades:
        px = last_price(live, t["asset"])
        alerts = [
            f"choque {s['tipo']}: {s['detalle']}" for s in shocks if s["symbol"] == t["asset"]
        ]
        alerts += [
            f"noticia de riesgo [{','.join(n.keywords)}]: {n.title[:80]}"
            for n in news
            if n.keywords
            and t["asset"].replace("USDT", "").upper() in [a.upper() for a in n.assets]
        ]
        d = diagnose(t, px, "(contexto completo en `qa agent run`)", alerts[:3])
        d.update(trade_geometry(t, px))
        typer.echo(str(d))


if __name__ == "__main__":
    app()
