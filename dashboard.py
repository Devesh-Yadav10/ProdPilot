"""Gradio dashboard for recent PR risk analyses."""

import html

from history_store import load_history


def render_history() -> str:
    rows = []
    for item in load_history():
        severity = item.get("severity", "low").lower()
        color = {"high": "#760000", "medium": "#BC8100", "low": "#79AD00"}.get(
            severity, "#FF4800"
        )
        rows.append(
            "<tr style='background:{color}'>"
            "<td>#{number}</td><td>{title}</td><td><strong>{severity}</strong></td>"
            "<td>{summary}</td><td>{when}</td></tr>".format(
                color=color,
                number=html.escape(str(item.get("pr_number", ""))),
                title=html.escape(str(item.get("title", ""))),
                severity=html.escape(severity.upper()),
                summary=html.escape(str(item.get("risk_summary", ""))),
                when=html.escape(str(item.get("analyzed_at", ""))),
            )
        )
    body = "".join(rows) or "<tr><td colspan='5'>No analyzed PRs yet.</td></tr>"
    return (
        "<table style='width:100%;border-collapse:collapse'>"
        "<thead><tr><th>PR</th><th>Title</th><th>Severity</th>"
        "<th>Risk summary</th><th>Analyzed</th></tr></thead>"
        f"<tbody>{body}</tbody></table>"
    )


def build_dashboard():
    import huggingface_hub

    if not hasattr(huggingface_hub, "HfFolder"):
        class HfFolder:
            get_token = staticmethod(huggingface_hub.get_token)

        huggingface_hub.HfFolder = HfFolder
    import gradio as gr

    with gr.Blocks(title="PR Risk History") as demo:
        gr.Markdown("# PR Risk Analysis History")
        gr.Markdown("Recent webhook analyses stored in `data/analysis_history.json`.")
        refresh = gr.Button("Refresh")
        table = gr.HTML(render_history())
        refresh.click(render_history, outputs=table)
    return demo


if __name__ == "__main__":
    build_dashboard().launch(server_name="127.0.0.1", server_port=8760)
