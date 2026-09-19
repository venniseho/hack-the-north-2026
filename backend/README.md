# Backend

The FastAPI service scores a store for the browser extension. The Reddit source
is real: it researches the store through Backboard web search (needs
`BACKBOARD_API_KEY` in `backend/.env`). Domain age and GPTZero are still
deterministic mock scores.

From the repository root, start it with:

```sh
python -m backend.api.server
```

The API listens at `http://127.0.0.1:8000`. The extension sends the active tab
URL to `POST /analyze`; the backend derives the store's hostname and brand,
researches Reddit, and combines that with the mock sources into category and
overall risk scores. A check takes a while (two LLM calls plus a web search), so
results are cached per domain for 15 minutes. If Reddit research fails or times
out (45s) the Reddit source is reported as `error`; a store with no Reddit posts
is `insufficient-data`, not safe. Either way the other sources still score. Interactive API documentation is available
at `http://127.0.0.1:8000/docs`.

Run backend tests from the repository root with:

```sh
python -m unittest discover -s backend/tests -v
```
