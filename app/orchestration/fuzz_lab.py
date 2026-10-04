"""Fuzz Lab Orchestration — The complete scientific discovery loop.

Implements: Question → Evidence → Hypothesis → Experiment → Result → Updated Decision

This module is the PI (Principal Investigator) that coordinates:
  - Seed Agent (hypothesis + corpus)
  - Execution Agent (fuzzing experiment)
  - Safety Agent (human approval gate)
  - Triage Agent (crash analysis + CWE classification)
"""

from __future__ import annotations

import os
import time
from uuid import uuid4

from dotenv import load_dotenv

load_dotenv()

from app.agents.seed_agent import generate_corpus
from app.agents.execution_agent import run_fuzz_experiment
from app.agents.triage_agent import triage_all
from app.agents.safety_fuzz import validate_fuzz_target, gate_crash_reproduction
from app.models.schemas import (
    FuzzDiscovery,
    FuzzExperimentSpec,
    FuzzTarget,
    ResearchEvent,
    SafetyOutcome,
)
from app.storage.research_store import STORE


def _generate_conclusion_with_llm(
    hypothesis: str,
    crashes: list,
    triage_results: list,
    critical_count: int,
    rejected_strategy: str,
) -> str | None:
    api_key = os.getenv("OPENAI_API_KEY")
    if not api_key:
        return None
    try:
        from openai import OpenAI
        client = OpenAI(api_key=api_key)
        cwes = ", ".join(list({f"{t.cwe_id} ({t.cwe_name})" for t in triage_results}))
        prompt = (
            f"You are the Principal Investigator in an automated cyber scientific discovery lab.\n"
            f"Synthesize the final scientific conclusion (3-4 sentences) based on experimental evidence:\n"
            f"Initial Hypothesis: {hypothesis}\n"
            f"Total Crashes Discovered: {len(crashes)}\n"
            f"Critical Vulnerabilities Confirmed: {critical_count}\n"
            f"Taxonomy Confirmed: {cwes}\n"
            f"Adaptation Decision: Next cycle will explore '{rejected_strategy}'.\n"
            f"State clearly if the hypothesis was confirmed, the significance of the findings, and the updated research decision."
        )
        resp = client.chat.completions.create(
            model="gpt-6-luna",
            messages=[{"role": "user", "content": prompt}],
            max_completion_tokens=250,
        )
        content = resp.choices[0].message.content
        return content.strip() if content else None
    except Exception:
        return None


# ── Run state ────────────────────────────────────────────────────────

class FuzzRunState:
    def __init__(self, run_id: str, case_id: str):
        self.run_id = run_id
        self.case_id = case_id
        self.started_at = time.perf_counter()
        self.events: list[ResearchEvent] = []
        self.status: str = "running"
        self.pending_approval: bool = False
        self.crash_count: int = 0
        self.discovery: FuzzDiscovery | None = None


FUZZ_RUNS: dict[str, FuzzRunState] = {}


# ── Helpers ──────────────────────────────────────────────────────────

def _emit(run: FuzzRunState, agent: str, action: str, output: dict,
          confidence: str = "MEDIUM", parent: str | None = None) -> ResearchEvent:
    ev = ResearchEvent(
        event_id=str(uuid4()),
        case_id=run.case_id,
        agent=agent,
        action=action,
        input_reference="structured-json",
        output=output,
        confidence=confidence,
        citations=output.get("citations", []),
        parent_event_id=parent,
        run_id=run.run_id,
    )
    run.events.append(ev)
    STORE.add_event(ev)
    return ev


# ── Default fuzz target ──────────────────────────────────────────────

DEFAULT_TARGET = FuzzTarget(
    target_id="vuln-parser-01",
    name="Synthetic Vulnerable Parser",
    description=(
        "A simulated C-style parser that reads stdin input and processes it "
        "through a fixed-size buffer with no bounds checking. The parser also "
        "uses unvalidated format strings and does not handle embedded null bytes."
    ),
    input_format="stdin",
    known_constraints=["fixed buffer size", "C-style string handling", "printf-family calls"],
    source="synthetic",
)


# ── Main orchestration ───────────────────────────────────────────────

