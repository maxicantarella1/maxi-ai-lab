import asyncio
import logging
import os
from contextlib import asynccontextmanager
from functools import partial

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from google import genai
from itsdangerous import BadSignature, SignatureExpired, URLSafeTimedSerializer
from pydantic import BaseModel, Field
from backend.enterprise import router as enterprise_router
from backend.database import init_db
from backend.observability import setup_observability

logger = logging.getLogger("maxi_ai_lab")
logging.basicConfig(level=logging.INFO)

API_KEY = os.getenv("GEMINI_API_KEY", "")
AGENT = os.getenv("GEMINI_AGENT", "antigravity-preview-09-2026")
ENVIRONMENT = os.getenv("GEMINI_ENVIRONMENT", "remote")
SIGNING_SECRET = os.getenv("TASK_SIGNING_SECRET", "")
ALLOWED_ORIGINS = [x.strip() for x in os.getenv("ALLOWED_ORIGINS", "").split(",") if x.strip()]

client = genai.Client(api_key=API_KEY) if API_KEY else None
signer = URLSafeTimedSerializer(SIGNING_SECRET, salt="maxi-ai-lab-tasks") if SIGNING_SECRET else None


@asynccontextmanager
async def lifespan(app: FastAPI):
    await asyncio.to_thread(init_db)
    yield


app = FastAPI(
    title="Maxi AI Lab Research API",
    version="2.0.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=ALLOWED_ORIGINS,
    allow_methods=["GET", "POST"],
    allow_headers=["Content-Type"],
)
app.include_router(enterprise_router)
setup_observability(app)
class ResearchRequest(BaseModel):
    message: str = Field(min_length=5, max_length=1200)


def configured():
    if client is None or signer is None:
        raise HTTPException(status_code=503, detail="API not configured")


def create_interaction(message):
    return client.interactions.create(
        agent=AGENT,
        input=message,
        background=True,
        tools=[{"type": "google_search"}, {"type": "url_context"}],
        environment=ENVIRONMENT,
    )


def get_interaction(interaction_id):
    return client.interactions.get(interaction_id)


@app.get("/health")
def health():
    return {"status": "ok", "provider": "gemini-interactions", "configured": bool(client and signer)}



@app.post("/api/research", status_code=202)
async def start_research(request: ResearchRequest):
    configured()

    try:
        interaction = await asyncio.wait_for(
            asyncio.to_thread(
                create_interaction,
                request.message
            ),
            timeout=40
        )

        if not interaction.id:
            raise ValueError("No interaction ID")

        return {
            "task": signer.dumps({"id": interaction.id}),
            "status": str(interaction.status or "pending")
        }

    except Exception as exc:
        logger.error(
            "Research creation failed: %s | Details: %s",
            type(exc).__name__,
            str(exc)[:1000],
        )

        raise HTTPException(
            status_code=502,
            detail="Could not start research; check Render logs"
        ) from exc

@app.get("/api/research/{task}")
async def research_status(task: str):
    configured()
    try:
        data = signer.loads(task, max_age=3600)
        interaction_id = data["id"]
    except (BadSignature, SignatureExpired, KeyError, TypeError) as exc:
        raise HTTPException(status_code=400, detail="Invalid or expired task token") from exc
    try:
        interaction = await asyncio.wait_for(
            asyncio.to_thread(get_interaction, interaction_id), timeout=30
        )
        status = str(interaction.status or "pending").lower()
        if status == "completed":
            return {"status": status, "answer": interaction.output_text or "Completed without text output"}
        if status == "failed":
            return {"status": status, "answer": "Research failed at provider"}
        return {"status": status, "answer": None}
    except Exception as exc:
        logger.warning("Research status failed: %s", type(exc).__name__)
        raise HTTPException(status_code=502, detail="Could not retrieve research status") from exc
