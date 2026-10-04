from __future__ import annotations

from fastapi import FastAPI, HTTPException
from fastapi.responses import HTMLResponse

from app.evaluation.evaluator import evaluate_latest, sealed_labels_hash
from app.evaluation.fuzz_evaluator import evaluate_fuzz_runs
from app.orchestration.lab import RUNS, execute_research_case, execute_run, get_run, get_timeline
from app.orchestration.omnigent_adapter import detect_omnigent
from app.orchestration.fuzz_lab import FUZZ_RUNS, start_fuzz_run, approve_and_triage
from app.services.data_store import load_detections
from app.storage.research_store import STORE
from app.models.schemas import ResearchCase

app = FastAPI(title="Cyber Research Lab — Fuzzing Discovery", version="0.3.0")
APPROVALS: dict[str, dict] = {}


@app.get("/health")
def health():
    return {"status": "ok", "omnigent": detect_omnigent()}


@app.get("/detections")
def detections():
    return [d.model_dump() for d in load_detections()]


@app.get("/cases")
def cases():
    return [case.model_dump() for case in STORE.cases.values()]


@app.post("/cases")
def create_case(case: ResearchCase):
    if case.case_id in STORE.cases:
        raise HTTPException(409, "case already exists")
    STORE.add_case(case)
    return case.model_dump()


@app.get("/cases/{case_id}")
def case(case_id: str):
    item = STORE.cases.get(case_id)
    if not item:
        raise HTTPException(404, "case not found")
    return item.model_dump()


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


@app.post("/research-runs")
def research_run(question: str, seed: int = 42, case_id: str = "CASE-001"):
    if case_id in STORE.cases:
        raise HTTPException(409, "case already exists")
    run_id = execute_research_case(question=question, seed=seed, case_id=case_id)
    return {"run_id": run_id, "case_id": case_id, "mode": detect_omnigent()["mode"]}


@app.get("/runs/{run_id}")
def run_status(run_id: str):
    run = get_run(run_id)
    if not run:
        raise HTTPException(404, "run not found")
    return {"run_id": run_id, "case_id": run.case_id, "event_count": len(run.events), "decision_count": len(run.decisions)}


@app.get("/runs/{run_id}/events")
def run_events(run_id: str):
    run = get_run(run_id)
    if not run:
        raise HTTPException(404, "run not found")
    return [e.model_dump(mode="json") for e in run.events]


@app.get("/detections/{id}/timeline")
def timeline(id: str):
    if id in STORE.cases:
        return [e.model_dump(mode="json") for e in STORE.timeline(id)]
    return [e.model_dump(mode="json") for e in get_timeline(id)]


@app.get("/cases/{case_id}/timeline")
def case_timeline(case_id: str):
    if case_id not in STORE.cases:
        raise HTTPException(404, "case not found")
    return [e.model_dump(mode="json") for e in STORE.timeline(case_id)]


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
    decision = next(
        (
            decision
            for run in RUNS.values()
            for decision in run.decisions.values()
            if decision.detection_id == decision_id
        ),
        None,
    )
    if decision is None:
        raise HTTPException(404, "decision not found")
    if not decision.requires_human_approval:
        raise HTTPException(409, "decision does not require human approval")
    APPROVALS[decision_id] = {"approved": approved}
    return {"decision_id": decision_id, "approved": approved}


@app.get("/research-record/{detection_id}")
def research_record(detection_id: str):
    if detection_id in STORE.cases:
        return [e.model_dump(mode="json") for e in STORE.timeline(detection_id)]
    return [e.model_dump(mode="json") for e in get_timeline(detection_id)]


@app.get("/cases/{case_id}/research-record")
def case_research_record(case_id: str):
    if case_id not in STORE.cases:
        raise HTTPException(404, "case not found")
    return [e.model_dump(mode="json") for e in STORE.timeline(case_id)]


# ── Fuzzing Lab Endpoints ────────────────────────────────────────────


