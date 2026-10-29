# QUANT-ARENA v2 — Agente Autónomo Conquistador (M6)

Agente autónomo de **Paper Trading en Criptomonedas** para gestión de cartera simulada sobre **$1,000 USD** con lectura de mercado en tiempo real, filtro de disciplina geométrica $R:R \ge 2.0\text{x}$ y registro contable inmutable auditado con SHA-256.

---

## 🚀 Inicio Rápido (Windows)

En esta carpeta principal tienes dos accesos directos:

1. **`EJECUTAR_QUANT_ARENA.bat`** (Doble clic):
   - Descarga velas y precios vivos desde la API pública de Binance (sin API keys ni riesgo).
   - Gestiona las posiciones abiertas: ejecuta Stop Loss, sube el SL a Break-Even si toca TP1, y toma ganancias al alcanzar TP2.
   - Escanea el universo de 10 monedas y abre las mejores oportunidades hasta un máximo de 5 posiciones simultáneas.
   - Abre automáticamente el Dashboard (`reports/dashboard/index.html`) en tu navegador web.

2. **`CONSOLA_COMANDOS.bat`** (Doble clic):
   - Abre la consola con el entorno virtual activado para consultar tu patrimonio (`qa capital status`), auditar el historial (`qa trade audit`) o gestionar operaciones.

---

## 📁 Estructura del Proyecto

```text
C:\Users\Acer\Documents\QUANT-ARENA\
├── EJECUTAR_QUANT_ARENA.bat       <-- Doble clic: actualiza el Agente en vivo y abre el Dashboard
├── CONSOLA_COMANDOS.bat           <-- Doble clic: abre terminal lista para comandos manuales
├── README.md                      <-- Este archivo explicativo
├── pyproject.toml                 <-- Configuración del paquete Python
├── config/                        <-- Configuración operativa
│   ├── watchlist.yaml             <-- Monedas seguidas, parámetros de riesgo y fuentes RSS
│   └── costs.yaml                 <-- Comisiones verificadas (spot y futuros USD-M)
├── docs/                          <-- Documentación de usuario
│   ├── GUIA_MODIFICACION_JP.md    <-- Guía de uso diario y lectura de métricas
│   ├── GLOSARIO.md                <-- Conceptos financieros y técnicos
│   └── TRAZABILIDAD_PROYECTO.md   <-- Resumen de hitos y trazabilidad
├── ledger/                        <-- Libros contables inmutables (cadena SHA-256)
│   ├── user_capital.jsonl         <-- Historial de capital aportado y retiros
│   └── user_trades.jsonl          <-- Registro auditado de operaciones abiertas y cerradas
├── reports/
│   └── dashboard/
│       └── index.html             <-- Dashboard visual HTML interactivo
├── src/qa/                        <-- Motor del Agente Autónomo M6
└── tests/                         <-- Pruebas automatizadas de consistencia
```

---

## 🛡️ Reglas y Seguridad

- **Sin dinero real ni API Keys privadas**: Todo funciona con endpoints públicos de Binance y simulación estricta de comisiones reales.
- **Riesgo controlado**: Máximo 1.5% de riesgo por operación ($15 USD) y límite estricto de calor de cartera (Portfolio Heat).
- **Relación Riesgo:Beneficio ($R:R$)**: Construcción matemática con $R:R \ge 2.2\text{x}$ hacia TP2.
