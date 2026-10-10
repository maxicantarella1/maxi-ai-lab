'use strict';
const el = id => document.getElementById(id);
el('validate').addEventListener('click', () => {
  try {
    const obj = JSON.parse(el('json').value);
    const errors = [];
    if (typeof obj.name !== 'string' || !obj.name.trim()) errors.push('name: texto no vacío requerido');
    if (typeof obj.email !== 'string' || !/^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(obj.email)) errors.push('email: formato inválido');
    if (!Number.isInteger(obj.quantity) || obj.quantity < 1) errors.push('quantity: entero positivo requerido');
    el('validation').textContent = JSON.stringify(errors.length ? {status: 422, errors} : {status: 200, data: obj}, null, 2);
  } catch (error) { el('validation').textContent = 'JSON inválido: ' + error.message; }
});
el('process').addEventListener('click', () => {
  const lines = el('csv').value.trim().split(/\r?\n/).map(line => line.split(',').map(cell => cell.trim()));
  if (!lines.length || lines[0].join(',') !== 'id,name') { el('csvResult').textContent = 'Encabezado esperado: id,name'; return; }
  const seen = new Set(), records = [], invalidLines = []; let duplicates = 0;
  lines.slice(1).forEach((row, i) => {
    if (row.length !== 2 || !row[0] || !row[1]) { invalidLines.push(i + 2); return; }
    if (seen.has(row[0])) { duplicates++; return; }
    seen.add(row[0]); records.push({id: row[0], name: row[1]});
  });
  el('csvResult').textContent = JSON.stringify({uniqueRecords: records.length, duplicates, invalidLines, records}, null, 2);
});
el('send').addEventListener('click', async () => {
  const tokens = Number(el('tokens').value), rate = Number(el('rate').value);
  el('estimate').textContent = Number.isFinite(tokens) && Number.isFinite(rate) && tokens >= 0 && rate >= 0
    ? 'Costo estimado: USD ' + (tokens * rate / 1_000_000).toFixed(6) : 'Ingresá valores válidos.';
});
el('send').addEventListener('click', async () => {
  const message = el('prompt').value.trim();
  if (!message) { el('chat').textContent = 'Escribí una consulta.'; return; }
  if (!window.AI_API_URL) { el('chat').textContent = 'Chat no conectado: falta configurar y desplegar la API FastAPI.'; return; }
  try {
    el('chat').textContent = 'Consultando modelo...';
    const response = await fetch(window.AI_API_URL.replace(/\/$/, '') + '/api/chat', {
      method: 'POST', headers: {'Content-Type': 'application/json'}, body: JSON.stringify({message})
    });
    const result = await response.json();
    el('chat').textContent = response.ok ? result.answer : 'Error del servidor: ' + JSON.stringify(result);
  } catch (error) { el('chat').textContent = 'Error de conexión: ' + error.message; }
});
