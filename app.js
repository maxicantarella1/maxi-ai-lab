
'use strict';

const el = id => document.getElementById(id);

// VALIDACIÓN JSON
el('validate').addEventListener('click', () => {
  try {
    const obj = JSON.parse(el('json').value);
    const errors = [];

    if (typeof obj.name !== 'string' || !obj.name.trim()) {
      errors.push('name: texto no vacío requerido');
    }

    if (
      typeof obj.email !== 'string' ||
      !/^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(obj.email)
    ) {
      errors.push('email: formato inválido');
    }

    if (!Number.isInteger(obj.quantity) || obj.quantity < 1) {
      errors.push('quantity: entero positivo requerido');
    }

    el('validation').textContent = JSON.stringify(
      errors.length
        ? { status: 422, errors }
        : { status: 200, data: obj },
      null,
      2
    );
  } catch (error) {
    el('validation').textContent =
      'JSON inválido: ' + error.message;
  }
});

// PROCESAMIENTO CSV
el('process').addEventListener('click', () => {
  const lines = el('csv').value
    .trim()
    .split(/\r?\n/)
    .map(line => line.split(',').map(cell => cell.trim()));

  if (!lines.length || lines[0].join(',') !== 'id,name') {
    el('csvResult').textContent = 'Encabezado esperado: id,name';
    return;
  }

  const seen = new Set();
  const records = [];
  const invalidLines = [];
  let duplicates = 0;

  lines.slice(1).forEach((row, i) => {
    if (row.length !== 2 || !row[0] || !row[1]) {
      invalidLines.push(i + 2);
      return;
    }

    if (seen.has(row[0])) {
      duplicates++;
      return;
    }

    seen.add(row[0]);

    records.push({
      id: row[0],
      name: row[1]
    });
  });

  el('csvResult').textContent = JSON.stringify(
    {
      uniqueRecords: records.length,
      duplicates,
      invalidLines,
      records
    },
    null,
    2
  );
});

// ESTIMADOR DE COSTOS
el('calculate').addEventListener('click', () => {
  const tokens = Number(el('tokens').value);
  const rate = Number(el('rate').value);

  const valid =
    Number.isFinite(tokens) &&
    Number.isFinite(rate) &&
    tokens >= 0 &&
    rate >= 0;

  el('estimate').textContent = valid
    ? 'Costo estimado: USD ' +
      (tokens * rate / 1_000_000).toFixed(6)
    : 'Ingresá valores válidos.';
});

// El agente de investigación se controla
// por separado desde research.js.
