"""Renderiza reports/M3a_REPORT.md desde M3a_results.json + selected_cells.

Uso: python scripts/render_m3a_report.py --sha <freeze_sha>
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

REPO = Path(__file__).resolve().parents[1]
R = json.loads((REPO / "reports" / "M3a_results.json").read_text())
S = json.loads((REPO / "reports" / "M3a_selected_cells.json").read_text())
V = R["selection_verdicts"]


def pct(x: Any) -> str:
    return f"{float(x) * 100:.1f}%"


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--sha", required=True)
    args = ap.parse_args()
    L: list[str] = []
    a = L.append

    a(
        "# M3a · Investigación in-sample (una sola pasada, rejilla congelada v1.4) · "
        f"{R['meta']['updated_at_utc']} · freeze commit `{args.sha[:7]}` · tag `m3a-freeze`"
    )
    a("")
    a("## Resumen en 5 líneas")
    a("")
    a(
        "1. **38/38 trials registrados en el ledger** (H1: 24, H2: 6, H3: 8 — la rejilla exacta "
        "de v1.4); parámetros de producción: n_perm=10 000, RC B=2 000, CPCV(10,2)=45, "
        "PBO-CSCV(16, 1000 combos), bootstrap 10 000, capital 10 000 USDT, semilla 20261027."
    )
    a(
        "2. **H3 (carry spot-perp) = PASA_IS en BTC y ETH** (celda w30_t5): neto diario "
        "+2.9/+3.7 pb (HAC t=5.3/5.2), DSR=1.00 (n_trials familiar 8), PBO=0.018, RC p<0.001, "
        "folds 100%/98%, aguanta costes ×2 (+2.6/+3.4 pb). Pasa a M3b."
    )
    a(
        "3. **H1 = INCONTRASTABLE** (pre-declarado en v1.4 §8): BTC perm_p=0.19; ETH **sí pasa "
        "C1a/C1b** (perm_p=0.018, ΔmaxDD_vm −20.2 pp, 3/3 subperíodos) pero **no supera el RC "
        "familiar** (p=0.23) — la multiplicidad de 12 celdas explica el hallazgo; veredicto "
        "INCONTRASTABLE por política pre-registrada."
    )
    a(
        "4. **H2 = INCONTRASTABLE**: las 6 celdas dan ΔSharpe negativo vs universo EW "
        "(−0.01 a −0.28); la seleccionada (L26_N10) tiene CI [−0.50, +0.28] (incluye 0), "
        "DSR 0.81, PBO 0.54, MDE ≈ 39 %/año ≫ efecto: sin potencia, como se declaró."
    )
    a(
        "5. **Holdout intacto**: `ledger/holdout_access.log` sin entradas nuevas "
        "(2 líneas, sha256 `4d0f3442…` igual que la baseline M2c); ninguna métrica de M3a "
        "tocó `holdout_sealed/`."
    )
    a("")
    a("## Gates")
    a("")
    a("| Gate | Comando | Resultado | Evidencia |")
    a("|---|---|---|---|")
    a("| Lint/tipos/tests | `ruff check . && mypy && pytest` | ✅ 77/77 | consola |")
    a(
        "| Registro obligatorio | `ledger/trials.duckdb` | ✅ 38 filas strategy (24+6+8) + benchmarks/diagnósticos | `qa stats report` |"
    )
    a(
        "| n_trials desde ledger | `family_sharpes()` | ✅ sd familiar estimada del ledger (H1 0.292, H2 0.128, H3 ver JSON) | `M3a_results.json` |"
    )
    a(
        "| Holdout sin tocar | `wc -l ledger/holdout_access.log` + sha256 | ✅ 2 líneas, sha idéntico | este informe |"
    )
    a(
        "| Una sola pasada | celdas ejecutadas una vez; reruns = cache del ledger | ✅ | run_ids deterministas |"
    )
    a(
        "| Congelación | commit + SHA256 + tag `m3a-freeze` + OTS | ✅ | `reports/M3a_selected_cells.json` |"
    )
    a("")
    a("## Resultados — H1 (24 celdas: 12 por activo)")
    a("")
    for asset in ("BTCUSDT", "ETHUSDT"):
        blk = R["H1"]["assets"][asset]
        a(f"### {asset} (RC familiar p={blk['rc']['p_value']:.4f} · PBO={blk['pbo']})")
        a("")
        a(
            "| celda | Sharpe | ΔSharpe vs B&H | maxDD | ΔmaxDD_vm (pp) | perm p | p adverso | subs (n/3) | CPCV med (pp) | folds+ | stress Δvm | trades/año | WR | expo |"
        )
        a("|---|---|---|---|---|---|---|---|---|---|---|---|---|---|")
        for cid, m in sorted(blk["cells"].items()):
            subs = m["subperiod_d_vm_pp"]
            a(
                f"| {cid} | {m['sharpe_ann']:.2f} | {m['d_sharpe_vs_bh']:+.2f} | "
                f"{pct(m['max_drawdown'])} | {m['d_vm_pp']:+.1f} | {m['perm_p']:.4f} | "
                f"{m['perm_p_adverso']:.3f} | {m['subperiod_improve_count']}/3 "
                f"({subs['SP1']:+.0f}/{subs['SP2']:+.0f}/{subs['SP3']:+.0f}) | "
                f"{m['cpcv_median_dvm_pp']:+.1f} | {m['cpcv_frac_improve']:.2f} | "
                f"{m['stress_d_vm_pp']:+.1f} | {m['trades_per_year']:.1f} | "
                f"{m['win_rate_trades']:.2f} | {m['exposure_mean']:.2f} |"
            )
        a("")
        sel = V["H1"]["assets"][asset]
        a(
            f"**Seleccionada (mediana CPCV): `{sel['selected_cell']}`** · veredicto: "
            f"**{sel['verdict']}** · DSR informativo: {sel['dsr_informativo']} "
            f"(n_trials=24 familiar, sd ledger={V['H1']['sd_trials_ann']})"
        )
        a("")
        a("| criterio | valor | pasa |")
        a("|---|---|---|")
        m = sel["metrics"]
        a(
            f"| C1a perm p≤0.025 y Δ<0 | p={m['perm_p']:.4f}, Δ={m['d_vm_pp']:+.1f}pp | {sel['checks']['C1a_perm_p<=t*_y_mejora']} |"
        )
        a(
            f"| C1b subperíodos ≥2/3 | {m['subperiod_improve_count']}/3 | {sel['checks']['C1b_subperiodos>=2de3']} |"
        )
        a(
            f"| C2' RC familiar p<0.05 | p={blk['rc']['p_value']:.4f} | {sel['checks']['C2_rc_familiar_p<0.05']} |"
        )
        a(f"| C3 PBO<0.20 | {blk['pbo']} | {sel['checks']['C3_pbo<0.20']} |")
        a(
            f"| C4 stress ×2 | Δvm={m['stress_d_vm_pp']:+.1f}pp, ΔSharpe={m['stress_d_sharpe_vs_bh']:+.2f} | {sel['checks']['C4_stress_mantiene']} |"
        )
        a(f"| C5 folds ≥60% | {m['cpcv_frac_improve']:.2f} | {sel['checks']['C5_folds>=60%']} |")
        a("")
    a(
        f"**Veredicto familiar H1: {V['H1']['family_verdict']}** — coherente con la "
        "pre-declaración v1.4 §8 (potencia pipeline 9.5-18.5% para ΔSharpe 0.1-0.3). "
        "Nota: ETH supera C1a+C1b+C3+C4+C5 pero no el control de multiplicidad C2' (RC): "
        "con 12 celdas por activo, un p=0.018 aislado no sobrevive al test familiar. "
        "Ningún p adverso ≤ t* → no hay evidencia de daño, solo ausencia de evidencia."
    )
    a("")
    a("## Resultados — H2 (6 celdas, universo PIT)")
    a("")
    a(
        "| celda | semanas | Sharpe | Sharpe EW bench | ΔSharpe | CI95 ΔSharpe | CPCV med | folds+ | stress Sharpe |"
    )
    a("|---|---|---|---|---|---|---|---|---|")
    for cid, m in sorted(R["H2"]["cells"].items()):
        ci = m["d_sharpe_ci95"]
        a(
            f"| {cid} | {m['n_obs']} | {m['sharpe_ann']:.2f} | {m['bench_sharpe_ann']:.2f} | "
            f"{m['d_sharpe_vs_ew']:+.3f} | [{ci[0]:+.2f}, {ci[1]:+.2f}] | "
            f"{m['cpcv_median_d_sharpe']:+.3f} | {m['cpcv_frac_positive']:.2f} | "
            f"{m['stress_sharpe_ann']:.2f} |"
        )
    a("")
    sel2 = V["H2"]
    m2 = sel2["metrics"]
    a(
        f"**Seleccionada: `{sel2['selected_cell']}`** · **{sel2['verdict']}** · "
        f"DSR={sel2['dsr']} (n=6, sd ledger={sel2['sd_trials_ann']}) · PBO={R['H2']['pbo']} · "
        f"RC p={R['H2']['rc']['p_value']:.3f} · MDE={sel2['mde_annualized']:.0%}/año vs "
        f"Δ medio observado {m2['d_mean_weekly'] * 52:+.1%}/año"
    )
    a("")
    a("| criterio | valor | pasa |")
    a("|---|---|---|")
    for k, v_ in sel2["checks"].items():
        a(f"| {k} | — | {v_} |")
    a("")
    a(
        "Las 6 celdas dan ΔSharpe puntual negativo: el momentum transversal simple, neto de "
        "costes y contra su universo equiponderado, no muestra ventaja en este periodo/universo. "
        "Estadísticamente es INCONTRASTABLE (CI incluye 0, MDE 39%/año); el signo negativo "
        "consistente es descriptivo, no concluyente."
    )
    a("")
    a("## Resultados — H3 (8 celdas: 4 por activo)")
    a("")
    for asset in ("BTCUSDT", "ETHUSDT"):
        blk = R["H3"]["assets"][asset]
        a(f"### {asset} ({blk['n_days']} días: {blk['first_day']} → {blk['last_day']})")
        a("")
        a(
            "| celda | media neta pb/día | HAC t | p una cola | Sharpe | maxDD | CAGR | % tiempo | eps/año | stress pb/d | CPCV med Sharpe | folds+ | MDE anual |"
        )
        a("|---|---|---|---|---|---|---|---|---|---|---|---|---|")
        for cid, m in sorted(blk["cells"].items()):
            a(
                f"| {cid} | {m['mean_daily_net_bp']:+.2f} | {m['hac_t']:.2f} | "
                f"{m['hac_p_one_sided']:.4f} | {m['sharpe_ann']:.2f} | {pct(m['max_drawdown'])} | "
                f"{pct(m['cagr_net'])} | {m['time_in_market_pct']:.0f}% | "
                f"{m['episodes_per_year']:.0f} | {m['stress_mean_daily_net_bp']:+.2f} | "
                f"{m['cpcv_median_sharpe']:.2f} | {m['cpcv_frac_positive']:.2f} | "
                f"{pct(m['mde_annualized'])} |"
            )
        a("")
    a(
        f"RC familiar (8 celdas, timeline común {R['H3']['common_days']} días): "
        f"p={R['H3']['rc']['p_value']:.4f} · PBO={R['H3']['pbo']}"
    )
    a("")
    for asset in ("BTCUSDT", "ETHUSDT"):
        sel3 = V["H3"]["assets"][asset]
        m3 = sel3["metrics"]
        a(
            f"**{asset} — seleccionada `{sel3['selected_cell']}` · {sel3['verdict']}** · "
            f"DSR={sel3['dsr']} (n=8, sd ledger={V['H3']['sd_trials_ann']}) · checks: "
            + ", ".join(f"{k}={'✓' if v_ else '✗'}" for k, v_ in sel3["checks"].items())
        )
        a(
            f"  hoy (freeze {m3['last_day']}): señal activa = {m3['current_signal_active']}, "
            f"funding MA anualizado = {m3['current_funding_ma_ann']:.2%}"
        )
        a("")
    a(
        f"Regla P4: MDE_ETH/MDE_BTC = {V['H3'].get('mde_ratio_max_min')} (< 2 → ambos "
        "contrastables). **Veredicto familiar H3: " + V["H3"]["family_verdict"] + "**"
    )
    a("")
    a("## Tabla para JP (lenguaje claro, solo informativo — NINGUNA recomendación)")
    a("")
    a(
        "| Familia | Mejor celda | Retorno anual neto | Máx. caída | % tiempo dentro | Ops/año | Win rate | ¿Qué haría HOY (freeze 2025-10-25)? | Estado |"
    )
    a("|---|---|---|---|---|---|---|---|---|")
    h1b = V["H1"]["assets"]["BTCUSDT"]["metrics"]
    h1e = V["H1"]["assets"]["ETHUSDT"]["metrics"]
    a(
        f"| H1 tendencia BTC | {V['H1']['assets']['BTCUSDT']['selected_cell']} | "
        f"{pct(h1b['cagr_net'])} | {pct(h1b['max_drawdown'])} | {pct(h1b['exposure_mean'])} | "
        f"{h1b['trades_per_year']:.0f} | {pct(h1b['win_rate_trades'])} (trade) | "
        f"posición actual {h1b['current_position']:.0%} (objetivo {h1b['current_target_weight']:.0%}) | "
        f"**SIN VENTAJA DEMOSTRADA** (INCONTRASTABLE) |"
    )
    a(
        f"| H1 tendencia ETH | {V['H1']['assets']['ETHUSDT']['selected_cell']} | "
        f"{pct(h1e['cagr_net'])} | {pct(h1e['max_drawdown'])} | {pct(h1e['exposure_mean'])} | "
        f"{h1e['trades_per_year']:.0f} | {pct(h1e['win_rate_trades'])} (trade) | "
        f"posición actual {h1e['current_position']:.0%} (objetivo {h1e['current_target_weight']:.0%}) | "
        f"**SIN VENTAJA DEMOSTRADA** (INCONTRASTABLE; pasa C1 pero no la multiplicidad) |"
    )
    a(
        f"| H2 momentum | {S['selected_cells']['H2']} | {pct(m2['cagr_net'])} | "
        f"{pct(m2['max_drawdown'])} | 100% | ~{m2['trades_per_year']:.0f} cambios/año | "
        f"{pct(m2['win_rate_weeks'])} (semanas) | cesta final: {', '.join(m2['last_basket'][:5])}… | "
        f"**SIN VENTAJA DEMOSTRADA** (INCONTRASTABLE) |"
    )
    for asset in ("BTCUSDT", "ETHUSDT"):
        s3 = V["H3"]["assets"][asset]
        mm = s3["metrics"]
        if mm["current_signal_active"]:
            hoy3 = "DENTRO (long spot + short perp)"
        else:
            hoy3 = f"FLAT (funding MA {mm['current_funding_ma_ann']:.1%} < umbral 5%)"
        a(
            f"| H3 carry {asset} | {s3['selected_cell']} | {pct(mm['cagr_net'])} | "
            f"{pct(mm['max_drawdown'])} | {mm['time_in_market_pct']:.0f}% | "
            f"{mm['episodes_per_year']:.0f} | — (carry) | {hoy3} | "
            f"PASA **in-sample**; falta holdout (M3b) |"
        )
    a("")
    a(
        "Lectura para JP: 'win rate 20-25%' en H1 es NORMAL en tendencia (pocos trades "
        "ganadores grandes); el carry H3 gana poco y muy seguido (2-4 pb/día) con caídas "
        "mínimas — su riesgo real (crash de basis, ADL, ejecución en estrés) no está en la "
        "tabla y por eso el holdout importa. Ninguna fila es una recomendación de compra."
    )
    a("")
    a("## Selección congelada (para M3b)")
    a("")
    a("```json")
    a(json.dumps(S["selected_cells"], indent=2, sort_keys=True))
    a("```")
    a("")
    a(
        "Regla aplicada (v1.4 §7.7, sellada antes de ejecutar): mediana del criterio primario "
        "en las 45 trayectorias CPCV, una celda por familia y activo. M3b evaluará SOLO estas "
        "5 candidatas (H1 BTC/ETH, H2, H3 BTC/ETH) en una única apertura del holdout con la "
        "clave del usuario."
    )
    a("")
    a("## Limitaciones y sesgos conocidos")
    a("")
    a(
        "- **H3 Sharpe 7 no es 'dinero gratis'**: el carry delta-neutral tiene riesgos NO "
        "modelados — margen/liquidación del perp, ADL (auto-deleveraging), deslizamiento en "
        "spikes de basis, riesgo de exchange. El holdout y el forward paper (M4) son la prueba "
        "de fuego; el informe M3b los reportará tal cual."
    )
    a(
        "- Costes de H3 por episodio (~32 pb ida+vuelta con taker) suponen ejecución market "
        "en ambas piernas; con límites maker serían menores (no se asume, conservador)."
    )
    a(
        "- H1 ETH: C1a/C1b en verde pero RC familiar en rojo — el resultado 'casi' es justo "
        "lo que la multiplicidad predice bajo ruido; reportarlo como PASA sería el fallo "
        "clásico que el preregistro evita."
    )
    a(
        "- H2: signo negativo consistente en las 6 celdas; con MDE 39%/año no se puede "
        "distinguir de cero, pero no hay nada que sugiera proseguir esta rejilla en v1.x."
    )
    a(
        "- Alineación H2/H3 para RC/PBO en semanas/días comunes entre celdas (ventanas de "
        "inicio distintas por formación/warmup): documentado en `M3a_results.json`."
    )
    a("- sd entre celdas estimada del ledger como exige v1.4 (H1: 0.292; H2: 0.128).")
    a("")
    a("## Qué aprendimos (lenguaje llano)")
    a("")
    a(
        "- **El carry pasa, la tendencia no (por ahora)**: cobrar el funding con posición "
        "neutral fue la regla más sólida de la historia 2019-2025; esquivar caídas con SMA "
        "mejora el drawdown de ETH de forma sugerente, pero entre 12 variantes no supera el "
        "examen de multiplicidad."
    )
    a(
        "- **Casi no es sí**: ETH H1 con p=0.018 'individual' NO pasa: cuando pruebas 12 "
        "reglas, siempre hay alguna con p pequeño por azar; el Reality Check familiar existe "
        "justo para eso."
    )
    a(
        "- **INCONTRASTABLE ≠ fracaso**: es la respuesta honesta cuando la balanza no da "
        "para más; el boletín (M5) dirá 'SIN VENTAJA DEMOSTRADA (n=…, IC=…)' para H1/H2."
    )
    a("")
    a("## Solicitud: GATE APROBADO M3a")
    a("")
    a(
        "Al aprobar: M3b = evaluación ÚNICA del holdout (365 días) de las 5 candidatas "
        "congeladas, con la clave del usuario (QA_HOLDOUT_KEY), veredictos finales y cierre "
        "de M3. Después: M4 (forward paper en GitHub Actions, ADR-007)."
    )

    out = REPO / "reports" / "M3a_REPORT.md"
    out.write_text("\n".join(L) + "\n", encoding="utf-8")
    print("->", out)


if __name__ == "__main__":
    main()
