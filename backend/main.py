
import os

import httpx
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field

app = FastAPI(title="Maxi AI Lab API", version="1.1.0")

origins = [
    origin.strip()
    for origin in os.getenv("ALLOWED_ORIGINS", "").split(",")
    if origin.strip()
]

app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_methods=["GET", "POST"],
    allow_headers=["Content-Type"],
)


class ChatRequest(BaseModel):
    message: str = Field(min_length=1, max_length=3000)


@app.get("/health")
def health():
    return {
        "status": "ok",
        "provider": "gemini",
        "llm_configured": bool(os.getenv("GEMINI_API_KEY")),
    }


@app.post("/api/chat")
async def chat(request: ChatRequest):
    api_key = os.getenv("GEMINI_API_KEY")
    if not api_key:
        raise HTTPException(
            status_code=503,
            detail="Gemini API key not configured",
        )

    model = os.getenv("GEMINI_MODEL", "gemini-2.5-flash")

    payload = {
        "systemInstruction": {
            "parts": [{
                "text": (
                    "You are the technical assistant for Maxi AI Lab. "
                    "Answer accurately and do not invent professional "
                    "clients or experience."
                )
            }]
        },
        "contents": [{
            "role": "user",
            "parts": [{"text": request.message}],
        }],
        "generationConfig": {
            "maxOutputTokens": 1024,
        },
    }

    try:
        async with httpx.AsyncClient(timeout=45.0) as client:
            response = await client.post(
                f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent",
                headers={
                    "x-goog-api-key": api_key,
                    "Content-Type": "application/json",
                },
                json=payload,
            )
            response.raise_for_status()
            data = response.json()

        parts = data["candidates"][0]["content"]["parts"]
        answer = "".join(
            part.get("text", "") for part in parts
        ).strip()

        if not answer:
            raise ValueError("Empty model response")

        return {"answer": answer}


    except httpx.HTTPStatusError as exc:
        print(
            f"Gemini HTTP error: {exc.response.status_code} "
            f"{exc.response.reason_phrase}",
            flush=True,
        )
        raise HTTPException(
            status_code=502,
            detail="Gemini provider returned an HTTP error",
        ) from exc

    except (httpx.RequestError, KeyError, IndexError, ValueError) as exc:
        print(
            f"Gemini integration error: {type(exc).__name__}",
            flush=True,
        )
        raise HTTPException(
            status_code=502,
            detail="Gemini request failed",
        ) from exc
