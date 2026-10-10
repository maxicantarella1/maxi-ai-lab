"""Production-oriented multi-agent demo router for Maxi AI Lab.

Three independently prompted LLM stages; not a CrewAI implementation.
Uses the Gemini generate_content API and optional OpenTelemetry instrumentation.
"""
import asyncio
import logging
import os
import time
import uuid
from collections import defaultdict, deque
from threading import Lock
from typing import Literal

from fastapi import APIRouter, Header, HTTPException, Request
from google import genai
from google.genai import types
from pydantic import BaseModel, Field
from google.genai import errors as genai_errors
from backend.database import SessionLocal, Execution, ExecutionStage
log = logging.getLogger('maxi_ai_lab.enterprise')
router = APIRouter(prefix='/api/enterprise', tags=['multi-agent demo'])
MODEL = os.getenv('GEMINI_MODEL', 'gemini-2.5-flash')
MAX_CONCURRENT = int(os.getenv('MAX_AGENT_CONCURRENT', '2'))
MAX_PER_HOUR = int(os.getenv('MAX_AGENT_PER_HOUR', '8'))
MAX_TOKENS = int(os.getenv('MAX_AGENT_OUTPUT_TOKENS', '600'))
DEMO_TOKEN = os.getenv('AGENT_DEMO_TOKEN', '')
GEMINI_KEY = os.getenv('GEMINI_API_KEY', '')
semaphore = asyncio.Semaphore(MAX_CONCURRENT)
limiter_lock = Lock()
recent = defaultdict(deque)

try:
    from opentelemetry import trace
    tracer = trace.get_tracer('maxi_ai_lab.enterprise')
except ImportError:
    tracer = None


class AgentRequest(BaseModel):
    prompt: str = Field(min_length=10, max_length=900)


class Stage(BaseModel):
    role: str
    elapsed_ms: int
    input_tokens: int | None = None
    output_tokens: int | None = None
    text: str


class AgentResult(BaseModel):
    run_id: str
    status: Literal['completed']
    model: str
    elapsed_ms: int
    stages: list[Stage]
    total_input_tokens: int | None = None
    total_output_tokens: int | None = None
    estimated_cost_usd: float | None = None
    answer: str


def enforce_limit(identity: str) -> None:
    now = time.monotonic()
    with limiter_lock:
        entries = recent[identity]
        while entries and now - entries[0] > 3600:
            entries.popleft()
        if len(entries) >= MAX_PER_HOUR:
            raise HTTPException(429, 'Hourly request limit reached')
        entries.append(now)



def invoke_llm(instruction: str, prompt: str):
    client = genai.Client(
        api_key=GEMINI_KEY,
        http_options=types.HttpOptions(
            timeout=20000,
            retry_options=types.HttpRetryOptions(
                attempts=1
            )
        )
    )

    try:
        response = client.models.generate_content(
            model=MODEL,
            contents=prompt,
            config={
                "system_instruction": instruction,
                "max_output_tokens": MAX_TOKENS,
                "temperature": 0.25
            }
        )

        usage = getattr(response, "usage_metadata", None)

        return (
            response.text or "",
            getattr(usage, "prompt_token_count", None)
            if usage else None,
            getattr(usage, "candidates_token_count", None)
            if usage else None,
        )
    finally:
        client.close()



