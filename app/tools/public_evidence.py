from __future__ import annotations

from app.models.schemas import Evidence


def collect_public_evidence(case_id: str, question: str) -> list[Evidence]:
    return [
        Evidence(
            evidence_id=f"{case_id}-mitre",
            case_id=case_id,
            kind="cti",
            claim="Behavioral indicators should be evaluated against an explicit technique context.",
            source="MITRE ATT&CK",
            citation="https://attack.mitre.org/",
            confidence=0.82,
            tool="mitre_adapter",
        ),
        Evidence(
            evidence_id=f"{case_id}-binary",
            case_id=case_id,
            kind="binary_finding",
            claim="The synthetic binary exposes a timing-sensitive parser branch suitable for a reproducible sensitivity test.",
            source="synthetic-binary-adapter",
            citation="scenario://synthetic-binary-01",
            confidence=0.76,
            tool="binary_analysis_adapter",
        ),
        Evidence(
            evidence_id=f"{case_id}-literature",
            case_id=case_id,
            kind="literature",
            claim=f"Public research can inform the question: {question}",
            source="public-literature-adapter",
            citation="https://www.cisa.gov/topics/cyber-threats-and-advisories",
            confidence=0.68,
            tool="literature_adapter",
        ),
    ]
