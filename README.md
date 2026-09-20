# Sham

**An AI-powered scam detector for online shopping.** Sham is a Chrome extension
that checks whether an online store is legitimate *before* you buy from it.

Scam e-commerce sites lure shoppers with unusually cheap deals, fake reviews,
misleading product claims and AI-generated social proof, and it is hard to tell
a real store from a fake one at a glance. Open the Sham side panel on any store,
run a check, and get a risk score backed by evidence you can read yourself.

Built at Hack the North 2026.

## How it works

```
 ┌───────────────────────┐   POST /analyze    ┌──────────────────────────────┐
 │  Chrome extension     │ ─────────────────▶ │  FastAPI backend             │
 │  (side panel, WXT)    │  url, reviews,     │                              │
 │                       │  instagram links   │  Reddit      Instagram  GPTZero
 │  reads the live tab   │                    │  (Backboard) (Apify)    (AI-text
 │  the user is on       │ ◀───────────────── │                          check)
 └───────────────────────┘  scored breakdown  │  → category + overall risk   │
                                              └──────────────────────────────┘
```

1. The user opens the side panel on a store and clicks scan.
2. The extension reads what only the user's own tab can see: the product
   reviews on the page and any Instagram links. A headless browser on the
   backend would hit the same anti-bot walls that block scrapers, whereas the
   user's tab is already past them.
3. It sends the URL, reviews and links to the backend, which runs three checks
   in parallel. A slow or broken source never fails the whole request.
4. Each check produces a 0-100 **risk score** plus findings (the evidence). The
   scores roll up into categories and one overall risk score.

### Signals

| Category | Weight | Source | What it checks |
| --- | --- | --- | --- |
| Third-Party Reviews | 50% | **Reddit** | An LLM agent searches the web (via [Backboard](https://backboard.io)) for Reddit threads about the store, verifies each post is a real Reddit permalink, and rates severity, from `critical` scam reports to `positive` mentions. |
| Social Proof | 40% | **Instagram comments** | Finds the store's Instagram account (from links on the page, else by searching), pulls recent comments with [Apify](https://apify.com), and flags customers warning others off and copy-pasted comments from many accounts, which suggests manufactured engagement. |
| Site Analysis | 10% | **GPTZero** | Runs the product reviews scraped from the page through [GPTZero](https://gptzero.me) to estimate how many are AI-generated. |

Weights live in [backend/scoring/config.py](backend/scoring/config.py).

**Missing data is not treated as safe.** Every source reports one of four
statuses: `available`, `insufficient-data`, `unavailable` or `error`. A store
nobody has discussed on Reddit is *unknown*, not trustworthy. A source that
didn't report drops out of the weighting and lowers the response's `coverage`
figure, so the UI can show how much of the picture the score is based on.

## Repository layout

| Path | What's in it |
| --- | --- |
| [frontend/](frontend/) | The extension: WXT + React 19 + Tailwind v4. Side-panel UI, review and link extraction from the active tab. |
| [backend/](backend/) | FastAPI service that runs the research and scoring. |
| [backend/agent/](backend/agent/) | Orchestration (`agent.py`) and the research tools for Reddit, Instagram and product reviews. |
| [backend/scoring/](backend/scoring/) | Pure, deterministic scoring: per-source scoring, category and overall aggregation, coverage. |
| [backend/services/](backend/services/) | Thin client for the GPTZero API. |
| [backend/tests/](backend/tests/) | Unit and API integration tests, using fakes for the external services. |

## Getting started

### Prerequisites

- Python 3.10+
- Node.js and npm
- Chrome (the extension uses the side panel API)
- API keys for [Backboard](https://backboard.io), [GPTZero](https://gptzero.me)
  and [Apify](https://apify.com)

### 1. Backend

From the repository root:

```sh
python -m venv .venv
source .venv/bin/activate
pip install -r backend/requirements.txt
cp backend/.env.example backend/.env   # then fill in the keys
python -m backend.api.server
```

| Variable | Used for |
| --- | --- |
| `BACKBOARD_API_KEY` | Reddit research and the Instagram comment review |
| `APIFY_API_TOKEN` | Scraping Instagram profiles and comments |
| `GPTZERO_API_KEY` | AI-generated review detection |
| `LOG_LEVEL` | Optional. Log level for backend loggers (default `INFO`). |

The API listens on `http://127.0.0.1:8000`, with interactive docs at
`http://127.0.0.1:8000/docs`. A missing key doesn't stop the server; it just
makes the affected source report `error` or `unavailable`.

### 2. Extension

```sh
cd frontend
npm install
cp .env.example .env    # WXT_API_BASE_URL defaults to http://localhost:8000
npm run dev             # launches Chrome with the extension loaded
```

Click the Sham toolbar icon on a store's page to open the side panel, then run a
scan. To install a production build instead, run `npm run build` and load
`frontend/.output/chrome-mv3` as an unpacked extension at `chrome://extensions`.

Other scripts: `npm run compile` (typecheck), `npm run zip` (package for
upload), and `dev:firefox` / `build:firefox` for Firefox builds.

## API

### `POST /analyze`

```jsonc
// request
{
  "currentUrl": "https://example-store.com/products/widget",
  "instagramLinks": ["https://instagram.com/examplestore"], // optional
  "reviews": ["Great product, arrived fast."],              // optional
  "via": "widget:judgeme"                                   // optional
}
```

`reviews` and `instagramLinks` are optional. Without reviews, GPTZero reports
`insufficient-data`. Without Instagram links, the backend tries to find the
account itself.

The response contains `store.domain` and a `scoring` object with `overallRisk`
(0-100, or `null` if nothing could be scored), `coverage`, and per-category
results, each with its source scores, statuses and findings.

Research results are cached in memory per domain. Every Instagram cache miss
spends Apify credit, so those are kept for hours.

## Tests

From the repository root:

```sh
python -m unittest discover -s backend/tests -v
```

The tests use fakes, so they need no API keys or network access.

To try GPTZero scoring on its own against the sample data, run
`python backend/examples/score_reviews.py` (needs `GPTZERO_API_KEY`).

## Tech stack

- **Extension:** [WXT](https://wxt.dev), React 19, Tailwind CSS v4, TypeScript
- **Backend:** Python, FastAPI, Uvicorn, Pydantic
- **Research and detection:** [Backboard](https://backboard.io) (LLM + web
  search), [Apify](https://apify.com) (Instagram scraping),
  [GPTZero](https://gptzero.me) (AI-text detection)

## Roadmap

Planned signals not yet built:

- Trustpilot and other reputable third-party review sites
- AI-generated social media posts used to promote products
- Inconsistent or misleading product specs and claims
- Missing tags and mentions on Instagram and other social platforms (no one else
  is promoting the store)
