"""
CLI minima de QUANT-ARENA v2 (typer).

En M0 todos los comandos son stubs que salen con codigo 3 ("no implementado"):
el hito M0 es preregistro y diseno, sin codigo de datos. Los comandos se activan
segun el plan de hitos (M1: data; M2: stats; M3: research; M4: forward; M5: report).

Todo comando sera determinista (semillas fijas en config) y registrara sus
ejecuciones en el ledger correspondiente antes de devolver resultados.
"""

from __future__ import annotations

from datetime import UTC
from pathlib import Path
from typing import Annotated, Any

import typer

# Compatibilidad PyYAML -> ruamel.yaml (pure Python) para Python 3.15+ en Windows sin MSVC
import qa._yaml_compat  # noqa: F401

app = typer.Typer(help="QUANT-ARENA v2 - laboratorio de investigacion (sin dinero real)")
data_app = typer.Typer(help="Ingesta y verificacion de datos (M1)")
research_app = typer.Typer(help="Ejecucion de hipotesis pre-registradas (M3)")
stats_app = typer.Typer(help="Estadistica y validacion anti-sobreajuste (M2)")
forward_app = typer.Typer(help="Forward-test en paper (M4)")
report_app = typer.Typer(help="Boletin informativo (M5)")
agent_app = typer.Typer(help="Agente operativo M4/M5 (estados + tracker + vigilancia)")
trade_app = typer.Typer(help="Registro de operaciones del USUARIO (el agente no abre nada)")
capital_app = typer.Typer(help="Contabilidad de capital del USUARIO (M5b, libro append-only)")

