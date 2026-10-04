"""Record final verdicts. Guarded by an Omnigent ASK policy: a human must approve before this runs."""
import fcntl, json, os, time
from omnigent_client import tool

ROOT = os.environ.get("TRIAGE_LAB_ROOT", os.path.expanduser("~/hack-nation/triage-lab"))


@tool
def finalize_verdict(verdicts_json: str) -> str:
    """
    Make verdicts FINAL (consequential). Requires human approval via Omnigent policy.

    :param verdicts_json: JSON list of {rule_id, verdict (keep|decommission|retune|investigate),
        params (e.g. {"threshold": 80}), basis (experiment ids / analysis ids), safety_ok (bool)}.
    :returns: ``"ok n=<count>"`` or an error string.
    """
    try:
        items = json.loads(verdicts_json)
    except json.JSONDecodeError as e:
        return f"error: invalid JSON: {e}"
    with open(os.path.join(ROOT, "research_record.jsonl"), "a+") as f:
        fcntl.flock(f, fcntl.LOCK_EX)
        f.seek(0)
        seq = sum(1 for _ in f)
        f.write(json.dumps({"seq": seq, "ts": time.time(), "stage": "final_verdict", "agent": "orchestrator",
                            "payload": {"verdicts": items, "human_approved": True}}) + "\n")
    return f"ok n={len(items)}"
