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
from pydantic import BaseModel, Field
from google.genai import errors as genai_errors
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
    # Each stage gets a separate invocation; no fabricated tool use or token counts.
    client = genai.Client(api_key=GEMINI_KEY)
    response = client.models.generate_content(
        model=MODEL,
        contents=prompt,
        config={'system_instruction': instruction, 'max_output_tokens': MAX_TOKENS, 'temperature': 0.25},
    )
    usage = getattr(response, 'usage_metadata', None)
    return (
        response.text or '',
        getattr(usage, 'prompt_token_count', None) if usage else None,
        getattr(usage, 'candidates_token_count', None) if usage else None,
    )


async def stage(role: str, instruction: str, prompt: str) -> Stage:
    started = time.perf_counter()
    if tracer:
        with tracer.start_as_current_span(f'agent.{role}') as span:
            span.set_attribute('agent.role', role)
            span.set_attribute('gen_ai.request.model', MODEL)
            text, in_tokens, out_tokens = await asyncio.wait_for(
                asyncio.to_thread(invoke_llm, instruction, prompt), timeout=75
            )
            if in_tokens is not None:
                span.set_attribute('gen_ai.usage.input_tokens', in_tokens)
            if out_tokens is not None:
                span.set_attribute('gen_ai.usage.output_tokens', out_tokens)
    else:
        text, in_tokens, out_tokens = await asyncio.wait_for(
            asyncio.to_thread(invoke_llm, instruction, prompt), timeout=75
        )
    if not text.strip():
        raise ValueError(f'Empty response in {role}')
    return Stage(role=role, elapsed_ms=round((time.perf_counter()-started)*1000),
                 input_tokens=in_tokens, output_tokens=out_tokens, text=text)


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
    return AgentResult(run_id=run_id, status='completed', model=MODEL, elapsed_ms=elapsed,
        stages=stages,
        total_input_tokens=sum(in_values) if all(v is not None for v in in_values) else None,
        total_output_tokens=sum(out_values) if all(v is not None for v in out_values) else None,
        estimated_cost_usd=None, answer=writer.text)
