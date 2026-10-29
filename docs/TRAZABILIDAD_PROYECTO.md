# Trazabilidad del Proyecto QUANT-ARENA v2

Este documento detalla la estructura actual del proyecto, el flujo del agente autónomo M6 y el archivo histórico ordenado de los hitos anteriores (M0 a M5).

---

## 1. Estructura de Carpetas Actual

```
quant-arena/
├── archive/                     # Archivo histórico (M0 a M5, bundles git y holdout sellado)
│   ├── holdout_sealed/          # Conjunto sellado de datos M3 (desempaquetado y evaluado)
│   ├── quant-arena-M*.bundle    # Bundles Git de hitos previos (M0b, M2, M3a, M3b, M4, M5, M6)
│   └── M*_REPORT.* / M*.*       # Informes técnicos, JSONs y análisis de M0, M1, M2, M3, M4, M5
├── config/                      # Configuración del sistema (watchlist, costs, universo, etc.)
│   ├── watchlist.yaml           # Configuración del universo de 10 monedas, feeds RSS y parámetros
│   ├── costs.yaml               # Estructura verificada de comisiones (spot y futuros USD-M)
│   └── ...
├── data/                        # Almacén de datos de mercado
│   ├── curated/                 # Datos curados e índices PIT (pit_universe.parquet)
│   ├── manifests/               # Manifiestos de integridad SHA-256
│   └── raw/                     # Datos crudos de Binance
├── docs/                        # Documentación metodológica y registros
│   ├── adr/                     # Architectural Decision Records (ADR-001 a ADR-008)
│   ├── PREREGISTRO.md           # Pre-registro formal de hipótesis científicas (v1.4)
│   ├── TRAZABILIDAD_PROYECTO.md # Este documento de trazabilidad y estructura
│   └── ...
├── ledger/                      # Libros contables inmutables (append-only con cadena SHA-256)
│   ├── user_trades.jsonl        # Registro criptográfico de operaciones del agente autónomo
│   ├── user_capital.jsonl       # Registro inmutable de flujos y estado del capital
│   └── trials.duckdb            # Registro determinista de backtests y corridas de investigación
├── reports/
│   └── dashboard/
│       └── index.html           # Dashboard interactivo autocontenido generado por el Agente
├── src/qa/                      # Código fuente principal de la plataforma
│   ├── agent/                   # Lógica del Agente Autónomo (Autopilot, Live ingesta, News RSS, Telemetría)
│   │   ├── autopilot.py         # Motor de decisión autónomo "Conquistador" Multi-Indicador
│   │   ├── live.py              # Ingesta pública Binance (velas 1h/4h/1d/1w, precios, funding)
│   │   ├── news.py              # Monitor de noticias RSS y radar Macro/FED/Finanzas
│   │   ├── capital.py           # Contabilidad patrimonial y control de riesgo de cartera
│   │   ├── tracker.py           # Verificación de cadena y diagnóstico de operaciones
│   │   └── signals.py           # Cálculo de estados e indicadores técnicos
│   ├── report/
│   │   └── dashboard.py         # Generación del Dashboard HTML con tablas 1A, 1B, 2 y 3
│   ├── cli.py                   # Orquestador Typer (`qa agent run`, etc.)
│   └── ...
├── tests/                       # Suite de pruebas unitarias, de integración y propiedades
└── 1_ACTUALIZAR_Y_ABRIR_DASHBOARD.bat # Lanzador de Windows para actualización de un clic
```

---

## 2. Historial de Hitos Archivados en `archive/`

| Hito | Nombre | Descripción | Ubicación Archivo |
| :--- | :--- | :--- | :--- |
| **M0** | Pre-registro & Potencia | Hipótesis H1-H3 formuladas, FWER controlado, análisis de potencia estadística. | `archive/M0*` |
| **M1** | Ingesta & Calidad de Datos | Sincronización inmutable Binance, control de duplicados, universo PIT. | `archive/M1*` |
| **M2** | Pipeline Estadístico & T-Star | Bootstrap por bloques, corrección White / Hansen, validación t*. | `archive/M2*` |
| **M3a** | Research In-Sample | Evaluación de rejilla de celdas sobre período IS, selección m3a-freeze. | `archive/M3a*` |
| **M3b** | Evaluación Holdout Sellado | Desprecintado único de los últimos 12 meses. H3 Carry pasa con advertencias; H1/H2 incontrastables. | `archive/M3b*`, `archive/holdout_sealed/` |
| **M4** | Forward Testing & Ingesta Viva | Ingesta de velas en tiempo real, detección de choques y primeras alertas. | `archive/M4*` |
| **M5** | Dashboard & Contabilidad M5b | Dashboard autocontenido HTML con libros contables con cadena de hash y auditoría. | `archive/M5*` |
| **M6** | Agente Autónomo "Conquistador" | Paper trading totalmente autónomo sobre $1,000 USD, motor multi-indicador (EMA, RSI, MACD, ATR, RVOL), gestión activa de SL/TP y radar Macro FED. | `src/qa/agent/autopilot.py` (activo) |