@app.post("/fuzz-runs")
def fuzz_run(
    question: str = "What specific inputs cause memory corruption or crashes in this binary?",
    seed: int = 42,
):
    """Start a new fuzzing research run.

    Executes phases 1-3 (Question → Hypothesis → Experiment),
    then pauses at phase 4 (human approval).
    """
    run_id = start_fuzz_run(question=question, seed=seed)
    run = FUZZ_RUNS[run_id]
    return {
        "run_id": run_id,
        "case_id": run.case_id,
        "status": run.status,
        "crash_count": run.crash_count,
        "pending_approval": run.pending_approval,
        "mode": detect_omnigent()["mode"],
        "events_so_far": len(run.events),
    }


@app.get("/fuzz-runs/{run_id}")
def fuzz_run_status(run_id: str):
    """Get the status of a fuzzing run."""
    run = FUZZ_RUNS.get(run_id)
    if not run:
        raise HTTPException(404, "fuzz run not found")
    result = {
        "run_id": run_id,
        "case_id": run.case_id,
        "status": run.status,
        "event_count": len(run.events),
        "crash_count": run.crash_count,
        "pending_approval": run.pending_approval,
    }
    if run.discovery:
        result["discovery"] = run.discovery.model_dump(mode="json")
    return result


@app.get("/fuzz-runs/{run_id}/events")
def fuzz_run_events(run_id: str):
    """Get the research event timeline for a fuzzing run."""
    run = FUZZ_RUNS.get(run_id)
    if not run:
        raise HTTPException(404, "fuzz run not found")
    return [e.model_dump(mode="json") for e in run.events]


@app.post("/fuzz-approvals/{run_id}")
def fuzz_approval(run_id: str, approved: bool = True):
    """Approve or reject crash reproduction (Phase 4 → Phase 5).

    After approval, the Triage Agent runs and produces the final discovery.
    """
    run = FUZZ_RUNS.get(run_id)
    if not run:
        raise HTTPException(404, "fuzz run not found")
    if not run.pending_approval:
        raise HTTPException(409, "run is not awaiting approval")

    discovery = approve_and_triage(run_id, approved)
    if discovery is None and approved:
        raise HTTPException(500, "triage failed unexpectedly")

    result = {
        "run_id": run_id,
        "approved": approved,
        "status": run.status,
    }
    if discovery:
        result["discovery"] = discovery.model_dump(mode="json")
    return result


@app.get("/fuzz-runs-list")
def fuzz_runs_list():
    """List all fuzz runs."""
    return [
        {
            "run_id": run_id,
            "case_id": run.case_id,
            "status": run.status,
            "crash_count": run.crash_count,
            "pending_approval": run.pending_approval,
        }
        for run_id, run in FUZZ_RUNS.items()
    ]


@app.get("/fuzz-metrics")
def fuzz_metrics():
    """Get aggregate scientific metrics and discovery acceleration."""
    return evaluate_fuzz_runs(FUZZ_RUNS).model_dump()


# ── Landing Page ─────────────────────────────────────────────────────

