# Validacion de t* = 0.025 (condicion A, gate M2)

- Generado: 2026-10-27T17:11:10+00:00 | n_sims=5000 por mundo | n_perm=199
- Semillas NUEVAS (no las de calibracion). Objetivo FPR(p<=t*) en (0.035, 0.065).

| mundo | semilla | FPR p<=t* | FPR p<t* | FPR p<0.05 | p medio | E[DmaxDD vm] pp | en rango |
|---|---|---|---|---|---|---|---|
| gbm | 987654321 | 0.046 | 0.0392 | 0.0746 | 0.5046 | 4.02 | SI |
| ms_vol | 555444333 | 0.0154 | 0.0114 | 0.0348 | 0.4723 | 2.34 | NO |
| ms_vol_jump | 246813579 | 0.0226 | 0.0174 | 0.0476 | 0.4653 | -1.27 | NO |

**Overall en rango: False**
