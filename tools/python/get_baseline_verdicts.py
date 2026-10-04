"""Return the rule-only (baseline) verdicts from the deterministic baseline/ version."""
import json, os, subprocess, sys
from omnigent_client import tool

ROOT = os.environ.get("TRIAGE_LAB_ROOT", os.path.expanduser("~/hack-nation/triage-lab"))


@tool
def get_baseline_verdicts() -> str:
    """
    Score the SYNTHETIC portfolio with the rule-only baseline (precision, analyst hours, verdict).

    :returns: JSON list of {detection_id, name, mitre_technique, fires, tp, precision, cost_hours,
        last_tuned_days, healthy, verdict}.
    """
    code = ("import json,sys;sys.path.insert(0,'baseline');from lab.tools import score_detections as s;"
            "print(json.dumps([{k:r[k] for k in ('detection_id','name','mitre_technique','fires','tp',"
            "'precision','cost_hours','last_tuned_days','healthy','verdict')} for r in s('data/portfolio.csv')]))")
    p = subprocess.run([sys.executable, "-c", code], capture_output=True, text=True, cwd=ROOT)
    return p.stdout if not p.returncode else f"error: {p.stderr[-600:]}"
