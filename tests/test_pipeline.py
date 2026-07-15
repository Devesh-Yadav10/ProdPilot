from pipeline import run_pipeline
from comment_formatter import format_pr_comment


def test_pipeline_wires_hardcoded_diff(monkeypatch) -> None:
    source = """
for order in user.orders:
    for item in order.items:
        product = Product.query.get(item.product_id)
"""

    monkeypatch.setattr(
        "pipeline.assess_risk",
        lambda findings, impact: {
            "severity": "high",
            "threshold_breached": True,
            "risk_summary": "High risk: 15 queries/request and 75000.0% pool utilization.",
        },
    )
    monkeypatch.setattr(
        "pipeline.suggest_fix",
        lambda risk_summary, snippet: {
            "suggested_fix": "Batch product loading.",
            "fix_code_snippet": "products = load_products(product_ids)",
        },
    )
    monkeypatch.setattr(
        "pipeline.assess_business_impact",
        lambda risk_summary: {
            "user_facing_impact": "Users may see timeouts.",
            "cost_estimate": "Incident cost possible.",
            "narrative": "deploy -> queries -> saturation -> latency -> fix",
        },
    )

    result = run_pipeline(source, "orders.py")

    assert result["findings"][0]["nesting_depth"] == 2
    assert result["impact"]["projected_query_count"] == 15
    assert result["risk"]["severity"] == "high"
    assert result["recommendation"]["suggested_fix"] == "Batch product loading."
    assert result["business_impact"]["narrative"].startswith("deploy")


def test_pipeline_handles_clean_source(monkeypatch) -> None:
    monkeypatch.setattr(
        "pipeline.assess_risk",
        lambda findings, impact: {
            "severity": "low",
            "threshold_breached": False,
            "risk_summary": "No findings; threshold is not breached.",
        },
    )
    monkeypatch.setattr(
        "pipeline.assess_business_impact",
        lambda risk_summary: {
            "user_facing_impact": "None.",
            "cost_estimate": "None.",
            "narrative": "deploy -> no findings -> no impact",
        },
    )

    result = run_pipeline("def get_orders(user):\n    return user.orders\n", "orders.py")

    assert result["findings"] == []
    assert result["impact"]["threshold_breached"] is False
    assert result["recommendation"]["fix_code_snippet"] == ""


def test_comment_formatter_handles_no_findings() -> None:
    comment = format_pr_comment([])

    assert "No issues found" in comment
    assert "nested database-call patterns" in comment
