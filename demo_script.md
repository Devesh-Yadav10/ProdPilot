# Live Demo Script

## Before the audience joins

1. Run `python seed_demo.py` and `python dashboard.py`; keep
   `http://127.0.0.1:7860` open.
2. Start FastAPI and the smee tunnel in separate terminals, following the README.
3. Confirm `/health` returns `{"status":"ok"}` and that the scratch repository
   webhook is active.
4. Keep the three seeded dashboard rows visible as the fallback demo path.

## Demo flow (about four minutes)

1. Open **PR #101 — Seeded N+1 query example**.
   - Say: “This change performs a product lookup inside nested order and item
     loops. The Code Agent catches that pattern without an LLM.”
2. Update the PR or open it to trigger the webhook. Point to the bot comment.
   - Say: “The calculator deterministically projects 15 queries per request,
     100,000 QPS, and 75,000% connection-pool utilization. Those numbers are
     calculated in Python; the LLM only explains their operational meaning.”
3. Highlight the recommendation and causal narrative.
   - Say: “The recommendation is to eager-load or batch products before the
     nested loop. The business narrative walks from deployment to user impact.”
4. Switch to the dashboard.
   - Say: “Every webhook analysis is recorded here. Red is the known N+1 case;
     the green rows show the same pipeline handles a borderline change and a
     clean PR without exaggerating risk.”
5. Open **PR #103 — Seeded clean PR example**.
   - Say: “A clean change still receives an explicit no-issues result, which
     keeps the automation trustworthy.”

## Backup path

If GitHub, smee, or API quota is slow, use the seeded dashboard rows and open
`closing_narrative.md`. Explain that the same deterministic fixtures created the
records, then show the N+1 causal chain and recommendation.
