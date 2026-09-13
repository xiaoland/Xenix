"""Small author-side business-decision probe; no Subject, services or pytest."""

from dataclasses import asdict, dataclass, replace
from itertools import product
import json
from pathlib import Path


@dataclass(frozen=True)
class Offer:
    sku: str
    cost: int
    contribution: int
    boxes: int
    arrival_days: int


OFFERS = (
    Offer("A", 160, 240, 6, 2),
    Offer("B", 160, 240, 6, 2),
    Offer("C", 100, 130, 4, 3),
    Offer("D", 70, 85, 3, 1),
    Offer("E", 60, 72, 2, 1),
    Offer("F", 30, 28, 1, 1),
    Offer("G", 120, 230, 4, 8),
    Offer("H", 200, 320, 10, 4),
)


def outcomes(offers, budget=300, capacity=10, deadline=5):
    """Enumerate all 256 offered-batch subsets, retaining every equally good plan."""
    feasible = []
    for chosen in product((False, True), repeat=len(offers)):
        selected = [offer for offer, take in zip(offers, chosen, strict=True) if take]
        cost = sum(offer.cost for offer in selected)
        boxes = sum(offer.boxes for offer in selected)
        if cost > budget or boxes > capacity or any(offer.arrival_days > deadline for offer in selected):
            continue
        feasible.append(
            {
                "skus": sorted(offer.sku for offer in selected),
                "cost": cost,
                "boxes": boxes,
                "contribution": sum(offer.contribution for offer in selected),
            }
        )
    best = max(plan["contribution"] for plan in feasible)
    return {
        "budget": budget,
        "capacity": capacity,
        "deadline": deadline,
        "feasible_plan_count": len(feasible),
        "best_contribution": best,
        "optimal_plans": [plan for plan in feasible if plan["contribution"] == best],
    }


def plans(result):
    return {tuple(plan["skus"]) for plan in result["optimal_plans"]}


def main():
    standard = outcomes(OFFERS)
    constrained = outcomes(OFFERS, budget=240)
    changed_margin = outcomes(tuple(replace(o, contribution=60) if o.sku == "C" else o for o in OFFERS))
    same_decision = outcomes(tuple(replace(o, contribution=140) if o.sku == "C" else o for o in OFFERS))
    no_purchase = outcomes(OFFERS, budget=20)
    arrival_changed = outcomes(tuple(replace(o, arrival_days=3) if o.sku == "G" else o for o in OFFERS))
    assert plans(standard) == {("A", "C"), ("B", "C")}
    assert standard["best_contribution"] == 370
    assert plans(constrained) == {("A", "D"), ("B", "D")}
    assert plans(changed_margin) == {("A", "D", "F"), ("B", "D", "F")}
    assert plans(same_decision) == plans(standard)
    assert same_decision["best_contribution"] == 380
    assert plans(no_purchase) == {()}
    assert plans(arrival_changed) != plans(standard)
    assert plans(outcomes(tuple(reversed(OFFERS)))) == plans(standard)
    # Renaming offers changes identity only; translate the result back before comparison.
    renamed = outcomes(tuple(replace(o, sku=f"item-{i}") for i, o in enumerate(OFFERS)))
    inverse = {f"item-{i}": o.sku for i, o in enumerate(OFFERS)}
    assert {tuple(sorted(inverse[sku] for sku in plan)) for plan in plans(renamed)} == plans(standard)
    assert all(not (set(plan["skus"]) == {"H"}) for plan in standard["optimal_plans"])
    result = {
        "purpose": "Design probe only; authored subset-choice offers, not production demand or a live Agent result.",
        "offers": [asdict(offer) for offer in OFFERS],
        "scenarios": {
            "standard": standard,
            "budget_only_changes": constrained,
            "margin_only_changes_decision": changed_margin,
            "margin_only_preserves_decision": same_decision,
            "arrival_only_changes_decision": arrival_changed,
            "no_affordable_batch": no_purchase,
        },
        "observations": {
            "distinct_optimal_plans_are_accepted": True,
            "largest_individual_contribution_is_suboptimal": {"skus": ["H"], "contribution": 320},
            "empty_plan_is_correct_only_in_no_affordable_batch_scenario": True,
            "row_order_and_identity_changes_preserve_business_choice": True,
            "single_business_changes_have_computable_effects": True,
        },
    }
    target = Path(__file__).with_name("observations.json")
    target.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(
        json.dumps(
            {
                name: {"value": r["best_contribution"], "plans": sorted(plans(r))}
                for name, r in result["scenarios"].items()
            },
            ensure_ascii=False,
        )
    )


if __name__ == "__main__":
    main()
