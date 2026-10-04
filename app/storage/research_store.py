from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path

from app.models.schemas import Evidence, Hypothesis, ResearchCase, ResearchEvent


@dataclass
class ResearchStore:
    cases: dict[str, ResearchCase] = field(default_factory=dict)
    evidence: dict[str, Evidence] = field(default_factory=dict)
    hypotheses: dict[str, Hypothesis] = field(default_factory=dict)
    events: dict[str, list[ResearchEvent]] = field(default_factory=dict)
    path: Path = field(default_factory=lambda: Path(__file__).resolve().parents[2] / "data" / "research_record.json")

    def persist(self) -> None:
        payload = {
            "cases": [item.model_dump(mode="json") for item in self.cases.values()],
            "evidence": [item.model_dump(mode="json") for item in self.evidence.values()],
            "hypotheses": [item.model_dump(mode="json") for item in self.hypotheses.values()],
            "events": [item.model_dump(mode="json") for items in self.events.values() for item in items],
        }
        self.path.write_text(json.dumps(payload, indent=2, sort_keys=True))

    def add_case(self, case: ResearchCase) -> None:
        self.cases[case.case_id] = case
        self.events.setdefault(case.case_id, [])
        self.persist()

    def add_evidence(self, items: list[Evidence]) -> None:
        for item in items:
            self.evidence[item.evidence_id] = item
        self.persist()

    def add_hypotheses(self, items: list[Hypothesis]) -> None:
        for item in items:
            self.hypotheses[item.hypothesis_id] = item
        self.persist()

    def add_event(self, event: ResearchEvent) -> None:
        self.events.setdefault(event.case_id, []).append(event)
        self.persist()

    def timeline(self, case_id: str) -> list[ResearchEvent]:
        return self.events.get(case_id, [])


STORE = ResearchStore()
