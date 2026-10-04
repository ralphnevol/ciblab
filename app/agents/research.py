from app.models.schemas import Evidence, ResearchQuestion


def research(question: ResearchQuestion, evidence: list[Evidence]) -> dict:
    return {
        "case_id": question.case_id,
        "evidence_ids": [item.evidence_id for item in evidence],
        "evidence_gaps": ["validated behavior under timing perturbation"],
        "confidence": 0.76,
    }
