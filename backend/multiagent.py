"""Demo multiagente secuencial con Gemini. No sustituye el agente existente."""
import asyncio
import os
import time
import uuid
from typing import Literal

from fastapi import APIRouter, HTTPException
from google import genai
from pydantic import BaseModel, Field

router = APIRouter(prefix="/api/multiagent", tags=["multiagent"])

class TaskRequest(BaseModel):
    message: str = Field(min_length=5, max_length=1200)

class AgentStep(BaseModel):
    role: str
    duration_ms: int
    output: str

class TaskResult(BaseModel):
    trace_id: str
    status: Literal["completed"]
    total_duration_ms: int
    steps: list[AgentStep]
    answer: str

PROMPTS = [
    ("researcher", "Sos un investigador. Analizá la pregunta con rigor. Separá hechos de hipótesis. No inventes fuentes ni afirmes haber navegado por Internet."),
    ("reviewer", "Sos un evaluador crítico. Identificá errores, afirmaciones no verificadas, omisiones y mejoras concretas en el borrador."),
    ("coordinator", "Sos un coordinador. Prepará la respuesta final en español, clara y útil, incorporando las críticas. Indicá límites e incertidumbres."),
]

@router.post("/run", response_model=TaskResult)
async def run_multiagent(request: TaskRequest):
    key = os.getenv("GEMINI_API_KEY")
    if not key:
        raise HTTPException(status_code=503, detail="GEMINI_API_KEY no configurada")
    model = os.getenv("MULTIAGENT_MODEL", "gemini-2.5-flash")
    trace_id = str(uuid.uuid4())
    client = genai.Client(api_key=key)
    steps = []
    start = time.perf_counter()
    context = f"Pregunta original:\n{request.message}"
    try:
        for role, instruction in PROMPTS:
            step_start = time.perf_counter()
            response = await asyncio.wait_for(
                asyncio.to_thread(
                    client.models.generate_content,
                    model=model,
                    contents=f"{instruction}\n\n{context}",
                ),
                timeout=45,
            )
            content = response.text or "Sin salida de texto"
            steps.append(AgentStep(role=role, duration_ms=int((time.perf_counter()-step_start)*1000), output=content))
            context += f"\n\nResultado de {role}:\n{content[:8000]}"
        return TaskResult(trace_id=trace_id, status="completed", total_duration_ms=int((time.perf_counter()-start)*1000), steps=steps, answer=steps[-1].output)
    except Exception as exc:
        # No devolver secretos ni prompts internos en errores públicos.
        import logging
        logging.getLogger("maxi_ai_lab").exception("Multiagent failed trace_id=%s", trace_id)
        raise HTTPException(status_code=502, detail=f"Error de ejecución. Referencia: {trace_id}") from exc
