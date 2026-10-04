"""Run real, seeded replay experiments (parallel) and log the results to the shared record."""
import fcntl, json, os, subprocess, sys, time
from omnigent_client import tool

ROOT = os.environ.get("TRIAGE_LAB_ROOT", os.path.expanduser("~/hack-nation/triage-lab"))


@tool
def run_experiments(specs_json: str) -> str:
    """
    Replay seeded SYNTHETIC attack campaigns against the detection rules for each experiment spec, over 20 fixed
    seeds, in parallel. A control experiment (no-op identical, disable-all detects nothing, determinism) is added.

    :param specs_json: JSON list of specs, each like
        ``{"id": "E-D031-A", "type": "remove", "rule_id": "D031"}`` or
        ``{"id": "E-D031-B", "type": "tighten", "rule_id": "D031", "thresholds": [60, 70, 80, 90]}``.
        ``type`` is ``remove`` (disable the rule, measure coverage loss) or ``tighten`` (raise the score
        threshold, measure TP retention vs alert reduction). Results aggregate the seeds as mean/min/max.
    :returns: JSON string with seeds, parallel wall seconds, the sequential sum of experiment seconds and per-experiment results.
    """
    try:
        json.loads(specs_json)
    except json.JSONDecodeError as e:
        return f"error: specs_json is not valid JSON: {e}"
    p = subprocess.run([sys.executable, "run_experiments.py"], input=specs_json, text=True,
                       capture_output=True, cwd=ROOT, timeout=300)
    if p.returncode:
        return f"error: {p.stderr[-800:]}"
    with open(os.path.join(ROOT, "research_record.jsonl"), "a+") as f:
        fcntl.flock(f, fcntl.LOCK_EX)
        f.seek(0)
        seq = sum(1 for _ in f)
        f.write(json.dumps({"seq": seq, "ts": time.time(), "stage": "result", "agent": "experiment_runner",
                            "payload": json.loads(p.stdout)}) + "\n")
    return p.stdout
