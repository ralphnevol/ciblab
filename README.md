# Detection Triage Lab (MVP)

Scientific, agentic MVP for cybersecurity detection triage using synthetic/public data only.

## Guarantees
- Fictitious/public data only (no employer/employee telemetry)
- Ground truth labels sealed in `data/ground_truth/sealed_labels.json`
- Human approval required for decommission decisions
- Red-team is simulation-only over synthetic traces

## Architecture
- FastAPI backend (`app/main.py`)
- Deterministic multi-agent loop (`app/orchestration/lab.py`)
- Omnigent integration path + local fallback (`app/orchestration/omnigent_adapter.py`, `omnigent/config/agents.yaml`)
- Structured Pydantic models (`app/models/schemas.py`)
- Deterministic synthetic generator (`app/experiments/synthetic_generator.py`)
- Evaluation (`app/evaluation/evaluator.py`)

## Run
```bash
pip install -e .[dev]
uvicorn app.main:app --reload
```

## Tests
```bash
pytest
```

## Demo Flow
1. `POST /runs` to execute all 18 detections.
2. `GET /detections/D03/timeline` to view adaptation sequence and `ADAPTATION_EVENT`.
3. `GET /evaluation` for metrics/confusion matrix/reproducibility.
