from __future__ import annotations

from app.models.schemas import PlannerDecision

TEST_COSTS = {
    "literature_check": 1,
    "evidence_quality_review": 1,
    "efficacy_test": 3,
    "alert_volume_test": 2,
    "redundancy_check": 2,
    "robustness_test": 4,
}


def select_test(remaining_budget: int, uncertainty: float, last_result: dict | None, d03_adapted: bool) -> PlannerDecision:
    options = {
        "efficacy_test": 0.9,
        "alert_volume_test": 0.55,
        "redundancy_check": 0.45,
        "robustness_test": 0.85 if uncertainty < 0.5 else 1.0,
        "evidence_quality_review": 0.4,
        "literature_check": 0.35,
    }
    if last_result is not None:
        options["efficacy_test"] = 0.2
        options["robustness_test"] = max(options["robustness_test"], 1.6)
        options["evidence_quality_review"] = 0.2
    if d03_adapted:
        options["robustness_test"] = 0.2
        options["evidence_quality_review"] = 0.95
    scores = []
    for test_name, gain in options.items():
        cost = TEST_COSTS[test_name]
        if cost <= remaining_budget:
            scores.append((test_name, gain / cost, gain, cost))
    scores.sort(key=lambda x: x[1], reverse=True)
    selected, value, gain, cost = scores[0]
    rejected = [
        {"test": t, "priority": round(v, 4), "cost": c, "expected_information_gain": g}
        for t, v, g, c in scores[1:]
    ]
    return PlannerDecision(
        selected_test=selected,
        remaining_budget=remaining_budget - cost,
        rejected_alternatives=rejected,
        estimated_value=round(value, 4),
        rationale=f"Selected by deterministic gain/cost ratio; uncertainty={uncertainty:.2f}",
    )
