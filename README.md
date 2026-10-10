# Maxi AI Lab — Job-ready engineering module

This package extends the existing FastAPI backend without replacing the working research endpoint.

## Install (GitHub)
1. Upload `backend/enterprise.py` and `backend/observability.py` into your repository's `backend/` directory.
2. Add the lines in `requirements-enterprise.txt` to your existing `requirements.txt` (do not replace it).
3. In `backend/main.py`, add near the imports:
   ```python
   from backend.enterprise import router as enterprise_router
   from backend.observability import setup_observability
   ```
   Then after `app = FastAPI(...)` and its CORS setup, add:
   ```python
   app.include_router(enterprise_router)
   setup_observability(app)
   ```
4. In Render > Environment, set `AGENT_DEMO_TOKEN` to a long random secret, generated privately. Never place it in GitHub or browser JS. Existing `GEMINI_API_KEY` is reused. Optionally set `GEMINI_MODEL` to a model your key can access.
5. Deploy; visit `/api/enterprise/health`. `configured: true` means credentials are present, not that the model is reachable.
6. Run a private request using a REST client with header `X-Demo-Token` and JSON body `{"prompt":"Explain an enterprise AI agent architecture with tracing and retry strategy."}` to `POST /api/enterprise/run`. Do not share the token in screenshots or logs.
7. Optional: set `OTEL_EXPORTER_OTLP_ENDPOINT` to your authorized collector and redeploy for tracing. Do not put credentials in URLs.

## Tests
Install `pytest` in a local dev environment and run `python -m pytest tests/test_enterprise.py`. Tests are not a substitute for a live integration test.

## Before publishing
The existing research endpoint is publicly callable. Add authenticated access, distributed rate limiting and spending limits before inviting broad usage. Do not add `AGENT_DEMO_TOKEN` to `config.js`, `research.js` or `index.html`.

Read `docs/ARCHITECTURE.md` for accurate technical claims and limitations.
