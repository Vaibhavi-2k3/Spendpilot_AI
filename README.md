# SpendPilot AI

[![License: MIT](https://img.shields.io/badge/License-MIT-blue.svg)](LICENSE)

A shopping-assistant MVP with a FastAPI/PostgreSQL backend and a static frontend.
Discover demo or live Google Shopping listings, rank them by query relevance and
budget, and compare the results. Optional Gemini integration interprets shopping
intent and explains the top eligible options with listing-text citations.
Catalog eligibility and baseline ranking remain deterministic. PayPal checkout
is the next integration.

## Features

- Enter a shopping request, maximum budget, and USD or INR currency.
- Search a built-in demo catalog or live Google Shopping listings via SerpApi.
- Save sessions/products in PostgreSQL and compare budget-filtered recommendations.
- Use Gemini to interpret shopping intent and explain eligible products with
  verified listing-text citations, with an explicit rule-based fallback.
- View a responsive browser interface with product cards, comparison summaries,
  suggested picks, and external listing links.

## Tools and AI services

| Tool/service | How the project uses it |
| --- | --- |
| Google Gemini API | Structured shopping-intent extraction and grounded comparisons of up to five eligible products. Model selected by `GEMINI_MODEL`. |
| SerpApi Google Shopping | Retrieves live USD/INR listings, then normalizes prices, merchants, images, and product links. |
| FastAPI and Pydantic | HTTP API, validated request/response contracts, and interactive API documentation. |
| PostgreSQL, SQLAlchemy, Alembic | Persistent shopping data, transactional writes, concurrency controls, and schema migrations. |
| HTML, CSS, JavaScript | Functional browser interface; no frontend build step. |
| Docker Compose | Local PostgreSQL service and persistent database volume. |
| pytest and httpx | Backend/provider tests and API integration verification. |

## Get the source

```shell
git clone https://github.com/Vaibhavi-2k3/Spendpilot_AI.git
cd Spendpilot_AI
```

## Local setup

Requires Python 3.11+ and Docker Compose. Run these commands from the project root.

1. Create and activate a virtual environment:

   ```powershell
   python -m venv .venv
   .\.venv\Scripts\Activate.ps1
   python -m pip install -r backend/requirements.txt
   ```

2. Copy `.env.example` to `.env`. Set matching passwords in `POSTGRES_PASSWORD`
   and `DATABASE_URL`. URL-encode special characters in the URL password. Set
   `SERPAPI_API_KEY` to enable live discovery; demo searches do not need it.
   Set `GEMINI_API_KEY` to enable AI intent analysis and comparisons.

3. Start PostgreSQL:

   ```powershell
   docker compose up -d --wait db
   ```

4. From `backend/`, migrate and start the API:

   ```powershell
   python -m alembic upgrade head
   python -m uvicorn app.main:app --reload
   ```

5. In a separate terminal, serve the frontend from the project root:

   ```powershell
   python -m http.server 5500 --directory frontend
   ```

Open http://127.0.0.1:5500. API documentation is at http://127.0.0.1:8000/docs.
For demo searches select **Demo Catalog** and **USD**. Live search supports USD
and INR. External listings have unverified stock and are comparison-only.

### macOS/Linux terminal commands

Follow the same setup steps above, using these commands for the virtual
environment and configuration copy:

```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -r backend/requirements.txt
cp .env.example .env
```

On Windows, the equivalent configuration-copy command is:

```powershell
Copy-Item .env.example .env
```

Edit `.env` before starting Docker. Run API commands from `backend/`; run the
frontend server from the repository root. Activate the virtual environment in
each new terminal (`source .venv/bin/activate` on macOS/Linux or
`.\.venv\Scripts\Activate.ps1` on Windows, from the repository root).

### Judge walkthrough: working build without API keys

1. Complete local setup and open http://127.0.0.1:5500.
2. Enter **wireless headphones**, budget **100**, currency **USD**, source
   **Demo Catalog**.
3. Click **Find Products**. The app creates a database session, discovers and
   saves matching demo products, ranks them, and displays product cards.
4. With no Gemini key, the interface explicitly identifies the rule-based
   fallback. Add your own Gemini key and restart the API to enable AI analysis.
5. For live search, add your own SerpApi key, restart the API, choose
   **Live Shopping Search**, and try INR with a budget of **5000**.

This is a functioning local build backed by the API and database, not a static
mockup. `/health` checks API liveness; `/ready` checks database connectivity.

### Troubleshooting

- **Cannot connect to API:** start Uvicorn from `backend/`; open the frontend on
  port 5500, which is permitted by the API's local CORS configuration.
- **Database unavailable:** confirm Docker Desktop/the Docker engine is running
  and `docker compose ps` shows a healthy database. The URL uses host port 5433.
- **Database authentication fails after changing `.env`:** PostgreSQL retains
  the password set when its existing volume was initialized. Use that password
  in `DATABASE_URL` or update the database role password intentionally.
- **AI/live search unavailable:** check your own provider key, model access,
  and provider quota. Missing keys do not prevent demo-catalog searches.

## Tests

Create the separate test database once, from the project root:

```powershell
docker compose exec -T db createdb -U spendpilot spendpilot_test_db
```

Then, from `backend/` with the virtual environment activated:

```powershell
python -m scripts.initialize_test_db
python -m pytest -q
python -m alembic check
```

The tests require the local PostgreSQL service. Most database tests roll back
their transactions; concurrency tests use independently committed test sessions
and delete those sessions afterward.

### Verify real SerpApi integration

From `backend/`, run:

```powershell
python -m scripts.verify_live_serpapi
```

This makes one real search per market (USD/INR), exercises session creation,
product saving/retrieval, recommendations, and comparisons through FastAPI,
and verifies that external listings cannot be checked out. It uses
`spendpilot_test_db` and rolls back verification rows.

## Discovery behavior

- Queries are trimmed; supported currencies are USD/INR and budgets are positive
  whole numbers up to 2,147,483,647.
- Provider results are checked against database field sizes and price precision.
- Rediscovery updates existing listings by URL, preserves their IDs, and records
  `last_seen_at`. Listings absent from a later search are retained as historical
  results; their prices and stock are not treated as newly verified.
- Changed/new listings invalidate saved recommendations. Generate recommendations
  again before fetching an updated comparison; the frontend does this automatically.
- Database uniqueness and per-session row locks protect concurrent discovery and
  recommendation writes. Search requests finish before the write lock is acquired.
- Prices support Western grouping and Indian grouping such as `₹1,23,456.00`.
- Products with no matching query terms are excluded from recommendations.

## Gemini shopping intelligence

Add these values to your local `.env` and restart the API:

```dotenv
GEMINI_API_KEY=your-google-ai-studio-key
GEMINI_MODEL=gemini-3.8-flash
```

The integration calls Google's Gemini REST API using the existing `httpx`
dependency. The model is configurable; choose a model that supports structured
JSON output with `generateContent`/`responseJsonSchema`.

The frontend automatically runs this sequence:

1. Create the shopping session with the original query, budget, and currency.
2. `POST /api/shopping-sessions/{id}/intent` extracts a concise search query,
   use case, and stated preferences. The search query drives discovery/ranking;
   Gemini cannot change the entered budget or currency.
3. Discover products and generate baseline recommendations.
4. `POST /api/shopping-sessions/{id}/ai-comparison` explains up to the top five
   eligible products and suggests a pick. Explanations must reference exactly
   those product IDs and cite verbatim text from their names/descriptions.

AI explanations are supplemental: they cannot write prices, stock status,
catalog ranking scores, or checkout eligibility. Prices, stock notices, and
checkout links in the interface always use the catalog response. Listing quotes
are verified against the provided text; natural-language interpretations are
model-generated and are not independent feature/stock verification.

Intent is stored on the session and cannot be changed after discovery. Comparison
responses are cached against their product/context snapshot and model name.
Changed listings invalidate the cache, and a response is discarded if its
snapshot changed during inference. No database connection/row lock is held while
waiting for Gemini. Product descriptions sent to Gemini are capped at 4,000
characters per listing; URLs, images and API credentials are not prompt content.

Without a key, or on timeout, quota failure, blocked/incomplete output, or invalid
citations, the interface explicitly falls back to the original query and
rule-based recommendations. No API credentials or raw provider errors are
returned to the browser. Empty recommendation sets do not trigger a model call.

### Verify real Gemini integration

After configuring the key and migrating both databases, run from `backend/`:

```powershell
python -m scripts.verify_live_gemini
```

This runs real Gemini intent/comparison requests with the demo catalog and
`spendpilot_test_db`, verifies cached comparisons, and rolls back verification
rows. The normal automated test suite mocks Gemini and does not consume quota.

## Current scope and submission

The shopping/discovery/comparison interface is implemented. PayPal sandbox
checkout has an order-model foundation but no payment endpoints or checkout UI
yet. The demo does not process payments.

See [the submission description and demo-video outline](docs/SUBMISSION.md).
Local setup instructions above provide the runnable-build option; no hosted
demo or YouTube video URL has been published in this repository yet.

## License

This project's source code is available under the [MIT License](LICENSE).
Third-party services and remotely returned listing content remain subject to
their respective terms; they are not relicensed by this project's license.
