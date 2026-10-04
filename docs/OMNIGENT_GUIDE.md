# 📘 Guía Completa de Uso de Omnigent

Esta guía explica en detalle cómo funciona **Omnigent (v0.16.0)**, cómo está integrado en nuestro laboratorio de investigación y cómo resolver los escenarios habituales al usar la CLI en Windows.

---

## 1. ¿Qué es Omnigent?

Omnigent es una plataforma de orquestación de agentes de IA diseñada para ejecutar, supervisar y controlar agentes autónomos mediante:
1. **Configuración declarativa en YAML** (`spec_version: 1`).
2. **Políticas contextuales y guardrails** (límites de llamadas a herramientas, control de costos y aprobación humana obligatoria).
3. **Soporte multi-harness** (Claude, OpenAI, Codex, Antigravity, etc.).
4. **Arquitectura Servidor + REPL** para sesiones persistentes y trazables.

---

## 2. Configurar Omnigent en tu Terminal (Windows)

En Windows, cuando instalás Omnigent con `pip` en una instalación de Python proveniente de la Microsoft Store, los ejecutables `.exe` (`omni.exe` y `omnigent.exe`) se ubican en:
```text
C:\Users\<TuUsuario>\AppData\Local\Packages\PythonSoftwareFoundation.Python.3.12_qbz5n2kfra8p0\LocalCache\local-packages\Python312\Scripts
```

### Cómo habilitar los comandos en PowerShell:
Para que tu terminal reconozca `omni` u `omnigent` de forma permanente, ejecutá:
```powershell
[Environment]::SetEnvironmentVariable("Path", $env:Path + ";$((Get-Item env:APPDATA).Value)\..\Local\Packages\PythonSoftwareFoundation.Python.3.12_qbz5n2kfra8p0\LocalCache\local-packages\Python312\Scripts", "User")
```
O para la sesión de PowerShell actual únicamente:
```powershell
$env:PATH += ";$((Get-Item env:APPDATA).Value)\..\Local\Packages\PythonSoftwareFoundation.Python.3.12_qbz5n2kfra8p0\LocalCache\local-packages\Python312\Scripts"
```

> **Alternativa directa (sin tocar PATH):** Podés utilizar siempre:
> ```powershell
> python -m omnigent <comando>
> ```

---

## 3. Cómo Ejecutar Agentes con `python -m omnigent run` (Directo vs Atajo)

### ¿Se puede ejecutar directamente con `python -m omnigent run`?
**SÍ, absolutamente.** Pero en Windows PowerShell hay que tener en cuenta 3 detalles del entorno para evitar errores:

1. **Codificación UTF-8 (Bug de `cp1252`):** El demonio de túnel de Omnigent imprime el símbolo `✓` (`\u2713`). Si la consola usa la codificación tradicional de Windows (`cp1252`), Python crashea internamente y el túnel se desconecta arrojando:
   `Error: The connect daemon for host did not come online within 30s`.
2. **Credenciales en el entorno:** Omnigent lee `OPENAI_API_KEY` directamente de las variables del proceso de PowerShell (no lee archivos `.env` automáticamente).
3. **Servidor en background:** Para evitar timeouts al arrancar, se debe iniciar primero el servidor local con `server --background` o pasar `--server http://127.0.0.1:6767`.

### El comando directo en Windows (PowerShell):
```powershell
# 1. Configurar encoding y cargar credenciales en la sesión
$env:PYTHONUTF8 = 1
$env:PYTHONIOENCODING = "utf-8"
$env:OPENAI_API_KEY = (Get-Content .env | Select-String "OPENAI_API_KEY=").ToString().Split("=")[1].Trim()

# 2. Iniciar el servidor local en segundo plano (si no está corriendo)
python -m omnigent server --background

# 3. Ejecutar el agente directamente con la CLI oficial de Omnigent
python -m omnigent run omnigent/agents/seed-agent/ --server http://127.0.0.1:6767
```

---

### En macOS y Linux (Bash / Zsh): ¿Por qué funciona de forma directa y nativa?

En sistemas basados en UNIX (macOS y Linux) **la experiencia con Omnigent es 100% nativa y fluida**:

1. **UTF-8 nativo por defecto:** Los entornos UNIX tienen configurada la variable `LANG=en_US.UTF-8` o equivalente. El demonio de túnel de Omnigent emite caracteres Unicode (el checkmark `✓` o `\u2713`, flechas de progreso `➜`). En Windows esto genera el error `charmap codec can't encode character` bajo `cp1252`, pero en Mac y Linux se procesa directamente sin requerir flags adicionales.
2. **Sockets y TTYs POSIX:** Omnigent gestiona los procesos locales del agente y la conexión WebSocket mediante interfaces POSIX estándar (`pty`, `fork`), las cuales funcionan de manera instantánea y sin bloqueos de red local o timeouts de named pipes.
3. **Binarios en el PATH:** Al instalar con `pip install omnigent` en Linux/Mac, los ejecutables `omni` y `omnigent` se instalan habitualmente en `/usr/local/bin` o `~/.local/bin` (o en el directorio `bin/` de tu virtualenv), quedando disponibles de inmediato en la terminal.