app.add_typer(data_app, name="data")
app.add_typer(research_app, name="research")
app.add_typer(stats_app, name="stats")
app.add_typer(forward_app, name="forward")
app.add_typer(report_app, name="report")
app.add_typer(agent_app, name="agent")
app.add_typer(trade_app, name="trade")
app.add_typer(capital_app, name="capital")

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
    pit_file = root / "data" / "curated" / "pit_universe.parquet"
    if pit_file.exists():
        pit = _pd.read_parquet(pit_file)
        members = membership_at(pit, _pd.Timestamp.now(tz=UTC), 10)
    else:
        members = ["BTCUSDT", "ETHUSDT", "SOLUSDT", "BNBUSDT", "XRPUSDT"]
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
    """One-shot: ingesta viva -> estados + contabilidad + tracker + vigilancia -> dashboard."""
    import json as _json

    import pandas as _pd
    import yaml as _yaml

    from qa.agent.audit import run_audit
    from qa.agent.capital import (
        compute_status,
        load_capital,
        load_costs,
        load_rr_config,
        net_contributed,
        verify_capital_chain,
    )
    from qa.agent.geometry import fee_roundtrip, fee_taker_side
    from qa.agent.live import fetch_extra_daily, fetch_extra_multi, fetch_live, fetch_prices, last_price
    from qa.agent.news import calcular_termometro_macro, detect_shocks, fetch_news
    from qa.agent.autopilot import gestionar_y_ejecutar, UNIVERSO as AUTOPILOT_UNIVERSO
    from qa.agent.signals import compute_states
    from qa.agent.telemetry import atr, h1_levels, trade_geometry, watchlist_telemetry
    from qa.agent.tracker import diagnose, load_trades, verify_chain
    from qa.data.paths import get_root, reports_dir
    from qa.data.pit import membership_at
    from qa.report.dashboard import render_dashboard

    root = get_root()
    cfg = _yaml.safe_load((root / "config" / "watchlist.yaml").read_text(encoding="utf-8"))
    watchlist = list(cfg["watchlist"])
    costs = load_costs(root)
    rr_cfg = load_rr_config(root)
    min_rr = rr_cfg["min_rr"]
    fee_rt_spot = fee_roundtrip("spot", costs)
    
    # Miembros del universo: usar el universo de Autopilot M6 directamente si no existe parquet antiguo
    pit_file = root / "data" / "curated" / "pit_universe.parquet"
    if pit_file.exists():
        pit = _pd.read_parquet(pit_file)
        members = membership_at(pit, _pd.Timestamp.now(tz=UTC), 10)
    else:
        members = list(AUTOPILOT_UNIVERSO)

    # Asegurar que se descargan los 10 activos completos
    all_syms = sorted(set(watchlist) | set(AUTOPILOT_UNIVERSO) | set(members))
    live = fetch_live(all_syms)
    extra_syms = [m for m in members if m not in live["klines"]]
    if extra_syms:
        extra_1d = fetch_extra_daily(extra_syms)
        for sym, df in extra_1d.items():
            live["klines"].setdefault(sym, {})["1d"] = df
        extra_multi = fetch_extra_multi(extra_syms)
        for sym, frames in extra_multi.items():
            for interval, df in frames.items():
                if not df.empty:
                    live["klines"].setdefault(sym, {})[interval] = df
    states = compute_states(live, members)

    # Obtener precios spot/perp instantáneos en vivo para ejecución estricta
    live_spot_prices = fetch_prices(all_syms)

    # 1. EJECUCIÓN AUTÓNOMA DEL AGENTE (M6.3 Autopilot: Futuros + Spot)
    # Gestiona operaciones existentes (TP1/TP2/SL) y abre nuevas (instant + programadas) con precio vivo estricto
    cap_records_pre = load_capital(root)
    cap_aportado = net_contributed(cap_records_pre) if cap_records_pre else 1000.0
    auto_res = gestionar_y_ejecutar(
        root,
        live["klines"],
        capital_total=cap_aportado,
        max_open_ops=6,
        live_prices=live_spot_prices,
    )

    # Recargar trades tras la intervención del autopilot
    trades = load_trades(root)
    ok, n_lines, msg = verify_chain(root)
    if not ok:
        typer.echo(f"CADENA DE OPERACIONES ROTA: {msg}")
        raise typer.Exit(code=1)
    okc, n_cap, msgc = verify_capital_chain(root)
    if not okc:
        typer.echo(f"CADENA DE CAPITAL ROTA: {msgc}")
        raise typer.Exit(code=1)

    bases = sorted(
        {t["asset"].replace("USDT", "") for t in trades}
        | {w.replace("USDT", "") for w in watchlist}
        | {s.replace("USDT", "") for s in AUTOPILOT_UNIVERSO}
    )
    news_cfg = cfg["noticias"]
    news_items, feed_status = fetch_news(
        news_cfg["feeds"],
        list(news_cfg["keywords_riesgo"]),
        bases,
        int(news_cfg.get("max_age_hours", 72)),
    )
    shocks = detect_shocks(live["klines"], live["premium"], cfg.get("choques", {}))
    termometro = calcular_termometro_macro(news_items)

    # telemetria descriptiva + geometria R:R del filtro de disciplina (M5b)
    tele = watchlist_telemetry(
        dict(live["klines"]),
        fee_rt=fee_rt_spot,
        min_rr=min_rr,
        reward_mult=rr_cfg["reward_mult"],
        risk_mult=rr_cfg["risk_mult"],
    )

    # Precios vivos reales para los 10 activos (¡cero '?' en el dashboard!)
    # Prioridad absoluta al precio spot/ticker en tiempo real (live_spot_prices)
    prices_map: dict[str, float] = {}
    trends_map: dict[str, dict[str, str]] = {}
    for sym in set(AUTOPILOT_UNIVERSO) | set(watchlist):
        if sym in live_spot_prices and live_spot_prices[sym] > 0:
            prices_map[sym] = float(live_spot_prices[sym])
        else:
            frames = live["klines"].get(sym, {})
            for tf in ("1h", "4h", "1d"):
                df = frames.get(tf)
                if df is not None and not df.empty:
                    prices_map[sym] = float(df["close"].iloc[-1])
                    break
        # Tendencias 4h, 1d, 1w
        trends_map[sym] = {}
        for tf in ("4h", "1d", "1w"):
            tl = tele.get(sym, {}).get(tf) or {}
            if tl.get("disponible") and tl.get("dist_sma50_pct") is not None:
                dist = tl["dist_sma50_pct"]
                sentido = "Alcista" if dist >= 0 else "Bajista"
                trends_map[sym][tf] = f"{sentido} ({dist:+.1f}%)"
            else:
                trends_map[sym][tf] = "neutral"

    # Inyectar precios, tendencias, scores y termómetro en states para el Dashboard
    states["prices"] = prices_map
    states["trends"] = trends_map
    states["autopilot_scores"] = auto_res.get("scores", {})
    states["termometro_macro"] = termometro

    # contabilidad de capital del usuario (M5b): equity vivo = base de la escala teorica
    cap_records = load_capital(root)
    capital_status = compute_status(cap_records, trades, prices_map, costs)
    capital_cfg_ref = float(cfg.get("capital_ref_usd", 0.0))
    if cap_records and capital_status["patrimonio_total"] > 0:
        capital_base = capital_status["patrimonio_total"]
        capital_origen = "patrimonio vivo (tu contabilidad M5b)"
    else:
        capital_base = capital_cfg_ref
        capital_origen = "config capital_ref_usd"

    h1_lv: dict[str, Any] = {}
    for asset in ("BTCUSDT", "ETHUSDT"):
        st = states["cells"].get(f"H1_{asset}")
        d1 = live["klines"].get(asset, {}).get("1d")
        if st and d1 is not None and not d1.empty:
            h1_lv[asset] = h1_levels(
                d1,
                float(st["posicion_regla"]),
                capital_base,
                fee_rt_spot=fee_rt_spot,
                min_rr=min_rr,
                reward_mult=rr_cfg["reward_mult"],
                risk_mult=rr_cfg["risk_mult"],
                capital_base_origen=capital_origen,
            )

    diags = []
    for t in trades:
        if t.get("status") != "open":
            diags.append({**diagnose(t, None, "", []), "example": t.get("example", False), "status": "closed"})
            continue
        px = prices_map.get(t["asset"])
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
        tf_key = {"1w": "1w", "1s": "1w", "4h": "4h"}.get(
            (t.get("timeframe") or "1d").lower(), "1d"
        )
        frame = live["klines"].get(t["asset"], {}).get(tf_key)
        atr_marco = atr(frame) if frame is not None and not frame.empty else None
        d.update(
            trade_geometry(
                t,
                px,
                atr_marco=atr_marco if atr_marco == atr_marco else None,
                fee_taker_lado=fee_taker_side(str(t.get("kind", "spot")), costs),
            )
        )
        d["timeframe"] = t.get("timeframe")
        tl = tele.get(t["asset"], {}).get(tf_key) or {}
        if tl.get("disponible"):
            d["sma50_marco_txt"] = (
                f"SMA50({tf_key}) {tl['sma50']} — precio {tl['lado_sma50']} "
                f"({tl['dist_sma50_pct']:+}%)"
            )
        d["example"] = t.get("example", False)
        d["status"] = "open"
        # Propagar campos clave del trade a diagnose para el Dashboard M6.3
        d["entry"] = t.get("entry_price")
        d["sl"] = t.get("sl")
        d["tp"] = t.get("tp")
        d["size_usd"] = t.get("size_usd")
        d["note"] = t.get("note")
        d["rr_neto_inicial"] = t.get("rr_neto_inicial")
        d["leverage"] = t.get("leverage") or "4x"
        d["ts_utc"] = t.get("ts_utc")
        d["tp1_hit"] = t.get("tp1_hit", False)
        d["entry_mode"] = t.get("entry_mode", "INSTANTE")
        d["order_state"] = t.get("order_state", "ACTIVE")
        d["target_entry"] = t.get("target_entry")
        d["thesis"] = t.get("thesis") or t.get("note", "")
        d["margin_usd"] = t.get("margin_usd")
        d["risk_usd"] = t.get("risk_usd")
        diags.append(d)

    # Auditorías M6.3: Futuros (Pestaña 1) y Spot & Ciclos (Pestaña 2)
    from qa.agent.audit import audit_futures, audit_spot
    spot_plans = auto_res.get("spot_plans", [])
    aportado = net_contributed(cap_records) if cap_records else None
    audit_out = run_audit(trades, costs, aportado)
    audit_fut = audit_futures(trades, costs, live_prices=prices_map)
    audit_sp = audit_spot(spot_plans)

    # Exportación automática de los 3 CSVs estadísticos (audit_futures.csv, audit_spot.csv, trades_statistical_log.csv)
    try:
        import csv as _csv

        # 1. audit_futures.csv
        fut_csv_path = root / "ledger" / "audit_futures.csv"
        fut_fields = [
            "id", "asset", "kind", "leverage", "timeframe", "entry_mode", "order_state",
            "status", "opened_at", "closed_at", "duracion", "entry", "exit", "live_price",
            "size_usd", "margin_usd", "sl", "tp1", "tp2", "rr_neto", "pnl_vivo_usd",
            "pnl_vivo_pct", "pnl_neto_usd", "r_multiplo", "thesis", "tag"
        ]
        with open(fut_csv_path, "w", newline="", encoding="utf-8-sig") as f_fut:
            writer = _csv.DictWriter(f_fut, fieldnames=fut_fields, extrasaction="ignore")
            writer.writeheader()
            for r in (audit_fut.get("master_rows") or []):
                writer.writerow(r)

        # 2. audit_spot.csv
        spot_csv_path = root / "ledger" / "audit_spot.csv"
        spot_fields = [
            "id", "asset", "timeframe", "horizon_label", "status", "opened_at", "closed_at",
            "duracion", "allocated_usd", "buy_zone_low", "buy_zone_high", "buy_ref_price",
            "entry_executed_price", "current_price", "dist_zona_txt", "tp1_zone", "tp2_zone",
            "sl_spot", "tp_updated", "rr_ciclo", "pnl_usd", "pnl_pct", "thesis"
        ]
        with open(spot_csv_path, "w", newline="", encoding="utf-8-sig") as f_spot:
            writer = _csv.DictWriter(f_spot, fieldnames=spot_fields, extrasaction="ignore")
            writer.writeheader()
            for r in (audit_sp.get("master_rows") or []):
                writer.writerow(r)

        # 3. Log Consolidado General (trades_statistical_log.csv)
        csv_path = root / "ledger" / "trades_statistical_log.csv"
        csv_fieldnames = [
            "id", "tipo_libro", "status", "asset", "timeframe", "opened_at", "closed_at",
            "duracion", "entry", "exit", "size_usd", "sl", "tp", "rr_neto",
            "pnl_neto_usd", "pnl_pct", "r_multiplo", "tag", "thesis_or_note"
        ]
        csv_rows: list[dict[str, Any]] = []
        for r in (audit_fut.get("master_rows") or []):
            csv_rows.append({
                "id": r.get("id"),
                "tipo_libro": "FUTUROS",
                "status": r.get("status"),
                "asset": r.get("asset"),
                "timeframe": r.get("timeframe"),
                "opened_at": r.get("opened_at"),
                "closed_at": r.get("closed_at"),
                "duracion": r.get("duracion"),
                "entry": r.get("entry"),
                "exit": r.get("exit"),
                "size_usd": r.get("size_usd"),
                "sl": r.get("sl"),
                "tp": r.get("tp2"),
                "rr_neto": r.get("rr_neto"),
                "pnl_neto_usd": r.get("pnl_neto_usd"),
                "pnl_pct": r.get("pnl_vivo_pct"),
                "r_multiplo": r.get("r_multiplo"),
                "tag": r.get("tag"),
                "thesis_or_note": r.get("thesis"),
            })
        for r in (audit_sp.get("master_rows") or []):
            csv_rows.append({
                "id": r.get("id"),
                "tipo_libro": "SPOT",
                "status": r.get("status"),
                "asset": r.get("asset"),
                "timeframe": r.get("timeframe"),
                "opened_at": r.get("opened_at"),
                "closed_at": r.get("closed_at"),
                "duracion": r.get("duracion"),
                "entry": r.get("entry_executed_price"),
                "exit": r.get("current_price"),
                "size_usd": r.get("allocated_usd"),
                "sl": r.get("sl_spot"),
                "tp": r.get("tp2_zone"),
                "rr_neto": r.get("rr_ciclo"),
                "pnl_neto_usd": r.get("pnl_usd"),
                "pnl_pct": r.get("pnl_pct"),
                "r_multiplo": "-",
                "tag": "SPOT_M63",
                "thesis_or_note": r.get("thesis"),
            })
        with open(csv_path, "w", newline="", encoding="utf-8-sig") as f_csv:
            writer = _csv.DictWriter(f_csv, fieldnames=csv_fieldnames, extrasaction="ignore")
            writer.writeheader()
            for r in csv_rows:
                writer.writerow(r)
    except Exception:
        pass

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
    calc_cfg = {
        "equity_usd": capital_base,
        "equity_origen": capital_origen,
        "min_rr": min_rr,
        "fee_taker_spot": fee_taker_side("spot", costs),
        "fee_taker_perp": fee_taker_side("future_long", costs),
        "risk_pcts": list(rr_cfg["risk_pcts"]),
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
        capital_ref=capital_cfg_ref,
        capital=capital_status,
        audit=audit_out,
        calc=None,
        spot_plans=spot_plans,
        audit_futuros=audit_fut,
        audit_spot_data=audit_sp,
    )
    outdir = reports_dir(root) / "dashboard"
    outdir.mkdir(parents=True, exist_ok=True)
    (outdir / "index.html").write_text(html_out, encoding="utf-8")
    typer.echo(f"dashboard -> {outdir / 'index.html'}")
    typer.echo(f"operaciones: {len(trades)} (cadena: {n_lines} lineas, {msg})")
    typer.echo(f"capital: {n_cap} movimientos (cadena: {msgc})")
    if not capital_status["sin_registros"]:
        typer.echo(
            "patrimonio: aportado "
            f"{capital_status['capital_aportado_neto']:,.2f} + realizado "
            f"{capital_status['pnl_realizado_usd']:+,.2f} + flotante "
            f"{capital_status['pnl_flotante_usd']:+,.2f} = "
            f"{capital_status['patrimonio_total']:,.2f} USD · heat "
            f"{capital_status['portfolio_heat_usd']:,.2f} USD "
            f"({capital_status['portfolio_heat_pct_patrimonio']}%)"
        )
    summ = audit_out["summary"]
    if summ.get("total_cerradas"):
        typer.echo(
            f"trade audit: {summ['total_cerradas']} cerradas · win rate "
            f"{summ['win_rate_pct']}% · neto {summ['pnl_neto_usd']:+,.2f} USD · PF "
            f"{summ['profit_factor']}"
        )
    rr_resumen = {a: (lv.get("rr_filtro") or {}).get("label", "n/d") for a, lv in h1_lv.items()}
    typer.echo(f"filtro R:R (H1 diario): {_json.dumps(rr_resumen, ensure_ascii=False)}")
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
    tag: Annotated[str, typer.Option("--tag", help="etiqueta de tu diario (M5b)")] = "",
    ts: Annotated[
        str, typer.Option("--ts", help="fecha UTC declarada del registro (ISO; defecto: ahora)")
    ] = "",
    example: Annotated[bool, typer.Option("--example")] = False,
    force_low_rr: Annotated[
        bool,
        typer.Option(
            "--force-low-rr",
            help="registra aunque el R:R neto incumpla tu minimo (queda marcado rr_forzado)",
        ),
    ] = False,
) -> None:
    """Registra una operacion ABIERTA POR TI (el agente nunca abre nada).

    M5b: aplica tu filtro de disciplina R:R Neto >= min_rr_ratio
    (config/watchlist.yaml). Si la configuracion incumple, el registro se
    BLOQUEA salvo --force-low-rr (quedara marcado en el libro, auditable).
    """
    from qa.agent.capital import load_costs, load_rr_config
    from qa.agent.geometry import check_rr_discipline
    from qa.agent.tracker import open_trade
    from qa.data.paths import get_root

    root = get_root()
    costs = load_costs(root)
    min_rr = load_rr_config(root)["min_rr"]

    rr_neto: float | None = None
    if entry > 0 and sl > 0 and tp > 0:
        disc = check_rr_discipline(entry, sl, tp, kind, costs, min_rr)
        rr_neto = disc["rr_neto"]
        if disc["cumple"] is False:
            typer.echo(f"⚠ {disc['aviso']}")
            if not force_low_rr:
                typer.echo(
                    "registro BLOQUEADO por tu filtro de disciplina (no se ha escrito nada). "
                    "Si aun asi quieres anotarla: repite con --force-low-rr "
                    "(quedara marcada rr_forzado=true en el libro)."
                )
                raise typer.Exit(code=2)
            typer.echo("--force-low-rr presente: se registra marcada como rr_forzado=true.")
        else:
            typer.echo(f"✓ {disc['aviso']}")
        long_side = kind != "future_short"
        orden_ok = (sl < entry < tp) if long_side else (tp < entry < sl)
        if not orden_ok:
            typer.echo(
                "AVISO: niveles inhabituales para la direccion indicada "
                "(esperado SL<entrada<TP en largos / TP<entrada<SL en cortos). ¿Errata?"
            )
    elif entry > 0 and (sl <= 0 or tp <= 0):
        typer.echo(
            "AVISO: sin SL y/o TP: el filtro R:R >= "
            f"{min_rr:.1f}x no es evaluable en esta operacion (se registra sin filtro)."
        )

    rec = open_trade(
        root,
        asset,
        kind,
        timeframe,
        entry,
        size_usd,
        sl or None,
        tp or None,
        note,
        example,
        tag=tag,
        ts_utc=ts or None,
        rr_neto_inicial=rr_neto,
        rr_forzado=bool(force_low_rr and rr_neto is not None),
    )
    typer.echo(
        f"registrada: id={rec['id']} {asset} {kind} entrada={entry} tam=${size_usd} "
        f"SL={sl or '—'} TP={tp or '—'}"
        f"{f' R:R neto={rr_neto:.2f}x' if rr_neto is not None else ''}"
        f"{f' tag={tag}' if tag else ''}{' [EJEMPLO]' if example else ''}"
    )


