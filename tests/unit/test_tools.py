from unittest.mock import MagicMock, patch

import pytest

from src.tools.fazendas import (
    buscar_por_municipio,
    buscar_por_area,
    buscar_por_status,
    localizar_por_coordenada,
    estatisticas_municipio,
    detalhes_da_fazenda,
    contar_por_municipio,
    buscar_por_raio,
)


FAKE_FAZENDA = {
    "cod_imovel": "MT-5100250-AAABBBCCC",
    "nome_fazenda": "Fazenda Teste",
    "municipio": "Sorriso",
    "uf": "MT",
    "area_ha": 1200.50,
    "status": "ativo",
    "tipo_imovel": "IRU",
}

FAKE_FAZENDA_DETALHE = {
    **FAKE_FAZENDA,
    "modulos_fiscais": 12.5,
    "area_calculada_ha": 1198.72,
}

FAKE_STATS = {
    "municipio": "Sorriso",
    "uf": "MT",
    "total_fazendas": 450,
    "area_total_ha": 5600000.00,
    "ativas": 380,
    "pendentes": 40,
    "canceladas": 20,
    "suspensas": 10,
}

FAKE_FAZENDA_RAIO = {
    **FAKE_FAZENDA,
    "distancia_km": 12.34,
}


def _mock_conn(fetchall=None, fetchone=None):
    """Helper que retorna um context manager mockado para psycopg.connect."""
    mock_cur = MagicMock()
    mock_cur.fetchall.return_value = fetchall or []
    mock_cur.fetchone.return_value = fetchone

    mock_conn = MagicMock()
    mock_conn.execute.return_value = mock_cur
    mock_conn.__enter__ = MagicMock(return_value=mock_conn)
    mock_conn.__exit__ = MagicMock(return_value=False)
    return mock_conn


class TestBuscarPorMunicipio:
    def test_retorna_lista_de_fazendas(self):
        with patch("src.tools.fazendas.psycopg.connect", return_value=_mock_conn(fetchall=[FAKE_FAZENDA])):
            result = buscar_por_municipio("Sorriso", "MT")

        assert len(result) == 1
        assert result[0]["municipio"] == "Sorriso"

    def test_limit_maximo_e_50(self):
        with patch("src.tools.fazendas.psycopg.connect", return_value=_mock_conn(fetchall=[])) as mock:
            buscar_por_municipio("Sorriso", "MT", limit=999)
            call_args = mock.return_value.execute.call_args
            params = call_args[0][1]
            assert params[-1] == 50

    def test_municipio_vazio_retorna_lista_vazia(self):
        with patch("src.tools.fazendas.psycopg.connect", return_value=_mock_conn(fetchall=[])):
            result = buscar_por_municipio("CidadeInexistente", "XX")

        assert result == []


class TestBuscarPorArea:
    def test_retorna_fazendas_no_intervalo(self):
        with patch("src.tools.fazendas.psycopg.connect", return_value=_mock_conn(fetchall=[FAKE_FAZENDA])):
            result = buscar_por_area(500, 2000)

        assert len(result) == 1
        assert result[0]["area_ha"] == 1200.50

    def test_filtro_uf_opcional(self):
        with patch("src.tools.fazendas.psycopg.connect", return_value=_mock_conn(fetchall=[])) as mock:
            buscar_por_area(100, 500, uf="MT")
            call_args = mock.return_value.execute.call_args
            sql = call_args[0][0]
            assert "UPPER(%s)" in sql


class TestBuscarPorStatus:
    @pytest.mark.parametrize("status", ["ativo", "pendente", "cancelado", "suspenso"])
    def test_aceita_status_validos(self, status: str):
        with patch("src.tools.fazendas.psycopg.connect", return_value=_mock_conn(fetchall=[])):
            result = buscar_por_status(status)
        assert isinstance(result, list)

    def test_com_municipio_e_uf(self):
        with patch("src.tools.fazendas.psycopg.connect", return_value=_mock_conn(fetchall=[FAKE_FAZENDA])):
            result = buscar_por_status("ativo", uf="MT", municipio="Sorriso")
        assert len(result) == 1


