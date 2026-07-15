"""Application pipeline connecting deterministic and LLM analysis stages."""

import logging
from concurrent.futures import ThreadPoolExecutor

from agents.code_agent import analyze_code
from agents.impact_agent import _fallback_impact, assess_business_impact
from agents.metrics_agent import load_metrics
from agents.recommendation_agent import _fallback_recommendation, suggest_fix
from agents.risk_agent import _fallback_assessment, assess_risk
from calculator import compute_impact

logger = logging.getLogger(__name__)

# fallback if load_metrics doesn't work and real time metrics are not available
DEFAULT_METRICS = {
    "avg_orders_per_user": 5,
    "avg_items_per_order": 3,
    "connection_pool_size": 20,
    "p95_latency_ms": 150,
    "peak_concurrent_users": 1000,
}

### _safe_* functions - used to choose whether the agent runs or fails (assess_* functions)
### if fails (API timeouts, rate limits, malformed JSON responses, content filtering) it 
### throws an exception, then switch back to deterministic backstop (_fallback_* functions)

def _safe_risk(findings: list[dict], impact: dict) -> dict:
    try:
        return assess_risk(findings, impact)
    except Exception:
        logger.exception("Risk Agent failed; using deterministic fallback")
        return _fallback_assessment(findings, impact)


def _safe_recommendation(risk_summary: str, snippet: str) -> dict:
    try:
        return suggest_fix(risk_summary, snippet)
    except Exception:
        logger.exception("Recommendation Agent failed; using deterministic fallback")
        return _fallback_recommendation(snippet)


def _safe_impact(risk: dict, impact: dict) -> dict:
    try:
        return assess_business_impact(risk, impact)
    except Exception:
        logger.exception("Impact Agent failed; using deterministic fallback")
        return _fallback_impact(risk, impact)


def run_pipeline(source_code: str, filename: str = "<string>") -> dict:
    """Run the complete analysis chain for one changed source file."""
    # STAGE 1
    # Metrics loading is independent of AST analysis. The calculator consumes
    # both results, so it starts after these two independent stages complete.
    with ThreadPoolExecutor(max_workers=2) as executor:
        metrics_future = executor.submit(load_metrics)
        # AST analysis
        try:
            code_result = analyze_code(source_code, filename)
        except Exception:
            logger.exception("Code Agent failed for %s", filename)
            code_result = {"findings": [], "error": "Code analysis failed"}
        
        # metrics loading
        try:
            metrics = metrics_future.result()
        except Exception:
            logger.exception("Metrics Agent failed; using safe defaults")
            metrics = DEFAULT_METRICS.copy()

    # STAGE 2 - Impact Calculation
    findings = code_result.get("findings", [])
    try:
        # combines the AST findings with the metrics to estimate real-world impact
        impact = compute_impact(findings, metrics)
    except Exception:
        logger.exception("Impact Calculator failed; using zero-impact result")
        impact = {
            "endpoint": "unknown",
            "projected_query_count": 0,
            "projected_qps": 0.0,
            "pool_utilization_pct": 0.0,
            "latency_estimate_ms": 0.0,
            "threshold_breached": False,
        }
    risk = _safe_risk(findings, impact)
    # grabs the first finding's code snippet to hand to the fix-suggestion agent
    snippet = findings[0].get("snippet", "") if findings else ""

    # STAGE 3 - recommendation + business impact
    # These agents depend only on risk_summary and are intentionally concurrent.
    # translates the technical risk into a business-facing statement
    with ThreadPoolExecutor(max_workers=2) as executor:
        recommendation_future = executor.submit(
            _safe_recommendation, risk["risk_summary"], snippet
        )
        impact_future = executor.submit(_safe_impact, risk, impact)
        recommendation = recommendation_future.result()
        business_impact = impact_future.result()

    return {
        "filename": filename,
        "findings": findings,
        "metrics": metrics,
        "impact": impact,
        "risk": risk,
        "recommendation": recommendation,
        "business_impact": business_impact,
    }
