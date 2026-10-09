# Maxi AI Lab

Technical engineering portfolio by Máximo Valentín Cantarella. Includes three interactive browser demos and an optional FastAPI-backed LLM chat. **The AI chat is not live until a backend is deployed and configured.**

## Static site (GitHub Pages)

1. Upload the root files `index.html`, `app.js`, `config.js` and this README to the repository. Upload the `backend` folder and the other configuration files too.
2. In GitHub repository Settings → Pages → Build and deployment, choose Deploy from a branch, `main`, `/ (root)`, then Save.
3. After GitHub finishes publishing, open `https://maxicantarella1.github.io/maxi-ai-lab/`.

## FastAPI backend

Run locally:

```bash
python -m pip install -r requirements.txt
uvicorn backend.main:app --reload
```

`GET /health` is available without credentials. `POST /api/chat` needs `OPENAI_API_KEY` configured on the server. Interactive API documentation: `/docs`.

To deploy, connect the repository to Render and use the included `render.yaml` blueprint (or configure the Python web service manually). Set `OPENAI_API_KEY` as a secret environment variable. Restrict `ALLOWED_ORIGINS` to the frontend origin. When the HTTPS backend URL is known, edit `config.js` to set `window.AI_API_URL = 'https://YOUR-REAL-BACKEND-HOST';` and commit it.

**Security:** Never put an API key in `config.js`, GitHub, or frontend JavaScript. Before sharing a publicly usable chat, add authentication, per-user rate limiting, abuse monitoring, and a spending cap at the model provider. A public unauthenticated endpoint can incur unexpected costs.

## Scope and limitations

- JSON validation demo: client-side type and format validation.
- CSV demo: simple comma-delimited input, deduplicated by ID (not a full quoted-field CSV parser).
- Token calculator: user-provided price; not a live price quote.
- LLM chat: real provider request **only after deployment and API configuration**.
- No CrewAI, Bedrock, OpenTelemetry, or production multi-agent implementation is claimed in this initial release.