async def stage(role: str, instruction: str, prompt: str) -> Stage:
    started = time.perf_counter()

    async def execute(span=None):
        for attempt in range(1, 3):
            try:
                result = await asyncio.wait_for(
                    asyncio.to_thread(invoke_llm, instruction, prompt),
                    timeout=25
                )
                if span:
                    span.set_attribute("agent.attempts", attempt)
                return result

            except genai_errors.ServerError as exc:
                status = getattr(exc, "code", None)
                if status not in (500, 502, 503, 504) or attempt == 2:
                    raise

            except genai_errors.ClientError as exc:
                status = getattr(exc, "code", None)
                if status != 429 or attempt == 2:
                    raise

            delay = 2 ** attempt

            log.warning(
                "Gemini temporary failure role=%s attempt=%s/3 "
                "status=%s retry_in_s=%s",
                role, attempt, status, delay
            )

            if span:
                span.add_event("gemini.retry", {
                    "agent.role": role,
                    "retry.attempt": attempt,
                    "http.status_code": status,
                    "retry.delay_seconds": delay
                })

            await asyncio.sleep(delay)

        raise RuntimeError("Retry loop exhausted")

    if tracer:
        with tracer.start_as_current_span(f"agent.{role}") as span:
            span.set_attribute("agent.role", role)
            span.set_attribute("gen_ai.request.model", MODEL)

            try:
                text, in_tokens, out_tokens = await execute(span)
            except Exception as exc:
                span.record_exception(exc)
                raise

            if in_tokens is not None:
                span.set_attribute(
                    "gen_ai.usage.input_tokens", in_tokens
                )
            if out_tokens is not None:
                span.set_attribute(
                    "gen_ai.usage.output_tokens", out_tokens
                )
    else:
        text, in_tokens, out_tokens = await execute()

    if not text.strip():
        raise ValueError(f"Empty response in {role}")

    return Stage(
        role=role,
        elapsed_ms=round((time.perf_counter() - started) * 1000),
        input_tokens=in_tokens,
        output_tokens=out_tokens,
        text=text
    )

@router.get('/health')
def enterprise_health():
    return {'status': 'ok', 'configured': bool(GEMINI_KEY and DEMO_TOKEN), 'model': MODEL}


@router.post('/run', response_model=AgentResult)
async def run_agents(payload: AgentRequest, request: Request, x_demo_token: str | None = Header(default=None)):
    import secrets
    if not GEMINI_KEY or not DEMO_TOKEN:
        raise HTTPException(503, 'Enterprise demo not configured')
    if not x_demo_token or not secrets.compare_digest(x_demo_token, DEMO_TOKEN):
        raise HTTPException(401, 'Invalid demo token')
    # Limit per token AND caller IP; in-memory, per instance. Use Redis for multi-instance deployments.
    identity = request.client.host if request.client else 'unknown'
    enforce_limit(identity)
    if semaphore.locked():
        raise HTTPException(429, 'Demo busy; try again later')
    run_id = str(uuid.uuid4())
    started = time.perf_counter()
    stages = []
    try:
        async with semaphore:
            researcher = await stage('researcher',
                'Act as a careful technical researcher. Explain uncertainty; never invent citations or web access. Produce a concise structured draft.',
                payload.prompt)
            stages.append(researcher)
            critic = await stage('reviewer',
                'Act as a critical reviewer. Identify unsupported assertions, technical gaps and risks. Do not claim to have independently verified external facts.',
                f'User request:\n{payload.prompt}\n\nDraft:\n{researcher.text[:6000]}')
            stages.append(critic)
            writer = await stage('coordinator',
                'Synthesize the draft and critique into a clear final answer. Disclose limitations and do not invent sources.',
                f'User request:\n{payload.prompt}\n\nDraft:\n{researcher.text[:6000]}\n\nReview:\n{critic.text[:5000]}')
            stages.append(writer)
    except Exception as exc:
        log.exception('Multi-agent run failed run_id=%s error_type=%s', run_id, type(exc).__name__)
        raise HTTPException(502, f'Agent execution failed (run_id: {run_id})') from exc
    elapsed = round((time.perf_counter()-started)*1000)
    in_values = [s.input_tokens for s in stages]
    out_values = [s.output_tokens for s in stages]
    log.info('Multi-agent run complete run_id=%s elapsed_ms=%s', run_id, elapsed)
    
    result = AgentResult(
        run_id=run_id,
        status='completed',
        model=MODEL,
        elapsed_ms=elapsed,
        stages=stages,
        total_input_tokens=(
            sum(in_values)
            if all(v is not None for v in in_values)
            else None
        ),
        total_output_tokens=(
            sum(out_values)
            if all(v is not None for v in out_values)
            else None
        ),
        estimated_cost_usd=None,
        answer=writer.text,
    )

    def save_execution():
        if SessionLocal is None:
            log.warning("Database not configured; execution not saved")
            return

        with SessionLocal() as db:
            execution = Execution(
                id=run_id,
                prompt=payload.prompt,
                status=result.status,
                model=result.model,
                elapsed_ms=result.elapsed_ms,
                input_tokens=result.total_input_tokens,
                output_tokens=result.total_output_tokens,
                answer=result.answer,
            )

            for item in result.stages:
                execution.stages.append(
                    ExecutionStage(
                        role=item.role,
                        elapsed_ms=item.elapsed_ms,
                        input_tokens=item.input_tokens,
                        output_tokens=item.output_tokens,
                        text=item.text,
                    )
                )

            db.add(execution)
            db.commit()

    try:
        await asyncio.wait_for(
            asyncio.to_thread(save_execution),
            timeout=10,
        )
        log.info("Execution persistence attempted run_id=%s", run_id)
    except Exception:
        log.exception("Failed to persist execution run_id=%s", run_id)

    return result


