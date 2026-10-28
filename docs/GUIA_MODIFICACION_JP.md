# GUÍA DE MODIFICACIÓN Y OPERACIÓN DIARIA PARA JP (M5b)

Todo en lenguaje llano. Esta guía asume que ya descargaste el bundle a tu PC y
ejecutaste la instalación inicial (sección 0). Si algo no funciona, mira la
sección 6 (problemas comunes). **Recordatorio importante:** esta herramienta
es un laboratorio de investigación + contabilidad personal. No da consejos;
los veredictos científicos del proyecto siguen siendo los del preregistro v1.4
(H1 y H2 SIN VENTAJA DEMOSTRADA; H3-BTC pasa solo a nivel de signo; H3-ETH no
pasa).

---

## 0. Instalación inicial en tu PC (una sola vez)

Necesitas: Python 3.11+, git y make. En la carpeta del proyecto:

```bash
git init && git fetch /ruta/a/quant-arena-M5.bundle main && git reset --mixed FETCH_HEAD
make git-config        # identidad de git local (firma SSH de los sellos)
make install           # crea .venv e instala el paquete (qa)
```

Comprobación rápida: `.venv/bin/qa --help` debe listar los comandos
(`data`, `research`, `stats`, `forward`, `report`, `agent`, `trade`,
`capital`).

---

## 0b. Acceso rápido en Windows (doble clic) — M5c

Para máxima comodidad en Windows, se incluyen dos scripts `.bat` en la raíz
del proyecto. Solo tienes que hacer doble clic:

| Script | Qué hace |
|---|---|
| **`1_ACTUALIZAR_Y_ABRIR_DASHBOARD.bat`** | Activa el `.venv`, ejecuta `qa agent run` (descarga datos vivos, regenera dashboard) y abre automáticamente `reports\dashboard\index.html` en tu navegador predeterminado. Úsalo cada mañana como rutina diaria. |
| **`2_CONSOLA_QUANT_ARENA.bat`** | Abre una ventana de consola (`cmd`) ya situada en la carpeta del proyecto y con el `.venv` activado. Muestra en pantalla el recordatorio de comandos rápidos (`qa capital status`, `qa trade calc`, `qa trade open`, `qa trade close`, `qa trade audit`) para que escribas directamente. |

> **Nota:** En Windows, `qa` se invoca como `qa` (no `.venv/bin/qa`) porque el `.bat` ya activa el entorno. Los ejemplos de esta guía usan la forma Unix (`.venv/bin/qa`); en Windows sustituye por `qa` tras activar el `.venv` (o usa los `.bat`).

---

## 1. Operación diaria desde cero

### Paso 1 — Borrar los datos de EJEMPLO

El proyecto viene con ejemplos marcados (`[EJEMPLO]`) en los dos libros:
capital ($1,000 + $200) y operaciones (2 cerradas + 2 abiertas). Para
empezar limpio con TU dinero real:

```bash
.venv/bin/qa capital reset-examples
```

- Solo borra registros marcados `example=true` (los tuyos reales NUNCA se
  tocan).
- Antes de borrar crea copias de seguridad en `ledger/backup/` por si te
  arrepientes.
- Reconstruye y reverifica las cadenas de hashes de ambos libros.

### Paso 2 — Fijar tu capital inicial y registrar aportes/retiros

```bash
.venv/bin/qa capital set --amount 1000 --note "Capital inicial"
.venv/bin/qa capital add --amount 250 --note "Adición mensual"
.venv/bin/qa capital add --amount -100 --note "Retiro parcial"   # negativo = retiro
```

### Paso 3 — Consultar tu ecuación patrimonial

```bash
.venv/bin/qa capital status
```

Muestra: (1) Capital Aportado Neto + tabla de movimientos, (2) PnL Realizado
neto de comisiones, (3) PnL Flotante a precios vivos, (4) Patrimonio Total
(Equity Vivo) y (5) Portfolio Heat (lo que perderías si TODOS tus stops
saltaran hoy a la vez). Necesita internet (precios públicos de Binance, sin
claves). El Equity Vivo se usa automáticamente como base de la columna
*Escala teórica* de H1 en el dashboard.