@trade_app.command("close")
def trade_close(
    id: Annotated[str, typer.Option("--id")],
    exit: Annotated[float, typer.Option("--exit")],
    note: Annotated[str, typer.Option("--note")] = "",
    tag: Annotated[str, typer.Option("--tag", help="etiqueta de tu diario (M5b)")] = "",
    ts: Annotated[str, typer.Option("--ts", help="fecha UTC declarada del cierre (ISO)")] = "",
) -> None:
    """Registra el cierre de una operacion."""
    from qa.agent.tracker import close_trade
    from qa.data.paths import get_root

    close_trade(get_root(), id, exit, note, tag=tag, ts_utc=ts or None)
    typer.echo(f"cerrada {id} a {exit}")


@trade_app.command("list")
def trade_list() -> None:
    """Lista operaciones (abiertas y cerradas)."""
    import json as _json

    from qa.agent.tracker import load_trades
    from qa.data.paths import get_root

    for t in load_trades(get_root()):
        typer.echo(_json.dumps(t, default=str))


def _resolve_equity(root: Path, equity_cli: float) -> tuple[float, str]:
    """Base patrimonial: --equity > equity vivo (libro de capital) > capital_ref_usd."""
    import yaml as _yaml

    from qa.agent.capital import compute_status, load_capital, load_costs

    if equity_cli > 0:
        return equity_cli, "--equity (override CLI)"
    cap = load_capital(root)
    if cap:
        from qa.agent.live import fetch_prices
        from qa.agent.tracker import load_trades

        trades = load_trades(root)
        assets = sorted({t["asset"] for t in trades if t.get("status") == "open"})
        try:
            prices = fetch_prices(assets)
        except Exception:
            prices = {}
        st = compute_status(cap, trades, prices, load_costs(root))
        if st["patrimonio_total"] > 0:
            return st["patrimonio_total"], "patrimonio vivo (tu contabilidad M5b)"
        return st["patrimonio_total"], "patrimonio vivo <= 0 (revisa tu contabilidad)"
    cfg = _yaml.safe_load((root / "config" / "watchlist.yaml").read_text(encoding="utf-8"))
    return float(cfg.get("capital_ref_usd", 0.0)), "config capital_ref_usd"


