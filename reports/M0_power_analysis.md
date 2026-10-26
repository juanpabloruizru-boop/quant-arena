# Analisis de potencia v1.2 - M0c/M1 (QUANT-ARENA v2)

- Generado: 2026-10-26T19:06:04+00:00 | semilla: 20261026 | alpha una cola 5% | potencia objetivo 80% | K = 2.4865
- Horizontes in-sample: H1 8.19 a, H2 6.82 a, H3 6.13 a. Coste por lado: 13 pb. Banda: 10 pp.
- **Nota v1.2:** Tablas v1.1 de exposure-matched como criterio RETIRADAS (defecto 1 gate M0b: sesgo de Jensen E[w^2]>=ebar^2 contra exposicion variable bajo el nulo). Benchmark primario: vol-matched. Criterio: permutacion del vector de exposicion.

## S1. MDE de diferencia de Sharpe (no pareada; cota conservadora)
| anios | MDE DSharpe |
|---|---|
| 3.3 | 1.936 |
| 5.0 | 1.573 |
| 8.2 | 1.228 |
| 10.0 | 1.112 |
| 15.0 | 0.908 |
| 20.0 | 0.786 |
| 30.0 | 0.642 |
| 50.0 | 0.497 |

## S1b. Anios necesarios por efecto objetivo
| DSharpe | anios |
|---|---|
| 0.2 | 309.1 |
| 0.3 | 137.4 |
| 0.5 | 49.5 |
| 1.0 | 12.4 |
| 1.5 | 5.5 |

## S2. Sharpe minimo para DSR >= 0.95 (gate de H2/H3; informativo en H1)
| anios | n_trials | sd celdas | skew | kurt | SR0 | Sharpe min |
|---|---|---|---|---|---|---|
| 3.3 | 38 | 0.5 | 0.0 | 3.0 | 1.085 | 1.993 |
| 3.3 | 38 | 0.5 | -0.5 | 6.0 | 1.085 | 2.02 |
| 3.3 | 38 | 0.75 | 0.0 | 3.0 | 1.627 | 2.537 |
| 3.3 | 38 | 0.75 | -0.5 | 6.0 | 1.627 | 2.573 |
| 3.3 | 60 | 0.5 | 0.0 | 3.0 | 1.173 | 2.081 |
| 3.3 | 60 | 0.5 | -0.5 | 6.0 | 1.173 | 2.11 |
| 3.3 | 60 | 0.75 | 0.0 | 3.0 | 1.759 | 2.669 |
| 3.3 | 60 | 0.75 | -0.5 | 6.0 | 1.759 | 2.707 |
| 8.2 | 38 | 0.5 | 0.0 | 3.0 | 1.085 | 1.66 |
| 8.2 | 38 | 0.5 | -0.5 | 6.0 | 1.085 | 1.674 |
| 8.2 | 38 | 0.75 | 0.0 | 3.0 | 1.627 | 2.203 |
| 8.2 | 38 | 0.75 | -0.5 | 6.0 | 1.627 | 2.223 |
| 8.2 | 60 | 0.5 | 0.0 | 3.0 | 1.173 | 1.748 |
| 8.2 | 60 | 0.5 | -0.5 | 6.0 | 1.173 | 1.763 |
| 8.2 | 60 | 0.75 | 0.0 | 3.0 | 1.759 | 2.336 |
| 8.2 | 60 | 0.75 | -0.5 | 6.0 | 1.759 | 2.356 |

## S3. Calibracion del nulo (GBM sin habilidad) - criterio v1.2 completo
| metrica | valor | lectura |
|---|---|---|
| E[DmaxDD vol-matched] | 4.42 pp | debe ser ~0 (identidad) |
| E[DmaxDD exposure-matched] (diagnostico) | 17.16 pp | sesgo de Jensen: NO es criterio |
| E[DmaxDD vs B&H crudo] | -40.24 pp | efecto exposicion, no skill |
| p medio de permutacion | 0.5198 | ~0.5 = uniforme |
| FPR P(p<0.05) | 0.066 | <= 0.05 nominal |
| FPR regla compuesta | 0.066 | <= 0.05 nominal |
| turnover/ano, sangria costes | 6.57x, 0.854 %/ano | con banda 10 pp |

## S4. Habilidad plantada (drift AR(1) calibrado) - potencia REAL por efecto
### S4a. Calibracion
| ventana | objetivo DSharpe | s_mu diario | logrado (cal) |
|---|---|---|---|
| 100 | 0.1 | 0.0001671 | 0.1298 |
| 100 | 0.3 | 0.00024911 | 0.3376 |
| 100 | 0.5 | 0.00031601 | 0.5685 |
| 200 | 0.1 | 0.00015349 | 0.1372 |
| 200 | 0.3 | 0.00021931 | 0.2999 |
| 200 | 0.5 | 0.00029777 | 0.5127 |