### Paso 4 — La calculadora antes de anotar nada

```bash
.venv/bin/qa trade calc --entry 80848 --sl 78500 --tp 87000 --kind spot
```

Te dice, para 0.5 %, 1.0 % y 2.0 % de riesgo sobre tu patrimonio: riesgo en
$, tamaño de posición equivalente (USD y unidades), break-even neto, el TP
que satisfaría R:R 2.0x y 3.0x, y si TU configuración pasa tu filtro
R:R ≥ 2.0. Opciones útiles: `--risk-pct 1.0` (una sola fila),
`--equity 2000` (fuerza otra base), `--kind future_long|future_short`
(comisiones perp). Si la configuración incumple tu mínimo, el comando sale
con código 2 tras mostrar la `ALERTA DE DISCIPLINA`.

### Paso 5 — Registrar y cerrar TUS operaciones

```bash
.venv/bin/qa trade open --asset BTCUSDT --kind spot --timeframe 1d \
    --entry 80848 --size-usd 431 --sl 78500 --tp 87000 \
    --tag "Tendencia 1D" --note "entrada tras cierre sobre SMA50"
```

- **El filtro de disciplina actúa aquí**: si el R:R Neto de esos niveles es
  < 2.0, el registro se BLOQUEA. Si aun así quieres anotarla (para medir tu
  indisciplina con datos, que es legítimo), repite con `--force-low-rr`:
  quedará marcada `rr_forzado=true` en el libro y el audit lo reflejará.
- `--ts "2026-10-28T10:00:00+00:00"` permite registrar con fecha declarada
  (útil si anotas la operación horas después de ejecutarla en tu exchange).
- Cortos: `--kind future_short` (recuerda: ahí TP < entrada < SL).

```bash
.venv/bin/qa trade close --id 97f22a6d --exit 87756 --note "cierre en TP"
.venv/bin/qa trade list      # todas (abiertas y cerradas, JSON)
.venv/bin/qa trade status    # diagnóstico en vivo de las abiertas
.venv/bin/qa trade audit     # auditoría completa del historial cerrado
```

### Paso 6 — El dashboard

```bash
.venv/bin/qa agent run
# abre reports/dashboard/index.html en tu navegador
```

Un solo comando: descarga datos públicos en vivo, refresca estados de las
reglas congeladas, tu contabilidad (barra de patrimonio + heat), el filtro
R:R de la watchlist y de H1, tus operaciones abiertas (break-even, cota
2×ATR, R:R residual), el Trade Audit, el historial de capital, choques
técnicos y noticias. El archivo es autocontenido (sin internet funciona la
vista, no la actualización).

**Rutina diaria sugerida (5 minutos):** `qa agent run` → mirar barra de
patrimonio + heat + panel de tus operaciones → si tomaste alguna decisión en
tu exchange, anotarla con `qa trade open/close`. Nada más.

---

## 2. Cambiar el umbral R:R, la watchlist y las fuentes de noticias

Todo vive en **`config/watchlist.yaml`**. Ábrelo con cualquier editor de
texto:

```yaml
watchlist: [BTCUSDT, ETHUSDT, SOLUSDT, BNBUSDT, XRPUSDT]   # ← tus monedas
capital_ref_usd: 1000        # solo se usa si NO hay libro de capital
filtro_rr:
  min_rr_ratio: 2.0          # ← TU umbral de disciplina (cámbialo aquí)
  reward_atr_mult: 3.0       # recompensa = 3 × ATR14 − extensión
  risk_atr_mult_min: 1.0     # riesgo mínimo = 1 × ATR14
  risk_pcts: [0.5, 1.0, 2.0] # filas de la calculadora
```

