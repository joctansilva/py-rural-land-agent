from unittest.mock import MagicMock, patch

import pytest

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

_MOCK_PATH = "src.database.psycopg.connect"


def _mock_conn(fetchone=None, fetchall=None):
    mock_cur = MagicMock()
    mock_cur.fetchone.return_value = fetchone
    mock_cur.fetchall.return_value = fetchall or []

    mock_conn = MagicMock()
    mock_conn.execute.return_value = mock_cur
    mock_conn.__enter__ = MagicMock(return_value=mock_conn)
    mock_conn.__exit__ = MagicMock(return_value=False)
    return mock_conn


@pytest.mark.integration
def test_agente_chama_localizar_por_coordenada():
    """
    Verifica que, para uma pergunta de geolocalização,
    o agente chama a tool correta e retorna uma resposta coerente.
    """
    with patch(_MOCK_PATH, return_value=_mock_conn(fetchone=FAKE_FAZENDA)):
        agent = build_agent()
        response = agent.run("Qual fazenda está na coordenada -12.545, -55.721?")

    assert response is not None

    content = response.get_content_as_string()
    assert len(content) > 10

    tools_called = [t.tool_name for t in (response.tools or [])]
    assert "localizar_por_coordenada" in tools_called

    assert any(kw in content for kw in ["Sorriso", "MT-5100250-TESTE", "Fazenda Integração"])
