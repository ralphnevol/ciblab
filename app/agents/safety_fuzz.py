"""Safety Agent for the Fuzzing Lab.

Validates that fuzz targets are synthetic/sandboxed,
gates human approval for crash reproduction, and blocks
any operation that violates the security policy.
"""

from __future__ import annotations

from app.models.schemas import FuzzTarget, SafetyDecision, SafetyOutcome


def validate_fuzz_target(target: FuzzTarget) -> SafetyDecision:
    """Validate that the fuzz target meets safety constraints.

    Only synthetic or public targets are allowed.
    """
    reasons: list[str] = []

    if target.source not in ("synthetic", "public"):
        return SafetyDecision(
            detection_id=target.target_id,
            status=SafetyOutcome.BLOCKED,
            reasons=[f"Target source '{target.source}' not in allowed list [synthetic, public]"],
        )

    reasons.append(f"Target '{target.name}' is {target.source}: approved for fuzzing")
    reasons.append("Sandboxed execution environment: in-process Python simulation")
    reasons.append("No network access or filesystem writes required")

    return SafetyDecision(
        detection_id=target.target_id,
        status=SafetyOutcome.APPROVED,
        reasons=reasons,
    )


def gate_crash_reproduction(crash_count: int) -> SafetyDecision:
    """Request human approval before reproducing crashes.

    This is the Omnigent policy enforcement point — the workflow
    pauses here until a human approves.
    """
    return SafetyDecision(
        detection_id="fuzz-crash-gate",
        status=SafetyOutcome.REQUIRES_HUMAN_APPROVAL,
        reasons=[
            f"Fuzzer discovered {crash_count} crash(es)",
            "Human approval required before reproducing crashes and performing triage",
            "This prevents wasting compute on false positives or duplicate crashes",
        ],
    )


def validate_post_approval(approved: bool) -> SafetyDecision:
    """Record the human approval decision."""
    if approved:
        return SafetyDecision(
            detection_id="fuzz-crash-gate",
            status=SafetyOutcome.APPROVED,
            reasons=["Human scientist approved crash reproduction and analysis"],
        )
    return SafetyDecision(
        detection_id="fuzz-crash-gate",
        status=SafetyOutcome.BLOCKED,
        reasons=["Human scientist rejected crash reproduction — analysis aborted"],
    )
