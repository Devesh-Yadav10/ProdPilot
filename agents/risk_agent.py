"""LLM-backed risk assessment with a deterministic unavailable-API fallback."""

import json
import logging
import os

from dotenv import load_dotenv
import httpx
from openai import OpenAI

load_dotenv()
logger = logging.getLogger(__name__)

MODEL = os.getenv("OPENAI_MODEL", "gpt-5.6-terra")
FALLBACK_MODEL = os.getenv("OPENAI_FALLBACK_MODEL", "gpt-4o-mini")

SYSTEM_PROMPT = """You are a senior backend reliability engineer assessing PR risk.
Reason only over the pre-computed impact numbers supplied in the input. Do not
invent numbers, recalculate metrics, or replace the calculator's arithmetic.
Return only valid JSON with exactly these keys:
severity (one of high, medium, low), threshold_breached (boolean), and
risk_summary (string). Keep the summary understandable to an engineering
reviewer and cite the supplied numbers without changing them."""

RISK_SCHEMA = {
    "type": "object",
    "properties": {
        "severity": {"type": "string", "enum": ["high", "medium", "low"]},
        "threshold_breached": {"type": "boolean"},
        "risk_summary": {"type": "string"},
    },
    "required": ["severity", "threshold_breached", "risk_summary"],
    "additionalProperties": False,
}


def _client() -> OpenAI:
    for variable in ("HTTP_PROXY", "HTTPS_PROXY", "http_proxy", "https_proxy"):
        os.environ.pop(variable, None)
    kwargs = {"api_key": os.getenv("OPENAI_API_KEY"), "http_client": httpx.Client()}
    base_url = os.getenv("OPENAI_BASE_URL")
    if base_url:
        kwargs["base_url"] = base_url
    return OpenAI(**kwargs)


def _parse_response(raw_text: str) -> dict | None:
    try:
        cleaned = raw_text.strip()
        if cleaned.startswith("```"):
            cleaned = cleaned.split("\n", 1)[1].rsplit("```", 1)[0].strip()
        result = json.loads(cleaned)
        if (
            result.get("severity") not in {"high", "medium", "low"}
            or not isinstance(result.get("threshold_breached"), bool)
            or not isinstance(result.get("risk_summary"), str)
        ):
            raise ValueError("response does not match the risk schema")
        return {
            "severity": result["severity"],
            "threshold_breached": result["threshold_breached"],
            "risk_summary": result["risk_summary"],
        }
    except (json.JSONDecodeError, TypeError, ValueError) as error:
        logger.error("Failed to parse Risk Agent response: %s; raw=%r", error, raw_text)
        return None


def _fallback_assessment(findings: list[dict], impact: dict) -> dict:
    breached = bool(impact.get("threshold_breached", False))
    severity = "high" if breached else "low"
    summary = (
        f"{len(findings)} nested query finding(s) project "
        f"{impact.get('projected_query_count', 0)} queries/request, "
        f"{impact.get('projected_qps', 0)} QPS, and "
        f"{impact.get('pool_utilization_pct', 0)}% pool utilization; "
        f"the calculated threshold is {'breached' if breached else 'not breached'}."
    )
    return {
        "severity": severity,
        "threshold_breached": breached,
        "risk_summary": summary,
    }


def _quota_error(error: Exception) -> bool:
    message = str(error).lower()
    return "insufficient_quota" in message or ("429" in message and "quota" in message)


def assess_risk(findings: list[dict], impact: dict) -> dict:
    """Assess risk from findings and calculator output using the Responses API."""
    fallback = _fallback_assessment(findings, impact)
    if not findings:
        return fallback
    if not os.getenv("OPENAI_API_KEY"):
        logger.warning("OPENAI_API_KEY is not configured; using fallback risk assessment")
        return fallback

    payload = {"findings": findings, "impact": impact}
    try:
        client = _client()
        models = [MODEL] if MODEL == FALLBACK_MODEL else [MODEL, FALLBACK_MODEL]
        for model in models:
            try:
                response = client.responses.create(
                    model=model,
                    input=[
                        {"role": "system", "content": SYSTEM_PROMPT},
                        {"role": "user", "content": json.dumps(payload, indent=2)},
                    ],
                    text={"format": {"type": "json_schema", "name": "risk", "schema": RISK_SCHEMA}},
                )
                parsed = _parse_response(response.output_text)
                if parsed is not None:
                    return parsed
            except Exception as error:
                logger.warning("Risk Agent model %s failed: %s", model, error)
                if _quota_error(error):
                    break
    except Exception as error:
        logger.error("Risk Agent client setup failed: %s", error)
    return fallback
