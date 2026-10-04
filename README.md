# Cyber Research Lab (MVP)

## 1) Problem & Scientific Question
How can a research lab move reproducibly from a research question to evidence, hypotheses, experiments, results, and an updated decision?

## 2) Architecture
- FastAPI API/UI shell
- Deterministic multi-agent orchestration loop
- Omnigent integration adapter (`native` when installed, `local_fallback` otherwise)
- Event-oriented shared research record
- Synthetic/public binary-research vertical slice

## 3) Agent Architecture
- Research
- Hypothesis
- Literature
- Evaluation Planner (gain/cost budgeted selection)
- Experiment Runner
- Analysis
- Adaptive Red Team (simulation only)
- Portfolio Decision
- Safety/Governance

## 4) Data Model
Strict Pydantic schemas in `app/models/schemas.py` for Detection, LiteratureEvidence, ExperimentSpec/Result, Scorecard, RobustnessResult, PlannerDecision, PortfolioDecision, SafetyDecision, ResearchEvent, ManualBaselineResult, EvaluationResult.

## 5) MVP Vertical
The primary demo investigates `synthetic-binary-01`. Public literature, MITRE, and binary findings are tools that emit typed evidence; agents interpret that evidence and plan safe experiments. The original 18-detection portfolio remains available as a D03 compatibility regression scenario.

## 6) Experiment Methodology
- Deterministic synthetic data (`seed`, generator version, parameters, dataset_id)
- Deterministic rule engine
- Budgeted experiment planning
- Adaptation loop (notably D03 timing randomization)

## 7) Evaluation Methodology
`app/evaluation/evaluator.py` calculates:
- accuracy
- 3x3 confusion matrix
- time per detection
- decisions/hour
- speedup vs manual baseline
- justification quality (MVP heuristic)
- adaptation count
- reproducibility status

## 8) Security Model
- Data is fictitious/public only
- No employer/employee telemetry
- Red-team only on synthetic traces
- Human approval required for DECOMMISSION
- Ground truth sealed in `data/ground_truth/sealed_labels.json`

## 9) Local Setup
```bash
pip install -e .[dev]
uvicorn app.main:app --reload
```

## 10) Omnigent Setup
Agent/policy definitions live under `omnigent/`. Runtime detection is exposed in `GET /health`.

## 11) Running the MVP
1. `POST /research-runs?question=Does%20timing%20change%20the%20parser%20result%3F&seed=42`
2. `GET /runs/{run_id}/events`
3. `GET /cases/CASE-001/research-record`
4. Observe `candidates_selected` followed by `ADAPTATION_EVENT`.

## 12) Running the compatibility scenario
1. `POST /runs`
2. `GET /runs/{run_id}`
3. `GET /runs/{run_id}/events`
4. `GET /detections/D03/timeline`

## 13) Running Evaluation
- `GET /evaluation`
- `GET /metrics`

## 14) Running Tests
```bash
pytest
```

## 15) API
- `GET /cases`
- `POST /cases`
- `GET /cases/{case_id}`
- `POST /research-runs`
- `GET /health`
- `GET /detections`
- `GET /detections/{id}`
- `POST /runs`
- `GET /runs/{run_id}`
- `GET /runs/{run_id}/events`
- `GET /detections/{id}/timeline`
- `GET /evaluation`
- `GET /metrics`
- `POST /approvals/{decision_id}`
- `GET /research-record/{detection_id}`

## 16) Demo Walkthrough
The primary demo proposes two experiments, executes the selected stable-timing test, observes a new timing uncertainty, and changes the next planner selection to randomized timing. The D03 compatibility scenario separately demonstrates adaptive robustness degradation.

## 17) Known Limitations
- Lightweight local evidence adapter (no full RAG/graph pipeline yet)
- Omnigent adapter path + local fallback; native runtime depends on environment
- UI is intentionally minimal for hackathon reliability

## 18) Path to Scale
- Swap storage/event backend to PostgreSQL/Elasticsearch
- Replace heuristic literature/planner reasoning with provider-backed LLM adapters
- Expand calibration/quality scoring and governance policy enforcement depth
