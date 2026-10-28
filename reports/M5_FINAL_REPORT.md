# CIERRE M4/M5 FINAL — Telemetría descriptiva ampliada + forward-v1 operativo

**Fecha:** 2026-10-28 · **Gate:** `GATE APROBADO M4/M5` + ADR-008 RATIFICADO (Q1/Q2/Q3 cerradas)
**Estado:** motor `forward-v1` activo (tag firmado) · dashboard v2 · 93/93 tests · mypy --strict ✓

## 1. Decisiones del orquestador implementadas

| Pregunta | Respuesta | Implementación |
|---|---|---|
| Q1 ADR-008 | RATIFICADO; la telemetría descriptiva (SMA/ATR/cotas/distancias) NO es asesoramiento | 3 paneles nuevos con banners explícitos; guard de lenguaje intacto y ampliado |
| Q2 Sizing | `capital_ref_usd` lo aporta el usuario; solo multiplicación aritmética etiquetada | `config/watchlist.yaml: capital_ref_usd: 1000`; columna "Escala teórica s/ capital ref." |
| Q3 forward-v1 | APROBADO: motor de fills t+1 + tag firmado | `qa/forward/paper.py` v1; tag `forward-v1`; workflow pinneado al tag |

## 2. Telemetría descriptiva nueva (dashboard + `qa agent run`)

1. **Niveles observables H1** (por activo): precio · nivel SMA50 y distancia % (donde la
   regla congelada pasaría mecánicamente a FLAT/LONG) · ATR14 en USD y % · rango estadístico
   `[close−2×ATR, close+3×ATR]` · exposición de la regla · **escala teórica** = exposición ×
   capital de referencia (etiquetada "informativo; no es cantidad sugerida").
