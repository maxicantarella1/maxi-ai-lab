# Maxi AI Lab — Research Agent (Interactions API)

## Upload
Replace `backend/main.py`, `requirements.txt`, `config.js` in the repository root and add `research.js`. Update `index.html` to include the research form and script (snippet below). Preserve all other portfolio files.

```html
<section class="panel" id="research">
  <h2>Agente de investigación con Gemini</h2>
  <p>Investigaciones con herramientas de Google; las tareas pueden tardar varios minutos.</p>
  <form id="research-form">
    <textarea id="research-question" rows="4" required minlength="5" maxlength="1200" placeholder="¿Qué querés investigar?"></textarea>
    <button id="research-submit" type="submit">Iniciar investigación</button>
  </form>
  <p id="research-status" role="status">Listo</p>
  <pre id="research-output" style="white-space:pre-wrap"></pre>
</section>
<script src="config.js"></script>
<script src="research.js" defer></script>
```

Add the HTML section before `</main>`; place the research.js script AFTER config.js and before `</body>`. Avoid adding config.js twice. The old chat block should be removed or marked inactive; it still calls `/api/chat`, which this backend no longer implements.

## Render variables
GEMINI_API_KEY = secret from Google AI Studio
GEMINI_AGENT = antigravity-preview-09-2026
GEMINI_ENVIRONMENT = remote (recommended initially; use an existing environment ID only if you know it belongs to your account)
TASK_SIGNING_SECRET = random long secret, e.g. `python -c "import secrets; print(secrets.token_urlsafe(48))"`
ALLOWED_ORIGINS = https://maxicantarella1.github.io

Build: pip install -r requirements.txt
Start: uvicorn backend.main:app --host 0.0.0.0 --port $PORT

Test GET /health and then POST /api/research. The task token is a bearer capability; do not share it. Public use needs authentication, quotas, per-IP limits, spending caps, and abuse monitoring before sharing widely. Provider access and billing may vary.
