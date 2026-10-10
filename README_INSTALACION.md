# Maxi AI Lab v3 — Agent Workspace

Versión visual profesional con métricas reales de cliente (tiempo y cantidad de consultas de estado), sin simular trazas internas.

## Archivos

- `index.html`: reemplazar en la raíz de GitHub.
- `styles.css`: agregar en la raíz.
- `research.js`: reemplazar en la raíz.
- `app.js`: **mantener el archivo actual** (validación JSON, CSV, estimador).
- `config.js`: **mantener el archivo actual** con `window.AI_API_URL` apuntando a Render.
- `backend/main.py`: **mantener el backend que ya funciona**.

## Pasos

1. Subí o reemplazá los tres archivos indicados en el repositorio `maxicantarella1/maxi-ai-lab`.
2. Confirmá que GitHub Pages esté habilitado en la rama `main` y carpeta raíz.
3. Abrí `https://maxicantarella1.github.io/maxi-ai-lab/?v=3` para evitar caché antigua.
4. Comprobá `/health` en Render, y probá la investigación.

## Advertencia de seguridad

El endpoint `POST /api/research` del backend actual es público y **no tiene autenticación ni rate limiting**. Una persona podría consumir la cuota de la API. No difundas el enlace hasta agregar control de acceso, límites por usuario/IP, cuotas de costo y monitoreo. Los tokens firmados de tarea no sustituyen autenticación.

El indicador "API configurada" solo indica que el servidor respondió a `/health` con `configured: true`. No garantiza disponibilidad de Google en ese momento.
