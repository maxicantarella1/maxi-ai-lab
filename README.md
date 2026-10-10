# Maxi AI Lab — módulo multiagente experimental

Implementa una **cadena secuencial de tres llamadas LLM**, con roles investigador, evaluador y coordinador. No es CrewAI ni Amazon Bedrock, no navega por la web, y no incorpora todavía trazas OpenTelemetry. Incluye métricas reales de duración y un ID de correlación; no expone consumo de tokens.

## Instalación

1. Copiá `backend/multiagent.py` a tu repositorio, dentro de `backend/`.
2. En `backend/main.py`, agregá `from backend.multiagent import router as multiagent_router` **si tu comando de Render inicia `uvicorn backend.main:app`**. Si inicia `uvicorn main:app` desde `backend/`, usá `from multiagent import router as multiagent_router`.
3. Después de crear `app = FastAPI(...)`, agregá `app.include_router(multiagent_router)`.
4. Confirmá que Render tenga `GEMINI_API_KEY` y, opcionalmente, `MULTIAGENT_MODEL=gemini-2.5-flash`.
5. Probá desde `/docs` el endpoint `POST /api/multiagent/run` con `{ "message": "Explicá una arquitectura multiagente con sus riesgos" }`.

**Seguridad:** El endpoint es público y puede consumir cuota y dinero por cada ejecución (tres llamadas). No lo publiques para uso abierto sin autenticación, rate limiting y límites de gasto. Para pruebas, protegelo antes de desplegarlo o ejecutalo en un entorno privado. El endpoint no guarda datos en base de datos.
