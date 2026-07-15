"""Business impact narrative agent with Terra/Sol model switching."""

import json
import logging
import os
import re

import httpx
from dotenv import load_dotenv
from openai import OpenAI

load_dotenv()
logger = logging.getLogger(__name__)

MODEL = os.getenv("IMPACT_AGENT_MODEL", "gpt-5.6-terra")

SYSTEM_PROMPT = """You are a principal engineer translating a PR risk summary into
a presentation-ready business impact narrative. Do not invent numbers or
recalculate anything. Use only the values and threshold status in the supplied
risk summary. Explain the causal chain explicitly:
deploy -> traffic increases -> query explosion -> pool saturation -> latency
spike -> user-facing impact -> recommended fix.
Return only valid JSON with exactly these string keys: user_facing_impact,
cost_estimate, narrative. For a clean or non-breaching case, clearly say that
no immediate user impact is expected instead of exaggerating the risk."""

IMPACT_SCHEMA = {
    "type": "object",
    "properties": {
        "user_facing_impact": {"type": "string"},
        "cost_estimate": {"type": "string"},
        "narrative": {"type": "string"},
    },
    "required": ["user_facing_impact", "cost_estimate", "narrative"],
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
        required = ("user_facing_impact", "cost_estimate", "narrative")
        if any(not isinstance(result.get(key), str) for key in required):
            raise ValueError("response does not match the impact schema")
        return {key: result[key] for key in required}
    except (json.JSONDecodeError, TypeError, ValueError) as error:
        logger.error("Failed to parse Impact Agent response: %s; raw=%r", error, raw_text)
        return None


def _number(summary: str, pattern: str) -> str:
    match = re.search(pattern, summary, re.IGNORECASE)
    return match.group(1) if match else "0"


def _fallback_impact(risk_summary: str) -> dict:
    lowered = risk_summary.lower()
    clean = "0 nested query" in lowered
    breached = "not breached" not in lowered and "threshold is breached" in lowered
    severity_match = re.search(r"\b(high|medium|low)\b", lowered)
    severity = severity_match.group(1) if severity_match else ("low" if not breached else "high")
    queries = _number(risk_summary, r"([\d,.]+)\s+queries/request")
    qps = _number(risk_summary, r"([\d,.]+)\s+QPS")
    pool = _number(risk_summary, r"([\d,.]+)%\s+pool utilization")

    if clean:
        return {
            "user_facing_impact": "No user-facing impact is expected; the PR contains no detected nested query findings.",
            "cost_estimate": "No incremental incident or revenue cost expected from the analyzed change.",
            "narrative": "deploy -> no nested query findings -> no query explosion -> connection pool remains unaffected -> no latency spike -> no user-facing impact -> no performance fix required",
        }
    if breached:
        return {
            "user_facing_impact": f"Users may see slow responses, timeouts, or errors when traffic reaches the affected path ({severity} risk).",
            "cost_estimate": "Potential lost conversions and incident-response cost during peak traffic; exact dollars require business telemetry.",
            "narrative": f"deploy -> traffic reaches the affected endpoint -> each request can issue {queries} queries at {qps} QPS -> the connection pool reaches {pool}% utilization and saturates -> queries queue and latency spikes -> users experience slow pages or timeouts -> eager-load or batch the related records before deployment",
        }
    return {
        "user_facing_impact": "No immediate user-facing impact is expected at the supplied traffic level, but the query pattern reduces headroom.",
        "cost_estimate": "No immediate incident cost expected; future traffic growth could create performance cost.",
        "narrative": f"deploy -> traffic reaches the affected endpoint -> each request can issue {queries} queries at {qps} QPS -> pool utilization remains {pool}% without threshold breach -> no immediate latency spike or user impact -> eager-load or batch records to preserve headroom",
    }


def assess_business_impact(risk_summary: str) -> dict:
    """Generate a causal business-impact narrative from a risk summary."""
    fallback = _fallback_impact(risk_summary)
    if "0 nested query" in risk_summary.lower():
        return fallback
    if not os.getenv("OPENAI_API_KEY"):
        logger.warning("OPENAI_API_KEY is not configured; using fallback impact narrative")
        return fallback
    try:
        response = _client().responses.create(
            model=MODEL,
            input=[
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": risk_summary},
            ],
            text={"format": {"type": "json_schema", "name": "impact", "schema": IMPACT_SCHEMA}},
        )
        return _parse_response(response.output_text) or fallback
    except Exception as error:
        logger.warning("Impact Agent model %s failed: %s", MODEL, error)
        return fallback
