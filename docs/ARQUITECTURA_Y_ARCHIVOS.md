# 🏛️ Arquitectura del Proyecto, Catálogo de Archivos y Uso de Omnigent

Este documento responde de forma clara y directa a las dudas fundamentales sobre el proyecto: **qué hacían los agentes antes vs qué hacen ahora**, **cuáles son los archivos activos y cuáles se eliminaron**, y **cómo encaja Omnigent dentro del laboratorio**.

---

## 1. La Verdad sobre los Agentes: ¿Antes se usaban o eran simulados?

### El Escenario Anterior (Código Base Inicial)
En el repositorio original (`ciblab`), los archivos dentro de `app/agents/` (`research.py`, `hypothesis.py`, `planner.py`, etc.) eran **heurísticas determinísticas en Python con plantillas de texto fijas**. 
* Tenían contratos de datos con Pydantic (`schemas.py`), pero **no se comunicaban con ningún modelo de inteligencia artificial**.
* Las "hipótesis" y los "planes" eran cadenas estáticas formateadas con `f-strings`.

### El Escenario Actual (Laboratorio con GPT-6 Luna)
Ahora los agentes son **agentes cognitivos reales** integrados con la API de OpenAI:
* **Fase 2 (Evidencia e Hipótesis):** El [seed_agent.py](../app/agents/seed_agent.py) toma la descripción y restricciones del parser, envía un prompt a **`gpt-6-luna`** en tiempo real y recibe una hipótesis científica comprobable y no trivial sobre cómo provocar fallos de memoria.
* **Fase 5 (Triaje y Conclusión):** El [fuzz_lab.py](../app/orchestration/fuzz_lab.py) toma los resultados de los crashes reproducidos y le pide a **`gpt-6-luna`** que evalúe si la hipótesis se confirmó, sintetice los patrones de vulnerabilidad detectados y recomiende la adaptación del siguiente ciclo.
* **Frontera de Seguridad y Rigor:** Las mutaciones de bytes, la ejecución del parser y la medición del tiempo se realizan en Python determinístico para garantizar que las métricas y la reproducibilidad sean matemáticamente exactas y sin alucinaciones.

---

## 2. Mapa Completo de Archivos Activos (Lo que SÍ se usa)

La estructura del proyecto quedó depurada y 100% enfocada en el **Laboratorio de Fuzzing Científico**:

```text
ciblab/
├── run.py                                    <-- Punto de entrada principal (Web, Interactivo o Demo)
├── pyproject.toml                            <-- Configuración del paquete y dependencias
├── AGENTS.md                                 <-- Reglas del sistema y misión del laboratorio
├── FLOWCHART.md                              <-- Arquitectura y diagrama de secuencia de Fuzzing
├── .env                                      <-- Credenciales locales (OpenAI, Gemini, etc.) [Ignorado en Git]
│
├── app/
│   ├── main.py                               <-- Servidor FastAPI + Interfaz Web interactiva
│   │
│   ├── agents/                               <-- Agentes especialistas del método científico
│   │   ├── seed_agent.py                     <-- Fase 2: Hipótesis con GPT-6 Luna y generación de semillas
│   │   ├── execution_agent.py                <-- Fase 3: Operador del fuzzer y mutaciones de bytes
│   │   ├── safety_fuzz.py                    <-- Fase 4: Validador de sandbox y Gate de Aprobación Humana
│   │   └── triage_agent.py                   <-- Fase 5: Reproducción de fallos y clasificación CWE
│   │
│   ├── orchestration/                        <-- Coordinación del flujo científico
│   │   ├── fuzz_lab.py                       <-- Orquestador principal (PI), adaptaciones y síntesis LLM
│   │   └── omnigent_adapter.py               <-- Detección del runtime instalado de Omnigent
│   │
│   ├── experiments/
│   │   └── vulnerable_binary.py              <-- Parser C vulnerable sintético (Buffer Overflow, Format String, Null byte)
│   │
│   ├── models/
│   │   └── schemas.py                        <-- Esquemas de datos Pydantic fuertemente tipados
│   │
│   ├── evaluation/
│   │   └── fuzz_evaluator.py                 <-- Métricas de aceleración (Speedup) y reproducibilidad
│   │
│   └── storage/
│       └── research_store.py                 <-- Registro de investigación persistente (append-only)
│
├── omnigent/
│   └── agents/                               <-- Agentes declarativos de Omnigent (spec_version: 1)
│       ├── fuzz-orchestrator/config.yaml     <-- Agente Orquestador en Omnigent
│       ├── seed-agent/config.yaml            <-- Agente de Semillas en Omnigent
│       ├── execution-agent/config.yaml       <-- Agente de Ejecución en Omnigent
│       ├── safety-agent/config.yaml          <-- Agente de Seguridad en Omnigent
│       └── triage-agent/config.yaml          <-- Agente de Triaje en Omnigent
│
├── tests/
│   └── test_fuzz_lab.py                      <-- Batería completa de pruebas unitarias y de integración
│
└── docs/
    ├── README.md                             <-- Documentación general del laboratorio
    ├── OMNIGENT_GUIDE.md                     <-- Guía de uso profundo de la CLI de Omnigent
    └── ARQUITECTURA_Y_ARCHIVOS.md            <-- Este documento
```

