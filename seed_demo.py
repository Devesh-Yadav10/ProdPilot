"""Seed three reproducible local PR analyses for dashboard demos."""

from agents.metrics_agent import load_metrics
from history_store import record_analysis
from pipeline import run_pipeline


SCENARIOS = [
    (101, "Seeded N+1 query example", "for order in user.orders:\n    for item in order.items:\n        product = Product.query.get(item.product_id)\n", {}),
    (102, "Seeded borderline query example", "for order in user.orders:\n    product = Product.query.get(order.product_id)\n", {"peak_concurrent_users": 2}),
    (103, "Seeded clean PR example", "def get_orders(user):\n    return user.orders\n", {}),
]


def main() -> None:
    import pipeline

    for number, title, source, overrides in SCENARIOS:
        original_loader = pipeline.load_metrics
        pipeline.load_metrics = lambda: {**load_metrics(), **overrides}
        try:
            result = run_pipeline(source, f"seeded_{number}.py")
        finally:
            pipeline.load_metrics = original_loader
        record_analysis(number, title, [result])
        print(f"Seeded PR #{number}: {result['risk']['severity']}")


if __name__ == "__main__":
    main()
