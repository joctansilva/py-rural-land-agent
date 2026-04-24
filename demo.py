import time
from dataclasses import dataclass, field

import typer
import structlog

from src.logging_config import configure_logging
from src.agent.agent import build_agent

configure_logging()
logger = structlog.get_logger(__name__)

app = typer.Typer()


@dataclass
class QuestionResult:
    index: int
    question: str
    answer: str
    elapsed_s: float
    tools_called: list[str] = field(default_factory=list)


SEPARATOR = "─" * 70


def run_question(agent, index: int, question: str) -> QuestionResult:
    print(f"\n{SEPARATOR}")
    print(f"[{index}] {question}")
    print(SEPARATOR)

    start = time.perf_counter()
    try:
        response = agent.run(question)
        elapsed = time.perf_counter() - start

        tools_called = [t.tool_name for t in (response.tools or [])]
        answer = response.get_content_as_string() or str(response)

    except Exception as exc:
        elapsed = time.perf_counter() - start
        answer = f"ERRO: {exc}"
        tools_called = []

    print(f"\nResposta: {answer}")
    print(f"Tools: {', '.join(tools_called) if tools_called else 'nenhuma registrada'}")
    print(f"Tempo: {elapsed:.2f}s")

    return QuestionResult(
        index=index,
        question=question,
        answer=answer,
        elapsed_s=elapsed,
        tools_called=tools_called,
    )


@app.command()
def main(
    cod_imovel: str = typer.Option(
        None,
        "--cod-imovel",
        help="Código real de um imóvel do dataset para a pergunta 6",
    ),
) -> None:
    agent = build_agent()

    # Se não informado, a pergunta fica com placeholder e o agente buscará o primeiro disponível
    pergunta_6_cod = cod_imovel or "<substitua por um cod_imovel real do seu dataset>"

    perguntas = [
        "Quantas fazendas existem no município de Lajeado/RS?",
        "Liste as 10 maiores fazendas ativas em RS.",
        "Me dá um resumo das fazendas com status pendente em Venâncio Aires.",
        "Qual fazenda está na coordenada -12.545, -55.721?",
        "Quantas fazendas acima de 500 hectares existem?",
        f"Quais os detalhes da fazenda de código {pergunta_6_cod}?",
        "Qual o CAR da maior fazenda do RS?",
        "Qual a maior fazenda cancelada?",
    ]

    results: list[QuestionResult] = []

    print("\n" + "=" * 70)
    print("  DEMO — DadosFazenda Agente de Consulta Geoespacial")
    print("=" * 70)

    for i, pergunta in enumerate(perguntas, start=1):
        result = run_question(agent, i, pergunta)
        results.append(result)

    # Resumo final
    print(f"\n{'=' * 70}")
    print("  RESUMO")
    print("=" * 70)

    total_time = sum(r.elapsed_s for r in results)
    slow = [r for r in results if r.elapsed_s > 30]

    print(f"Total de perguntas: {len(results)}")
    print(f"Tempo total:        {total_time:.2f}s")
    print(f"Tempo médio:        {total_time / len(results):.2f}s")
    print(f"Perguntas > 30s:    {len(slow)}")

    if slow:
        print("\nAtenção — perguntas acima do limite de 30s:")
        for r in slow:
            print(f"  [{r.index}] {r.elapsed_s:.2f}s — {r.question[:60]}")


if __name__ == "__main__":
    app()