'use strict';
(() => {
  const API = (window.AI_API_URL || '').replace(/\/$/, '');
  const $ = id => document.getElementById(id);
  const form = $('research-form');
  const question = $('research-question');
  const status = $('research-status');
  const output = $('research-output');
  const submit = $('research-submit');
  const badge = $('state-badge');
  const description = $('monitor-description');
  const orb = $('orb');
  const elapsed = $('elapsed');
  const polls = $('polls');
  const providerState = $('provider-state');
  const copy = $('copy-result');
  let answer = '';
  let running = false;
  const sleep = ms => new Promise(resolve => setTimeout(resolve, ms));
  const fmt = ms => `${String(Math.floor(ms / 60000)).padStart(2, '0')}:${String(Math.floor(ms / 1000) % 60).padStart(2, '0')}`;
  function show(state, title, detail) {
    badge.textContent = state.toUpperCase();
    badge.className = 'state-badge' + (state === 'completado' ? ' done' : state === 'error' ? ' error' : state === 'en curso' ? ' running' : '');
    status.textContent = title;
    description.textContent = detail;
    orb.classList.toggle('active', state === 'en curso');
  }
  async function jsonResponse(response) {
    let data;
    try { data = await response.json(); } catch { throw new Error(`Respuesta no válida (HTTP ${response.status})`); }
    if (!response.ok) throw new Error(typeof data.detail === 'string' ? data.detail : `HTTP ${response.status}`);
    return data;
  }
  question.addEventListener('input', () => $('char-count').textContent = `${question.value.length} / 1200`);
  document.querySelectorAll('[data-example]').forEach(button => button.addEventListener('click', () => {
    question.value = button.dataset.example;
    question.dispatchEvent(new Event('input'));
    question.focus();
  }));
  copy.addEventListener('click', async () => {
    if (!answer) return;
    try { await navigator.clipboard.writeText(answer); copy.textContent = 'Copiado ✓'; }
    catch { copy.textContent = 'No se pudo copiar'; }
  });
  async function health() {
    if (!API) { $('api-state').textContent = 'API sin configurar'; $('api-dot').className = 'dot bad'; return; }
    try {
      const res = await fetch(`${API}/health`, {cache:'no-store', signal: AbortSignal.timeout(15000)});
      const data = await jsonResponse(res);
      const ok = data.configured === true;
      $('api-state').textContent = ok ? 'API configurada' : 'API sin configurar';
      $('api-dot').className = `dot ${ok ? 'ok' : 'bad'}`;
    } catch { $('api-state').textContent = 'API no disponible'; $('api-dot').className = 'dot bad'; }
  }
  form.addEventListener('submit', async event => {
    event.preventDefault();
    if (running) return;
    if (!API) { show('error', 'API sin configurar', 'Revisá config.js.'); return; }
    const message = question.value.trim();
    if (message.length < 5) { show('error', 'Consulta demasiado corta', 'Escribí al menos cinco caracteres.'); return; }
    running = true; submit.disabled = true; copy.disabled = true; copy.textContent = 'Copiar resultado';
    answer = ''; output.textContent = 'Esperando respuesta del agente…';
    let count = 0; const start = Date.now(); polls.textContent = '0'; providerState.textContent = '—';
    show('en curso', 'Iniciando investigación…', 'Conectando con Gemini Interactions API.');
    const timer = setInterval(() => elapsed.textContent = fmt(Date.now() - start), 1000);
    try {
      const created = await jsonResponse(await fetch(`${API}/api/research`, {
        method:'POST', headers:{'Content-Type':'application/json'}, body:JSON.stringify({message})
      }));
      if (!created.task) throw new Error('El servidor no devolvió un identificador de tarea.');
      providerState.textContent = String(created.status || 'pending').slice(0, 20);
      show('en curso', 'Investigación en proceso', 'La tarea está en segundo plano. Consultando su estado cada 7 segundos.');
      const deadline = Date.now() + 10 * 60 * 1000;
      while (Date.now() < deadline) {
        await sleep(7000);
        const data = await jsonResponse(await fetch(`${API}/api/research/${encodeURIComponent(created.task)}`));
        count++; polls.textContent = String(count);
        const state = String(data.status || 'pending').toLowerCase();
        providerState.textContent = state.slice(0,20);
        if (state === 'completed') {
          answer = data.answer || 'La tarea terminó sin texto de salida.';
          output.textContent = answer;
          copy.disabled = false;
          show('completado', 'Investigación completada', 'Resultado recibido correctamente del servidor.');
          return;
        }
        if (state === 'failed' || state === 'cancelled') {
          output.textContent = data.answer || 'La investigación no se completó.';
          show('error', 'Investigación no completada', `El proveedor devolvió el estado ${state}.`);
          return;
        }
        show('en curso', 'Investigación en proceso', `Estado informado por Google: ${state}.`);
      }
      show('en espera', 'Tiempo de espera agotado', 'La página dejó de consultar después de 10 minutos; la tarea podría continuar en Google.');
    } catch (error) {
      output.textContent = 'No se pudo obtener el resultado.';
      show('error', 'Error de investigación', error.message);
    } finally {
      clearInterval(timer); elapsed.textContent = fmt(Date.now() - start);
      running = false; submit.disabled = false;
    }
  });
  health();
})();