---

#### Guía Paso a Paso para macOS y Linux

##### 1. Configurar Entorno y Credenciales
Abrí tu terminal (Terminal en macOS, Bash/Zsh en Linux):
```bash
# Entrar al directorio del proyecto
cd ciblab

# Cargar las variables de entorno desde el archivo .env (incluye OPENAI_API_KEY)
export $(grep -v '^#' .env | xargs)

# Verificar que la variable esté disponible
echo "API Key configurada: ${OPENAI_API_KEY:0:10}..."
```

##### 2. Iniciar el Servidor de Omnigent con todos los agentes pre-registrados
Para tener disponibles **los 5 agentes del laboratorio** en la interfaz web y en la CLI:

```bash
omni server --agent omnigent/agents/fuzz-orchestrator/ \
            --agent omnigent/agents/seed-agent/ \
            --agent omnigent/agents/execution-agent/ \
            --agent omnigent/agents/safety-agent/ \
            --agent omnigent/agents/triage-agent/ \
            --background
```
*(Nota: Si no tenés `omni` en tu PATH, podés usar `python3 -m omnigent server ...` con los mismos parámetros).*

Para verificar que el servidor está levantado y saludable:
```bash
omni server status
```
Salida esperada:
```text
Background server: running at http://127.0.0.1:6767 (pid 45892, port 6767)
  log: ~/.omnigent/logs/server/...
  live sessions: 1
  host daemon attached: yes
```

##### 3. Ejecutar un Agente en la Terminal (Opcional)
Si querés interactuar desde la consola en lugar del navegador:
```bash
omni run omnigent/agents/seed-agent/
```
En macOS/Linux el REPL interactivo abrirá de inmediato la sesión con **GPT-6 Luna**, mostrando el prompt del agente y esperando tus órdenes.

##### 4. Cómo Apagar / Detener el Servidor en macOS y Linux
Cuando termines de trabajar y quieras liberar el puerto `6767`:
```bash
# Opción A: Detener el servidor en segundo plano y su demonio host
omni server stop

# Opción B: Detener absolutamente todos los procesos de Omnigent activos
omni stop
```
*(Si no tenés el alias en el PATH: `python3 -m omnigent server stop`)*.

Para confirmar que se apagó correctamente:
```bash
omni server status
# Salida esperada: No background server is running.
```

---

### La Alternativa Rápida Multiplataforma (Atajo en `run.py`)
Tanto en Windows como en Mac o Linux, creamos un atajo en Python que automatiza la configuración de entorno y el chequeo del servidor:
```bash
python run.py --omni seed-agent
# o para el orquestador:
python run.py --omni fuzz-orchestrator
```

---

## 4. Paso a Paso: Probar los Agentes desde la UI Web Oficial de Omnigent

Omnigent incluye un **servidor web completo con una interfaz gráfica (SPA moderna en React)** para interactuar con tus agentes en el navegador sin tocar la terminal, monitorear el razonamiento en streaming y ver la ejecución de herramientas en vivo.

### Paso 1: Levantar el Servidor Web de Omnigent
Asegurate de que el servidor esté corriendo en segundo plano con los agentes registrados:

**En macOS / Linux:**
```bash
omni server --agent omnigent/agents/fuzz-orchestrator/ \
            --agent omnigent/agents/seed-agent/ \
            --agent omnigent/agents/execution-agent/ \
            --agent omnigent/agents/safety-agent/ \
            --agent omnigent/agents/triage-agent/ \
            --background
```

**En Windows (PowerShell - Recomendado con carga automática de credenciales):**
```powershell
python run.py --omni-start
```
*(Alternativa directa: `python -m omnigent start`)*.

*(Si necesitás reiniciar el servicio para recargar cambios: ejecutá `omni stop` o `python -m omnigent stop` y luego volvé a ejecutar el comando de arriba).*

---

### Paso 2: Abrir la Interfaz Web en el Navegador
Abrí cualquier navegador web moderno (Chrome, Firefox, Safari, Edge) e ingresá a:

👉 **`http://127.0.0.1:6767`**

Vas a ver la interfaz oscura oficial de Omnigent:
* Panel lateral izquierdo con el historial de sesiones y conversaciones.
* Botón superior **"+ New Chat"** para iniciar una interacción.
* Selector de agentes registrados en la barra superior.

