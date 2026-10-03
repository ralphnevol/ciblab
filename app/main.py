from __future__ import annotations

from fastapi import FastAPI, HTTPException
from fastapi.responses import HTMLResponse

from app.evaluation.evaluator import evaluate_latest, sealed_labels_hash
from app.orchestration.lab import RUNS, execute_run, get_run, get_timeline
from app.orchestration.omnigent_adapter import detect_omnigent
from app.services.data_store import load_detections

app = FastAPI(title="Detection Triage Lab", version="0.1.0")
APPROVALS: dict[str, dict] = {}


@app.get("/health")
def health():
    return {"status": "ok", "omnigent": detect_omnigent()}


@app.get("/detections")
def detections():
    return [d.model_dump() for d in load_detections()]


@app.get("/detections/{id}")
def detection(id: str):
    for d in load_detections():
        if d.detection_id == id:
            return d.model_dump()
    raise HTTPException(404, "detection not found")


@app.post("/runs")
def run_all(seed: int = 42):
    run_id = execute_run(seed=seed)
    return {"run_id": run_id, "sealed_ground_truth_hash": sealed_labels_hash()}


@app.get("/runs/{run_id}")
def run_status(run_id: str):
    run = get_run(run_id)
    if not run:
        raise HTTPException(404, "run not found")
    return {"run_id": run_id, "event_count": len(run.events), "decision_count": len(run.decisions)}


@app.get("/runs/{run_id}/events")
def run_events(run_id: str):
    run = get_run(run_id)
    if not run:
        raise HTTPException(404, "run not found")
    return [e.model_dump(mode="json") for e in run.events]


@app.get("/detections/{id}/timeline")
def timeline(id: str):
    return [e.model_dump(mode="json") for e in get_timeline(id)]


@app.get("/evaluation")
def evaluation():
    ev = evaluate_latest()
    if ev is None:
        raise HTTPException(404, "no runs yet")
    return ev.model_dump()


@app.get("/metrics")
def metrics():
    ev = evaluate_latest()
    if ev is None:
        raise HTTPException(404, "no runs yet")
    return {"accuracy": ev.accuracy, "decisions_per_hour": ev.decisions_per_hour, "adaptation_count": ev.adaptation_count}


@app.post("/approvals/{decision_id}")
def approval(decision_id: str, approved: bool = True):
    APPROVALS[decision_id] = {"approved": approved}
    return {"decision_id": decision_id, "approved": approved}


@app.get("/research-record/{detection_id}")
def research_record(detection_id: str):
    return [e.model_dump(mode="json") for e in get_timeline(detection_id)]


@app.get("/", response_class=HTMLResponse)
def ui_home():
    return """
    <html><body><h1>DETECTION TRIAGE LAB</h1><p>Use API endpoints for timeline/evaluation. D03 adaptation visible in /detections/D03/timeline after POST /runs.</p></body></html>
    """
