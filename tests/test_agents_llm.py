from types import SimpleNamespace

from agents import impact_agent, recommendation_agent, risk_agent


FINDINGS = [{"file": "orders.py", "line": 10, "nesting_depth": 2}]
IMPACT = {
    "projected_query_count": 15,
    "projected_qps": 30000.0,
    "pool_utilization_pct": 750.0,
    "threshold_breached": True,
}
RISK = {
    "severity": "high",
    "threshold_breached": True,
    "risk_summary": "The calculated threshold is breached.",
}


class MockCompletions:
    def __init__(self, content: str) -> None:
        self.content = content
        self.calls: list[dict] = []

    def create(self, **kwargs):
        self.calls.append(kwargs)
        return SimpleNamespace(
            choices=[SimpleNamespace(message=SimpleNamespace(content=self.content))]
        )


def _mock_client(content: str) -> tuple[SimpleNamespace, MockCompletions]:
    completions = MockCompletions(content)
    return SimpleNamespace(chat=SimpleNamespace(completions=completions)), completions


def test_risk_fallback_runs_without_a_groq_key(monkeypatch) -> None:
    monkeypatch.delenv("GROQ_API_KEY", raising=False)

    result = risk_agent.assess_risk(FINDINGS, IMPACT)

    assert result == risk_agent._fallback_assessment(FINDINGS, IMPACT)


def test_recommendation_fallback_runs_without_a_groq_key(monkeypatch) -> None:
    monkeypatch.delenv("GROQ_API_KEY", raising=False)

    result = recommendation_agent.suggest_fix(RISK["risk_summary"], "query()")

    assert result == recommendation_agent._fallback_recommendation("query()")


def test_impact_fallback_runs_without_a_groq_key(monkeypatch) -> None:
    monkeypatch.delenv("GROQ_API_KEY", raising=False)

    result = impact_agent.assess_business_impact(RISK, IMPACT)

    assert result == impact_agent._fallback_impact(RISK, IMPACT)


def test_risk_uses_mocked_groq_chat_completion(monkeypatch) -> None:
    client, completions = _mock_client(
        '{"severity": "high", "threshold_breached": true, "risk_summary": "Risk found."}'
    )
    monkeypatch.setenv("GROQ_API_KEY", "test-key")
    monkeypatch.setattr(risk_agent, "_client", lambda: client)

    result = risk_agent.assess_risk(FINDINGS, IMPACT)

    assert result["risk_summary"] == "Risk found."
    assert completions.calls[0]["model"] == risk_agent.MODEL
    assert completions.calls[0]["response_format"]["type"] == "json_schema"


def test_recommendation_uses_mocked_groq_chat_completion(monkeypatch) -> None:
    client, completions = _mock_client(
        '{"suggested_fix": "Batch the query.", "fix_code_snippet": "load_all()"}'
    )
    monkeypatch.setenv("GROQ_API_KEY", "test-key")
    monkeypatch.setattr(recommendation_agent, "_client", lambda: client)

    result = recommendation_agent.suggest_fix(RISK["risk_summary"], "query()")

    assert result["suggested_fix"] == "Batch the query."
    assert completions.calls[0]["model"] == recommendation_agent.MODEL
    assert completions.calls[0]["response_format"]["type"] == "json_schema"


def test_impact_uses_mocked_groq_chat_completion(monkeypatch) -> None:
    client, completions = _mock_client(
        '{"user_facing_impact": "Latency may increase.", "cost_estimate": "Incident cost.", "narrative": "deploy -> traffic -> latency"}'
    )
    monkeypatch.setenv("GROQ_API_KEY", "test-key")
    monkeypatch.setattr(impact_agent, "_client", lambda: client)

    result = impact_agent.assess_business_impact(RISK, IMPACT)

    assert result["narrative"] == "deploy -> traffic -> latency"
    assert completions.calls[0]["model"] == impact_agent.MODEL
    assert completions.calls[0]["response_format"]["type"] == "json_schema"
