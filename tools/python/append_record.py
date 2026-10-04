"""Append one structured record to the shared research_record.jsonl (every handoff is logged here)."""
import fcntl, json, os, time
from omnigent_client import tool

ROOT = os.environ.get("TRIAGE_LAB_ROOT", os.path.expanduser("~/hack-nation/triage-lab"))


@tool
def append_record(stage: str, agent: str, payload_json: str) -> str:
    """
    Append a record to research_record.jsonl so the decision can be reconstructed later.

    :param stage: One of question, evidence, hypothesis, experiment_plan, result, analysis, safety,
        reopen, final_verdict.
    :param agent: Name of the agent writing the record, e.g. ``"evidence"``.
    :param payload_json: The structured JSON handoff (as a JSON string) to store.
    :returns: ``"ok seq=<n>"`` or an error string.
    """
    try:
        payload = json.loads(payload_json)
    except json.JSONDecodeError as e:
        return f"error: payload_json is not valid JSON: {e}"
    path = os.path.join(ROOT, "research_record.jsonl")
    with open(path, "a+") as f:
        fcntl.flock(f, fcntl.LOCK_EX)
        f.seek(0)
        seq = sum(1 for _ in f)
        f.write(json.dumps({"seq": seq, "ts": time.time(), "stage": stage, "agent": agent,
                            "payload": payload}) + "\n")
    return f"ok seq={seq}"
