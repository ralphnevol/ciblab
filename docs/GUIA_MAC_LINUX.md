# 🍎🐧 Guía Rápida de Ejecución en macOS y Linux (CLI y Web UI)

Esta guía explica cómo ejecutar y probar los agentes del laboratorio en **macOS y distribuciones Linux (Ubuntu, Debian, Fedora, Arch, etc.)** utilizando Bash o Zsh.

En entornos UNIX, la compatibilidad con **Omnigent** y **GPT-6 Luna** es **100% nativa**: UTF-8 viene configurado por defecto y los procesos de conexión operan sobre sockets POSIX estándar sin bloqueos.

---

## ⚡ Paso 1: Configurar Variables de Entorno

Abrí tu terminal (Terminal en macOS o tu consola habitual en Linux):

```bash
# 1. Entrar al directorio del proyecto
cd ciblab

# 2. Cargar las credenciales desde el archivo .env (incluye OPENAI_API_KEY)
export $(grep -v '^#' .env | xargs)

# 3. Verificar que la variable se cargó correctamente
echo "API Key configurada: ${OPENAI_API_KEY:0:10}..."
```

---

## 💻 MODO 1: Probar Agentes en la Terminal (CLI)

Podés ejecutar los agentes directamente en la consola con lenguaje natural.

### Opción A: Sesión interactiva con un agente especialista
Conecta una sesión REPL directa con el runtime de Omnigent y **GPT-6 Luna**:

```bash
# Probar el Seed Agent (genera hipótesis y corpus de semillas de fuzzing):
python3 run.py --omni seed-agent
# (O comando nativo: omni run omnigent/agents/seed-agent/)

# O probar el Fuzz Orchestrator (Investigador Principal):
python3 run.py --omni fuzz-orchestrator
# (O comando nativo: omni run omnigent/agents/fuzz-orchestrator/)
```
* Presioná `Ctrl + C` para salir de la sesión interactiva.

---

### Opción B: Demostración Científica Paso a Paso (Human-in-the-Loop)
Si querés experimentar el ciclo científico de descubrimiento completo con pausas interactivas y control de seguridad:

```bash
python3 run.py --interactive
```
* **Qué hace:**
  1. Envía la especificación del parser al Seed Agent (`gpt-6-luna`).
  2. Formula la hipótesis científica y genera 5 semillas de prueba.
  3. Ejecuta el fuzzing en sandbox detectando más de 30 crashes.
  4. **Pausa de Seguridad (Omnigent Policy):** Te solicita confirmación explícita por consola (`[S/n]`).
  5. Reproduce fallos, clasifica vulnerabilidades por CWE (CWE-120, CWE-134, CWE-626) y actualiza la decisión con métricas de aceleración.

---

### Opción C: Test Rápido Automatizado (1 comando)
```bash
python3 run.py --demo
```

---

## 🌐 MODO 2: Probar los Agentes en la Interfaz Web Oficial (UI)

Omnigent incluye un servidor web completo con interfaz visual en React (`http://127.0.0.1:6767`) para chatear con los agentes, ver streaming de razonamiento y auditar la ejecución de herramientas (*Tool Calls*).

### Paso 1: Asegurar el registro de los agentes
Registra los 5 agentes del laboratorio (`omnigent/agents/`) en la base de datos persistente de Omnigent:

```bash
python3 run.py --register
```
*Salida esperada:*
```text
  agent: fuzz_orchestrator (from omnigent/agents/fuzz-orchestrator)
  agent: seed_agent (from omnigent/agents/seed-agent)
  agent: execution_agent (from omnigent/agents/execution-agent)
  agent: safety_agent (from omnigent/agents/safety-agent)
  agent: triage_agent (from omnigent/agents/triage-agent)
[✓] ¡Los 5 agentes están registrados y listos para la UI en http://127.0.0.1:6767!
```

---

### Paso 2: Iniciar el servidor web en segundo plano
```bash
omni server --background
# (O si no tenés el alias en el PATH: python3 -m omnigent server --background)
```

Para verificar que está activo:
```bash
omni server status
```
*Salida:* `Background server: running at http://127.0.0.1:6767 (pid ..., port 6767)`.

---

### Paso 3: Abrir el navegador e interactuar
Abrí tu navegador web (Chrome, Firefox, Safari) e ingresá a:
👉 **`http://127.0.0.1:6767`**

1. Hacé clic en **"+ New Chat"** (arriba a la izquierda).
2. En el menú desplegable de selección de modelo/agente, elegí por ejemplo **`seed_agent`**.
3. En la caja de chat inferior escribile:
   ```text
   Analiza la estructura del parser binario y genera una hipótesis con 5 semillas de prueba.
   ```
4. **Qué vas a ver en pantalla:**
   - **Streaming de Razonamiento:** Verás cómo **GPT-6 Luna** analiza la especificación y los supuestos de memoria.
   - **Bloque Visual de Herramientas (`Tool Call`):** Un bloque interactivo muestra la llamada a `generate_corpus` ejecutando [`app/agents/seed_agent.py`](../app/agents/seed_agent.py).
   - **Respuesta:** El corpus con las 5 semillas generadas en hexadecimal.

---

### Paso 4: Detener el servidor de Omnigent al terminar
Cuando termines de probar, liberá el puerto `6767`:

```bash
omni server stop
# (O con python3: python3 -m omnigent server stop)
```

O para detener todos los procesos activos de Omnigent en el sistema:
```bash
omni stop
```

---

## 🔬 Interfaz Web Adicional: Dashboard del Laboratorio (`:8000`)

Además de la UI de Omnigent, podés iniciar el dashboard visual del experimento con tarjetas de las 5 fases y el botón interactivo de aprobación humana:

```bash
python3 run.py
```
Abrí tu navegador en:
👉 **`http://127.0.0.1:8000`**

*(Documentación OpenAPI Swagger interactiva en `http://127.0.0.1:8000/docs`).*

---

## 📌 Tabla Resumen de Comandos en macOS y Linux

| Tarea | Comando Bash / Zsh |
|---|---|
| Cargar credenciales (.env) | `export $(grep -v '^#' .env \| xargs)` |
| Registrar agentes en el Store | `python3 run.py --register` |
| Probar agente en CLI | `python3 run.py --omni seed-agent` *(o `omni run omnigent/agents/seed-agent/`)* |
| Probar bucle interactivo | `python3 run.py --interactive` |
| Levantar Servidor UI Omnigent | `omni server --background` *(o `python3 -m omnigent server --background`)* |
| Estado Servidor Omnigent | `omni server status` |
| Apagar Servidor Omnigent | `omni server stop` |
| Levantar Dashboard Lab | `python3 run.py` |
