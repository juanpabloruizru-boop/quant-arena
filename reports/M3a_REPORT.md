# M3a · Investigación in-sample (una sola pasada, rejilla congelada v1.4) · 2026-10-28T14:22:44+00:00 · freeze commit `f834bfd` · tag `m3a-freeze`

## Resumen en 5 líneas

1. **38/38 trials registrados en el ledger** (H1: 24, H2: 6, H3: 8 — la rejilla exacta de v1.4); parámetros de producción: n_perm=10 000, RC B=2 000, CPCV(10,2)=45, PBO-CSCV(16, 1000 combos), bootstrap 10 000, capital 10 000 USDT, semilla 20261027.
2. **H3 (carry spot-perp) = PASA_IS en BTC y ETH** (celda w30_t5): neto diario +2.9/+3.7 pb (HAC t=5.3/5.2), DSR=1.00 (n_trials familiar 8), PBO=0.018, RC p<0.001, folds 100%/98%, aguanta costes ×2 (+2.6/+3.4 pb). Pasa a M3b.
3. **H1 = INCONTRASTABLE** (pre-declarado en v1.4 §8): BTC perm_p=0.19; ETH **sí pasa C1a/C1b** (perm_p=0.018, ΔmaxDD_vm −20.2 pp, 3/3 subperíodos) pero **no supera el RC familiar** (p=0.23) — la multiplicidad de 12 celdas explica el hallazgo; veredicto INCONTRASTABLE por política pre-registrada.
4. **H2 = INCONTRASTABLE**: las 6 celdas dan ΔSharpe negativo vs universo EW (−0.01 a −0.28); la seleccionada (L26_N10) tiene CI [−0.50, +0.28] (incluye 0), DSR 0.81, PBO 0.54, MDE ≈ 39 %/año ≫ efecto: sin potencia, como se declaró.
5. **Holdout intacto**: `ledger/holdout_access.log` sin entradas nuevas (2 líneas, sha256 `4d0f3442…` igual que la baseline M2c); ninguna métrica de M3a tocó `holdout_sealed/`.

## Gates

| Gate | Comando | Resultado | Evidencia |
|---|---|---|---|
| Lint/tipos/tests | `ruff check . && mypy && pytest` | ✅ 77/77 | consola |
| Registro obligatorio | `ledger/trials.duckdb` | ✅ 38 filas strategy (24+6+8) + benchmarks/diagnósticos | `qa stats report` |
| n_trials desde ledger | `family_sharpes()` | ✅ sd familiar estimada del ledger (H1 0.292, H2 0.128, H3 ver JSON) | `M3a_results.json` |
| Holdout sin tocar | `wc -l ledger/holdout_access.log` + sha256 | ✅ 2 líneas, sha idéntico | este informe |
| Una sola pasada | celdas ejecutadas una vez; reruns = cache del ledger | ✅ | run_ids deterministas |
| Congelación | commit + SHA256 + tag `m3a-freeze` + OTS | ✅ | `reports/M3a_selected_cells.json` |

## Resultados — H1 (24 celdas: 12 por activo)

### BTCUSDT (RC familiar p=0.2025 · PBO=0.062)

