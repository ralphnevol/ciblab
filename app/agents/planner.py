from __future__ import annotations

from app.models.schemas import Decision, PlannerDecision
from app.orchestration.state import TriageState

TEST_COSTS = {
    "literature_check": 1,
    "evidence_quality_review": 1,
    "efficacy_test": 3,
    "alert_volume_test": 2,
    "redundancy_check": 2,
    "robustness_test": 4,
}
# Tests the planner chooses between once the baseline (literature + efficacy) is in.
PLANNABLE_TESTS = ("robustness_test", "redundancy_check", "alert_volume_test", "evidence_quality_review")
MIN_VALUE = 0.1


def expected_gain(test: str, state: TriageState, provisional: Decision) -> float:
    """Heuristic information gain: how likely the test is to change the provisional decision."""
    if test == "robustness_test":
        # An adversary can only flip a detection we are about to KEEP.
        return 1.4 if provisional == Decision.KEEP else 0.3
    if test == "redundancy_check":
        return 0.6 if provisional == Decision.KEEP else 0.15
    if test == "alert_volume_test":
        return 0.6 if 0.015 <= state.scorecard.false_positive_rate <= 0.08 else 0.15
    if test == "evidence_quality_review":
        return 0.2 + 0.8 * state.uncertainty.value if provisional == Decision.INVESTIGATE else 0.2
    raise ValueError(test)


def rank_tests(state: TriageState, provisional: Decision, exclude: tuple[str, ...] = ()) -> list[tuple[str, float, float, int]]:
    ranked = []
    for test in PLANNABLE_TESTS:
        if test in state.tests_run or test in exclude:
            continue
        gain = expected_gain(test, state, provisional)
        cost = TEST_COSTS[test]
        ranked.append((test, round(gain / cost, 4), round(gain, 4), cost))
    return sorted(ranked, key=lambda r: (-r[1], r[3], r[0]))


def _first_viable(ranked, budget: int):
    return next((r for r in ranked if r[3] <= budget and r[1] >= MIN_VALUE), None)


def select_test(state: TriageState, provisional: Decision) -> PlannerDecision:
    ranked = rank_tests(state, provisional)
    chosen = _first_viable(ranked, state.remaining_budget)
    remaining = state.remaining_budget - (chosen[3] if chosen else 0)
    follow_up = None
    if chosen:
        follow_up = _first_viable(rank_tests(state, provisional, exclude=(chosen[0],)), remaining)

    rejected = []
    for test, value, gain, cost in ranked:
        if chosen and test == chosen[0]:
            continue
        if cost > state.remaining_budget:
            reason = "over budget"
        elif value < MIN_VALUE:
            reason = "value below threshold"
        else:
            reason = "lower priority"
        rejected.append({"test": test, "priority": value, "cost": cost, "expected_information_gain": gain, "reason": reason})

    u = state.uncertainty.value
    if chosen:
        rationale = (
            f"{chosen[0]} has the best gain/cost ({chosen[2]}/{chosen[3]}={chosen[1]}) given provisional "
            f"{provisional.value} at uncertainty {u:.2f}; budget {state.remaining_budget} -> {remaining}"
        )
    else:
        rationale = f"Stopping: no affordable test with gain/cost >= {MIN_VALUE} (budget {state.remaining_budget})"
    return PlannerDecision(
        selected_test=chosen[0] if chosen else None,
        provisional_decision=provisional,
        uncertainty=u,
        remaining_budget=remaining,
        planned_follow_up=follow_up[0] if follow_up else None,
        rejected_alternatives=rejected,
        estimated_value=chosen[1] if chosen else 0.0,
        rationale=rationale,
    )


def recommend_next(state: TriageState, provisional: Decision) -> str:
    """Most informative next experiment for an INVESTIGATE outcome, ignoring the spent budget."""
    ranked = rank_tests(state, provisional)
    return ranked[0][0] if ranked else "replication_with_new_seed"