@trade_app.command("calc")
def trade_calc(
    entry: Annotated[float, typer.Option("--entry", help="precio de entrada de TU configuracion")],
    sl: Annotated[float, typer.Option("--sl", help="TU stop loss")],
    tp: Annotated[float, typer.Option("--tp", help="TU take profit (0 = sin TP)")] = 0.0,
    kind: Annotated[str, typer.Option("--kind", help="spot|future_long|future_short")] = "spot",
    risk_pct: Annotated[
        float, typer.Option("--risk-pct", help="riesgo % unico (0 = filas 0.5/1.0/2.0)")
    ] = 0.0,
    equity: Annotated[
        float, typer.Option("--equity", help="patrimonio base (0 = auto: equity vivo o config)")
    ] = 0.0,
) -> None:
    """Calculadora ARITMETICA de escala y riesgo (hechos matematicos, no consejo).

    Para cada % de riesgo sobre el patrimonio: riesgo $, tamano de posicion
    equivalente (USD y unidades) y % del patrimonio. Ademas: precio de
    break-even neto (taker ida y vuelta), TP que satisface R:R = 2.0x y 3.0x,
    R:R Neto de tu configuracion y estado de tu filtro de disciplina.
    """
    from qa.agent.capital import load_costs, load_rr_config
    from qa.agent.geometry import trade_calc as calc_geom
    from qa.data.paths import get_root

    root = get_root()
    costs = load_costs(root)
    rr_cfg = load_rr_config(root)
    equity_base, origen = _resolve_equity(root, equity)
    pcts = (risk_pct,) if risk_pct > 0 else rr_cfg["risk_pcts"]
    res = calc_geom(
        entry,
        sl,
        tp,
        kind,
        costs,
        rr_cfg["min_rr"],
        equity_base,
        risk_pcts=tuple(pcts),
    )
    typer.echo("═══ CALCULADORA ARITMÉTICA DE RIESGO (informativo, no es sizing recomendado) ═══")
    typer.echo(
        f"configuración: {kind} entrada {entry} · SL {sl}"
        f"{f' · TP {tp}' if tp > 0 else ' · sin TP'} · patrimonio base "
        f"{equity_base:,.2f} USD ({origen})"
    )
    fee_lado = costs["spot"]["taker_fee"] if kind == "spot" else costs["perp_usdm"]["taker_fee"]
    typer.echo(
        f"comisiones: taker ida y vuelta {2 * float(fee_lado) * 100:.3f}% (costs.yaml VERIFICADO)"
    )
    typer.echo("")
    typer.echo(
        f"{'Riesgo %':>9} | {'Riesgo $':>10} | {'Tamaño $':>12} | {'Unidades':>12} | "
        f"{'% patrim.':>9}"
    )
    for f in res["filas_riesgo"]:
        typer.echo(
            f"{f['risk_pct']:>8.1f}% | {f['risk_usd']:>10,.2f} | {f['size_usd']:>12,.2f} | "
            f"{f['unidades']:>12.6f} | {f['size_pct_equity']:>8.1f}%"
        )
    typer.echo("")
    typer.echo(f"Precio Break-Even Neto (taker i/v): {res['breakeven_neto']:,.2f}")
    if res["tp_min_2r"] is None or res["tp_min_3r"] is None:
        typer.echo(
            "AVISO: SL igual a la entrada (riesgo indefinido): los TP mínimos y el tamaño "
            "de posición no son computables."
        )
    else:
        typer.echo(
            f"TP que satisface R:R = 2.0x: {res['tp_min_2r']:,.2f}   ·   "
            f"R:R = 3.0x: {res['tp_min_3r']:,.2f}   (aritmética de tu regla)"
        )
    if res["rr_neto"] is not None:
        typer.echo(
            f"R:R Neto de tu configuración: {res['rr_neto']:.2f}x (mínimo {res['min_rr']:.1f}x)"
        )
        if res["cumple_filtro"]:
            typer.echo(
                f"✓ FILTRO R:R >= {res['min_rr']:.1f}: CUMPLE (Asimetría {res['rr_neto']:.2f}x)"
            )
        else:
            typer.echo(f"⚠ {res['aviso_filtro']}")
            typer.echo(
                f"✗ FILTRO R:R >= {res['min_rr']:.1f}: NO CUMPLE (Asimetría "
                f"{res['rr_neto']:.2f}x < {res['min_rr']:.1f})"
            )
            raise typer.Exit(code=2)
    else:
        typer.echo(
            "sin TP (o SL = entrada): el filtro R:R no es evaluable; se muestran los TP "
            "que satisfarían 2.0x/3.0x con tu SL."
        )


