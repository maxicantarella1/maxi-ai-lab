import os

import httpx
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field

app = FastAPI(title="Maxi AI Lab API", version="1.0.0")
origins = [origin.strip() for origin in os.getenv("ALLOWED_ORIGINS", "").split(",") if origin.strip()]
app.add_middleware(CORSMiddleware, allow_origins=origins, allow_methods=["GET", "POST"], allow_headers=["Content-Type"])


class ChatRequest(BaseModel):
    message: str = Field(min_length=1, max_length=3000)


@app.get("/health")
def health():
    return {"status": "ok", "llm_configured": bool(os.getenv("OPENAI_API_KEY"))}


@app.post("/api/chat")
async def chat(request: ChatRequest):
    api_key = os.getenv("OPENAI_API_KEY")
    if not api_key:
        raise HTTPException(status_code=503, detail="LLM provider not configured")
    try:
        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.post(
                "https://api.openai.com/v1/chat/completions",
                headers={"Authorization": f"Bearer {api_key}"},
                json={
                    "model": os.getenv("OPENAI_MODEL", "gpt-4o-mini"),
                    "messages": [
                        {"role": "system", "content": "You are a technical assistant for the Maxi AI Lab engineering portfolio. Answer technical questions accurately. Do not fabricate clients or commercial experience."},
                        {"role": "user", "content": request.message},
                    ],
                    "max_tokens": 500,
                },
            )
            response.raise_for_status()
            return {"answer": response.json()["choices"][0]["message"]["content"]}
    except (httpx.HTTPError, KeyError, IndexError, TypeError, ValueError) as exc:
        raise HTTPException(status_code=502, detail="LLM provider request failed") from exc
