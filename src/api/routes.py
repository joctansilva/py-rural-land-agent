from __future__ import annotations

import asyncio
import json
import time
from functools import lru_cache

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from sse_starlette.sse import EventSourceResponse

from src.agent.agent import Agent, build_agent
from src.logging_config import configure_logging

configure_logging()

app = FastAPI(title="DadosFazenda API", version="0.1.0")


@lru_cache(maxsize=1)
def _get_agent() -> Agent:
    return build_agent()


class ChatRequest(BaseModel):
    pergunta: str


class ChatResponse(BaseModel):
    resposta: str
    tools_chamadas: list[str]
    tempo_s: float


@app.post("/chat", response_model=ChatResponse)
async def chat(body: ChatRequest) -> ChatResponse:
    if not body.pergunta.strip():
        raise HTTPException(status_code=422, detail="Pergunta não pode ser vazia")

    start = time.perf_counter()
    try:
        response = await asyncio.to_thread(_get_agent().run, body.pergunta)
    except Exception as exc:
        raise HTTPException(status_code=502, detail=str(exc))

    return ChatResponse(
        resposta=response.get_content_as_string() or "Sem resposta",
        tools_chamadas=[t.tool_name for t in (response.tools or [])],
        tempo_s=round(time.perf_counter() - start, 3),
    )


@app.get("/health")
async def health() -> dict:
    return {"status": "ok"}


@app.post("/chat/stream")
async def chat_stream(body: ChatRequest):
    if not body.pergunta.strip():
        raise HTTPException(status_code=422, detail="Pergunta não pode ser vazia")

    async def event_generator():
        try:
            async for chunk in _get_agent().arun(body.pergunta, stream=True):
                if hasattr(chunk, "content") and chunk.content:
                    yield {
                        "event": "message",
                        "data": json.dumps({"token": chunk.content}, ensure_ascii=False),
                    }
            yield {"event": "done", "data": json.dumps({"status": "ok"})}
        except Exception as exc:
            yield {"event": "error", "data": json.dumps({"error": str(exc)})}

    return EventSourceResponse(event_generator())