@router.get("/history")
async def execution_history(
    x_demo_token: str | None = Header(default=None),
):
    import secrets
    from sqlalchemy import select

    if not DEMO_TOKEN:
        raise HTTPException(503, "Enterprise demo not configured")

    if not x_demo_token or not secrets.compare_digest(
        x_demo_token, DEMO_TOKEN
    ):
        raise HTTPException(401, "Invalid demo token")

    if SessionLocal is None:
        raise HTTPException(503, "Database not configured")

    def load_history():
        with SessionLocal() as db:
            statement = (
                select(Execution)
                .order_by(Execution.created_at.desc())
                .limit(50)
            )
            executions = db.scalars(statement).all()

            return [
                {
                    "run_id": item.id,
                    "created_at": item.created_at.isoformat(),
                    "prompt": item.prompt,
                    "status": item.status,
                    "model": item.model,
                    "elapsed_ms": item.elapsed_ms,
                    "input_tokens": item.input_tokens,
                    "output_tokens": item.output_tokens,
                }
                for item in executions
            ]

    try:
        return await asyncio.wait_for(
            asyncio.to_thread(load_history),
            timeout=10,
        )
    except Exception:
        log.exception("Failed to load execution history")
        raise HTTPException(
            503, "Could not load execution history"
        )



@router.get("/history/{run_id}")
async def execution_detail(
    run_id: uuid.UUID,
    x_demo_token: str | None = Header(default=None),
):
    import secrets
    from sqlalchemy import select
    from sqlalchemy.orm import selectinload

    if not DEMO_TOKEN:
        raise HTTPException(503, "Enterprise demo not configured")

    if not x_demo_token or not secrets.compare_digest(
        x_demo_token, DEMO_TOKEN
    ):
        raise HTTPException(401, "Invalid demo token")

    if SessionLocal is None:
        raise HTTPException(503, "Database not configured")

    def load_detail():
        with SessionLocal() as db:
            statement = (
                select(Execution)
                .options(selectinload(Execution.stages))
                .where(Execution.id == str(run_id))
            )
            item = db.scalar(statement)

            if item is None:
                return None

            return {
                "run_id": item.id,
                "created_at": item.created_at.isoformat(),
                "prompt": item.prompt,
                "status": item.status,
                "model": item.model,
                "elapsed_ms": item.elapsed_ms,
                "input_tokens": item.input_tokens,
                "output_tokens": item.output_tokens,
                "answer": item.answer,
                "stages": [
                    {
                        "role": stage.role,
                        "elapsed_ms": stage.elapsed_ms,
                        "input_tokens": stage.input_tokens,
                        "output_tokens": stage.output_tokens,
                        "text": stage.text,
                    }
                    for stage in item.stages
                ],
            }

    try:
        result = await asyncio.wait_for(
            asyncio.to_thread(load_detail),
            timeout=10,
        )
    except Exception:
        log.exception("Failed to load execution detail")
        raise HTTPException(
            503, "Could not load execution detail"
        )

    if result is None:
        raise HTTPException(404, "Execution not found")

    return result