@app.get("/", response_class=HTMLResponse)
def ui_home():
    return """<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8"/>
<meta name="viewport" content="width=device-width, initial-scale=1"/>
<title>🧪 Cyber Research Lab — Fuzzing Discovery</title>
<style>
  :root { --bg: #0a0e17; --surface: #141926; --border: #1e2738; --accent: #00d4aa;
          --accent2: #6366f1; --text: #e2e8f0; --muted: #64748b; --danger: #ef4444; }
  * { margin: 0; padding: 0; box-sizing: border-box; }
  body { font-family: 'Inter', system-ui, sans-serif; background: var(--bg); color: var(--text);
         min-height: 100vh; display: flex; flex-direction: column; align-items: center; padding: 2rem; }
  h1 { font-size: 2rem; margin-bottom: 0.5rem; background: linear-gradient(135deg, var(--accent), var(--accent2));
       -webkit-background-clip: text; -webkit-text-fill-color: transparent; }
  .subtitle { color: var(--muted); margin-bottom: 2rem; }
  .card { background: var(--surface); border: 1px solid var(--border); border-radius: 12px;
          padding: 1.5rem; margin: 0.75rem 0; width: 100%; max-width: 700px; }
  .card h3 { color: var(--accent); margin-bottom: 0.5rem; font-size: 1.1rem; }
  .card p { color: var(--muted); font-size: 0.9rem; line-height: 1.5; }
  .phase { display: flex; align-items: flex-start; gap: 1rem; padding: 0.75rem 0;
           border-bottom: 1px solid var(--border); }
  .phase:last-child { border-bottom: none; }
  .phase-num { background: var(--accent); color: var(--bg); width: 28px; height: 28px;
               border-radius: 50%; display: flex; align-items: center; justify-content: center;
               font-weight: 700; font-size: 0.85rem; flex-shrink: 0; }
  .phase-num.danger { background: var(--danger); }
  .phase-text strong { display: block; margin-bottom: 2px; }
  .phase-text span { color: var(--muted); font-size: 0.85rem; }
  .btn { display: inline-block; padding: 0.75rem 1.5rem; border-radius: 8px; font-weight: 600;
         text-decoration: none; cursor: pointer; border: none; font-size: 0.95rem; margin: 0.5rem 0.25rem;
         transition: transform 0.15s, box-shadow 0.15s; }
  .btn:hover { transform: translateY(-1px); box-shadow: 0 4px 20px rgba(0,212,170,0.3); }
  .btn-primary { background: linear-gradient(135deg, var(--accent), var(--accent2)); color: white; }
  .btn-outline { background: transparent; border: 1px solid var(--accent); color: var(--accent); }
  .endpoints { font-family: monospace; font-size: 0.85rem; color: var(--muted); }
  .endpoints code { color: var(--accent); }
  #output { white-space: pre-wrap; font-family: monospace; font-size: 0.8rem; max-height: 400px;
            overflow-y: auto; background: #0d1117; padding: 1rem; border-radius: 8px; margin-top: 1rem;
            display: none; }
  .badge { display: inline-block; padding: 2px 8px; border-radius: 4px; font-size: 0.75rem;
           font-weight: 600; margin-left: 8px; }
  .badge-ok { background: rgba(0,212,170,0.2); color: var(--accent); }
  .badge-wait { background: rgba(239,68,68,0.2); color: var(--danger); }
</style>
</head>
<body>
<h1>🧪 Agentic Fuzzing Lab</h1>
<p class="subtitle">Scientific Discovery through Automated Vulnerability Research</p>

<div class="card">
  <h3>Scientific Method Phases</h3>
  <div class="phase"><div class="phase-num">1</div><div class="phase-text"><strong>Question</strong><span>What inputs cause memory corruption in this binary?</span></div></div>
  <div class="phase"><div class="phase-num">2</div><div class="phase-text"><strong>Hypothesis &amp; Seeds</strong><span>Seed Agent formulates hypothesis and generates mutation corpus</span></div></div>
  <div class="phase"><div class="phase-num">3</div><div class="phase-text"><strong>Experiment</strong><span>Execution Agent runs fuzzer with seed corpus against target</span></div></div>
  <div class="phase"><div class="phase-num danger">4</div><div class="phase-text"><strong>Human Approval 🛑</strong><span>Crashes found — human scientist must approve reproduction</span></div></div>
  <div class="phase"><div class="phase-num">5</div><div class="phase-text"><strong>Triage &amp; Discovery</strong><span>Triage Agent reproduces crashes, classifies CWEs, confirms hypothesis</span></div></div>
</div>

<div class="card">
  <h3>Run Experiment</h3>
  <p>Start a fuzzing run, then approve the crashes when prompted.</p>
  <button class="btn btn-primary" onclick="startFuzz()">🚀 Start Fuzzing Experiment</button>
  <button class="btn btn-outline" id="approveBtn" onclick="approveCrashes()" style="display:none">✅ Approve Crash Reproduction</button>
  <div id="output"></div>
</div>

<div class="card">
  <h3>API Endpoints</h3>
  <div class="endpoints">
    <code>POST /fuzz-runs</code> — Start fuzzing research run<br/>
    <code>GET  /fuzz-runs/{id}</code> — Run status + discovery<br/>
    <code>GET  /fuzz-runs/{id}/events</code> — Research event timeline<br/>
    <code>POST /fuzz-approvals/{id}</code> — Approve crash reproduction<br/>
    <code>GET  /health</code> — Omnigent status<br/>
  </div>
</div>

<script>
let currentRunId = null;
const out = document.getElementById('output');
const approveBtn = document.getElementById('approveBtn');

function log(msg) { out.style.display = 'block'; out.textContent += msg + '\\n'; out.scrollTop = out.scrollHeight; }

async function startFuzz() {
  out.textContent = ''; approveBtn.style.display = 'none';
  log('🧪 Starting fuzzing experiment...');
  try {
    const res = await fetch('/fuzz-runs', { method: 'POST' });
    const data = await res.json();
    currentRunId = data.run_id;
    log(`✅ Run started: ${data.run_id}`);
    log(`   Case: ${data.case_id}`);
    log(`   Status: ${data.status}`);
    log(`   Crashes found: ${data.crash_count}`);
    log(`   Omnigent mode: ${data.mode}`);
    if (data.pending_approval) {
      log('\\n🛑 HUMAN APPROVAL REQUIRED');
      log('   The fuzzer found crashes. Review and approve reproduction.');
      approveBtn.style.display = 'inline-block';
    }
    // Fetch events
    const evRes = await fetch(`/fuzz-runs/${data.run_id}/events`);
    const events = await evRes.json();
    log('\\n📋 Research Event Timeline:');
    events.forEach((e, i) => {
      log(`   ${i+1}. [${e.agent}] ${e.action} (confidence: ${e.confidence})`);
      if (e.action === 'hypothesis_and_corpus' && e.output && e.output.hypothesis) {
        log(`      💡 Hipótesis (GPT-6 Luna): "${e.output.hypothesis}"`);
      }
      if (e.action === 'experiment_selection' && e.output && e.output.rationale) {
        log(`      ⚖️  Planificación: ${e.output.rationale}`);
      }
    });
  } catch(err) { log('❌ Error: ' + err.message); }
}

async function approveCrashes() {
  if (!currentRunId) return;
  log('\\n✅ Approving crash reproduction...');
  try {
    const res = await fetch(`/fuzz-approvals/${currentRunId}?approved=true`, { method: 'POST' });
    const data = await res.json();
    log(`   Status: ${data.status}`);
    if (data.discovery) {
      const d = data.discovery;
      log('\\n🏆 SCIENTIFIC DISCOVERY:');
      log(`   Hypothesis confirmed: ${d.hypothesis_confirmed}`);
      log(`   Crashes found: ${d.crashes_found}`);
      log(`   Experiments proposed: ${d.experiments_proposed}`);
      log(`   Experiment selected: ${d.experiment_selected}`);
      log(`   Speedup vs manual: ${d.speedup_vs_manual}x`);
      log(`   Reproducibility seed: ${d.reproducibility_seed}`);
      log('\\n   Triage Results:');
      d.triage_results.forEach(t => {
        log(`     • ${t.cwe_id} (${t.cwe_name}) — ${t.severity}`);
      });
      log('\\n   Adaptation: ' + d.adaptation_event);
      log('\\n   Conclusion: ' + d.scientific_conclusion);
    }
    approveBtn.style.display = 'none';
  } catch(err) { log('❌ Error: ' + err.message); }
}
</script>
</body>
</html>"""

