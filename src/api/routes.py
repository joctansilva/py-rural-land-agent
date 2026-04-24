from __future__ import annotations

import asyncio
import json
import threading
import time

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from sse_starlette.sse import EventSourceResponse

from src.agent.agent import build_agent
from src.logging_config import configure_logging

configure_logging()

app = FastAPI(title="DadosFazenda API", version="0.1.0")

_agent = None
_agent_lock = threading.Lock()


def get_agent():
    global _agent
    if _agent is None:
        with _agent_lock:
            if _agent is None:
                _agent = build_agent()
    return _agent


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

    agent = get_agent()
    start = time.perf_counter()
    try:
        response = await asyncio.to_thread(agent.run, body.pergunta)
        elapsed = time.perf_counter() - start

        tools_called = []
        for msg in (getattr(response, "messages", None) or []):
            if hasattr(msg, "tool_calls") and msg.tool_calls:
                tools_called.extend(tc.function.name for tc in msg.tool_calls)

        resposta = getattr(response, "content", None) or "Sem resposta"

    except Exception as exc:
        elapsed = time.perf_counter() - start
        raise HTTPException(status_code=502, detail=str(exc))

    return ChatResponse(
        resposta=resposta,
        tools_chamadas=tools_called,
        tempo_s=round(elapsed, 3),
    )


@app.get("/health")
async def health() -> dict:
    return {"status": "ok"}


@app.post("/chat/stream")
async def chat_stream(body: ChatRequest):
    if not body.pergunta.strip():
        raise HTTPException(status_code=422, detail="Pergunta não pode ser vazia")

    agent = get_agent()

    async def event_generator():
        try:
            async for chunk in agent.arun(body.pergunta, stream=True):
                if hasattr(chunk, "content") and chunk.content:
                    yield {
                        "event": "message",
                        "data": json.dumps({"token": chunk.content}, ensure_ascii=False),
                    }
            yield {"event": "done", "data": json.dumps({"status": "ok"})}
        except Exception as exc:
            yield {"event": "error", "data": json.dumps({"error": str(exc)})}

    return EventSourceResponse(event_generator())
