# PR Risk Agent

PR Risk Agent analyzes Python pull-request changes for N+1 database-query risks, estimates the operational impact with deterministic arithmetic, and posts a clear risk report to the pull request. A local Gradio dashboard keeps a history of analyzed PRs.

The core detection and impact calculation run without GitHub access, paid API credits, or an LLM. LLM agents are optional enhancements for risk summaries, suggested fixes, and business-impact narratives.

## What It Does

1. Receives a GitHub `pull_request` webhook.
2. Fetches changed Python files from the pull request.
3. Detects database-query-shaped expressions inside nested loops using Python `ast`.
4. Reads synthetic demo metrics and calculates projected query count, QPS, connection-pool utilization, and latency.
5. Produces risk, recommendation, and impact outputs with an LLM when configured, or safe deterministic fallbacks otherwise.
6. Posts a Markdown comment on the pull request and saves the result for the dashboard.

## Architecture

```text
GitHub PR update
  -> GitHub webhook
  -> smee.io tunnel
  -> FastAPI /webhook
  -> Code Agent + Metrics Agent
  -> Deterministic Calculator
  -> Risk / Recommendation / Impact Agents
  -> GitHub PR comment + Gradio dashboard
```

## Supported Platform

- Windows 10 or Windows 11
- Python 3.11 or later
- Node.js 18 or later (only required for the `smee` webhook tunnel)
- GitHub account and personal access token (only required for live PR comments)

## Project Structure

```text
pr-risk-agent/
├── agents/
│   ├── code_agent.py             # AST-based N+1 pattern detection
│   ├── metrics_agent.py          # Loads synthetic metrics
│   ├── risk_agent.py             # Risk assessment with LLM/fallback
│   ├── recommendation_agent.py   # Fix recommendation with LLM/fallback
│   └── impact_agent.py           # Business narrative with LLM/fallback
├── data/
│   └── synthetic_metrics.json    # Clearly synthetic demo telemetry
├── tests/                        # Unit, pipeline, and integration tests
├── calculator.py                 # Deterministic impact arithmetic
├── pipeline.py                   # Orchestrates all analysis stages
├── main.py                       # FastAPI GitHub webhook application
├── dashboard.py                  # Gradio analysis-history dashboard
├── history_store.py              # Local JSON history storage
├── comment_formatter.py          # GitHub PR Markdown formatter
├── seed_demo.py                  # Seeds local demo scenarios
├── test_openai_sanity.py         # Optional OpenAI connectivity check
├── requirements.txt
└── .env.example
```

## Quick Start: Offline Demo

Use this path to evaluate the project without GitHub, a webhook tunnel, or any API key.

### 1. Clone and enter the project

```powershell
git clone <YOUR_REPOSITORY_URL>
cd pr-risk-agent
```

### 2. Create a virtual environment

```powershell
py -m venv .venv
.\.venv\Scripts\Activate.ps1
```

If PowerShell blocks activation, run this once in the same terminal:

```powershell
Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass
```

Then activate the environment again.

### 3. Install dependencies

```powershell
python -m pip install --upgrade pip
pip install -r requirements.txt
```

### 4. Run all tests

```powershell
python -m pytest -v
```

The deterministic unit tests do not require secrets or external services. Tests that require a live LLM should be clearly marked as integration tests and may be skipped when no API key is configured.

### 5. Seed local demo data

```powershell
python seed_demo.py
```

This creates three reproducible scenarios for the dashboard:

- **High risk:** nested-loop N+1 query pattern.
- **Borderline/low risk:** nested loop with low projected traffic.
- **Clean PR:** no detected findings.

### 6. Start the dashboard

```powershell
python dashboard.py
```

