# 🚀 Guía de Despliegue 100% Gratis en la Nube (QUANT-ARENA v2)

Ejecuta QUANT-ARENA de forma autónoma **24 horas al día, 7 días a la semana, con el PC completamente apagado**. 
El sistema correrá mediante **GitHub Actions** (cada 25 minutos), te enviará alertas instantáneas a **Telegram**, consultará a **Google Gemini 2.5 Flash** y publicará tu Dashboard interactivo en **GitHub Pages** para que puedas revisarlo desde el navegador de tu teléfono móvil en cualquier lugar.

---

## 📋 Resumen de la Arquitectura en la Nube
- **Motor Cuantitativo y Decisorio**: GitHub Actions (servidor gratuito de Ubuntu).
- **Cadencia**: Cada 25 minutos (`cron: "*/25 * * * *"`), sincronizado con velas cerradas.
- **Failover Anti-Bloqueo EE.UU.**: Conmutación automática a `data-api.binance.vision` y fallback neutral de funding para evadir el error HTTP 451 en servidores cloud de EE.UU.
- **Persistencia**: El bot hace auto-commit de los ledgers (`ledger/*.jsonl`, `ledger/*.csv`) tras cada ciclo para conservar memoria operativa y contabilidad.
- **Dashboard Web**: Desplegado en GitHub Pages con URL pública segura (HTTPS).

---

## 🛠️ Paso 1: Crear el Repositorio en GitHub y Subir el Código

1. Entra a [github.com/new](https://github.com/new) e inicia sesión.
2. Nombra tu repositorio (por ejemplo, `QUANT-ARENA` o `quant-arena-v2`).
3. Elige si prefieres que sea **Privado** (GitHub ofrece 2.000 minutos gratis/mes, más que suficiente) o **Público** (minutos de GitHub Actions 100% ilimitados).
4. **NO** marques las casillas de añadir README, .gitignore ni licencia (ya existen en tu proyecto).
5. Haz clic en el botón verde **Create repository**.
6. En tu ordenador, abre la consola en la carpeta de QUANT-ARENA (o usa `CONSOLA_COMANDOS.bat`) y ejecuta:

```bash
git remote add origin https://github.com/TU_USUARIO/QUANT-ARENA.git
git branch -M main
git push -u origin main
```
*(Reemplaza `TU_USUARIO` y `QUANT-ARENA` por tu nombre de usuario y nombre del repo en GitHub).*

---

## 🔑 Paso 2: Configurar tus Secretos en GitHub (Settings → Secrets)

Para que el bot de la nube pueda enviar mensajes a tu Telegram y consultar al modelo IA de Gemini, debes guardar tus claves en GitHub (están cifradas y son 100% privadas):

1. En tu repositorio de GitHub, haz clic en la pestaña **Settings** (arriba a la derecha).
2. En el menú lateral izquierdo, haz clic en **Secrets and variables** → **Actions**.
3. Haz clic en el botón verde **New repository secret**.
4. Añade uno a uno los siguientes secretos:

| Nombre del Secreto (Name) | Valor (Secret) | Descripción |
| :--- | :--- | :--- |
| `QA_TELEGRAM_BOT_TOKEN` | Tu Token de Telegram | Ej: `1234567890:ABCdefGHIjklMNOpqrsTUVwxyz` |
| `QA_TELEGRAM_CHAT_ID` | Tu Chat ID numérico | El ID numérico obtenido al iniciar tu bot en Telegram |
| `QA_GEMINI_API_KEY` | Tu API Key de Gemini | La clave obtenida en Google AI Studio (ej. `AIzaSy...`) |
| `QA_GEMINI_MODEL` *(opcional)* | `gemini-2.5-flash` | Modelo de IA cognitivo |

> [!NOTE]
> Puedes consultar tus valores actuales abriendo el archivo local `.env` en la raíz de tu proyecto.

---

## 🌐 Paso 3: Activar GitHub Pages para el Dashboard en tu Teléfono

1. En la pestaña **Settings** de tu repositorio de GitHub, busca **Pages** en el menú de la izquierda (sección *Code and automation*).
2. En la sección **Build and deployment**:
   - En el menú desplegable **Source**, selecciona: **`GitHub Actions`**.
3. ¡Listo! Ya no tienes que configurar nada más aquí. En cuanto finalice la primera ejecución, GitHub Pages te mostrará arriba el enlace a tu Dashboard:
   `https://<TU_USUARIO>.github.io/QUANT-ARENA/`

> [!TIP]
> **En tu móvil**: Abre esa URL en Safari (iOS) o Chrome (Android) y pulsa en *"Compartir" → "Añadir a la pantalla de inicio"*. Tendrás un icono de QUANT-ARENA como si fuera una app nativa.

---

## 🚀 Paso 4: Primera Ejecución y Operación 24/7 con PC Apagado

1. En tu repositorio de GitHub, haz clic en la pestaña **Actions** (arriba).
2. En la lista de la izquierda, haz clic en **QUANT-ARENA Cloud Autopilot**.
3. Haz clic en el botón desplegable **Run workflow** (a la derecha) y presiona el botón verde **Run workflow**.
4. Verás cómo arranca el proceso:
   - Descarga las velas de la Cesta Élite con failover a `data-api.binance.vision`.
   - Evalúa los motores CRUISE PRO (4H), Sniper Intradía (1H) y Cartera Spot.
   - Consulta el Cerebro Cognitivo Gemini 2.5 Flash.
   - Notifica a tu Telegram con las decisiones del ciclo.
   - Guarda los registros en el repositorio (`git push`).
   - Despliega el Dashboard interactivo en GitHub Pages.
5. **Apaga tu ordenador con total tranquilidad**: GitHub Actions continuará ejecutándose automáticamente cada 25 minutos, vigilando los mercados por ti.

---

## 🛡️ Solución a Preguntas Frecuentes

- **¿Qué pasa con el bloqueo de Binance en servidores de EE.UU. (HTTP 451)?**
  QUANT-ARENA v2 cuenta con conmutación automática (*failover*): si `api.binance.com` o `fapi.binance.com` rechazan la conexión de un runner en EE.UU., el sistema conmuta transparentemente a `data-api.binance.vision` (el endpoint oficial de datos públicos de Binance no restringido) y aplica tasas neutrales para el funding sin interrumpir la ejecución.
- **¿Se pierden las operaciones si el servidor de GitHub se apaga?**
  No. Al terminar cada ciclo de 25 minutos, el workflow hace un `git commit` automático de los archivos `ledger/` y `reports/`, por lo que el siguiente runner retoma el estado con continuidad contable matemática estricta.