@trade_app.command("audit")
def trade_audit(
    as_json: Annotated[bool, typer.Option("--json", help="vuelca el resultado en JSON")] = False,
) -> None:
    """Trade Audit completo del historial CERRADO (métricas contables, M5b)."""
    import json as _json

    from qa.agent.audit import run_audit
    from qa.agent.capital import load_capital, load_costs, net_contributed
    from qa.agent.tracker import load_trades
    from qa.data.paths import get_root

    root = get_root()
    costs = load_costs(root)
    cap = load_capital(root)
    aportado = net_contributed(cap) if cap else None
    out = run_audit(load_trades(root), costs, aportado)
    if as_json:
        typer.echo(_json.dumps(out, indent=2, default=str))
        return
    rows, summ = out["rows"], out["summary"]
    typer.echo("═══ TRADE AUDIT — HISTORIAL DE OPERACIONES CERRADAS (contabilidad del usuario) ═══")
    if not rows:
        typer.echo("sin operaciones cerradas registradas.")
        return
    typer.echo(
        f"{'cierre':<11}{'activo':<10}{'tipo/marco':<16}{'dur.':<8}{'entrada':>10}"
        f"{'salida':>10}{'tamaño$':>9}{'RR ini':>7}{'PnL neto$':>11}{'PnL%':>8}{'R':>7}  tag"
    )
    for r in rows:
        ex = " [EJEMPLO]" if r.get("example") else ""
        typer.echo(
            f"{str(r['closed_at'])[:10]:<11}{str(r['asset']):<10}"
            f"{str(r['kind']) + '/' + str(r['timeframe']):<16}{str(r['duracion']):<8}"
            f"{r['entry']:>10,.2f}{r['exit']:>10,.2f}{r['size_usd']:>9,.0f}"
            f"{(str(r['rr_inicial_bruto']) + 'x') if r['rr_inicial_bruto'] is not None else '—':>7}"
            f"{r['pnl_neto_usd']:>+11,.2f}{r['pnl_pct']:>+8.2f}"
            f"{(str(r['r_multiplo']) + 'R') if r['r_multiplo'] is not None else 'sinSL':>7}"
            f"  {r.get('tag') or '—'}{ex}"
        )
    typer.echo("")
    typer.echo("─── MÉTRICAS GLOBALES DE AUDITORÍA ───")
    typer.echo(f"operaciones cerradas:      {summ['total_cerradas']}")
    typer.echo(f"win rate:                  {summ['win_rate_pct']}%")
    typer.echo(
        f"ganancia/pérdida neta:     {summ['pnl_neto_usd']:+,.2f} USD"
        f" · {summ['pnl_neto_pct_aportado']}% s/ capital aportado"
        f" · {summ['pnl_neto_pct_rotacion']}% s/ rotación"
    )
    typer.echo(f"profit factor:             {summ['profit_factor']}")
    typer.echo(
        f"esperanza por operación:   {summ['esperanza_usd_por_trade']:+,.2f} USD"
        f" · {summ['esperanza_R_por_trade']} R"
    )
    typer.echo(f"R:R medio realizado:       {summ['rr_medio_realizado_R']} R")
    for key, lbl in (("mejor_peor_usd", "USD"), ("mejor_peor_R", "R")):
        d = summ.get(key) or {}
        mej, peo = d.get("mejor") or {}, d.get("peor") or {}
        if mej:
            typer.echo(
                f"mejor/peor operación ({lbl}): {mej.get('asset')} {mej.get('valor')} · "
                f"{peo.get('asset')} {peo.get('valor')}"
            )
    typer.echo(
        f"max drawdown realizado:    {summ['max_drawdown_realizado_usd']:,.2f} USD "
        "(sobre PnL acumulado)"
    )
    typer.echo(f"operaciones sin SL:        {summ['trades_sin_sl']} (R no computable)")
    typer.echo("")
    typer.echo("─── DESGLOSE POR TAG ───")
    for tag, d in sorted((summ.get("por_tag") or {}).items()):
        typer.echo(
            f"{tag:<22} ops {d['trades']:>3} · win rate {d['win_rate_pct']:>5}% · "
            f"neto {d['pnl_neto_usd']:>+10,.2f} USD · R medio {d['R_medio']}"
        )


