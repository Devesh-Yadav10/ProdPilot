import os

import pytest

from agents.recommendation_agent import suggest_fix


pytestmark = pytest.mark.integration


@pytest.mark.skipif(
    os.getenv("RUN_LLM_INTEGRATION") != "1",
    reason="Set RUN_LLM_INTEGRATION=1 to run live OpenAI integration tests",
)
def test_recommendation_agent_known_nested_query() -> None:
    result = suggest_fix(
        "High risk: calculated pool utilization is 75000.0% and the threshold is breached.",
        "product = Product.query.get(item.product_id)",
    )

    assert isinstance(result["suggested_fix"], str)
    assert isinstance(result["fix_code_snippet"], str)
    assert result["suggested_fix"]
    assert result["fix_code_snippet"]
