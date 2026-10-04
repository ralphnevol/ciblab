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
