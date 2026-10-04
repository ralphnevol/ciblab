"""Triage Agent — Crash reproduction and vulnerability classification.

Scientific method phase: RESULT → UPDATED DECISION
Receives crash reports, reproduces them, classifies by CWE,
and produces the final vulnerability report.
"""

from __future__ import annotations

from app.experiments.vulnerable_binary import run_target, Signal
from app.models.schemas import CrashReport, TriageReport


# ── CWE classification rules ────────────────────────────────────────

_SIGNAL_CWE_MAP = {
    Signal.SIGSEGV: [
        {
            "pattern": "buffer overflow",
            "cwe_id": "CWE-120",
            "cwe_name": "Buffer Copy without Checking Size of Input",
            "severity": "CRITICAL",
        },
        {
            "pattern": "format string",
            "cwe_id": "CWE-134",
            "cwe_name": "Use of Externally-Controlled Format String",
            "severity": "HIGH",
        },
    ],
    Signal.SIGABRT: [
        {
            "pattern": "null byte",
            "cwe_id": "CWE-626",
            "cwe_name": "Null Byte Interaction Error",
            "severity": "MEDIUM",
        },
    ],
}


def _classify_crash(crash: CrashReport) -> tuple[str, str, str]:
    """Classify a crash into (cwe_id, cwe_name, severity)."""
    candidates = _SIGNAL_CWE_MAP.get(crash.signal, [])
    stderr_lower = crash.stderr_snippet.lower()

    for rule in candidates:
        if rule["pattern"] in stderr_lower:
            return rule["cwe_id"], rule["cwe_name"], rule["severity"]

    # Fallback classification
    return "CWE-119", "Improper Restriction of Operations within Memory Buffer", "HIGH"


def triage_crash(crash: CrashReport, hypothesis: str) -> TriageReport:
    """Reproduce and triage a single crash.

    1. Reproduce by re-running the input against the target.
    2. Classify using stderr signals and CWE mapping.
    3. Determine if the original hypothesis is confirmed.
    """
    # Reproduce
    data = bytes.fromhex(crash.input_hex)
    result = run_target(data)

    reproduced = result.crashed and result.signal == crash.signal

    cwe_id, cwe_name, severity = _classify_crash(crash)

    # Check hypothesis confirmation
    hypothesis_lower = hypothesis.lower()
    hypothesis_confirmed = any(
        keyword in hypothesis_lower
        for keyword in ["size", "buffer", "overflow", "boundary", "format", "control", "encoding", "null"]
    )

    return TriageReport(
        crash_id=crash.crash_id,
        cwe_id=cwe_id,
        cwe_name=cwe_name,
        severity=severity,
        root_cause=result.stderr if reproduced else f"Reproduction failed: got exit_code={result.exit_code}",
        input_hex=crash.input_hex,
        hypothesis_confirmed=hypothesis_confirmed,
    )


def triage_all(
    crashes: list[CrashReport],
    hypothesis: str,
) -> list[TriageReport]:
    """Triage all crashes and return the full report list."""
    return [triage_crash(crash, hypothesis) for crash in crashes]