---

### Paso 3: Probar un Agente en la UI

#### Caso A: Probar el `seed_agent` (Formulación de Hipótesis y Corpus)
1. Hacé clic en **"+ New Chat"**.
2. En el menú desplegable de selección de modelo/agente, elegí **`seed_agent`**.
3. En la caja de texto inferior, escribí tu indicación:
   ```text
   Analiza la estructura del parser binario vulnerable y formula una hipótesis científica junto con un corpus de 5 semillas de prueba para provocar fallos de memoria.
   ```
4. Presioná `Enter` o hacé clic en el botón de enviar.

#### Qué vas a ver en la pantalla:
1. **Streaming de Razonamiento (CoT):** Verás cómo **GPT-6 Luna** analiza la especificación (`DATA_STREAM_v1`, longitud esperada, tokens de control).
2. **Invocación Visual de Herramientas (Tool Call):** Aparecerá un bloque interactivo con el nombre `Tool Call: generate_corpus`. Podés desplegarlo para ver cómo ejecutó el código Python de [`app/agents/seed_agent.py`](../app/agents/seed_agent.py) y las 5 semillas en hexadecimal generadas.
3. **Respuesta Sintetizada:** El agente presenta la hipótesis explicada de forma clara y lista para alimentar al planificador.

---

#### Caso B: Probar el `fuzz_orchestrator` (Investigador Principal - Ciclo Completo)
1. Iniciá un **New Chat** y seleccioná el agente **`fuzz_orchestrator`**.
2. Escribí:
   ```text
   Inicia una investigación científica autónoma sobre el objetivo vulnerable.
   ```
3. **Qué vas a ver en la pantalla:**
   - El orquestador ejecuta la herramienta `run_fuzz_discovery` vinculada a [`app/orchestration/fuzz_lab.py`](../app/orchestration/fuzz_lab.py).
   - Verás la ejecución en streaming: generación de semillas -> selección del experimento de mayor valor -> ejecución de 30+ mutaciones -> **bloqueo en la puerta de seguridad (Human Approval Gate)**.
   - El agente informará que se descubrieron anomalías de memoria y que requiere la aprobación humana para continuar con la fase de triaje.
4. Para autorizar la reproducción y clasificación de fallos, escribí en el mismo chat:
   ```text
   Apruebo la reproducción de crashes y el triaje.
   ```
   El orquestador llamará a `approve_triage`, reproducirá los fallos, clasificará los CWEs (CWE-120, CWE-134, CWE-626) y emitirá la conclusión científica final con las métricas de aceleración.

---

### Paso 4: Diferencia con la UI Web del Cyber Lab (`http://127.0.0.1:8000`)

En nuestro proyecto contás con **dos interfaces web complementarias**:

| Interfaz | URL | Propósito |
|---|---|---|
| **Omnigent Web UI** | `http://127.0.0.1:6767` | **Consola de Agentes Multi-Modal:** Ideal para interactuar en lenguaje natural con cada agente especialista por separado, auditar llamadas a herramientas paso a paso y evaluar el comportamiento de `gpt-6-luna`. |
| **Cyber Lab Web UI** | `http://127.0.0.1:8000` | **Dashboard Científico del Experimento:** Interfaz especializada creada con FastAPI y HTML5 donde ves el flujo visual de las 5 fases en tarjetas, el botón interactivo de aprobación humana de seguridad, y las gráficas de aceleración vs baseline humano (45 min/crash vs 0.3s/crash). Se levanta ejecutando `python run.py`. |

---

### Paso 5: Cómo Apagar el Servidor de Omnigent al Finalizar

Cuando termines tu sesión de pruebas o quieras reiniciar el servidor para recargar configuraciones, tenés dos formas según tu sistema operativo:

#### En macOS y Linux:
```bash
# Opción 1: Detener el servidor web en background y el host daemon
omni server stop

# Opción 2: Detener absolutamente todos los procesos de Omnigent
omni stop
```
*(O con `python3 -m omnigent server stop`)*.

#### En Windows (PowerShell):
```powershell
# Opción 1: Detener el servidor web en background
python -m omnigent server stop

# Opción 2: Detener todos los procesos de Omnigent activos
python -m omnigent stop
```

#### Si lo levantaste en primer plano (Foreground):
Si levantaste el servidor sin la bandera `--background`, simplemente presioná:
```text
Ctrl + C
```

Para verificar que el puerto `6767` quedó libre:
```bash
# macOS / Linux:
omni server status

# Windows:
python -m omnigent server status
# Salida esperada: No background server is running.
```

---

## 5. Estructura de un Agente Omnigent (`config.yaml`)