- **Cambiar el mínimo R:R**: edita `min_rr_ratio` (p. ej. `2.5` o `1.5`).
  Afecta a la calculadora, al bloqueo de `qa trade open`, a las etiquetas
  del dashboard y al bloqueo de la escala teórica de H1. Es TU regla: el
  sistema no la juzga.
- **Agregar/quitar monedas**: edita la lista `watchlist` con símbolos de
  Binance spot (formato `BASEUSDT`, p. ej. `LINKUSDT`, `DOGEUSDT`). Límite
  práctico: ~10 símbolos (cada uno descarga velas 1h/4h/1d/1w). Recuerda que
  la watchlist solo recibe telemetría descriptiva: ninguna altcoin tiene
  hipótesis validada (ADR-008).
- **Fuentes RSS de noticias**: sección `noticias.feeds` — añade/quita
  `{ nombre: X, url: "https://…" }`. Si un feed suele fallar, añade
  `tolerar_fallo: true`. Las palabras que disparan alerta de riesgo están en
  `keywords_riesgo` (puedes añadir las tuyas, p. ej. `regulation`).
- **Umbrales de choques técnicos**: sección `choques` (ATR de 4h/1h, volumen,
  funding extremo). Son convenciones descriptivas documentadas, no señales.

Los costes (comisiones) NO se editan a mano: viven en `config/costs.yaml`
con su evidencia de verificación. Si Binance cambia las comisiones, se
re-verifican con `make verify-endpoints` y se actualiza el archivo con fecha.

Después de editar: `qa agent run` y comprueba que el dashboard refleja tus
cambios.

---

## 3. Dónde tocar indicadores y columnas del dashboard

| Quiero… | Archivo | Qué buscar |
|---|---|---|
| Añadir otra media (SMA200, EMA21…) a la telemetría | `src/qa/agent/telemetry.py` | `_frame_stats()`: imita el bloque `s50 = sma(close, 50)` con tu ventana y añade la clave al dict `row` |
| Cambiar el multiplicador de ATR de las cotas (2×ATR) | `src/qa/agent/telemetry.py` | `trade_geometry()`: la línea `cota = price_now - 2.0 * …` |
| Cambiar la geometría del filtro R:R (3×ATR, 1×ATR mínimo) | `config/watchlist.yaml` primero; fórmulas en `src/qa/agent/geometry.py` | `rr_tendencia()` |
| Añadir/quitar columnas del dashboard | `src/qa/report/dashboard.py` | la función del panel correspondiente (`render_dashboard` para operaciones, `_audit_panel`, `_capital_panel`, `_equity_cards`) |
| Cambiar colores/estilos | `src/qa/report/dashboard.py` | la constante `CSS` al principio |
| Añadir términos al glosario | `src/qa/report/dashboard.py` (panel 9) y `docs/GLOSARIO.md` | bloque `<details>` del glosario |
| Cambiar las filas de riesgo de la calculadora | `config/watchlist.yaml` → `filtro_rr.risk_pcts` | (sin tocar código) |
| Los estados de las reglas congeladas (H1/H2/H3) | `src/qa/agent/signals.py` | **NO los toques**: reproducen celdas congeladas en `m3a-freeze`; cambiarlos invalida la trazabilidad científica |

Regla de oro: los indicadores nuevos en la telemetría son admisibles como
**descripción** (son hechos matemáticos del precio), pero NO convierten a
ningún activo en "señal validada": eso solo existe para las 5 celdas
congeladas. Si algún día quieres una hipótesis nueva de verdad (p. ej.
"SMA200 mejora H1"), el camino es el preregistro v1.5 completo, no editar el
dashboard (ADR-008).

---

## 4. Cuidado con el guard de lenguaje

El dashboard tiene un censor automático: al final de `render_dashboard()`
(`src/qa/report/dashboard.py`) existe la tupla `PROHIBIDOS` con imperativos
de trading ("COMPRAR", "VENDER", "CIERRA", "SUBIR STOP", "SUGERIDO"…). Si el
HTML generado contiene uno, **el programa falla a propósito** y no se genera
el dashboard. Además el test `test_dashboard_language_guard`
(`tests/unit/test_agent.py`) verifica lo mismo en cada `pytest`.

