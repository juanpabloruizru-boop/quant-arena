# Comparacion de esquemas de permutacion (nulo H1) - condicion 3 gate M1

- Generado: 2026-10-26T20:26:07+00:00 | n_sims=5000 | n_perm=199
- Tolerancia FPR exigida: (0.035, 0.065)

| esquema | FPR nulo (p<0.05) | FPR compuesta | p medio nulo | DSharpe logrado | potencia p<0.05 | potencia compuesta | >=2/3 subp. |
|---|---|---|---|---|---|---|---|
| block20 | 0.0668 | 0.0614 | 0.5025 | 0.3056 | 0.2806 | 0.2608 | 0.7316 |
| rotation | 0.0278 | 0.0258 | 0.5201 | 0.3056 | 0.0678 | 0.0666 | 0.7316 |

**Esquema adoptado (v1.3): `block20`** — FPR dentro de [3.5%,6.5%] y mas cercano a 5%; empate -> mayor potencia compuesta. Solo evidencia sintetica.

Calibracion habilidad: s_mu=0.00022497 (logrado en calibracion: 0.2899)
