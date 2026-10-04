"""MCP servers exposing the lab to Omnigent agents, one server per agent role.

Each role only sees the tools it needs, and the role recorded in the research record comes
from the endpoint the call arrived on, not from anything the model claims. Mounted by
app.main at /lab/<role>/mcp.
"""

from __future__ import annotations

from typing import Callable

from mcp.server.mcpserver import MCPServer

from app.orchestration import agentic

ROLE_TOOLS: dict[str, tuple[Callable, ...]] = {
    "director": (agentic.run_test,),
    "literature": (agentic.record_literature, agentic.record_evidence_review),
    "planner": (agentic.record_plan,),
    "red_team": (agentic.run_evasion_variant, agentic.finish_robustness),
    "analyst": (agentic.record_analysis,),
    "portfolio": (agentic.submit_decision,),
    "safety": (agentic.record_safety_review,),
}
SHARED_TOOLS = (agentic.lab_brief, agentic.detection_state, agentic.research_record)

DESCRIPTIONS = {
    "lab_brief": "Run overview: budget per detection, test costs, decision criteria, and the 18 detections with their status.",
    "detection_state": "Current evidence for one detection: budget, tests run, pending test, literature, scorecard, "
    "uncertainty breakdown, robustness, the rule-based provisional decision, and any submitted decision.",
    "research_record": "Full audit trail of events recorded for one detection in this run.",
    "run_test": "Execute the pending efficacy_test, redundancy_check or alert_volume_test on seeded synthetic data. "
    "The planner must have selected it first. Charges the test cost and returns metrics, scorecard and uncertainty.",
    "record_literature": "Record public literature evidence for a detection (costs 1). Sources must be public http(s) URLs "
    "such as MITRE ATT&CK pages. evidence_quality is 0-1; confidence is LOW, MEDIUM or HIGH. Once per detection.",
    "record_evidence_review": "Complete a planned evidence_quality_review (costs 1): cross-check literature claims against "
    "the experiments so far and revise evidence_quality by at most 0.2.",
    "record_plan": "Record the next experiment choice. options lists every candidate as {test, expected_information_gain}; "
    "the lab ranks them by gain/cost. selected_test must be affordable and unrun (null to stop). planned_follow_up is the "
    "test you expect to run after this one if nothing surprising happens; deviating from it later is logged as an "
    "ADAPTATION_EVENT. efficacy_test must come first.",
    "run_evasion_variant": "During a planned robustness_test, run one synthetic evasion variant at strength (0, 1]. "
    "The first variant charges the test cost (4); up to 4 variants. Returns recall degradation and whether the rule broke.",
    "finish_robustness": "Close the robustness test with your explanation. Needs at least one variant at strength <= 0.5, "
    "which is where degradation is scored.",
    "record_analysis": "Record your interpretation of the current scorecard and uncertainty, with specific concerns.",
    "submit_decision": "Submit the final KEEP / DECOMMISSION / INVESTIGATE decision with an evidence-based rationale and "
    "confidence (LOW/MEDIUM/HIGH). INVESTIGATE must name recommended_next_test. DECOMMISSION is held for human approval.",
    "record_safety_review": "Record the safety gate for a submitted decision: status APPROVED, FLAGGED, "
    "REQUIRES_HUMAN_APPROVAL or BLOCKED, with reasons. DECOMMISSION always requires human approval regardless.",
}


def build_server(role: str) -> MCPServer:
    server = MCPServer(f"triage-lab-{role}")
    for fn in (*SHARED_TOOLS, *ROLE_TOOLS[role]):
        server.add_tool(fn, name=fn.__name__, description=DESCRIPTIONS[fn.__name__])
    return server


SERVERS = {role: build_server(role) for role in ROLE_TOOLS}
