from agno.agent import Agent

from src.config import settings
from src.tools.fazendas import (
    buscar_maiores_fazendas,
    buscar_por_area,
    buscar_por_municipio,
    buscar_por_raio,
    buscar_por_status,
    contar_por_area,
    contar_por_municipio,
    detalhes_da_fazenda,
    estatisticas_municipio,
    localizar_por_coordenada,
)

SYSTEM_PROMPT = """
Você é um assistente especializado em dados de imóveis rurais do Brasil (Cadastro Ambiental Rural - CAR).

Responda sempre em português brasileiro, de forma clara e objetiva.

Ao receber uma pergunta:
1. Identifique quais tools são necessárias para responder
2. Chame as tools com os parâmetros corretos
3. Formule uma resposta clara baseada nos dados retornados
4. Se não encontrar dados, diga explicitamente que não foram encontrados registros

Regras:
- Nunca invente dados — use apenas o que as tools retornarem
- Para coordenadas, lembre que o formato é lat (latitude) e lng (longitude)
- Status válidos: ativo, pendente, cancelado, suspenso
- UF sempre em maiúsculas (ex: MT, GO, MS, RS)
""".strip()

_TOOLS = [
    buscar_por_municipio,
    buscar_por_area,
    buscar_maiores_fazendas,
    buscar_por_status,
    localizar_por_coordenada,
    detalhes_da_fazenda,
    estatisticas_municipio,
    contar_por_municipio,
    contar_por_area,
    buscar_por_raio,
]


def _build_model():
    if settings.openai_api_key:
        from agno.models.openai import OpenAIChat
        return OpenAIChat(
            id=settings.agent_model or "gpt-4o-mini",
            api_key=settings.openai_api_key,
            max_tokens=settings.agent_max_tokens,
        )

    if settings.anthropic_api_key:
        from agno.models.anthropic import Claude
        return Claude(
            id=settings.agent_model or "claude-haiku-4-5-20251001",
            api_key=settings.anthropic_api_key,
            max_tokens=settings.agent_max_tokens,
        )

    if settings.google_api_key:
        from agno.models.google import Gemini
        return Gemini(
            id=settings.agent_model or "gemini-2.0-flash",
            api_key=settings.google_api_key,
        )

    raise RuntimeError("Nenhuma chave de LLM configurada.")


def build_agent() -> Agent:
    return Agent(
        model=_build_model(),
        tools=_TOOLS,
        instructions=SYSTEM_PROMPT,
        debug_mode=settings.debug,
        markdown=False,
    )
