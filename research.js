const API = (window.AI_API_URL || '').replace(/\/$/, '');
const form = document.getElementById('research-form');
const question = document.getElementById('research-question');
const status = document.getElementById('research-status');
const output = document.getElementById('research-output');
const submit = document.getElementById('research-submit');
const sleep = ms => new Promise(resolve => setTimeout(resolve, ms));

async function jsonResponse(response) {
  let body;
  try { body = await response.json(); } catch { throw new Error('Respuesta no válida del servidor'); }
  if (!response.ok) throw new Error(typeof body.detail === 'string' ? body.detail : `HTTP ${response.status}`);
  return body;
}

form.addEventListener('submit', async event => {
  event.preventDefault();
  if (!API) { status.textContent = 'Backend sin configurar'; return; }
  submit.disabled = true;
  output.textContent = '';
  try {
    status.textContent = 'Iniciando investigación...';
    const started = await jsonResponse(await fetch(`${API}/api/research`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ message: question.value.trim() })
    }));
    const token = started.task;
    const deadline = Date.now() + 10 * 60 * 1000;
    while (Date.now() < deadline) {
      await sleep(7000);
      const result = await jsonResponse(await fetch(`${API}/api/research/${encodeURIComponent(token)}`));
      status.textContent = `Estado: ${result.status}`;
      if (result.status === 'completed') {
        output.textContent = result.answer || 'Sin respuesta de texto';
        return;
      }
      if (result.status === 'failed' || result.status === 'cancelled') {
        output.textContent = result.answer || 'La investigación no pudo completarse';
        return;
      }
    }
    status.textContent = 'La investigación sigue pendiente. Se detuvo la espera en esta página después de 10 minutos.';
  } catch (error) {
    status.textContent = 'Error: ' + error.message;
  } finally {
    submit.disabled = false;
  }
});