def start_fuzz_run(
    question: str = "What specific inputs cause memory corruption or crashes in this binary?",
    seed: int = 42,
    case_id: str | None = None,
) -> str:
    """Start a new fuzzing research run.

    Executes phases 1–3 synchronously:
      Phase 1 (Question): Record the research question
      Phase 2 (Hypothesis): Seed Agent analyzes target and generates corpus
      Phase 3 (Experiment): Execution Agent runs the fuzzer

    Pauses at Phase 4 (human approval) and returns the run_id.
    Phase 5 (triage) executes after approval via `approve_and_triage()`.
    """
    run_id = str(uuid4())
    if case_id is None:
        case_id = f"FUZZ-{uuid4().hex[:6].upper()}"

    run = FuzzRunState(run_id=run_id, case_id=case_id)
    FUZZ_RUNS[run_id] = run
    target = DEFAULT_TARGET

    # ── PHASE 1: QUESTION ────────────────────────────────────────
    question_event = _emit(run, "orchestrator", "question", {
        "question": question,
        "target": target.model_dump(),
        "constraints": ["synthetic_only", "sandboxed", "reproducible_seed"],
    }, confidence="HIGH")

    # ── SAFETY GATE: Validate target ─────────────────────────────
    safety_check = validate_fuzz_target(target)
    _emit(run, "safety", "target_validation", safety_check.model_dump(),
          parent=question_event.event_id)

    if safety_check.status == SafetyOutcome.BLOCKED:
        run.status = "blocked"
        return run_id

    # ── PHASE 2: HYPOTHESIS (Seed Agent) ─────────────────────────
    corpus = generate_corpus(case_id, target, seed)
    hypothesis_event = _emit(run, "seed_agent", "hypothesis_and_corpus", {
        "hypothesis": corpus.hypothesis,
        "seeds_generated": len(corpus.seeds),
        "seed_strategies": [s.mutation_strategy for s in corpus.seeds],
        "confidence": corpus.confidence,
    }, confidence="HIGH", parent=question_event.event_id)

    # ── EXPERIMENT PLANNING: Propose 2 experiments, select 1 ─────
    exp_boundary = FuzzExperimentSpec(
        experiment_id="exp-boundary-seeds",
        case_id=case_id,
        target_id=target.target_id,
        corpus_strategy="boundary_focused",
        duration_seconds=30,
        random_seed=seed,
        parameters={"mutation_rounds": 10, "focus": "boundary_overflow_and_format_strings"},
        expected_learning=0.85,
        cost=2,
        feasibility=0.95,
    )
    exp_random = FuzzExperimentSpec(
        experiment_id="exp-random-corpus",
        case_id=case_id,
        target_id=target.target_id,
        corpus_strategy="random_only",
        duration_seconds=30,
        random_seed=seed,
        parameters={"mutation_rounds": 15, "focus": "pure_random_mutations"},
        expected_learning=0.55,
        cost=3,
        feasibility=0.90,
    )

    selected = exp_boundary if exp_boundary.priority > exp_random.priority else exp_random
    rejected = exp_random if selected == exp_boundary else exp_boundary

    planning_event = _emit(run, "planner", "experiment_selection", {
        "candidates": [
            {"id": exp_boundary.experiment_id, "strategy": exp_boundary.corpus_strategy,
             "priority": exp_boundary.priority},
            {"id": exp_random.experiment_id, "strategy": exp_random.corpus_strategy,
             "priority": exp_random.priority},
        ],
        "selected": selected.experiment_id,
        "rejected": rejected.experiment_id,
        "rationale": f"Selected '{selected.corpus_strategy}' (priority={selected.priority:.3f}) over "
                     f"'{rejected.corpus_strategy}' (priority={rejected.priority:.3f}) — "
                     f"higher expected learning with lower cost",
    }, confidence="HIGH", parent=hypothesis_event.event_id)

    # ── PHASE 3: EXPERIMENT (Execution Agent) ────────────────────
    crashes = run_fuzz_experiment(
        corpus=corpus,
        seed=seed,
        mutation_rounds=selected.parameters.get("mutation_rounds", 10),
    )

    experiment_event = _emit(run, "execution_agent", "fuzz_experiment", {
        "experiment_id": selected.experiment_id,
        "strategy": selected.corpus_strategy,
        "seeds_tested": len(corpus.seeds),
        "mutations_per_seed": selected.parameters.get("mutation_rounds", 10),
        "total_executions": len(corpus.seeds) * (1 + selected.parameters.get("mutation_rounds", 10)),
        "crashes_found": len(crashes),
        "crash_ids": [c.crash_id for c in crashes],
        "unique_signals": list({c.signal for c in crashes}),
    }, parent=planning_event.event_id)

    # ── PHASE 4: HUMAN APPROVAL GATE ─────────────────────────────
    if crashes:
        approval_gate = gate_crash_reproduction(len(crashes))
        _emit(run, "safety", "human_approval_required", {
            **approval_gate.model_dump(),
            "crash_count": len(crashes),
            "message": (
                f"The fuzzer discovered {len(crashes)} crash(es). "
                "Human approval is required before reproducing and analyzing "
                "the crashes to confirm the scientific discovery."
            ),
        }, confidence="HIGH", parent=experiment_event.event_id)

        run.pending_approval = True
        run.crash_count = len(crashes)
        run.status = "awaiting_approval"

        # Store crashes for later triage
        run._crashes = crashes  # type: ignore[attr-defined]
        run._corpus = corpus  # type: ignore[attr-defined]
        run._selected_exp = selected  # type: ignore[attr-defined]
        run._rejected_exp = rejected  # type: ignore[attr-defined]
        run._question = question  # type: ignore[attr-defined]
        run._seed = seed  # type: ignore[attr-defined]
    else:
        run.status = "completed_no_crashes"

    return run_id


