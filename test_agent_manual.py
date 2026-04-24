from src.logging_config import configure_logging
from src.agent.agent import build_agent

configure_logging()

agent = build_agent()

resposta = agent.run("Quantas fazendas existem no município de Sorriso em MT?")
print(resposta.content)