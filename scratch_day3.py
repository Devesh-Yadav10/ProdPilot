"""Run the Day 1 -> Day 3 chain with the known nested-query example."""

import json

from agents.code_agent import analyze_code
from agents.metrics_agent import load_metrics
from agents.recommendation_agent import suggest_fix
from agents.risk_agent import assess_risk
from calculator import compute_impact


SOURCE = """
for order in user.orders:
    for item in order.items:
        product = Product.query.get(item.product_id)
"""


def main() -> None:
    code_result = analyze_code(SOURCE, "orders.py")
    impact = compute_impact(code_result["findings"], load_metrics())
    risk = assess_risk(code_result["findings"], impact)
    recommendation = suggest_fix(risk["risk_summary"], code_result["findings"][0]["snippet"])

    for name, value in (
        ("code_agent", code_result),
        ("calculator", impact),
        ("risk_agent", risk),
        ("recommendation_agent", recommendation),
    ):
        print(f"{name}:\n{json.dumps(value, indent=2)}\n")


if __name__ == "__main__":
    main()
