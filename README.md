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
- **Simulated world.** Each detection fires when an event's `signal` crosses its rule threshold (`parameters.signal_threshold` in `detections.json`). Benign and injected-malicious events are drawn from Gaussian distributions whose parameters live in `data/simulation/world_profiles.json`. Only the generator reads that file; agents see only the generated datasets.
- **Determinism.** Every dataset is seeded per `(seed, detection, stream)` and carries `dataset_id`, `generator_version` and parameters. Robustness variants reuse the baseline stream, so each comparison is paired and only the malicious signal shifts.
- **Intake.** Every detection gets a literature check (cost 1) and an efficacy test (cost 3) out of a per-detection budget (default 10).
- **Planning loop.** After each result the portfolio agent issues a provisional decision. The planner then ranks the remaining tests by `expected_information_gain / cost` given that decision and the current uncertainty. It also records the follow-up it expects to run next, and it stops when nothing affordable is worth at least 0.1.
- **Adaptive red team.** It escalates a synthetic evasion (strengths 0.25 → 1.0) until recall drops by more than 0.2. Degradation is scored at strength 0.5.
- **Uncertainty** is the sum of four components: the recall Wilson-interval width, literature quality (halved after an evidence review), robustness degradation (0.1 if untested), and a decision-margin penalty.
- **Adaptation.** An `ADAPTATION_EVENT` is emitted when new evidence makes the planner choose something other than the follow-up it had planned. Nothing in the orchestrator is specific to one detection.

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

## 10) Omnigent on Databricks (agentic mode)

In agentic mode, Omnigent LLM agents running on your Databricks workspace's Foundation Models drive the triage. There are seven agents: a director plus literature, planner, red team, analyst, portfolio and safety specialists. They reach the lab only through MCP tools, with one server per role at `/lab/<role>/mcp`. Each role sees only its own tools, and the role written to the research record comes from the endpoint, not the model.

**The models choose, the lab enforces.** All numbers (experiments, scorecards, uncertainty) are computed by the lab, deterministically. The lab refuses calls that break budget or ordering, and DECOMMISSION always waits for `POST /approvals/{decision_id}`. No agent has filesystem access, so the sealed labels and simulator parameters stay out of reach. Every submitted decision also records the rule-based reference decision, so you can see where the LLM disagreed.

**Prerequisites:** the **Omnigent** preview enabled in workspace settings, a region with Unity Gateway, Python 3.12+, Node.js 22, and `tmux`.

```bash
uv tool install "omnigent[databricks]"
omni setup                                  # choose Databricks Foundation Model APIs
omni login https://<workspace-host>
omni host --server https://<workspace-host> # keep running; sessions run on this machine

make run                                    # lab API + MCP endpoints on 127.0.0.1:8000
make agentic-run                            # all 18 detections
make agentic-run DETECTIONS="D03 D04"       # cheaper demo subset
```

Sessions appear at `https://<workspace-host>/omnigent`, and LLM calls are traced and costed through the workspace. The agent bundle is in `omnigent/triage_lab/`. Cost guardrails: the director has a $15 cap (asking for approval at $5 and $10) and each specialist is capped at 60 tool calls.

Reproducibility in agentic mode means every recorded experiment re-executes with identical results. The LLM choices themselves are not replayable; the deterministic `POST /runs` pipeline remains the reproducible reference.

## 11) Running the MVP
1. `POST /runs?seed=42&budget=10`
2. `GET /runs/{run_id}/decisions`
3. `GET /detections/D03/timeline` (latest run; pass `run_id=` for another)
4. `POST /approvals/{decision_id}?approved=true&reviewer=alice` for each pending DECOMMISSION

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
- `GET /runs/{run_id}/decisions`
- `GET /detections/{id}/timeline`
- `GET /evaluation`
- `GET /metrics`
- `POST /approvals/{decision_id}`
- `GET /research-record/{detection_id}`

## 15) Demo Walkthrough
For D03, the efficacy test looks strong and the provisional decision is KEEP, so the planner picks a robustness test and plans a redundancy check after it. The red team's timing randomisation breaks the rule at strength 0.5. Uncertainty rises and the provisional decision becomes INVESTIGATE. The planner drops the redundancy check, schedules an evidence quality review instead, and emits an `ADAPTATION_EVENT`. D18 (screenshot tool, defeated by tool renaming) goes through the same loop with no special-casing.

## 16) Known Limitations
- The sealed labels are the ground truth of the simulated world, which was designed to match them. Accuracy therefore shows that the pipeline recovers the simulator's truth, not that it judges real detections well.
- Literature agent is a static stub; justification quality and the manual baseline are still placeholders
- Runs, approvals and the research record are in-memory
- Lightweight local evidence adapter (no full RAG/graph pipeline yet)
- Agentic mode needs the lab and `omni host` on the same machine (MCP endpoints are localhost-only)
- UI is intentionally minimal for hackathon reliability

## 17) Path to Scale
- Swap storage/event backend to PostgreSQL/Elasticsearch
- Replace heuristic literature/planner reasoning with provider-backed LLM adapters
- Expand calibration/quality scoring and governance policy enforcement depth
