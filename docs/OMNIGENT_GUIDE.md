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

### El comando directo completo en PowerShell:
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

### La Alternativa Rápida (Atajo en `run.py`)
Para que no tengas que escribir esas 4 líneas de configuración de variables en cada terminal, creamos el atajo:
```powershell
python run.py --omni seed-agent
```
o para el orquestador principal:
```powershell
python run.py --omni fuzz-orchestrator
```
Este comando hace exactamente lo mismo por debajo: inyecta el UTF-8, carga tu clave de `.env`, levanta el servidor y conecta la sesión interactiva con Omnigent.

---

### Ver la Sesión en la Interfaz Gráfica Oficial de Omnigent
Cuando el servidor de Omnigent está corriendo, podés abrir en tu navegador:
👉 **`http://127.0.0.1:6767`**
Ahí vas a ver la UI oficial de Omnigent con las sesiones activas, las herramientas invocadas y los logs en tiempo real.

---

## 4. Estructura de un Agente Omnigent (`config.yaml`)

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

## 5. El Gate de Aprobación Humana en Omnigent

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

## 6. Comandos Útiles de Omnigent

| Comando | Descripción |
|---|---|
| `python -m omnigent doctor` | Diagnostica el estado del entorno de Omnigent y verifica harnesses disponibles. |
| `python -m omnigent run <directorio>` | Ejecuta un agente local a partir de su `config.yaml`. |
| `python -m omnigent server` | Inicia el servidor central de Omnigent en segundo plano. |
| `python -m omnigent session list` | Lista las conversaciones y ejecuciones activas. |
| `python -m omnigent usage` | Muestra el consumo de tokens y llamadas por sesión. |
