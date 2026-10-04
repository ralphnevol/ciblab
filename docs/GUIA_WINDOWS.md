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

### Paso 1: Asegurar el registro de los agentes
Registra los 5 agentes del laboratorio (`omnigent/agents/`) en la base de datos local de Omnigent:

```powershell
python run.py --register
```
*Salida esperada:*
```text
  agent: fuzz_orchestrator (from omnigent\agents\fuzz-orchestrator)
  agent: seed_agent (from omnigent\agents\seed-agent)
  agent: execution_agent (from omnigent\agents\execution-agent)
  agent: safety_agent (from omnigent\agents\safety-agent)
  agent: triage_agent (from omnigent\agents\triage-agent)
[✓] ¡Los 5 agentes están registrados y listos para la UI en http://127.0.0.1:6767!
```

---

### Paso 2: Iniciar el servidor web en segundo plano
```powershell
python -m omnigent server --background
```

Para verificar que está activo:
```powershell
python -m omnigent server status
```
*Salida:* `Background server: running at http://127.0.0.1:6767 (pid ..., port 6767)`.

---

### Paso 3: Abrir el navegador e interactuar
Abrí tu navegador web e ingresá a:
👉 **`http://127.0.0.1:6767`**

1. Hacé clic en **"+ New Chat"** (arriba a la izquierda).
2. En el menú desplegable de selección de modelo/agente, elegí por ejemplo **`seed_agent`**.
3. En la caja de chat inferior escribile:
   ```text
   Analiza la estructura del parser binario y genera una hipótesis con 5 semillas de prueba.
   ```
4. **Qué vas a ver en pantalla:**
   - **Streaming de Razonamiento:** Verás cómo **GPT-6 Luna** analiza la especificación y los límites de memoria.
   - **Bloque Visual de Herramientas (`Tool Call`):** Un bloque desplegable muestra la ejecución en tiempo real de `generate_corpus` ejecutando [`app/agents/seed_agent.py`](../app/agents/seed_agent.py).
   - **Respuesta:** El corpus con las 5 semillas generadas en hexadecimal.

---

### Paso 4: Detener el servidor de Omnigent al terminar
Cuando termines de probar, liberá el puerto `6767`:

```powershell
python -m omnigent server stop
```

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
| Configurar UTF-8 | `$env:PYTHONUTF8 = 1` |
| Registrar agentes | `python run.py --register` |
| Probar agente en CLI | `python run.py --omni seed-agent` |
| Probar bucle interactivo | `python run.py --interactive` |
| Levantar Servidor UI Omnigent | `python -m omnigent server --background` |
| Estado Servidor Omnigent | `python -m omnigent server status` |
| Apagar Servidor Omnigent | `python -m omnigent server stop` |
| Levantar Dashboard Lab | `python run.py` |