| celda | Sharpe | ΔSharpe vs B&H | maxDD | ΔmaxDD_vm (pp) | perm p | p adverso | subs (n/3) | CPCV med (pp) | folds+ | stress Δvm | trades/año | WR | expo |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| ret100_s15 | 0.69 | -0.23 | 31.0% | +3.7 | 0.5437 | 0.456 | 1/3 (-8/+0/+8) | +0.5 | 0.44 | +4.2 | 5.9 | 0.33 | 0.18 |
| ret100_s25 | 0.65 | -0.28 | 45.9% | +6.2 | 0.5946 | 0.405 | 1/3 (-9/+1/+7) | +2.5 | 0.38 | +6.9 | 5.9 | 0.33 | 0.28 |
| ret200_s15 | 0.59 | -0.33 | 26.4% | +0.0 | 0.3658 | 0.634 | 0/3 (+4/+2/+4) | +0.3 | 0.49 | +1.2 | 4.3 | 0.40 | 0.19 |
| ret200_s25 | 0.56 | -0.37 | 40.6% | +1.3 | 0.4130 | 0.587 | 0/3 (+4/+7/+3) | +3.1 | 0.40 | +2.9 | 4.3 | 0.43 | 0.32 |
| ret50_s15 | 1.11 | +0.19 | 27.2% | +0.8 | 0.3873 | 0.613 | 1/3 (+3/-3/+6) | -1.6 | 0.53 | +1.9 | 10.9 | 0.40 | 0.17 |
| ret50_s25 | 1.10 | +0.17 | 38.0% | -0.7 | 0.3091 | 0.691 | 1/3 (+4/-5/+7) | -1.7 | 0.60 | +0.9 | 10.9 | 0.39 | 0.28 |
| sma100_s15 | 1.12 | +0.20 | 18.1% | -7.9 | 0.0593 | 0.941 | 2/3 (-7/-7/+8) | -2.2 | 0.67 | -7.4 | 6.8 | 0.23 | 0.17 |
| sma100_s25 | 1.10 | +0.17 | 23.5% | -14.9 | 0.0163 | 0.984 | 2/3 (-8/-7/+8) | -4.0 | 0.69 | -14.0 | 6.8 | 0.21 | 0.28 |
| sma200_s15 | 0.75 | -0.18 | 20.8% | -4.0 | 0.1789 | 0.821 | 1/3 (+1/-0/+3) | +1.7 | 0.38 | -3.8 | 3.8 | 0.26 | 0.17 |
| sma200_s25 | 0.75 | -0.17 | 32.0% | -5.3 | 0.1690 | 0.831 | 0/3 (+2/+2/+4) | +1.3 | 0.40 | -4.9 | 3.8 | 0.26 | 0.28 |
| sma50_s15 | 1.39 | +0.46 | 23.2% | -2.8 | 0.2105 | 0.790 | 1/3 (-4/+3/+1) | -3.2 | 0.76 | -2.2 | 9.5 | 0.24 | 0.16 |
| sma50_s25 | 1.38 | +0.45 | 33.9% | -4.4 | 0.1871 | 0.813 | 1/3 (-4/+3/+3) | -4.6 | 0.71 | -3.5 | 9.5 | 0.21 | 0.27 |

**Seleccionada (mediana CPCV): `sma50_s25`** · veredicto: **INCONTRASTABLE** · DSR informativo: 0.9919 (n_trials=24 familiar, sd ledger=0.2922)

| criterio | valor | pasa |
|---|---|---|
| C1a perm p≤0.025 y Δ<0 | p=0.1871, Δ=-4.4pp | False |
| C1b subperíodos ≥2/3 | 1/3 | False |
| C2' RC familiar p<0.05 | p=0.2025 | False |
| C3 PBO<0.20 | 0.062 | True |
| C4 stress ×2 | Δvm=-3.5pp, ΔSharpe=+0.39 | True |
| C5 folds ≥60% | 0.71 | True |

### ETHUSDT (RC familiar p=0.2290 · PBO=0.055)

| celda | Sharpe | ΔSharpe vs B&H | maxDD | ΔmaxDD_vm (pp) | perm p | p adverso | subs (n/3) | CPCV med (pp) | folds+ | stress Δvm | trades/año | WR | expo |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| ret100_s15 | 1.17 | +0.37 | 14.9% | -16.3 | 0.0071 | 0.993 | 3/3 (-10/-4/-4) | -1.5 | 0.71 | -16.3 | 4.9 | 0.40 | 0.12 |
| ret100_s25 | 1.17 | +0.37 | 24.4% | -20.9 | 0.0113 | 0.989 | 3/3 (-13/-8/-5) | -2.3 | 0.69 | -20.1 | 4.9 | 0.40 | 0.21 |
| ret200_s15 | 0.38 | -0.43 | 26.7% | -4.7 | 0.3597 | 0.640 | 2/3 (-3/-0/+4) | +1.1 | 0.31 | -4.5 | 5.2 | 0.33 | 0.13 |
| ret200_s25 | 0.42 | -0.39 | 45.8% | -0.1 | 0.5538 | 0.446 | 1/3 (+2/-2/+4) | +2.7 | 0.31 | +0.3 | 5.2 | 0.35 | 0.22 |
| ret50_s15 | 1.17 | +0.36 | 18.0% | -12.9 | 0.0480 | 0.952 | 2/3 (-8/-3/+0) | -1.8 | 0.64 | -12.7 | 8.9 | 0.42 | 0.13 |
| ret50_s25 | 1.20 | +0.39 | 29.6% | -15.8 | 0.0619 | 0.938 | 2/3 (-13/-2/+1) | -3.7 | 0.64 | -15.4 | 8.9 | 0.41 | 0.21 |
| sma100_s15 | 1.10 | +0.29 | 17.3% | -13.5 | 0.0365 | 0.964 | 3/3 (-14/-2/-1) | -2.2 | 0.67 | -12.9 | 6.6 | 0.24 | 0.13 |
| sma100_s25 | 1.06 | +0.26 | 30.1% | -14.6 | 0.0835 | 0.917 | 1/3 (-20/+1/+1) | -2.9 | 0.71 | -13.9 | 6.6 | 0.24 | 0.21 |
| sma200_s15 | 0.89 | +0.09 | 15.9% | -13.8 | 0.0389 | 0.961 | 3/3 (-5/-3/-9) | -1.4 | 0.64 | -13.7 | 2.9 | 0.38 | 0.12 |
| sma200_s25 | 0.96 | +0.16 | 23.9% | -20.1 | 0.0199 | 0.980 | 3/3 (-6/-6/-13) | -2.1 | 0.71 | -19.7 | 2.9 | 0.33 | 0.20 |
| sma50_s15 | 1.18 | +0.38 | 14.4% | -15.1 | 0.0136 | 0.987 | 3/3 (-11/-4/-4) | -3.5 | 0.76 | -14.6 | 10.1 | 0.27 | 0.12 |
| sma50_s25 | 1.22 | +0.41 | 24.7% | -20.2 | 0.0177 | 0.982 | 3/3 (-16/-3/-7) | -5.3 | 0.69 | -19.4 | 10.1 | 0.25 | 0.20 |

