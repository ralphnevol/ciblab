from __future__ import annotations

from app.models.schemas import LiteratureEvidence, Confidence


def run_literature_agent(detection_id: str) -> LiteratureEvidence:
    return LiteratureEvidence(
        detection_id=detection_id,
        sources=["https://attack.mitre.org/"],
        evidence_summary=f"Public ATT&CK-aligned rationale for {detection_id}",
        supporting_claims=["Behavior-based detections can be effective with tuning."],
        contradicting_claims=["High false-positive risk in noisy environments."],
        confidence=Confidence.MEDIUM,
        evidence_quality=0.65,
    )


def review_evidence_quality(literature: LiteratureEvidence, robustness_degradation: float | None) -> dict:
    """Cross-check literature claims against the experiments run so far."""
    notes = []
    if robustness_degradation is None:
        notes.append("Robustness untested; evasion-related claims remain unverified.")
    elif robustness_degradation > 0.15:
        notes.append("Experimental evasion result supports the contradicting claims.")
    else:
        notes.append("Experimental robustness result is consistent with the supporting claims.")
    return {
        "detection_id": literature.detection_id,
        "evidence_quality_before": literature.evidence_quality,
        "literature_uncertainty_reduction": 0.5,
        "notes": notes,
        "sources": literature.sources,
    }