@trade_app.command("status")
def trade_status() -> None:
    """Diagnostico descriptivo de las operaciones abiertas (precios vivos)."""
    from qa.agent.capital import load_costs
    from qa.agent.geometry import fee_taker_side
    from qa.agent.live import fetch_live, last_price
    from qa.agent.news import detect_shocks, fetch_news
    from qa.agent.telemetry import atr, trade_geometry
    from qa.agent.tracker import diagnose, load_trades
    from qa.data.paths import get_root

    root = get_root()
    costs = load_costs(root)
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
        tf_key = {"1w": "1w", "1s": "1w", "4h": "4h"}.get(
            (t.get("timeframe") or "1d").lower(), "1d"
        )
        frame = live["klines"].get(t["asset"], {}).get(tf_key)
        atr_marco = atr(frame) if frame is not None and not frame.empty else None
        d.update(
            trade_geometry(
                t,
                px,
                atr_marco=atr_marco if atr_marco == atr_marco else None,
                fee_taker_lado=fee_taker_side(str(t.get("kind", "spot")), costs),
            )
        )
        typer.echo(str(d))


# ------------------------- capital (M5b) -------------------------
@capital_app.command("set")
def capital_set(
    amount: Annotated[float, typer.Option("--amount", help="capital inicial en USD")],
    note: Annotated[str, typer.Option("--note")] = "Capital inicial",
    ts: Annotated[str, typer.Option("--ts", help="fecha UTC declarada (ISO; defecto: ahora)")] = "",
    example: Annotated[
        bool, typer.Option("--example", help="marca el registro como EJEMPLO")
    ] = False,
) -> None:
    """Fija el capital inicial de tu libro contable (ledger/user_capital.jsonl)."""
    from qa.agent.capital import set_capital
    from qa.data.paths import get_root

    rec = set_capital(get_root(), amount, note, ts_utc=ts or None, example=example)
    typer.echo(
        f"capital inicial registrado: {amount:,.2f} USD ({rec['ts_utc']})"
        f"{' [EJEMPLO]' if example else ''}"
    )


