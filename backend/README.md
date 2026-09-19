# Backend

The FastAPI service exposes deterministic mock scoring data so the browser
extension can exercise the complete integration path without calling external
data providers.

From the repository root, start it with:

```sh
python -m backend.api.server
```

The API listens at `http://127.0.0.1:8000`. The extension sends the active tab
URL to `POST /analyze`; the backend calculates category and overall scores from
the configured mock source scores. Interactive API documentation is available
at `http://127.0.0.1:8000/docs`.

Run backend tests from the repository root with:

```sh
python -m unittest discover -s backend/tests -v
```
