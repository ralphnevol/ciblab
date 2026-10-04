# 🪟 Guía Rápida de Ejecución en Windows (CLI y Web UI)

Esta guía explica cómo ejecutar y probar los agentes del laboratorio en **Windows (PowerShell)** de forma directa, **sin modificar las variables de entorno del sistema (sin tocar el PATH)** y garantizando compatibilidad total con **GPT-6 Luna** y **Omnigent**.

---

## ⚡ Paso Previo Obligatorio (PowerShell)

En consolas de Windows tradicionales, la codificación por defecto es `cp1252`, lo cual genera fallos al imprimir caracteres Unicode del protocolo de agentes (`✓`, `➜`). 

Antes de ejecutar cualquier comando, configurá UTF-8 en la sesión de PowerShell activa:

```powershell
$env:PYTHONUTF8 = 1
```

*(Opcional: podés agregar `$env:PYTHONUTF8 = 1` a tu perfil de PowerShell `$PROFILE` si querés que quede permanente).*

---

## 💻 MODO 1: Probar Agentes en la Terminal (CLI)

Podés interactuar directamente con los agentes desde la consola con lenguaje natural.

### Opción A: Sesión NATIVA con Omnigent CLI (Usa el Runtime de Omnigent)
Esta opción **SÍ corre a través del runtime oficial de Omnigent**, levantando el servidor en `:6767`, cargando el arnés `openai-agents` y conectando el agente a **GPT-6 Luna**:

```powershell
# Probar el Seed Agent (genera hipótesis y corpus de semillas de fuzzing):
python run.py --omni seed-agent

# O probar el Fuzz Orchestrator (Investigador Principal que coordina todo el ciclo):
python run.py --omni fuzz-orchestrator
```
* Presioná `Ctrl + C` para salir de la sesión interactiva.

---

### Opción B: Demostración en Python Directo (Local Fallback — Sin demonio de Omnigent)
> ⚠️ **Atención:** Esta opción **NO pasa por el servidor ni los sockets de Omnigent**. Es una ejecución en Python puro (lo que en la arquitectura llamamos *Local Fallback Execution*). Llama a **GPT-6 Luna** en vivo vía OpenAI API y replica el flujo científico en tu consola, ideal para depurar código o probar si no querés levantar el servidor de Omnigent.

```powershell
python run.py --interactive
```
* **Qué hace:**
  1. Envía la especificación del parser al Seed Agent (`gpt-6-luna`).
  2. Formula la hipótesis y genera 5 semillas de mutación.
  3. Ejecuta el experimento en sandbox detectando más de 30 crashes.
  4. **Pausa de Seguridad:** Te solicita aprobación por teclado (`[S/n]`) emulando la política de Omnigent.
  5. Reproduce fallos, clasifica vulnerabilidades por CWE (CWE-120, CWE-134, CWE-626) y actualiza la decisión científica con métricas de aceleración.

---

### Opción C: Test Rápido Automatizado (Local Fallback)
```powershell
python run.py --demo
```

---

## 🌐 MODO 2: Probar los Agentes en la Interfaz Web Oficial (UI)

Omnigent incluye un servidor web en React (`http://127.0.0.1:6767`) para chatear con los agentes, ver streaming de razonamiento y auditar la ejecución visual de herramientas (*Tool Calls*).

### Paso 1: Levantar el Servicio Completo con Credenciales (Recomendado)
Para que la UI reconozca a tu máquina como **Host Online** y el arnés `openai-agents` esté autenticado con tu `OPENAI_API_KEY` de `.env`:

```powershell
python run.py --omni-start
```
* **Qué hace automáticamente este comando:**
  1. Carga `OPENAI_API_KEY` desde tu archivo `.env`.
  2. Sincroniza y registra los 5 agentes del laboratorio (`omnigent/agents/`) en la base de datos de Omnigent.
  3. Levanta tanto el **Servidor Web** (`:6767`) como el **Host Daemon** (runner de ejecución) en segundo plano.
  4. Garantiza que en la UI no aparezca la advertencia `isn't configured on Brian`.

---

