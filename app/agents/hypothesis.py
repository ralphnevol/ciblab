from app.models.schemas import Evidence, Hypothesis


def formulate_hypotheses(case_id: str, evidence: list[Evidence]) -> list[Hypothesis]:
    refs = [item.evidence_id for item in evidence]
    return [
        Hypothesis(
            hypothesis_id=f"{case_id}-H1",
            case_id=case_id,
            statement="The parser branch remains stable when input timing is randomized.",
            evidence_refs=refs,
            confidence=0.62,
            unknowns=["timing sensitivity"],
        ),
        Hypothesis(
            hypothesis_id=f"{case_id}-H2",
            case_id=case_id,
            statement="The parser branch is sensitive to fixed timing assumptions.",
            evidence_refs=refs,
            confidence=0.58,
            unknowns=["degradation threshold"],
        ),
    ]