**Seleccionada (mediana CPCV): `sma50_s25`** · veredicto: **INCONTRASTABLE** · DSR informativo: 0.969 (n_trials=24 familiar, sd ledger=0.2922)

| criterio | valor | pasa |
|---|---|---|
| C1a perm p≤0.025 y Δ<0 | p=0.0177, Δ=-20.2pp | True |
| C1b subperíodos ≥2/3 | 3/3 | True |
| C2' RC familiar p<0.05 | p=0.2290 | False |
| C3 PBO<0.20 | 0.055 | True |
| C4 stress ×2 | Δvm=-19.4pp, ΔSharpe=+0.36 | True |
| C5 folds ≥60% | 0.69 | True |

**Veredicto familiar H1: INCONTRASTABLE** — coherente con la pre-declaración v1.4 §8 (potencia pipeline 9.5-18.5% para ΔSharpe 0.1-0.3). Nota: ETH supera C1a+C1b+C3+C4+C5 pero no el control de multiplicidad C2' (RC): con 12 celdas por activo, un p=0.018 aislado no sobrevive al test familiar. Ningún p adverso ≤ t* → no hay evidencia de daño, solo ausencia de evidencia.

## Resultados — H2 (6 celdas, universo PIT)

| celda | semanas | Sharpe | Sharpe EW bench | ΔSharpe | CI95 ΔSharpe | CPCV med | folds+ | stress Sharpe |
|---|---|---|---|---|---|---|---|---|
| L12_N10 | 343 | 0.60 | 0.61 | -0.010 | [-0.30, +0.27] | -0.044 | 0.42 | 0.57 |
| L12_N20 | 343 | 0.38 | 0.51 | -0.124 | [-0.42, +0.18] | -0.089 | 0.36 | 0.35 |
| L26_N10 | 343 | 0.51 | 0.61 | -0.093 | [-0.50, +0.28] | +0.070 | 0.62 | 0.49 |
| L26_N20 | 343 | 0.22 | 0.51 | -0.282 | [-0.73, +0.11] | -0.183 | 0.33 | 0.20 |
| L4_N10 | 343 | 0.40 | 0.61 | -0.207 | [-0.52, +0.08] | -0.203 | 0.24 | 0.35 |
| L4_N20 | 343 | 0.48 | 0.51 | -0.026 | [-0.27, +0.22] | -0.025 | 0.42 | 0.43 |

**Seleccionada: `L26_N10`** · **INCONTRASTABLE** · DSR=0.8116 (n=6, sd ledger=0.1281) · PBO=0.535 · RC p=0.761 · MDE=39%/año vs Δ medio observado -4.2%/año

| criterio | valor | pasa |
|---|---|---|
| C1_dsharpe_CI_excluye_0 | — | False |
| C2_dsr>0.95 | — | False |
| C3_pbo<0.20 | — | False |
| C4_stress_sharpe>0 | — | True |
| C5_folds>=60% | — | True |
| C6_rc_p<0.05 | — | False |

