"""LLM-backed code recommendations with a deterministic fallback."""

import json
import logging
import os

from dotenv import load_dotenv
from openai import OpenAI

load_dotenv()
logger = logging.getLogger(__name__)

GROQ_BASE_URL = "https://api.groq.com/openai/v1"
MODEL = os.getenv("LLM_MODEL", "openai/gpt-oss-20b")

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
    return OpenAI(api_key=os.getenv("GROQ_API_KEY"), base_url=GROQ_BASE_URL)


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
        "suggested_fix": (
            "This nested database call should likely be replaced with a single "
            "batched query (e.g., using eager loading, `select_related`/`prefetch_related`, "
            "or an `IN` query) executed before the loop, rather than querying once per iteration."
        ),
        "fix_code_snippet": (
            f"# Original pattern:\n{snippet}\n\n"
            "# Consider batching this into a single query before the loop."
        ),
    }


def suggest_fix(risk_summary: str, snippet: str) -> dict:
    """Suggest a concrete fix from a risk summary and original code snippet."""
    fallback = _fallback_recommendation(snippet)
    if not snippet:
        return {
            "suggested_fix": "No fix is required because the Code Agent found no query pattern.",
            "fix_code_snippet": "",
        }
    if not os.getenv("GROQ_API_KEY"):
        logger.warning("GROQ_API_KEY is not configured; using fallback recommendation")
        return fallback

    payload = {"risk_summary": risk_summary, "snippet": snippet}
    try:
        client = _client()
        response = client.chat.completions.create(
            model=MODEL,
            messages=[
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": json.dumps(payload, indent=2)},
            ],
            response_format={
                "type": "json_schema",
                "json_schema": {
                    "name": "recommendation",
                    "strict": True,
                    "schema": RECOMMENDATION_SCHEMA,
                },
            },
        )
        parsed = _parse_response(response.choices[0].message.content or "")
        if parsed is not None:
            return parsed
    except Exception as error:
        logger.warning("Recommendation Agent model %s failed: %s", MODEL, error)
    return fallback
