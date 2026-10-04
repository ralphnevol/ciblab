# Cyber Research Lab

## Mission

Build a minimal agentic cybersecurity research laboratory that demonstrates:

`Question -> Evidence -> Hypothesis -> Experiment -> Result -> Updated Decision`

## Mandatory platform

Omnigent is the orchestration boundary for the live multi-agent workflow when available. Local fallback execution must be explicit and must not claim native Omnigent execution.

## Architecture

FastAPI + Pydantic + Omnigent + SQLite/JSON + Python experiments. Keep one narrow vertical slice ahead of broad platform features.

## Agents and tools

Research, Hypothesis, Planner, Experiment Runner, Analysis, and Safety are specialist agents. CTI, MITRE, literature, and binary analysis are tools; they are not agents.

## Reasoning boundary

Agents may synthesize evidence, formulate hypotheses, interpret results, and plan. Deterministic Python calculates metrics, executes experiments, validates inputs, measures performance, and proves reproducibility.

## Safety

Use public or synthetic data in sandboxed computational experiments only. Never use real employee telemetry, production systems, credentials, secrets, destructive operations, autonomous exploitation, or arbitrary network attacks. Human approval is required for gated decisions.

## Engineering rules

- Inspect before modifying and reuse existing contracts where compatible.
- Preserve citations, uncertainty, provenance, and append-only research events.
- Do not invent Omnigent APIs; detect the installed runtime and keep fallback behavior testable.
- Freeze scenario, seed, generator version, and prompts for the demo.
- Measure observed acceleration; never fabricate a target speedup.

## Definition of done

The application runs end-to-end, at least three specialist agents exchange typed outputs, tools are used, the shared research record reconstructs decisions, two experiments are proposed and one selected, the result changes the next decision, safety is enforced, and reproducibility and baseline metrics are reported.