En Omnigent v0.16+, cada agente es un **directorio** que contiene un archivo `config.yaml` con la especificación `spec_version: 1`:

```text
omnigent/
  agents/
    fuzz-orchestrator/
      config.yaml      <-- Agente Orquestador (PI)
    seed-agent/
      config.yaml      <-- Agente Generador de Hipótesis y Semillas
    execution-agent/
      config.yaml      <-- Agente de Ejecución de Fuzzing
    safety-agent/
      config.yaml      <-- Agente de Seguridad y Puerta de Aprobación
    triage-agent/
      config.yaml      <-- Agente de Triaje y Clasificación CWE
```

### Anatomía del archivo de configuración:
```yaml
spec_version: 1
name: fuzz_orchestrator
prompt: |
  Instrucciones del sistema para el agente...

executor:
  type: omnigent
  config:
    harness: openai-agents
  model: gpt-6-luna

os_env:
  type: caller_process
  cwd: .
  sandbox:
    write_paths: [.]
    allow_network: true

tools:
  run_fuzz_discovery:
    type: function
    callable: app.orchestration.fuzz_lab.start_fuzz_run
  approve_triage:
    type: function
    callable: app.orchestration.fuzz_lab.approve_and_triage

policies:
  rate_limit:
    type: function
    handler: omnigent.policies.builtins.safety.max_tool_calls_per_session
    factory_params:
      limit: 50
```

* **`executor`**: Define qué modelo impulsa el agente. Usamos `gpt-6-luna`.
* **`tools`**: Vincula funciones nativas de Python de nuestra aplicación (`app.*`) para que el agente las ejecute como herramientas tipadas.
* **`policies`**: Reglas y restricciones que Omnigent valida antes y después de cada invocación de herramienta.

---

## 6. El Gate de Aprobación Humana en Omnigent

Una de las características más importantes requeridas en la investigación científica asistida por IA es el **control humano (Human-in-the-loop)**.

En nuestro laboratorio:
1. El **Execution Agent** encuentra 30+ condiciones de fallo (crashes).
2. El flujo **no pasa automáticamente al triaje exhaustivo**.
3. Omnigent intercepta el evento e impone una política de seguridad:
   - Se emite el evento `human_approval_required`.
   - El estado del run pasa a `awaiting_approval`.
4. El investigador humano revisa el reporte preliminar y ejecuta la aprobación (mediante el botón web o el endpoint `POST /fuzz-approvals/{id}`).
5. Sólo tras la aprobación humana se habilita la fase de reproducción y clasificación formal.

---

## 7. Comandos Útiles de Omnigent

| Comando | Descripción |
|---|---|
| `python -m omnigent server --background` | Inicia el servidor central de Omnigent en segundo plano en el puerto `6767`. |
| `python -m omnigent server status` | Informa si el servidor de fondo está corriendo, su PID y puerto. |
| `python -m omnigent server stop` | **Apaga y detiene el servidor de fondo de Omnigent y su demonio host.** |
| `python -m omnigent stop` | **Detiene todos los procesos y ejecutores activos de Omnigent en la máquina.** |
| `python -m omnigent run <directorio>` | Ejecuta un agente local a partir de su `config.yaml`. |
| `python -m omnigent doctor` | Diagnostica el estado del entorno de Omnigent y verifica harnesses disponibles. |
| `python -m omnigent session list` | Lista las conversaciones y ejecuciones activas. |
| `python -m omnigent usage` | Muestra el consumo de tokens y llamadas por sesión. |

---

## 8. Documentación Técnica: Parche de Codificación en Windows (`connect.py`)

### Diagnóstico del Error Upstream:
En sistemas operativos Windows donde el juego de caracteres por defecto es `cp1252`, el demonio de conexión del host intentaba conectarse al servidor WebSocket en `ws://127.0.0.1:6767/v1/hosts/.../tunnel`. Al establecer el enlace, ejecutaba la siguiente línea en `omnigent/host/connect.py` (línea 4392):

```python
print(
    f"✓ Connected as {self._identity.name!r} "
    f"({self._identity.host_id}), {len(hello.runners)} live runner(s). "
    "Listening for sessions — Ctrl-C to disconnect.",
    flush=True,
)
```

Debido a que el glifo `✓` (`\u2713`) no tiene mapeo en la tabla `cp1252`, Python arrojaba:
```text
UnicodeEncodeError: 'charmap' codec can't encode character '\u2713' in position 0: character maps to <undefined>
```
Esto causaba que el túnel se desconectara inmediatamente, reintentando cada 3 segundos y dejando al host en estado `offline` permanente.

### Parche Aplicado:
Se envolvió la llamada en un bloque seguro:
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
Esto asegura estabilidad permanente del host daemon en Windows tanto en primer plano como en segundo plano.
