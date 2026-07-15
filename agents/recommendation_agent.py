"""LLM-backed code recommendations with a deterministic fallback."""

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

SYSTEM_PROMPT = """You are a senior Python performance engineer.
Given a risk summary and the original problematic code snippet, suggest one
concrete fix. Prefer eager loading or batching for nested database queries.
Return only valid JSON with exactly two string keys: suggested_fix and
fix_code_snippet. Do not invent metrics or claim numbers that are not in the
risk summary."""

RECOMMENDATION_SCHEMA = {
    "type": "object",
    "properties": {
        "suggested_fix": {"type": "string"},
        "fix_code_snippet": {"type": "string"},
    },
    "required": ["suggested_fix", "fix_code_snippet"],
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
        if not isinstance(result.get("suggested_fix"), str) or not isinstance(
            result.get("fix_code_snippet"), str
        ):
            raise ValueError("response does not match the recommendation schema")
        return {
            "suggested_fix": result["suggested_fix"],
            "fix_code_snippet": result["fix_code_snippet"],
        }
    except (json.JSONDecodeError, TypeError, ValueError) as error:
        logger.error(
            "Failed to parse Recommendation Agent response: %s; raw=%r",
            error,
            raw_text,
        )
        return None


def _fallback_recommendation(snippet: str) -> dict:
    return {
        "suggested_fix": "Eager-load the products before the nested loops instead of querying once per item.",
        "fix_code_snippet": (
            "# Load products in one batch before iterating.\n"
            "product_ids = [item.product_id for order in user.orders for item in order.items]\n"
            "products = {p.id: p for p in Product.query.filter(Product.id.in_(product_ids)).all()}\n\n"
            "for order in user.orders:\n"
            "    for item in order.items:\n"
            "        product = products[item.product_id]"
        ),
    }


def _quota_error(error: Exception) -> bool:
    message = str(error).lower()
    return "insufficient_quota" in message or ("429" in message and "quota" in message)


def suggest_fix(risk_summary: str, snippet: str) -> dict:
    """Suggest a concrete fix from a risk summary and original code snippet."""
    fallback = _fallback_recommendation(snippet)
    if not snippet:
        return {
            "suggested_fix": "No fix is required because the Code Agent found no query pattern.",
            "fix_code_snippet": "",
        }
    if not os.getenv("OPENAI_API_KEY"):
        logger.warning("OPENAI_API_KEY is not configured; using fallback recommendation")
        return fallback

    payload = {"risk_summary": risk_summary, "snippet": snippet}
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
                    text={
                        "format": {
                            "type": "json_schema",
                            "name": "recommendation",
                            "schema": RECOMMENDATION_SCHEMA,
                        }
                    },
                )
                parsed = _parse_response(response.output_text)
                if parsed is not None:
                    return parsed
            except Exception as error:
                logger.warning("Recommendation Agent model %s failed: %s", model, error)
                if _quota_error(error):
                    break
    except Exception as error:
        logger.error("Recommendation Agent client setup failed: %s", error)
    return fallback
