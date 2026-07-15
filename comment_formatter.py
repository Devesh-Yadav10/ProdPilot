"""Markdown formatting for GitHub pull-request comments."""


BOT_MARKER = "<!-- PR-Risk-Analysis-Bot -->"


def format_pr_comment(results: list[dict], pr_title: str = "") -> str:
    """Format one or more pipeline results as a single Markdown comment."""
    findings = [finding for result in results for finding in result.get("findings", [])]
    if not findings:
        return (
            f"{BOT_MARKER}\n\n## PR Risk Analysis\n\n"
            "No issues found. The Code Agent detected no nested database-call "
            "patterns in the changed Python files."
        )

    title_suffix = f" — {pr_title}" if pr_title else ""
    lines = [BOT_MARKER, "", f"## PR Risk Analysis{title_suffix}", ""]
    for result in results:
        if not result.get("findings"):
            continue
        risk = result["risk"]
        impact = result["impact"]
        recommendation = result["recommendation"]
        business_impact = result["business_impact"]
        lines.extend(
            [
                f"### `{result['filename']}`",
                f"**Severity:** `{risk['severity']}`  ",
                f"**Threshold breached:** `{risk['threshold_breached']}`  ",
                f"**Risk:** {risk['risk_summary']}",
                "",
                "**Calculated impact**",
                f"- Projected queries/request: `{impact['projected_query_count']}`",
                f"- Projected QPS: `{impact['projected_qps']}`",
                f"- Pool utilization: `{impact['pool_utilization_pct']}%`",
                f"- Latency estimate: `{impact['latency_estimate_ms']} ms`",
                "",
                "**Recommended fix**",
                recommendation["suggested_fix"],
                "",
                "```python",
                recommendation["fix_code_snippet"],
                "```",
                "",
                "**Business impact**",
                f"- {business_impact['user_facing_impact']}",
                f"- {business_impact['cost_estimate']}",
                f"- {business_impact['narrative']}",
                "",
            ]
        )
    return "\n".join(lines).rstrip()
