from __future__ import annotations

from contextlib import AsyncExitStack, asynccontextmanager

from fastapi import FastAPI, HTTPException
from fastapi.responses import HTMLResponse

from app.evaluation.evaluator import evaluate_latest, sealed_labels_hash
from app.mcp_tools import SERVERS
from app.orchestration import agentic
from app.orchestration.lab import DEFAULT_BUDGET, execute_run, get_run, get_timeline, record_approval
from app.orchestration.omnigent_adapter import detect_omnigent
from app.services.data_store import load_detections

MCP_APPS = {role: server.streamable_http_app(stateless_http=True) for role, server in SERVERS.items()}


@asynccontextmanager
async def lifespan(_: FastAPI):
    # Mounted sub-apps don't get their own lifespan, so run each MCP session manager here.
    async with AsyncExitStack() as stack:
        for server in SERVERS.values():
            await stack.enter_async_context(server.session_manager.run())
        yield


app = FastAPI(title="Detection Triage Lab", version="0.1.0", lifespan=lifespan)
for _role, _mcp_app in MCP_APPS.items():
    app.mount(f"/lab/{_role}", _mcp_app)

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
def run_all(seed: int = 42, budget: int = DEFAULT_BUDGET):
    run_id = execute_run(seed=seed, max_test_cost=budget)
    return {"run_id": run_id, "sealed_ground_truth_hash": sealed_labels_hash()}


@app.post("/agentic-runs")
def create_agentic_run(seed: int = 42, budget: int = DEFAULT_BUDGET):
    run = agentic.create_run(seed=seed, budget=budget)
    return {
        "run_id": run.run_id,
        "sealed_ground_truth_hash": sealed_labels_hash(),
        "launch": f'omnigent run omnigent/triage_lab -p "Triage every detection in lab run {run.run_id}"',
    }


@app.get("/runs/{run_id}")
def run_status(run_id: str):
    run = get_run(run_id)
    if not run:
        raise HTTPException(404, "run not found")
    return {"run_id": run_id, "mode": run.mode, "event_count": len(run.events), "decision_count": len(run.decisions)}


@app.get("/runs/{run_id}/events")
def run_events(run_id: str):
    run = get_run(run_id)
    if not run:
        raise HTTPException(404, "run not found")
    return [e.model_dump(mode="json") for e in run.events]


@app.get("/runs/{run_id}/decisions")
def run_decisions(run_id: str):
    run = get_run(run_id)
    if not run:
        raise HTTPException(404, "run not found")
    return [d.model_dump(mode="json") for d in run.decisions.values()]


@app.get("/detections/{id}/timeline")
def timeline(id: str, run_id: str | None = None):
    return [e.model_dump(mode="json") for e in get_timeline(id, run_id)]


@app.get("/evaluation")
def evaluation(run_id: str | None = None):
    ev = evaluate_latest(run_id)
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
def approval(decision_id: str, approved: bool = True, reviewer: str = "analyst"):
    try:
        decision = record_approval(decision_id, approved, reviewer)
    except LookupError:
        raise HTTPException(404, "decision not found")
    except ValueError as exc:
        raise HTTPException(409, str(exc))
    return decision.model_dump(mode="json")


@app.get("/research-record/{detection_id}")
def research_record(detection_id: str, run_id: str | None = None):
    return [e.model_dump(mode="json") for e in get_timeline(detection_id, run_id)]


@app.get("/", response_class=HTMLResponse)
def ui_home():
    return """
    <html><body><h1>DETECTION TRIAGE LAB</h1><p>Use API endpoints for timeline/evaluation. D03 adaptation visible in /detections/D03/timeline after POST /runs.</p></body></html>
    """