Open [http://127.0.0.1:8760](http://127.0.0.1:8760) in a browser. The dashboard displays saved analyses with severity-based coloring.

## Configuration

Copy the environment template:

```powershell
Copy-Item .env.example .env
```

Edit `.env` as needed:

```env
# Required only for live GitHub PR fetching and comment posting.
GITHUB_TOKEN=your_github_personal_access_token

# Optional: enables LLM-generated summaries, recommendations, and narratives.
OPENAI_API_KEY=your_openai_api_key
OPENAI_MODEL=gpt-5.6-terra
IMPACT_AGENT_MODEL=gpt-5.6-terra
```

Never commit `.env`, API keys, personal access tokens, or webhook secrets.

## Live GitHub Webhook Demo

This section is optional. The offline demo and test suite are enough to evaluate the core project.

### 1. Create a GitHub token

Create a classic GitHub personal access token with the `repo` scope. It allows the application to read pull-request files and create PR comments in a repository you control.

Add it to `.env`:

```env
GITHUB_TOKEN=ghp_your_token_here
```

### 2. Start FastAPI

Open a PowerShell terminal in the project with the virtual environment activated:

```powershell
uvicorn main:app --host 127.0.0.1 --port 7000
```

Verify the service:

- Health endpoint: [http://127.0.0.1:7000/health](http://127.0.0.1:7000/health)
- API documentation: [http://127.0.0.1:7000/docs](http://127.0.0.1:7000/docs)

`/webhook` accepts only `POST` requests. Opening it in a browser returns `405 Method Not Allowed`, which is expected.

### 3. Create a smee.io channel

1. Visit [https://smee.io](https://smee.io).
2. Click **Start a new channel**.
3. Copy the generated URL, such as `https://smee.io/your-channel-id`.

Install the smee client once:

```powershell
npm install --global smee-client
```

In a second terminal, start forwarding events:

```powershell
smee --url https://smee.io/your-channel-id --target http://127.0.0.1:7000/webhook
```

Leave both the FastAPI and smee terminals running.

### 4. Register the GitHub webhook

In your scratch repository:

1. Go to **Settings** -> **Webhooks** -> **Add webhook**.
2. Set **Payload URL** to your smee channel URL.
3. Set **Content type** to `application/json`.
4. Select **Let me select individual events**.
5. Select **Pull requests**.
6. Save the webhook.

### 5. Trigger the analysis

Create or update an open pull request with a changed `.py` file. For example:

```python
for order in user.orders:
    for item in order.items:
        product = Product.query.get(item.product_id)
```

GitHub sends the event through smee to FastAPI. The application analyzes the changed file, comments on the PR, and records the result in the dashboard history.

If no risky pattern is detected, the application posts a friendly no-issues-found comment instead.

## Sample Data and Deterministic Calculation

`data/synthetic_metrics.json` contains placeholder values standing in for production telemetry:

- `avg_orders_per_user`
- `avg_items_per_order`
- `connection_pool_size`
- `p95_latency_ms`
- `peak_concurrent_users`

These values are intentionally synthetic. Replace the metrics source with real observability data before any production use.

The calculator is deliberately plain Python arithmetic. LLMs receive computed numbers to explain risk; they never calculate query counts, QPS, pool utilization, or threshold decisions.

## Output Contracts

The Code Agent output remains stable for downstream stages:

```json
{
  "findings": [
    {
      "file": "example.py",
      "line": 3,
      "pattern_type": "nested_query",
      "nesting_depth": 2,
      "snippet": "Product.query.get(item.product_id)"
    }
  ]
}
```

The deterministic calculator output is:

```json
{
  "endpoint": "...",
  "projected_query_count": 0,
  "projected_qps": 0,
  "pool_utilization_pct": 0,
  "latency_estimate_ms": 0,
  "threshold_breached": false
}
```

## Optional LLM Setup

When `OPENAI_API_KEY` is set and has active OpenAI Platform billing/credits, the Risk, Recommendation, and Impact agents use the configured model. Without an API key or when the request fails, each agent logs the failure and returns a safe fallback response so the webhook does not crash.

Run the optional connectivity check:

```powershell
python test_openai_sanity.py
```

Do not run this test without a valid API key and active API billing/credits.

## Troubleshooting

| Problem | What to check |
| --- | --- |
| `localhost refused to connect` | Start the service first, then use the printed local URL. |
| `405 Method Not Allowed` at `/webhook` | Expected in a browser; the endpoint only accepts GitHub `POST` requests. |
| smee command not found | Install it with `npm install --global smee-client`, then open a new terminal. |
| GitHub comment returns `403` | Replace the token with a classic PAT that has `repo` scope, then restart Uvicorn. |
| OpenAI request returns `429 insufficient_quota` | Add API billing/credits or leave `OPENAI_API_KEY` unset to use fallback output. |
| Dashboard import fails with `HfFolder` | Reinstall dependencies from `requirements.txt` in the active virtual environment. |

## Security Notes

- Keep all credentials in `.env` only.
- Keep `.env` in `.gitignore`.
- Use a short-lived, least-privileged token for demos.
- Use a scratch repository for webhook demonstrations.
- This project uses synthetic metrics and is intended as a demo/prototype, not a production monitoring system.

## Judge Checklist

Judges can evaluate the project without rebuilding external infrastructure:

```powershell
py -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
python -m pytest -v
python seed_demo.py
python dashboard.py
```
Then open [http://127.0.0.1:7860](http://127.0.0.1:7860). No GitHub token, webhook tunnel, or paid LLM account is needed for this deterministic demo path.

## Figma Workflow

[ProdPilot-Figma-Workflow](https://www.figma.com/board/rdea1bdFcPJ1mVJUS13fsU/ProdPilot-workflow?node-id=0-1&t=Ff1t44gqj3mPMKkE-1)
