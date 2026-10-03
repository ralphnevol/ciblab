# Detection Triage Lab (MVP)

## 1) Problem & Scientific Question
How should a detection portfolio be evaluated as falsifiable hypotheses under explicit uncertainty, budget constraints, and adaptive adversarial pressure?

## 2) Architecture
- FastAPI API/UI shell
- Deterministic multi-agent orchestration loop
- Omnigent integration adapter (`native` when installed, `local_fallback` otherwise)
- Event-oriented shared research record

## 3) Agent Architecture
- Literature
- Evaluation Planner (gain/cost budgeted selection)
- Experiment Runner
- Analysis
- Adaptive Red Team (simulation only)
- Portfolio Decision
- Safety/Governance

## 4) Data Model
Strict Pydantic schemas in `app/models/schemas.py` for Detection, LiteratureEvidence, ExperimentSpec/Result, Scorecard, RobustnessResult, PlannerDecision, PortfolioDecision, SafetyDecision, ResearchEvent, ManualBaselineResult, EvaluationResult.

## 5) Detection Portfolio
18 seeded synthetic detections in `data/detections/detections.json`.

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
1. `POST /runs`
2. `GET /runs/{run_id}`
3. `GET /runs/{run_id}/events`
4. `GET /detections/D03/timeline`

## 12) Running Evaluation
- `GET /evaluation`
- `GET /metrics`

## 13) Running Tests
```bash
pytest
```

## 14) API
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

## 15) Demo Walkthrough
For D03: baseline appears strong, red-team timing randomization degrades performance, planner emits `ADAPTATION_EVENT`, final decision remains explicitly evidence-driven (`INVESTIGATE`).

## 16) Known Limitations
- Lightweight local evidence adapter (no full RAG/graph pipeline yet)
- Omnigent adapter path + local fallback; native runtime depends on environment
- UI is intentionally minimal for hackathon reliability

## 17) Path to Scale
- Swap storage/event backend to PostgreSQL/Elasticsearch
- Replace heuristic literature/planner reasoning with provider-backed LLM adapters
- Expand calibration/quality scoring and governance policy enforcement depth
