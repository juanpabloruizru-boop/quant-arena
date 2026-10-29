# GUÍA DE OPERACIÓN DIARIA PARA JP — MODO AUTOPILOT M6

Bienvenido a **QUANT-ARENA v2** en su versión final autónoma (**M6 Autopilot Conquistador**).

Esta herramienta funciona en modo **Paper Trading** con un capital simulado de **$1,000 USD** gestionado de forma matemática y autónoma en tu máquina local.

---

## 1. Uso Diario con Doble Clic (Windows)

En la carpeta principal `C:\Users\Acer\Documents\QUANT-ARENA` tienes dos archivos `.bat` listos para usar:

| Archivo | Qué hace |
| :--- | :--- |
| **`EJECUTAR_QUANT_ARENA.bat`** | **El botón principal**. Hace una pasada del Agente en vivo: consulta precios y velas en tiempo real desde Binance, audita las posiciones abiertas (SL/TP1/TP2), abre nuevas oportunidades si hay cupo (< 5 operaciones), actualiza el ledger criptográfico y abre automáticamente el Dashboard (`reports\dashboard\index.html`) en tu navegador web. |
| **`CONSOLA_COMANDOS.bat`** | Abre un terminal interactivo de Windows con el entorno virtual activado para consultar estados patrimoniales o auditar operaciones manualmente. |

---

## 2. Comandos Rápidos en Consola (`CONSOLA_COMANDOS.bat`)

Si abres la consola con doble clic, puedes ejecutar directamente cualquiera de estos comandos:

- **Actualizar agente y dashboard:**
  ```text
  qa agent run
  ```
- **Ver patrimonio vivo, PnL y riesgo en mesa (Portfolio Heat):**
  ```text
  qa capital status
  ```
- **Listar todas las operaciones abiertas y cerradas:**
  ```text
  qa trade list
  ```
- **Auditoría completa del historial cerrado (Win Rate, Profit Factor, etc.):**
  ```text
  qa trade audit
  ```
- **Añadir un aporte o retiro al capital simulado:**
  ```text
  qa capital add --amount 500       (añade $500 USD)
  qa capital add --amount -200      (retira $200 USD)
  ```

---

## 3. Cómo Interpreta el Dashboard JP

El Dashboard se divide en 4 bloques limpios:

1. **Tarjetas de Patrimonio Vivo (Top):**
   - **Capital Aportado Neto**: Tu base inicial ($1,000 USD).
   - **PnL Cerrado (Neto)**: Ganancia/pérdida realizada tras comisiones reales.
   - **PnL Abierto (Vivo)**: Ganancia/pérdida flotante al precio de Binance de este segundo.
   - **Patrimonio Total (Equity Vivo)**: Tu saldo real en cuenta.
   - **Riesgo en Mesa (Portfolio Heat)**: Suma de dólares expuestos si todas las operaciones tocaran simultáneamente su Stop Loss (tope de seguridad ≤ 10%).

2. **Tabla 1A: Posiciones Abiertas del Agente (Para copiar o monitorear):**
   - Muestra cada posición activa con su activo, apalancamiento (`4x`), precio de entrada, precio actual vivo, niveles vigentes de **Stop Loss**, **TP1** (asegurar ganancia / Break-Even) y **TP2** (meta final con $R:R \ge 2.2\text{x}$).
   - **Semáforo de Entrada**:
     - `🟢 EN ZONA DE ENTRADA`: El precio está a menos del 25% hacia el TP1 y mantiene un $R:R \ge 2.0\text{x}$.
     - `🟢 MEJOR PRECIO QUE EL AGENTE`: El precio retrocedió levemente hacia el SL pero mantiene su tesis intacta, ofreciendo un ratio riesgo/beneficio superior al del agente.
     - `🟡 YA EN MARCHA`: Avanzó entre 25% y 60% hacia TP1.
     - `🔴 TARDE PARA ENTRAR`: Avanzó más del 60% o ya tocó TP1.

3. **Tabla 1B: Escáner de Mercado y Decisión del Agente:**
   - Monitorea los 10 activos principales con su precio en vivo, alineación técnica (EMAs, SMA50, RSI, MACD, RVOL) y el Score de 0 a 100 que determina qué activos se abren automáticamente.

4. **Termómetro Macro y Noticias en Tiempo Real:**
   - Resumen cualitativo de fuentes RSS de primer nivel (Cointelegraph, Decrypt, CNBC Economy, CoinDesk).

---

## 4. Libros Inmutables (Ledger)

Toda la operativa queda registrada en la carpeta `ledger/`:
- `ledger/user_capital.jsonl`: Movimientos de capital con encadenamiento SHA-256.
- `ledger/user_trades.jsonl`: Registro inmutable de cada orden abierta, modificada o cerrada.

Ningún dato se pierde ni se sobrescribe.
