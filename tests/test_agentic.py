import asyncio
import json

import pytest
from fastapi.testclient import TestClient

from app.evaluation.evaluator import evaluate_latest
from app.main import app
from app.mcp_tools import SERVERS
from app.orchestration import agentic
from app.orchestration.agentic import ToolError

SOURCES = ["https://attack.mitre.org/techniques/T1078/"]
RATIONALE = "Efficacy and robustness evidence recorded in the research record support this outcome."


def _with_literature(run_id, det):
    agentic.record_literature(run_id, det, SOURCES, "summary", ["supports"], ["evasion risk"], 0.65, "medium")


def _with_efficacy(run_id, det, follow_up=None):
    _with_literature(run_id, det)
    agentic.record_plan(run_id, det, "efficacy_test", "baseline first", [{"test": "efficacy_test", "expected_information_gain": 1.0}], follow_up)
    agentic.run_test(run_id, det, "efficacy_test")


def test_d03_agentic_loop_records_adaptation_and_spends_budget():
    run = agentic.create_run(seed=42)
    rid = run.run_id
    _with_efficacy(rid, "D03", follow_up="robustness_test")

    plan = agentic.record_plan(rid, "D03", "robustness_test", "looks strong; test evasion", [{"test": "robustness_test", "expected_information_gain": 1.4}], "redundancy_check")
    assert not plan["adaptation_event"]
    first = agentic.run_evasion_variant(rid, "D03", 0.25)
    second = agentic.run_evasion_variant(rid, "D03", 0.5)
    assert second["degradation"] > first["degradation"]
    robustness = agentic.finish_robustness(rid, "D03", "timing randomisation breaks the rule")["robustness"]
    assert robustness["breaking_parameters"]["strength"] is not None

    plan = agentic.record_plan(rid, "D03", "evidence_quality_review", "evasion found", [{"test": "evidence_quality_review", "expected_information_gain": 0.7}], None)
    assert plan["adaptation_event"]
    agentic.record_evidence_review(rid, "D03", ["literature predicted evasion"], 0.7)
    agentic.record_plan(rid, "D03", None, "nothing affordable changes the decision", [], None)
    agentic.submit_decision(rid, "D03", "INVESTIGATE", RATIONALE, "medium", "alert_volume_test")
    assert agentic.record_safety_review(rid, "D03", "APPROVED", ["synthetic only"])["status"] == "APPROVED"

    state = agentic.detection_state(rid, "D03")
    assert state["remaining_budget"] == 10 - 1 - 3 - 4 - 1
    assert state["rule_based_provisional_decision"] == "INVESTIGATE"
    actions = [e["action"] for e in agentic.research_record(rid, "D03")]
    assert actions.count("ADAPTATION_EVENT") == 1
    assert "provisional_decision" in actions

    result = evaluate_latest(rid)
    assert result.reproducibility_result
    assert result.adaptation_count == 1
    assert len(result.undecided) == 17


def test_lab_refuses_out_of_order_and_over_budget_calls():
    rid = agentic.create_run(seed=1, budget=5).run_id
    with pytest.raises(ToolError, match="literature"):
        agentic.record_plan(rid, "D01", "efficacy_test", "x", [], None)
    _with_literature(rid, "D01")
    with pytest.raises(ToolError, match="efficacy_test must run"):
        agentic.record_plan(rid, "D01", "robustness_test", "x", [], None)
    with pytest.raises(ToolError, match="not planned"):
        agentic.run_test(rid, "D01", "efficacy_test")
    with pytest.raises(ToolError, match="efficacy_test must run before a decision"):
        agentic.submit_decision(rid, "D01", "KEEP", RATIONALE, "high", None)
    agentic.record_plan(rid, "D01", "efficacy_test", "x", [], None)
    agentic.run_test(rid, "D01", "efficacy_test")
    with pytest.raises(ToolError, match="remaining budget is 1"):
        agentic.record_plan(rid, "D01", "robustness_test", "x", [], None)
    with pytest.raises(ToolError, match="must name"):
        agentic.submit_decision(rid, "D01", "INVESTIGATE", RATIONALE, "low", None)
    agentic.record_plan(rid, "D01", "evidence_quality_review", "x", [], None)
    with pytest.raises(ToolError, match="planned but not"):
        agentic.submit_decision(rid, "D01", "KEEP", RATIONALE, "high", None)
    with pytest.raises(ToolError, match="within 0.2"):
        agentic.record_evidence_review(rid, "D01", ["n"], 0.95)


def test_decommission_always_waits_for_a_human():
    rid = agentic.create_run(seed=42).run_id
    _with_efficacy(rid, "D04")
    agentic.record_plan(rid, "D04", None, "stop", [], None)
    out = agentic.submit_decision(rid, "D04", "DECOMMISSION", RATIONALE, "high", None)
    assert out["approval_status"] == "PENDING"
    assert agentic.record_safety_review(rid, "D04", "APPROVED", ["looks fine"])["status"] == "REQUIRES_HUMAN_APPROVAL"


def test_each_role_only_gets_its_tools():
    def names(role):
        return {t.name for t in asyncio.run(SERVERS[role].list_tools())}

    shared = {"lab_brief", "detection_state", "research_record"}
    assert names("planner") == shared | {"record_plan"}
    assert names("red_team") == shared | {"run_evasion_variant", "finish_robustness"}
    assert names("safety") == shared | {"record_safety_review"}
    assert "submit_decision" not in set().union(*(names(r) for r in SERVERS if r != "portfolio"))


def _rpc(client, path, method, params, id_):
    resp = client.post(
        path,
        json={"jsonrpc": "2.0", "id": id_, "method": method, "params": params},
        headers={"Accept": "application/json, text/event-stream", "Content-Type": "application/json"},
    )
    assert resp.status_code == 200, resp.text
    if resp.headers["content-type"].startswith("text/event-stream"):
        data = next(line[5:] for line in resp.text.splitlines() if line.startswith("data:"))
        return json.loads(data)
    return resp.json()


def test_mcp_endpoint_is_mounted_and_serves_role_tools():
    # MCP's DNS-rebinding protection only accepts localhost Host headers.
    with TestClient(app, base_url="http://127.0.0.1:8000") as client:
        init = _rpc(
            client,
            "/lab/planner/mcp",
            "initialize",
            {"protocolVersion": "2025-03-26", "capabilities": {}, "clientInfo": {"name": "test", "version": "0"}},
            1,
        )
        assert init["result"]["serverInfo"]["name"] == "triage-lab-planner"
        tools = _rpc(client, "/lab/planner/mcp", "tools/list", {}, 2)
        assert "record_plan" in {t["name"] for t in tools["result"]["tools"]}