@capital_app.command("add")
def capital_add(
    amount: Annotated[float, typer.Option("--amount", help="aporte (negativo = retiro)")],
    note: Annotated[str, typer.Option("--note")] = "",
    ts: Annotated[str, typer.Option("--ts", help="fecha UTC declarada (ISO; defecto: ahora)")] = "",
    example: Annotated[
        bool, typer.Option("--example", help="marca el registro como EJEMPLO")
    ] = False,
) -> None:
    """Registra un aporte adicional (o retiro si el importe es negativo)."""
    from qa.agent.capital import add_capital
    from qa.data.paths import get_root

    rec = add_capital(get_root(), amount, note, ts_utc=ts or None, example=example)
    tipo = "aporte" if amount >= 0 else "retiro"
    typer.echo(
        f"{tipo} registrado: {amount:+,.2f} USD ({rec['ts_utc']}){' [EJEMPLO]' if example else ''}"
    )


@capital_app.command("status")
def capital_status() -> None:
    """Ecuación patrimonial completa: aportado, realizado, flotante, equity y heat."""
    from qa.agent.capital import (
        compute_status,
        load_capital,
        load_costs,
        verify_capital_chain,
    )
    from qa.agent.live import fetch_prices
    from qa.agent.tracker import load_trades, verify_chain
    from qa.data.paths import get_root

    root = get_root()
    okc, nc, msgc = verify_capital_chain(root)
    okt, nt, msgt = verify_chain(root)
    if not (okc and okt):
        typer.echo(f"CADENA ROTA — capital: {msgc} · operaciones: {msgt}")
        raise typer.Exit(code=1)
    cap = load_capital(root)
    trades = load_trades(root)
    assets = sorted({t["asset"] for t in trades if t.get("status") == "open"})
    try:
        prices = fetch_prices(assets)
    except Exception as e:
        prices = {}
        if assets:
            typer.echo(
                "⚠ No se pudo obtener precios vivos (sin red o error: "
                f"{e}). PnL flotante = 0."
            )
    st = compute_status(cap, trades, prices, load_costs(root))
    if st["sin_registros"]:
        typer.echo(
            "sin libro de capital: empieza con `qa capital set --amount 1000 --note "
            '"Capital inicial"`.'
        )
        return
    typer.echo("═══ ECUACIÓN PATRIMONIAL (contabilidad del usuario · M5b) ═══")
    typer.echo(f"1) Capital Aportado Neto: {st['capital_aportado_neto']:,.2f} USD")
    typer.echo(f"   {'fecha':<17}{'tipo':<9}{'importe':>12}{'acumulado':>12}  nota")
    for m in st["movimientos"]:
        ex = " [EJEMPLO]" if m["example"] else ""
        typer.echo(
            f"   {str(m['ts_utc'])[:16]:<17}{m['tipo']:<9}{m['amount']:>+12,.2f}"
            f"{m['acumulado']:>12,.2f}  {m['note']}{ex}"
        )
    typer.echo(
        f"2) PnL Realizado Acumulado: {st['pnl_realizado_usd']:+,.2f} USD "
        f"({st['pnl_realizado_pct_aportado']}% s/ aportado) · {st['n_cerradas']} cerradas · "
        f"comisiones est. {st['comisiones_cerradas_est_usd']:,.2f} USD descontadas"
    )
    typer.echo(
        f"3) PnL Flotante: {st['pnl_flotante_usd']:+,.2f} USD "
        f"({st['pnl_flotante_pct_aportado']}% s/ aportado) · {st['n_abiertas']} abiertas · "
        "bruto de comisiones (se descuentan al cerrar)"
    )
    if st["sin_precio_vivo"]:
        typer.echo(f"   ⚠ sin precio vivo para: {', '.join(st['sin_precio_vivo'])}")
    typer.echo(f"4) PATRIMONIO TOTAL (Equity Vivo): {st['patrimonio_total']:,.2f} USD")
    typer.echo(
        f"   = aportado {st['capital_aportado_neto']:,.2f} + realizado "
        f"{st['pnl_realizado_usd']:+,.2f} + flotante {st['pnl_flotante_usd']:+,.2f}"
    )
    typer.echo(
        f"5) Riesgo en Mesa (Portfolio Heat): {st['portfolio_heat_usd']:,.2f} USD = "
        f"{st['portfolio_heat_pct_patrimonio']}% del patrimonio "
        "(si TODOS los SL saltaran hoy a la vez; SL en zona de ganancia/break-even aporta $0)"
    )
    for h in st["heat_detalle"]:
        if h["sin_sl"]:
            typer.echo(f"   ⚠ {h['id']} ({h['asset']}): SIN SL — riesgo no acotado, no computable")
        else:
            typer.echo(f"   {h['id']} ({h['asset']}): riesgo aportado {h['riesgo_usd']:,.2f} USD")
    typer.echo("")
    typer.echo(
        "Este patrimonio vivo se usa automáticamente como base de la columna "
        "'Escala teórica' de H1 en el dashboard (informativo, no sizing recomendado)."
    )


