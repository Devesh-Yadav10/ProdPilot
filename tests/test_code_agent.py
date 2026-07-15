from agents.code_agent import analyze_code


def test_nested_query_detected() -> None:
    code = """
for order in user.orders:
    for item in order.items:
        product = Product.query.get(item.product_id)
"""

    result = analyze_code(code, "orders.py")

    assert result == {
        "findings": [
            {
                "file": "orders.py",
                "line": 4,
                "pattern_type": "nested_query",
                "nesting_depth": 2,
                "snippet": "product = Product.query.get(item.product_id)",
            }
        ]
    }

