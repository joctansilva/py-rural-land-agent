import pytest
from unittest.mock import patch, MagicMock

from src.agent.agent import build_agent


FAKE_FAZENDA = {
    "cod_imovel": "MT-5100250-TESTE",
    "nome_fazenda": "Fazenda Integração",
    "municipio": "Sorriso",
    "uf": "MT",
    "area_ha": 850.0,
    "status": "ativo",
    "tipo_imovel": "IRU",
}


@pytest.mark.integration
def test_agente_chama_localizar_por_coordenada():
    """
    Verifica que, para uma pergunta de geolocalização,
    o agente chama a tool correta e retorna uma resposta coerente.
    """
    with patch("src.tools.fazendas.psycopg.connect") as mock_connect:
        mock_cur = MagicMock()
        mock_cur.fetchone.return_value = FAKE_FAZENDA
        mock_conn = MagicMock()
        mock_conn.execute.return_value = mock_cur
        mock_conn.__enter__ = MagicMock(return_value=mock_conn)
        mock_conn.__exit__ = MagicMock(return_value=False)
        mock_connect.return_value = mock_conn

        agent = build_agent()
        response = agent.run("Qual fazenda está na coordenada -12.545, -55.721?")

    assert response is not None
    content = response.content if hasattr(response, "content") else str(response)
    assert len(content) > 10

    # Verifica que a tool correta foi chamada
    tools_called = []
    for msg in (getattr(response, "messages", None) or []):
        if hasattr(msg, "tool_calls") and msg.tool_calls:
            tools_called.extend(tc.function.name for tc in msg.tool_calls)
    assert "localizar_por_coordenada" in tools_called

    # Resposta deve mencionar dados da fazenda retornada pelo mock
    assert any(kw in content for kw in ["Sorriso", "MT-5100250-TESTE", "Fazenda Integração"])