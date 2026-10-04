"""Build report.md from research_record.jsonl (observed data only)."""
import os, subprocess, sys
from omnigent_client import tool

ROOT = os.environ.get("TRIAGE_LAB_ROOT", os.path.expanduser("~/hack-nation/triage-lab"))


@tool
def build_report() -> str:
    """
    Generate report.md (ranked verdict table, baseline comparison, citations, uncertainty) from the record.

    :returns: Status string with the path of the generated report, or an error.
    """
    p = subprocess.run([sys.executable, "build_report.py"], capture_output=True, text=True, cwd=ROOT)
    return p.stdout.strip() if not p.returncode else f"error: {p.stderr[-800:]}"