### S4b. Potencia del criterio v1.2 (permutacion + subperiodos)
| ventana | DSharpe obj | DSharpe logrado | pot. perm p<0.05 | pot. (p<.05 y D<0) | P(>=2/3 subp.) | pot. REGLA COMPUESTA | E[DmaxDD_vm] pp |
|---|---|---|---|---|---|---|---|
| 100 | 0.1 | 0.1129 | 0.1725 | 0.1725 | 0.6475 | 0.165 | -6.99 |
| 100 | 0.3 | 0.3115 | 0.28 | 0.28 | 0.7525 | 0.265 | -14.38 |
| 100 | 0.5 | 0.4967 | 0.4025 | 0.4025 | 0.8525 | 0.39 | -20.48 |
| 200 | 0.1 | 0.1151 | 0.1875 | 0.1875 | 0.625 | 0.175 | -6.76 |
| 200 | 0.3 | 0.2794 | 0.245 | 0.245 | 0.7275 | 0.235 | -13.11 |
| 200 | 0.5 | 0.4961 | 0.4325 | 0.4325 | 0.8275 | 0.415 | -20.6 |

## S6. Sensibilidad de la banda de rebalanceo (ventana 200)
| dgp | banda | turnover/ano | sangria %/ano | E[DmaxDD_vm] pp | E[DSharpe] |
|---|---|---|---|---|---|
| gbm | 0.0 | 8.19 | 1.064 | 4.32 | -0.1614 |
| gbm | 0.02 | 7.65 | 0.994 | 4.19 | -0.1574 |
| gbm | 0.05 | 7.05 | 0.916 | 4.07 | -0.1528 |
| gbm | 0.1 | 6.57 | 0.855 | 4.05 | -0.1488 |
| gbm | 0.2 | 6.14 | 0.798 | 3.89 | -0.1444 |
| ms_vol_jump | 0.0 | 7.84 | 1.019 | -0.29 | 0.0112 |
| ms_vol_jump | 0.02 | 7.44 | 0.968 | -0.38 | 0.0143 |
| ms_vol_jump | 0.05 | 6.98 | 0.908 | -0.47 | 0.0164 |
| ms_vol_jump | 0.1 | 6.54 | 0.851 | -0.57 | 0.0185 |
| ms_vol_jump | 0.2 | 6.14 | 0.798 | -0.73 | 0.019 |

## S7. H2 momentum transversal (spread semanal)
| n sem | sigma sem | rho | MDE sem | MDE anual |
|---|---|---|---|---|
| 354 | 0.03 | 0.0 | 0.00396 | 0.206 |
| 354 | 0.03 | 0.15 | 0.00461 | 0.2396 |
| 354 | 0.04 | 0.0 | 0.00528 | 0.2747 |
| 354 | 0.04 | 0.15 | 0.00614 | 0.3195 |
| 354 | 0.05 | 0.0 | 0.0066 | 0.3433 |
| 354 | 0.05 | 0.15 | 0.00768 | 0.3993 |

### S7b. Anios necesarios (sigma 4%/sem, rho 0.15)
| mu semanal | anios |
|---|---|
| 0.001 | 257.4 |
| 0.002 | 64.3 |
| 0.004 | 16.1 |

## S8. H3 carry delta-neutral (neto diario)
| n dias | sigma dia | rho | MDE diario | MDE anual |
|---|---|---|---|---|
| 2237 | 0.0005 | 0.0 | 2.63e-05 | 0.0096 |
| 2237 | 0.0005 | 0.1 | 2.91e-05 | 0.0106 |
| 2237 | 0.001 | 0.0 | 5.26e-05 | 0.0192 |
| 2237 | 0.001 | 0.1 | 5.81e-05 | 0.0212 |
| 2237 | 0.002 | 0.0 | 0.0001051 | 0.0384 |
| 2237 | 0.002 | 0.1 | 0.0001162 | 0.0424 |

### S8b. Anios necesarios (sigma 10 pb/dia, rho 0.10)
| mu anual | anios |
|---|---|
| 0.01 | 27.58 |
| 0.02 | 6.9 |
| 0.04 | 1.72 |

## S9. Discriminar tasas de acierto
| WR nulo | WR alt | n trades |
|---|---|---|
| 0.4 | 0.42 | 3729 |
| 0.4 | 0.45 | 600 |
| 0.4 | 0.5 | 151 |