@router.get("/public/history")
async def public_execution_history():
    from sqlalchemy import select

    if SessionLocal is None:
        raise HTTPException(503, "Database not configured")

    def load_public_history():
        with SessionLocal() as db:
            statement = (
                select(Execution)
                .where(Execution.is_public.is_(True))
                .where(Execution.status == "completed")
                .order_by(Execution.created_at.desc())
                .limit(50)
            )

            executions = db.scalars(statement).all()

            return [
                {
                    "run_id": item.id,
                    "created_at": item.created_at.isoformat(),
                    "prompt": item.prompt,
                    "status": item.status,
                    "model": item.model,
                    "elapsed_ms": item.elapsed_ms,
                    "input_tokens": item.input_tokens,
                    "output_tokens": item.output_tokens,
                }
                for item in executions
            ]

    try:
        return await asyncio.wait_for(
            asyncio.to_thread(load_public_history),
            timeout=10,
        )
    except Exception:
        log.exception("Failed to load public history")
        raise HTTPException(
            503, "Public history temporarily unavailable"
        )


@router.get("/public/history/{run_id}")
async def public_execution_detail(run_id: uuid.UUID):
    from sqlalchemy import select
    from sqlalchemy.orm import selectinload

    if SessionLocal is None:
        raise HTTPException(503, "Database not configured")

    def load_public_detail():
        with SessionLocal() as db:
            statement = (
                select(Execution)
                .options(selectinload(Execution.stages))
                .where(Execution.id == str(run_id))
                .where(Execution.is_public.is_(True))
                .where(Execution.status == "completed")
            )

            item = db.scalar(statement)

            if item is None:
                return None

            return {
                "run_id": item.id,
                "created_at": item.created_at.isoformat(),
                "prompt": item.prompt,
                "status": item.status,
                "model": item.model,
                "elapsed_ms": item.elapsed_ms,
                "input_tokens": item.input_tokens,
                "output_tokens": item.output_tokens,
                "answer": item.answer,
                "stages": [
                    {
                        "role": stage.role,
                        "elapsed_ms": stage.elapsed_ms,
                        "input_tokens": stage.input_tokens,
                        "output_tokens": stage.output_tokens,
                        "text": stage.text,
                    }
                    for stage in item.stages
                ],
            }

    try:
        result = await asyncio.wait_for(
            asyncio.to_thread(load_public_detail),
            timeout=10,
        )
    except Exception:
        log.exception("Failed to load public execution detail")
        raise HTTPException(
            503, "Public detail temporarily unavailable"
        )

    if result is None:
        raise HTTPException(404, "Public execution not found")

    return result

@router.post("/history/{run_id}/publish")
async def publish_execution(
    run_id: uuid.UUID,
    x_demo_token: str | None = Header(default=None),
):
    import secrets
    from sqlalchemy import select

    if not DEMO_TOKEN:
        raise HTTPException(503, "Enterprise demo not configured")

    if not x_demo_token or not secrets.compare_digest(
        x_demo_token, DEMO_TOKEN
    ):
        raise HTTPException(401, "Invalid demo token")

    if SessionLocal is None:
        raise HTTPException(503, "Database not configured")

    def publish():
        with SessionLocal() as db:
            item = db.scalar(
                select(Execution).where(
                    Execution.id == str(run_id)
                )
            )

            if item is None:
                return None

            if item.status != "completed":
                return "not_completed"

            item.is_public = True
            db.commit()

            return {
                "run_id": item.id,
                "is_public": True,
                "message": "Execution published successfully",
            }

    try:
        result = await asyncio.wait_for(
            asyncio.to_thread(publish),
            timeout=10,
        )
    except Exception:
        log.exception("Failed to publish execution")
        raise HTTPException(
            503, "Could not publish execution"
        )

    if result is None:
        raise HTTPException(404, "Execution not found")

    if result == "not_completed":
        raise HTTPException(
            409, "Only completed executions can be published"
        )

    return result