Las 6 celdas dan ΔSharpe puntual negativo: el momentum transversal simple, neto de costes y contra su universo equiponderado, no muestra ventaja en este periodo/universo. Estadísticamente es INCONTRASTABLE (CI incluye 0, MDE 39%/año); el signo negativo consistente es descriptivo, no concluyente.

## Resultados — H3 (8 celdas: 4 por activo)

### BTCUSDT (2238 días: 2019-09-10 → 2025-10-25)

| celda | media neta pb/día | HAC t | p una cola | Sharpe | maxDD | CAGR | % tiempo | eps/año | stress pb/d | CPCV med Sharpe | folds+ | MDE anual |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| w30_t10 | +2.35 | 4.26 | 0.0000 | 6.07 | 2.2% | 8.9% | 35% | 21 | +2.18 | 5.82 | 0.98 | 2.5% |
| w30_t5 | +2.91 | 5.34 | 0.0000 | 7.25 | 2.1% | 11.2% | 71% | 42 | +2.61 | 7.76 | 1.00 | 2.4% |
| w7_t10 | +2.36 | 6.88 | 0.0000 | 4.88 | 1.9% | 9.0% | 41% | 24 | +1.87 | 4.91 | 0.96 | 2.2% |
| w7_t5 | +2.43 | 6.84 | 0.0000 | 4.82 | 2.8% | 9.3% | 69% | 41 | +1.54 | 4.54 | 0.93 | 2.3% |

### ETHUSDT (2160 días: 2019-11-27 → 2025-10-25)

| celda | media neta pb/día | HAC t | p una cola | Sharpe | maxDD | CAGR | % tiempo | eps/año | stress pb/d | CPCV med Sharpe | folds+ | MDE anual |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| w30_t10 | +3.25 | 4.49 | 0.0000 | 6.28 | 1.7% | 12.6% | 42% | 26 | +3.05 | 7.54 | 0.98 | 2.9% |
| w30_t5 | +3.69 | 5.15 | 0.0000 | 7.02 | 1.7% | 14.4% | 71% | 44 | +3.38 | 8.00 | 0.98 | 2.9% |
| w7_t10 | +3.06 | 7.02 | 0.0000 | 5.68 | 2.2% | 11.8% | 43% | 26 | +2.60 | 5.67 | 0.93 | 3.0% |
| w7_t5 | +3.37 | 7.67 | 0.0000 | 6.08 | 2.8% | 13.0% | 72% | 44 | +2.66 | 6.35 | 0.93 | 2.9% |

RC familiar (8 celdas, timeline común 2160 días): p=0.0000 · PBO=0.018

**BTCUSDT — seleccionada `w30_t5` · PASA_IS** · DSR=1.0 (n=8, sd ledger=0.8825) · checks: C1_media>0_HAC_p<0.05=✓, C2_dsr>0.95=✓, C3_pbo<0.20=✓, C4_stress_media>0=✓, C5_folds>=60%=✓, C6_rc_p<0.05=✓
  hoy (freeze 2025-10-25): señal activa = False, funding MA anualizado = 3.30%

**ETHUSDT — seleccionada `w30_t5` · PASA_IS** · DSR=1.0 (n=8, sd ledger=0.8825) · checks: C1_media>0_HAC_p<0.05=✓, C2_dsr>0.95=✓, C3_pbo<0.20=✓, C4_stress_media>0=✓, C5_folds>=60%=✓, C6_rc_p<0.05=✓
  hoy (freeze 2025-10-25): señal activa = False, funding MA anualizado = 3.57%

Regla P4: MDE_ETH/MDE_BTC = 1.187 (< 2 → ambos contrastables). **Veredicto familiar H3: PASA_IS**

## Tabla para JP (lenguaje claro, solo informativo — NINGUNA recomendación)