### Paso 2: Abrir el navegador e interactuar
Abrí tu navegador web e ingresá a:
👉 **`http://127.0.0.1:6767`**

1. En la pantalla inicial verás tu máquina conectada (**Host: Brian, Online**).
2. En el menú desplegable de selección de modelo/agente, elegí por ejemplo **`Fuzz_orchestrator`** o **`Seed_agent`**.
3. En la caja de chat inferior escribile:
   ```text
   Analiza el parser vulnerable y genera el corpus de 5 semillas de prueba
   ```
4. **Qué vas a ver en pantalla:**
   - **Streaming de Razonamiento:** Verás cómo **GPT-6 Luna** analiza la especificación y los límites de memoria.
   - **Bloque Visual de Herramientas (`Tool Call`):** Un bloque desplegable muestra la ejecución en tiempo real de la herramienta en Python.
   - **Respuesta:** La conclusión científica y los datos estructurados devueltos en el chat.

---

### Paso 3: Detener el servidor de Omnigent al terminar
Cuando termines de probar, liberá el puerto `6767` y detén los procesos de Omnigent:

```powershell
python -m omnigent stop
```

---

## 🛠️ Documentación Técnica: Parche de Codificación en Windows (`connect.py`)

### El Problema Identificado:
En consolas tradicionales de Windows (`cp1252`), cuando el daemon de conexión del host intentaba conectarse al servidor WebSocket en `ws://127.0.0.1:6767/v1/hosts/.../tunnel`, ejecutaba la siguiente línea en `omnigent/host/connect.py` (línea 4392):
```python
print(
    f"✓ Connected as {self._identity.name!r} "
    f"({self._identity.host_id}), {len(hello.runners)} live runner(s). "
    "Listening for sessions — Ctrl-C to disconnect.",
    flush=True,
)
```
Dado que el carácter `✓` (`\u2713`) no existe en el juego de caracteres `cp1252`, Python lanzaba una excepción fatal:
`UnicodeEncodeError: 'charmap' codec can't encode character '\u2713' in position 0: character maps to <undefined>`.
Esto provocaba que el túnel del host se desconectara y reconectara cada 3 segundos en un bucle infinito, dejando al Host en estado **`offline`** y arrojando en la UI los errores `The session's runner isn't connected to the server` y `No host selected`.

### La Solución Aplicada:
Se aplicó un parche seguro en `omnigent/host/connect.py`:
```python
try:
    print(
        f"✓ Connected as {self._identity.name!r} "
        f"({self._identity.host_id}), {len(hello.runners)} live runner(s). "
        "Listening for sessions — Ctrl-C to disconnect.",
        flush=True,
    )
except Exception:
    print(
        f"[+] Connected as {self._identity.name!r} "
        f"({self._identity.host_id}), {len(hello.runners)} live runner(s). "
        "Listening for sessions — Ctrl-C to disconnect.",
        flush=True,
    )
```
Con este manejo de excepción, el túnel permanece conectado de forma estable en `online`, permitiendo la comunicación fluida entre el navegador y el ejecutor de Python.

---

## 🔬 Interfaz Web Adicional: Dashboard del Laboratorio (`:8000`)

Además de la UI de Omnigent, tenés el dashboard integral del experimento con tarjetas visuales para las 5 fases y el botón de autorización humana:

```powershell
python run.py
```
Abrí tu navegador en:
👉 **`http://127.0.0.1:8000`**

*(Swagger OpenAPI disponible en `http://127.0.0.1:8000/docs`).*

---

## 📌 Tabla Resumen de Comandos en Windows

| Tarea | Comando en PowerShell |
|---|---|
| Iniciar Servicio Omnigent (UI + Host + .env) | `python run.py --omni-start` |
| Sincronizar agentes con Omnigent | `python run.py --register` |
| Probar agente en CLI | `python run.py --omni seed-agent` |
| Probar bucle interactivo | `python run.py --interactive` |
| Estado Servidor Omnigent | `python -m omnigent server status` |
| Apagar Omnigent completo | `python -m omnigent stop` |
| Levantar Dashboard Lab | `python run.py` |