class TestLocalizarPorCoordenada:
    def test_retorna_fazenda_quando_encontrada(self):
        with patch("src.tools.fazendas.psycopg.connect", return_value=_mock_conn(fetchone=FAKE_FAZENDA)):
            result = localizar_por_coordenada(lat=-12.545, lng=-55.721)

        assert result is not None
        assert result["cod_imovel"] == "MT-5100250-AAABBBCCC"

    def test_retorna_none_quando_fora_de_qualquer_fazenda(self):
        with patch("src.tools.fazendas.psycopg.connect", return_value=_mock_conn(fetchone=None)):
            result = localizar_por_coordenada(lat=0.0, lng=0.0)

        assert result is None

    def test_coordenada_usa_lon_lat_no_sql(self):
        """PostGIS espera (longitude, latitude) — não (lat, lng)."""
        with patch("src.tools.fazendas.psycopg.connect", return_value=_mock_conn(fetchone=None)) as mock:
            localizar_por_coordenada(lat=-12.545, lng=-55.721)
            call_args = mock.return_value.execute.call_args
            params = call_args[0][1]
            assert params[0] == -55.721  # lng
            assert params[1] == -12.545  # lat


class TestEstatisticasMunicipio:
    def test_retorna_estatisticas_agregadas(self):
        with patch("src.tools.fazendas.psycopg.connect", return_value=_mock_conn(fetchone=FAKE_STATS)):
            result = estatisticas_municipio("Sorriso", "MT")

        assert result is not None
        assert result["total_fazendas"] == 450
        assert result["ativas"] == 380


class TestDetalhesDaFazenda:
    def test_retorna_ficha_completa(self):
        with patch("src.tools.fazendas.psycopg.connect", return_value=_mock_conn(fetchone=FAKE_FAZENDA_DETALHE)):
            result = detalhes_da_fazenda("MT-5100250-AAABBBCCC")

        assert result is not None
        assert result["cod_imovel"] == "MT-5100250-AAABBBCCC"
        assert "area_calculada_ha" in result

    def test_retorna_none_para_codigo_inexistente(self):
        with patch("src.tools.fazendas.psycopg.connect", return_value=_mock_conn(fetchone=None)):
            result = detalhes_da_fazenda("COD-INEXISTENTE")

        assert result is None


class TestContarPorMunicipio:
    def test_retorna_contagem_por_municipio(self):
        fake_row = {"municipio": "Sorriso", "uf": "MT", "total": 450}
        with patch("src.tools.fazendas.psycopg.connect", return_value=_mock_conn(fetchall=[fake_row])):
            result = contar_por_municipio("Sorriso", uf="MT")

        assert result["total_municipios_encontrados"] == 1
        assert result["resultados"][0]["total"] == 450

    def test_sem_uf_retorna_todos_municipios_com_nome(self):
        rows = [
            {"municipio": "Sorriso", "uf": "MT", "total": 450},
            {"municipio": "Sorriso", "uf": "GO", "total": 12},
        ]
        with patch("src.tools.fazendas.psycopg.connect", return_value=_mock_conn(fetchall=rows)):
            result = contar_por_municipio("Sorriso")

        assert result["total_municipios_encontrados"] == 2


class TestBuscarPorRaio:
    def test_retorna_fazendas_dentro_do_raio(self):
        with patch("src.tools.fazendas.psycopg.connect", return_value=_mock_conn(fetchall=[FAKE_FAZENDA_RAIO])):
            result = buscar_por_raio(lat=-29.452, lng=-51.975, raio_km=50)

        assert len(result) == 1
        assert result[0]["distancia_km"] == 12.34

    def test_limit_maximo_e_50(self):
        with patch("src.tools.fazendas.psycopg.connect", return_value=_mock_conn(fetchall=[])) as mock:
            buscar_por_raio(lat=-29.452, lng=-51.975, raio_km=10, limit=999)
            call_args = mock.return_value.execute.call_args
            params = call_args[0][1]
            assert params[-1] == 50

    def test_raio_convertido_para_metros(self):
        """ST_DWithin espera metros, não km."""
        with patch("src.tools.fazendas.psycopg.connect", return_value=_mock_conn(fetchall=[])) as mock:
            buscar_por_raio(lat=-29.452, lng=-51.975, raio_km=50)
            call_args = mock.return_value.execute.call_args
            params = call_args[0][1]
            # raio_metros deve ser o 5º parâmetro (lng, lat, lng, lat, raio_metros, limit)
            raio_metros = params[4]
            assert raio_metros == 50_000

    def test_coordenada_usa_lon_lat_no_sql(self):
        """PostGIS espera (longitude, latitude) — não (lat, lng)."""
        with patch("src.tools.fazendas.psycopg.connect", return_value=_mock_conn(fetchall=[])) as mock:
            buscar_por_raio(lat=-29.452, lng=-51.975, raio_km=10)
            call_args = mock.return_value.execute.call_args
            params = call_args[0][1]
            assert params[0] == -51.975  # lng
            assert params[1] == -29.452  # lat