2. **Panel watchlist 4H·1D·1W** (banner: *"Telemetría descriptiva de precios — No constituye
   hipótesis evaluada ni señal de trading"*): precio, 24 h %, lado de la SMA50 y distancia en
   cada marco, ATR14 % por marco, choque técnico activo. Ingesta ampliada a velas semanales
   (110) y 4H (180).
3. **Tracker enriquecido**: tiempo transcurrido desde la apertura · ratio RR TP/SL
   **inicial → actual** (geometría de los niveles DEL usuario) · nivel SMA50 del marco elegido
   por el usuario y de qué lado está el precio.
4. **Glosario integrado** (panel 6): SMA50, ATR14, exposición/banda, funding/carry,
   ΔmaxDD vol-matched y p de permutación, DSR/PBO/RC, INCONTRASTABLE, cadena de hashes —
   en lenguaje llano para JP.

El guard de lenguaje sigue activo y el test ampliado verifica los banners obligatorios y que
ninguna palabra imperativa aparezca en el HTML.

## 3. Motor forward-v1 (ADR-007) — contabilidad y garantías

- **t+1 real**: `fetch_live` descarta la vela en formación; la señal se computa con datos
  ≤ D−1 y el fill se ejecuta al cierre de D−1 (misma convención que el backtest de
  investigación). Cero look-ahead estructural.
- **Single source of truth**: las exposiciones salen de `compute_states` (reglas congeladas
  M3a); el motor NO reimplementa ninguna regla. H1 con banda ±10 pp congelada (los flips
  siempre operan; dentro de banda no se toca nada → sin sangrado de comisiones por deriva).
- **4 sleeves paper autofinanciados** (25 % c/u de 10 000 USDT iniciales): H1-BTC, H1-ETH,
  H3 delta-neutra (spot largo + perp corto por activo, señal MA30d>5 % congelada), H2 cesta
  (rebalanceo solo cuando cambia la semana ISO, pesos iguales de la cesta teórica).
- **Costes nivel estrés**: spot 0.10 % + 2 pb; perp 0.05 % + 2 pb por punta. **Funding REAL**
  por evento: `cash += −qty×precio×tasa` (el corto cobra tasa positiva); perp liquidado a
  diario contra caja (mark-to-market).
- **Auditoría**: cada paso añade `forward_v1_step` a `ledger/forward.jsonl` encadenado
  (sha256 de la línea anterior + git SHA), con fills detallados, funding, marcas por sleeve y
  patrimonio total. El estado mutable (`forward_state.json`) está gitignoreado: la evidencia
  es la cadena.
- **GitHub Actions**: el workflow queda pinneado al tag firmado `forward-v1` (el motor no
  cambia sin nuevo preregistro/tag) y commitea la línea diaria del ledger a `main`
  (evidencia acumulada en el repo).

**Primer paso en vivo (2026-10-28):** 6 fills (H1 BTC 60 % → 15.0 BTC-paper… en escala
sleeve; H1 ETH 65 %; cesta H2 ZEC/NEAR/UNI/SOL) · H3 inactiva (MA30 4.4 %/4.1 % < 5 %) ·
TOTAL 9 993.27 USDT paper (−0.067 % = costes de entrada, coherente) · cadena OK (2 registros).

## 4. Cifras de cierre del hito

| Métrica | Valor |
|---|---|
| Tests | **93/93** (7 nuevos del motor forward: banda, flips, funding, MTM perp, semanalidad H2, cadena, trazabilidad) |
| mypy --strict / ruff | ✓ (81 ficheros) / ✓ |
| Apertura del holdout | 0 nuevas (sigue = 1 única, M3b) |
| Juicios nuevos sobre estrategias | 0 (solo celdas congeladas + descriptivos) |
| Tag | `forward-v1` firmado (SSH) + hashes anclados en OTS |

## 5. Limitaciones honestas del motor paper

1. La cadena de hashes no detecta manipulación de la ÚLTIMA línea (no tiene sucesor); se
   mitiga con git SHA por registro + commits diarios en GitHub + anclajes OTS periódicos.
2. Contabilidad simplificada: sin margen/liquidación del perp (delta-neutro a tamaño spot),
   fills únicos al cierre diario (no intradía), slippage fijo 2 pb.
3. H2 opera la cesta teórica descriptiva (igual ponderación); la regla L26_N10 congelada es
   semanal y su veredicto sigue siendo INCONTRASTABLE: el sleeve acumula evidencia forward,
   no confirma ventaja.
4. El P&L forward es **out-of-sample cronológico real**, pero su lectura exige las revisiones
   30/60/90 predefinidas: antes de 30 días no se interpreta nada (ruido).

## 6. Qué aprendimos (lenguaje llano)

- El sistema ya hace lo que JP pidió, dentro de lo que la ciencia del proyecto permite:
  **números observables** (dónde está la media, cuánto se mueve el activo, cuánto valdría una
  exposición teórica sobre su capital de referencia) sin convertirlos en consejos.
- El forward paper es el "cuaderno de laboratorio en marcha": cada día anota qué habría hecho
  la regla congelada, con costes y funding reales, y encadena la firma del día anterior. Si
  alguien edita historia, el sello se rompe.
- Primer dato real: entrar cuesta (−0.067 % en un día por los 6 fills). Es exactamente el
  tipo de fricción que el estudio midió y que se come las ventajas pequeñas.

## 7. Checklist del orquestador / usuario

- [ ] Push del bundle M5 a GitHub (main + tags): activa el forward diario automático con
      commit de evidencia (permiso `contents: write` del workflow).
- [ ] Revisión forward a 30/60/90 días (primera: ~2026-11-27).
- [ ] Registro OSF del preregistro v1.4 (pendiente desde M2b).
- [ ] Telegram: sigue opcional (`TELEGRAM_BOT_TOKEN` en `.env`); el canal principal es el
      dashboard.
- [ ] `make ots-check`: verificar anclas BTC pendientes (m3a, m3b, forward-v1).

## 8. Propuesta de siguiente paso

M4/M5 queda CERRADO. Propongo **M6 = operación y revisión**: (a) dejar correr el forward
30 días y producir el primer informe de revisión forward contra el benchmark B&H (descriptivo,
sin tests nuevos); (b) cerrar el registro OSF; (c) decidir con datos forward si algún día se
justifica un preregistro v1.5 (hipótesis 4H/semanal/SL-TP). Alternativa: cierre definitivo
del proyecto con el veredicto negativo documentado. Espero instrucciones.