Esto no es decorativo: es la garantía (tuya y del orquestador) de que la
herramienta nunca degenera en un asesor de trading con barniz científico.
Durante M5b el guard llegó a bloquear un texto propio del agente ("Cierra
con…"), o sea: funciona.

**Si en TU copia local, para TU uso privado**, quieres escribir una palabra
prohibida (p. ej. una nota personal que contenga "comprar"):

1. Quita la palabra de la tupla `PROHIBIDOS` en `src/qa/report/dashboard.py`,
   **o** no uses esa palabra en textos renderizados (más simple: tus notas de
   trade viajan por el libro JSONL y el audit las muestra sin filtro).
2. Ajusta el test `test_dashboard_language_guard` en
   `tests/unit/test_agent.py` (importa `PROHIBIDOS`, así que suele bastar el
   paso 1).

Ten en cuenta que entonces tu copia diverge del repo sellado: cualquier
comparación de hashes de evidencia dejará de cuadrar. Nuestra recomendación:
no lo toques; no hace falta para nada de lo que la herramienta ofrece.

---

## 5. Flujo seguro de cambios (3 comandos)

Después de CUALQUIER edición de código o configuración:

```bash
.venv/bin/pytest                     # 110 tests: nada se rompió
.venv/bin/qa agent run               # el dashboard se genera sin que el guard salte
git add -A && git commit -m "cambio: descripción clara"   # punto de restauración
```

Si `pytest` falla: `git checkout -- <archivo>` deshace tu último cambio. Si
todo pasa, tu cambio queda versionado y puedes seguir. Para los libros
contables no hace falta git especial: ya tienen cadena de hashes propia
(`qa capital status` la reverifica en cada corrida).

---

## 6. Problemas comunes

| Síntoma | Causa probable | Solución |
|---|---|---|
| `CADENA ROTA` en status/agent run | Alguien editó un JSONL a mano | Restaurar desde `ledger/backup/` o desde git (`git checkout -- ledger/user_trades.jsonl`) |
| `sin precio vivo para X` | Sin internet o símbolo mal escrito en watchlist | Revisa conexión; el símbolo debe existir en Binance spot (`BASEUSDT`) |
| La calculadora no muestra nada al pulsar Calcular | Estás viendo una copia antigua o el navegador bloquea scripts locales | Abre el HTML generado tras `qa agent run`; permite scripts locales si el navegador pregunta |
| `qa trade open` sale con código 2 | Tu filtro R:R bloqueó el registro (es la función trabajando) | Mejora la geometría o usa `--force-low-rr` consciente de que queda marcado |
| El dashboard muestra "Sin libro de capital" | Todavía no hiciste `qa capital set` | Sección 1, paso 2 |
| RSS "no disponible (feed bloqueado)" | El feed te bloquea o cambió de URL | Edita `noticias.feeds` (sección 2); CoinDesk ya está marcado `tolerar_fallo` |
| Números de la barra de patrimonio raros | PnL flotante es BRUTO (sin comisiones) y usa precios spot aunque el trade sea perp | Es por diseño (documentado en las tarjetas); el realizado sí descuenta comisiones |

---

## 7. Lo que esta guía NO te enseña a hacer (y por qué)

- Poner órdenes reales: el proyecto tiene prohibido tocar dinero real
  (prohibición global de la carta). Todo aquí es registro y aritmética.
- "Señales" para altcoins o marcos 4H/semanal: no existen hipótesis
  validadas fuera de las 5 celdas congeladas; la watchlist es vigilancia
  descriptiva.
- Interpretar el forward P&L antes de 30 días: el motor forward-v1 tiene su
  propia regla de revisión (primera ~2026-11-27).

Si en algún momento sientes que la herramienta te está "diciendo" qué hacer:
relee el banner rojo del dashboard. Está diseñada para mostrar hechos, no
para darte la razón.