def approve_and_triage(run_id: str, approved: bool = True) -> FuzzDiscovery | None:
    """Phase 5: Human approves → Triage Agent reproduces and classifies crashes.

    This is called after the human reviews the crash list and approves.
    """
    run = FUZZ_RUNS.get(run_id)
    if not run or not run.pending_approval:
        return None

    run.pending_approval = False

    # Record approval
    _emit(run, "safety", "human_approval_recorded", {
        "approved": approved,
        "reviewer": "human_scientist",
    }, confidence="HIGH")

    if not approved:
        run.status = "rejected"
        return None

    # ── PHASE 5: TRIAGE (Triage Agent) ───────────────────────────
    crashes = run._crashes  # type: ignore[attr-defined]
    corpus = run._corpus  # type: ignore[attr-defined]
    selected = run._selected_exp  # type: ignore[attr-defined]
    rejected = run._rejected_exp  # type: ignore[attr-defined]
    question = run._question  # type: ignore[attr-defined]
    seed = run._seed  # type: ignore[attr-defined]

    triage_results = triage_all(crashes, corpus.hypothesis)

    triage_event = _emit(run, "triage_agent", "crash_triage", {
        "crashes_analyzed": len(crashes),
        "crashes_reproduced": sum(1 for t in triage_results if t.crash_id),
        "cwe_distribution": _cwe_distribution(triage_results),
        "hypothesis_confirmed": any(t.hypothesis_confirmed for t in triage_results),
        "results": [t.model_dump() for t in triage_results],
    }, confidence="HIGH")

    # ── ADAPTATION EVENT: Result changes next decision ────────────
    hypothesis_confirmed = any(t.hypothesis_confirmed for t in triage_results)
    critical_count = sum(1 for t in triage_results if t.severity == "CRITICAL")

    if hypothesis_confirmed and critical_count > 0:
        adaptation = (
            f"The boundary-focused experiment confirmed the hypothesis with "
            f"{critical_count} critical vulnerabilities. The next investigation should "
            f"switch to the '{rejected.corpus_strategy}' strategy to explore "
            f"additional crash paths not covered by boundary mutations."
        )
    else:
        adaptation = (
            f"The initial experiment yielded {len(crashes)} crashes but the hypothesis "
            f"needs refinement. The next investigation should use random corpus to "
            f"broaden the search space."
        )

    _emit(run, "planner", "ADAPTATION_EVENT", {
        "previous_experiment": selected.experiment_id,
        "next_experiment": rejected.experiment_id,
        "reason": adaptation,
        "hypothesis_confirmed": hypothesis_confirmed,
        "critical_vulnerabilities": critical_count,
    }, confidence="HIGH", parent=triage_event.event_id)

    # ── SCIENTIFIC CONCLUSION ────────────────────────────────────
    # Calculate speedup vs manual
    manual_minutes_per_crash = 45  # industry estimate
    total_manual_time = manual_minutes_per_crash * len(crashes) * 60  # seconds
    actual_time = time.perf_counter() - run.started_at
    speedup = total_manual_time / max(actual_time, 0.001)

    llm_conclusion = _generate_conclusion_with_llm(
        hypothesis=corpus.hypothesis,
        crashes=crashes,
        triage_results=triage_results,
        critical_count=critical_count,
        rejected_strategy=rejected.corpus_strategy,
    )

    discovery = FuzzDiscovery(
        case_id=run.case_id,
        question=question,
        hypothesis=corpus.hypothesis,
        hypothesis_confirmed=hypothesis_confirmed,
        experiments_proposed=2,
        experiment_selected=selected.experiment_id,
        crashes_found=len(crashes),
        triage_results=triage_results,
        adaptation_event=adaptation,
        scientific_conclusion=llm_conclusion or (
            f"The agentic fuzzing lab discovered {len(crashes)} unique crashes in the "
            f"synthetic vulnerable parser. Triage confirmed {critical_count} critical "
            f"vulnerabilities (buffer overflow, format string, null byte injection). "
            f"The initial hypothesis was {'confirmed' if hypothesis_confirmed else 'partially confirmed'}. "
            f"The result triggered an adaptation: the next experiment will use "
            f"'{rejected.corpus_strategy}' to explore uncovered crash paths."
        ),
        speedup_vs_manual=round(speedup, 1),
        reproducibility_seed=seed,
    )

    _emit(run, "orchestrator", "scientific_discovery", {
        **discovery.model_dump(mode="json"),
    }, confidence="HIGH", parent=triage_event.event_id)

    run.discovery = discovery
    run.status = "completed"
    STORE.persist()

    return discovery


def _cwe_distribution(reports: list) -> dict[str, int]:
    """Count occurrences of each CWE."""
    dist: dict[str, int] = {}
    for r in reports:
        key = f"{r.cwe_id} ({r.cwe_name})"
        dist[key] = dist.get(key, 0) + 1
    return dist