| Familia | Mejor celda | Retorno anual neto | Máx. caída | % tiempo dentro | Ops/año | Win rate | ¿Qué haría HOY (freeze 2025-10-25)? | Estado |
|---|---|---|---|---|---|---|---|---|
| H1 tendencia BTC | sma50_s25 | 31.8% | 33.9% | 26.6% | 10 | 20.5% (trade) | posición actual 0% (objetivo 0%) | **SIN VENTAJA DEMOSTRADA** (INCONTRASTABLE) |
| H1 tendencia ETH | sma50_s25 | 27.2% | 24.7% | 19.7% | 10 | 25.3% (trade) | posición actual 0% (objetivo 0%) | **SIN VENTAJA DEMOSTRADA** (INCONTRASTABLE; pasa C1 pero no la multiplicidad) |
| H2 momentum | L26_N10 | 6.0% | 90.4% | 100% | ~9 cambios/año | 53.6% (semanas) | cesta final: ETHUSDT, BNBUSDT, SOLUSDT, BTCUSDT… | **SIN VENTAJA DEMOSTRADA** (INCONTRASTABLE) |
| H3 carry BTCUSDT | w30_t5 | 11.2% | 2.1% | 71% | 42 | — (carry) | FLAT (funding MA 3.3% < umbral 5%) | PASA **in-sample**; falta holdout (M3b) |
| H3 carry ETHUSDT | w30_t5 | 14.4% | 1.7% | 71% | 44 | — (carry) | FLAT (funding MA 3.6% < umbral 5%) | PASA **in-sample**; falta holdout (M3b) |

Lectura para JP: 'win rate 20-25%' en H1 es NORMAL en tendencia (pocos trades ganadores grandes); el carry H3 gana poco y muy seguido (2-4 pb/día) con caídas mínimas — su riesgo real (crash de basis, ADL, ejecución en estrés) no está en la tabla y por eso el holdout importa. Ninguna fila es una recomendación de compra.

## Selección congelada (para M3b)

```json
{
  "H1": {
    "BTCUSDT": "sma50_s25",
    "ETHUSDT": "sma50_s25"
  },
  "H2": "L26_N10",
  "H3": {
    "BTCUSDT": "w30_t5",
    "ETHUSDT": "w30_t5"
  }
}
```

Regla aplicada (v1.4 §7.7, sellada antes de ejecutar): mediana del criterio primario en las 45 trayectorias CPCV, una celda por familia y activo. M3b evaluará SOLO estas 5 candidatas (H1 BTC/ETH, H2, H3 BTC/ETH) en una única apertura del holdout con la clave del usuario.

## Limitaciones y sesgos conocidos

- **H3 Sharpe 7 no es 'dinero gratis'**: el carry delta-neutral tiene riesgos NO modelados — margen/liquidación del perp, ADL (auto-deleveraging), deslizamiento en spikes de basis, riesgo de exchange. El holdout y el forward paper (M4) son la prueba de fuego; el informe M3b los reportará tal cual.
- Costes de H3 por episodio (~32 pb ida+vuelta con taker) suponen ejecución market en ambas piernas; con límites maker serían menores (no se asume, conservador).
- H1 ETH: C1a/C1b en verde pero RC familiar en rojo — el resultado 'casi' es justo lo que la multiplicidad predice bajo ruido; reportarlo como PASA sería el fallo clásico que el preregistro evita.
- H2: signo negativo consistente en las 6 celdas; con MDE 39%/año no se puede distinguir de cero, pero no hay nada que sugiera proseguir esta rejilla en v1.x.
- Alineación H2/H3 para RC/PBO en semanas/días comunes entre celdas (ventanas de inicio distintas por formación/warmup): documentado en `M3a_results.json`.
- sd entre celdas estimada del ledger como exige v1.4 (H1: 0.292; H2: 0.128).

## Qué aprendimos (lenguaje llano)

- **El carry pasa, la tendencia no (por ahora)**: cobrar el funding con posición neutral fue la regla más sólida de la historia 2019-2025; esquivar caídas con SMA mejora el drawdown de ETH de forma sugerente, pero entre 12 variantes no supera el examen de multiplicidad.
- **Casi no es sí**: ETH H1 con p=0.018 'individual' NO pasa: cuando pruebas 12 reglas, siempre hay alguna con p pequeño por azar; el Reality Check familiar existe justo para eso.
- **INCONTRASTABLE ≠ fracaso**: es la respuesta honesta cuando la balanza no da para más; el boletín (M5) dirá 'SIN VENTAJA DEMOSTRADA (n=…, IC=…)' para H1/H2.

## Solicitud: GATE APROBADO M3a

Al aprobar: M3b = evaluación ÚNICA del holdout (365 días) de las 5 candidatas congeladas, con la clave del usuario (QA_HOLDOUT_KEY), veredictos finales y cierre de M3. Después: M4 (forward paper en GitHub Actions, ADR-007).
