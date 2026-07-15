# PR Risk Agent

Analyzes Python pull-request changes for nested database calls, calculates the
projected impact deterministically, and posts a structured risk comment to the
PR. The local Gradio dashboard keeps a color-coded history of analyses.

## Prerequisites (Windows)

Install these before cloning:

- [Git](https://git-scm.com/download/win)
- Python 3.10 or newer from [python.org](https://www.python.org/downloads/)
  (select **Add Python to PATH** during installation)
- Node.js LTS from [nodejs.org](https://nodejs.org/) for the smee tunnel

Verify the installs in a new PowerShell window:

```powershell
git --version
python --version
npm --version
```

## Fresh-clone setup

```powershell
git clone https://github.com/YOUR_ACCOUNT/pr-risk-agent.git
cd pr-risk-agent
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
python -m pip install -r requirements.txt
Copy-Item .env.example .env
```

If activation is blocked, run this once for the current PowerShell window and
retry the activation command:

```powershell
Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass
```

Edit `.env` and set:

```dotenv
GROQ_API_KEY=your_groq_api_key
GITHUB_TOKEN=your_github_fine_grained_token
GITHUB_WEBHOOK_SECRET=your_github_webhook_secret
LLM_MODEL=openai/gpt-oss-20b
IMPACT_AGENT_MODEL=openai/gpt-oss-20b
```

Create a Groq API key in the [Groq Console](https://console.groq.com/keys) and
copy it into `GROQ_API_KEY`. The Risk and Recommendation agents use
`LLM_MODEL`; the Impact agent uses `IMPACT_AGENT_MODEL`. Both default to
`openai/gpt-oss-20b` via Groq's OpenAI-compatible Chat Completions endpoint.
If `GROQ_API_KEY` is absent, all three agents use their deterministic fallbacks
and make no network calls.

For a fine-grained GitHub token, grant the scratch repository **Contents: Read**,
**Issues: Read and write**, **Pull requests: Read**, and **Metadata: Read**.
Never commit `.env`.

## Verify locally

Run deterministic and wiring tests first:

```powershell
python -m pytest tests/test_code_agent.py tests/test_calculator.py tests/test_pipeline.py -v
```

Run the seeded dashboard demo. It creates three repeatable analyses: high-risk
N+1, a non-breaching borderline case, and a clean PR.

```powershell
python seed_demo.py
python dashboard.py
```

Open `http://127.0.0.1:7860` and confirm that PRs `#101`, `#102`, and `#103`
appear with red, green, and green severity rows. The history is stored in
`data/analysis_history.json`.

## Connect GitHub with smee.io

1. Install the tunnel client:

   ```powershell
   npm install -g smee-client
   ```

2. Open [smee.io](https://smee.io), select **Start a new channel**, and copy
   the generated URL.

3. In terminal one, activate the virtual environment and start FastAPI:

   ```powershell
   .\.venv\Scripts\Activate.ps1
   uvicorn main:app --host 127.0.0.1 --port 8000
   ```

4. In terminal two, forward the smee channel:

   ```powershell
   smee forward https://smee.io/YOUR_CHANNEL --target http://127.0.0.1:8000/webhook
   ```

5. In the scratch repository, open **Settings → Webhooks → Add webhook**:
   - Payload URL: the smee URL
   - Content type: `application/json`
   - Secret: a strong value matching `GITHUB_WEBHOOK_SECRET` in `.env`
   - Events: **Let me select individual events → Pull requests**
   - Active: enabled

6. Open or update a pull request with a changed Python file. The webhook fetches
   the changed PR files, runs the pipeline, posts a Markdown comment, and records
   the result in the dashboard history. A README-only PR receives a friendly
   “No issues found” comment.

Use `http://127.0.0.1:8000/docs` to inspect the running FastAPI app. The
`/webhook` route accepts `POST` only; a browser `GET` returns `405` by design.

## Seed real GitHub PRs (optional)

Use only a disposable repository. With `.env` configured, set the target and run:

```powershell
$env:SCRATCH_REPO = "YOUR_ACCOUNT/YOUR_SCRATCH_REPO"
python seed_github_prs.py
```

This creates three branches and PRs matching the local demo fixtures.

## Reliability notes

- Query counts, QPS, pool utilization, and threshold checks are deterministic
  Python calculations. LLMs only reason over those supplied numbers.
- Every LLM response is structured JSON with defensive parsing and a fallback.
- GitHub rate limits, malformed payloads, empty Python changes, telemetry
  failures, and LLM failures are logged without crashing the webhook receiver.
- GitHub webhook payloads are HMAC-verified with `GITHUB_WEBHOOK_SECRET`; the
  server will not start until this variable is set.