@capital_app.command("reset-examples")
def capital_reset_examples(
    yes: Annotated[
        bool, typer.Option("--yes", help="no pide confirmación (borra los registros EJEMPLO)")
    ] = False,
) -> None:
    """Borra TODOS los registros marcados EJEMPLO (capital + operaciones) de un golpe.

    Solo toca registros con example=true (los reales jamás se eliminan). Crea
    copias de seguridad previas en ledger/backup/ y reconstruye las cadenas de
    hashes de ambos libros.
    """
    from qa.agent.capital import reset_examples
    from qa.data.paths import get_root

    root = get_root()
    if not yes:
        typer.confirm(
            "Se borrarán todos los registros marcados EJEMPLO de user_capital.jsonl y "
            "user_trades.jsonl (con backup previo en ledger/backup/). ¿Continuar?",
            abort=True,
        )
    out = reset_examples(root)
    typer.echo(
        f"reset-ejemplos: capital -{out['capital_removed']} registros · operaciones "
        f"-{out['trades_removed']} registros"
    )
    for b in out["backups"]:
        typer.echo(f"backup: {b}")
    for name in ("capital_chain", "trades_chain"):
        c = out[name]
        typer.echo(
            f"cadena {name.replace('_chain', '')}: {'OK' if c['ok'] else 'ROTA'} "
            f"({c['lineas']} lineas, {c['msg']})"
        )
        if not c["ok"]:
            raise typer.Exit(code=1)
    typer.echo("Listo: puedes empezar desde cero con tu dinero real (qa capital set --amount …).")


@capital_app.command("hard-reset")
def capital_hard_reset(
    amount: Annotated[float, typer.Option("--amount", help="Capital inicial simulado")] = 1000.0,
    note: Annotated[str, typer.Option("--note", help="Nota de reinicio")] = "Capital inicial limpio simulado",
) -> None:
    """Reinicia limpiamente tanto el libro de Futuros como el de Spot con el capital indicado ($1,000 USD)."""
    from qa.agent.capital import set_capital
    from qa.data.paths import get_root

    root = get_root()
    # 1. Limpiar user_trades.jsonl
    trades_path = root / "ledger" / "user_trades.jsonl"
    trades_path.parent.mkdir(parents=True, exist_ok=True)
    trades_path.write_text("", encoding="utf-8")

    # 2. Limpiar user_spot.jsonl
    spot_path = root / "ledger" / "user_spot.jsonl"
    spot_path.write_text("", encoding="utf-8")

    # 3. Limpiar y recrear user_capital.jsonl con el monto exacto
    cap_path = root / "ledger" / "user_capital.jsonl"
    cap_path.write_text("", encoding="utf-8")
    set_capital(root, amount, note)

    # 4. Limpiar CSVs estadísticos
    for csv_file in ("trades_statistical_log.csv", "audit_futures.csv", "audit_spot.csv"):
        p = root / "ledger" / csv_file
        if p.exists():
            try:
                p.unlink()
            except Exception:
                pass

    typer.echo(f"hard-reset completado con éxito: capital=${amount:,.2f} USD (libros de Futuros y Spot reiniciados)")


if __name__ == "__main__":
    app()