---

## 3. Archivos Eliminados (Código Muerto / Legacy)

Para evitar confusiones, eliminamos del repositorio 20 archivos que pertenecían a una prueba de concepto previa sobre triaje de alertas de SIEM / detección que no tenían relación con el laboratorio de fuzzing:

| Archivo Eliminado | Razón de la Eliminación |
|---|---|
| `app/agents/research.py` | Antiguo agente de búsqueda de reglas SIEM. |
| `app/agents/hypothesis.py` | Antiguo generador de hipótesis para falsos positivos. |
| `app/agents/literature.py` | Antiguo consultor de CVEs para reglas de detección. |
| `app/agents/planner.py` | Antiguo planificador de pruebas de regresión de SIEM. |
| `app/agents/portfolio.py` | Antiguo evaluador de portfolio de reglas. |
| `app/agents/red_team.py` | Antiguo generador de evasión de reglas. |
| `app/agents/safety.py` | Reemplazado por `app/agents/safety_fuzz.py`. |
| `app/agents/analysis.py` | Antiguo calculador de matrices de confusión SIEM. |
| `app/agents/experiment_runner.py` | Reemplazado por `app/agents/execution_agent.py`. |
| `app/experiments/synthetic_generator.py` | Antiguo generador de telemetría de alertas sintéticas. |
| `app/services/data_store.py` | Antiguo cargador de detecciones JSON. |
| `app/services/detection_engine.py` | Antiguo motor de evaluación de reglas Sigma/Yara. |
| `app/tools/public_evidence.py` | Antiguo adaptador de MITRE ATT&CK. |
| `app/evaluation/evaluator.py` | Reemplazado por `app/evaluation/fuzz_evaluator.py`. |
| `app/orchestration/lab.py` | Reemplazado por `app/orchestration/fuzz_lab.py`. |
| `data/detections/detections.json` | Dataset estático de alertas SIEM ya innecesario. |
| `data/ground_truth/sealed_labels.json` | Dataset estático de etiquetas SIEM ya innecesario. |
| `omnigent/config/agents.yaml` | Archivo en formato desactualizado (reemplazado por `omnigent/agents/*`). |
| `omnigent/policies/safety.yaml` | Archivo desactualizado integrado en las políticas de los agentes. |
| `tests/test_lab.py` | Pruebas del sistema viejo (reemplazado por `tests/test_fuzz_lab.py`). |

---

## 4. ¿Qué es Omnigent y Cómo se Usa en este Proyecto?

### El Rol de Omnigent
Mucha gente confunde el **Modelo de IA** (como GPT-6 Luna) con el **Orquestador** (como Omnigent):
* **GPT-6 Luna es el Cerebro:** Genera el texto, analiza el contexto y formula las hipótesis.
* **Omnigent es el Marco de Gobierno y Orquestación:**
  1. **Define las fronteras:** Qué herramientas puede tocar cada agente (`tools: ...`).
  2. **Impone Políticas de Seguridad:** Por ejemplo, la política `require_human_approval_on_crash` que impide que un agente ejecute volcados de memoria sin autorización expresa de un humano.
  3. **Permite Ejecución Autónoma:** Permite desplegar los agentes en servidores remotos o ejecutarlos localmente vía CLI.

### Cómo ejecutar los agentes en Omnigent
Para iniciar una sesión formal de un agente dentro del runtime de Omnigent:
```powershell
python -m omnigent run omnigent/agents/fuzz-orchestrator/
```
Esto levanta el runtime de Omnigent, carga el `config.yaml`, vincula las herramientas Python registradas (`app.orchestration.fuzz_lab.start_fuzz_run`) y abre la sesión del agente.

---

## 5. Resumen de Ejecución Rápida

| Qué querés hacer | Comando a ejecutar |
|---|---|
| **Ver la UI web interactiva** | `python run.py` (abrir en navegador `http://127.0.0.1:8000`) |
| **Hacer una prueba interactiva en terminal (con aprobación humana)** | `python run.py --interactive` |
| **Hacer una prueba rápida automatizada** | `python run.py --demo` |
| **Correr la suite de pruebas del laboratorio** | `python -c "import tests.test_fuzz_lab as t; t.test_vulnerable_binary_crashes(); t.test_seed_agent_generates_corpus(); t.test_execution_agent_discovers_crashes(); t.test_safety_agent_validates_and_gates(); t.test_fuzz_lab_end_to_end(); t.test_api_endpoints(); print('ALL 6 TESTS PASSED!')"` |
| **Verificar el estado de Omnigent** | `python -m omnigent doctor` |
