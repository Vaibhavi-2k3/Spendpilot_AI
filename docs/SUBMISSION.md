# SpendPilot AI — submission description

## Project summary

SpendPilot AI is a budget-aware shopping assistant that turns a shopping request
into a shortlist of products with transparent comparisons. Users enter what they
need, choose a budget and currency, and search either a demo catalog or live
Google Shopping listings. The application saves the shopping session, filters
results against the budget, and displays ranked product cards.

Optional Google Gemini integration interprets the request into a focused search
query and preferences, then explains the top eligible options with citations
from their listing text. Product IDs and cited quotes are checked against the
catalog. Prices, availability notices, and checkout eligibility stay controlled
by the backend. If Gemini is unavailable, the application continues with a
clearly identified keyword-and-budget ranking fallback.

## Features demonstrated

- Functional browser-based shopping form and responsive product cards.
- Budget-aware discovery with USD/INR support for live shopping results.
- Persistent shopping sessions, products, and recommendations in PostgreSQL.
- Gemini-powered intent extraction, explanations, and suggested picks when
  configured with an accessible model and valid API key.
- Evidence-checked model output and snapshot-scoped comparison caching.
- External merchant links and explicit unknown-stock handling.
- A no-key demo-catalog flow that judges can run locally.

PayPal sandbox payments are planned, not implemented, and should not be
presented as a completed feature.

## Tools and how they are used

- **Google Gemini API:** structured JSON shopping-intent extraction and
  evidence-cited product explanations. The configured model is identified by
  `GEMINI_MODEL`; the example configuration uses `gemini-3.8-flash`.
- **SerpApi:** live Google Shopping discovery for US/USD and India/INR markets.
- **FastAPI / Pydantic:** validated API and interactive endpoint documentation.
- **PostgreSQL / SQLAlchemy / Alembic:** persistent data and schema migrations.
- **HTML / CSS / JavaScript:** browser interface and API orchestration.
- **Docker Compose:** local database provisioning.
- **pytest / httpx:** automated validation of providers and complete API flows.

## Source and functional demo

- Public source: https://github.com/Vaibhavi-2k3/Spendpilot_AI
- License: [MIT](../LICENSE).
- Runnable build: follow [README setup and judge walkthrough](../README.md).
- Hosted demo URL: not published; use the documented local build.

The local demo creates real database records and calls the actual application
API. Optional external integrations require judges' own provider credentials.

## Demo video outline — target 2 minutes 40 seconds

The video still needs to be recorded and uploaded publicly to YouTube. Add its
actual URL to the submission form and README after publication.

| Time | Show on screen | Explain |
| --- | --- | --- |
| 0:00–0:20 | The running browser interface | The problem: comparing shopping options within a budget. |
| 0:20–0:50 | Enter a request, budget, currency, and source; submit | A real session is created and products are discovered. |
| 0:50–1:25 | Product cards, prices, scores, and listing links | Budget filtering, persistence, and comparison functionality. |
| 1:25–2:05 | Gemini intent and explanation panels, if successfully configured | Focused search, cited listing evidence, and a suggested pick. Clearly identify fallback if it is being used. |
| 2:05–2:25 | API docs or readiness check, then the public repository | Working backend, reproducible setup instructions, and open-source license. |
| 2:25–2:40 | Return to the functioning shopping interface | Recap the implemented features and current scope. |

Record the actual working desktop-browser application. Use the built-in demo
catalog and your own narration to avoid including third-party product imagery,
logos, or copyrighted music/material without permission. Keep the finished
video under three minutes and make its YouTube visibility **Public**.
