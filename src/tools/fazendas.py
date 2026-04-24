from __future__ import annotations

from typing import Any

import structlog

from src.database import get_connection

logger = structlog.get_logger(__name__)

_FIELDS_LIST = "cod_imovel, nome_fazenda, municipio, uf, area_ha, status, tipo_imovel"
_FIELDS_DETAIL = (
    "cod_imovel, nome_fazenda, municipio, uf, area_ha, status, "
    "modulos_fiscais, tipo_imovel, "
    "ROUND((ST_Area(geom::geography) / 10000)::numeric, 2) AS area_calculada_ha"
)


def buscar_por_municipio(municipio: str, uf: str, limit: int = 20) -> list[dict[str, Any]]:
    """
    Retorna fazendas de um município específico.

    Args:
        municipio: Nome do município (case-insensitive, aceita parcial)
        uf: Sigla do estado (ex: MT, GO, MS)
        limit: Número máximo de resultados (padrão 20, máx 50)
    """
    limit = min(limit, 50)
    sql = f"""
        SELECT {_FIELDS_LIST}
        FROM fazendas
        WHERE unaccent(municipio) ILIKE unaccent(%s) AND uf = UPPER(%s)
        ORDER BY area_ha DESC NULLS LAST
        LIMIT %s
    """
    with get_connection() as conn:
        rows = conn.execute(sql, (f"%{municipio}%", uf, limit)).fetchall()

    logger.info("buscar_por_municipio", municipio=municipio, uf=uf, found=len(rows))
    return rows


def buscar_por_area(
    area_min_ha: float,
    area_max_ha: float,
    uf: str | None = None,
    limit: int = 20,
) -> list[dict[str, Any]]:
    """
    Retorna fazendas dentro de um intervalo de área em hectares.

    Args:
        area_min_ha: Área mínima em hectares
        area_max_ha: Área máxima em hectares
        uf: Filtro opcional por estado
        limit: Número máximo de resultados (padrão 20, máx 50)
    """
    limit = min(limit, 50)
    params: list[Any] = [area_min_ha, area_max_ha]
    uf_filter = ""

    if uf:
        uf_filter = "AND uf = UPPER(%s)"
        params.append(uf)

    params.append(limit)
    sql = f"""
        SELECT {_FIELDS_LIST}
        FROM fazendas
        WHERE area_ha BETWEEN %s AND %s
        {uf_filter}
        ORDER BY area_ha DESC NULLS LAST
        LIMIT %s
    """
    with get_connection() as conn:
        rows = conn.execute(sql, params).fetchall()

    logger.info("buscar_por_area", min=area_min_ha, max=area_max_ha, uf=uf, found=len(rows))
    return rows


def buscar_por_status(
    status: str,
    uf: str | None = None,
    municipio: str | None = None,
    limit: int = 20,
) -> list[dict[str, Any]]:
    """
    Retorna fazendas filtradas por status.

    Args:
        status: ativo | pendente | cancelado | suspenso
        uf: Filtro opcional por estado
        municipio: Filtro opcional por município
        limit: Número máximo de resultados (padrão 20, máx 50)
    """
    limit = min(limit, 50)
    params: list[Any] = [status.lower()]
    filters = ["status = %s"]

    if uf:
        filters.append("uf = UPPER(%s)")
        params.append(uf)
    if municipio:
        filters.append("unaccent(municipio) ILIKE unaccent(%s)")
        params.append(f"%{municipio}%")

    params.append(limit)
    where = " AND ".join(filters)
    sql = f"""
        SELECT {_FIELDS_LIST}
        FROM fazendas
        WHERE {where}
        ORDER BY area_ha DESC NULLS LAST
        LIMIT %s
    """
    with get_connection() as conn:
        rows = conn.execute(sql, params).fetchall()

    logger.info("buscar_por_status", status=status, uf=uf, municipio=municipio, found=len(rows))
    return rows


def localizar_por_coordenada(lat: float, lng: float) -> dict[str, Any] | None:
    """
    Retorna a fazenda cujo polígono contém o ponto dado.

    Args:
        lat: Latitude em graus decimais (ex: -12.545)
        lng: Longitude em graus decimais (ex: -55.721)
    """
    sql = f"""
        SELECT {_FIELDS_LIST}
        FROM fazendas
        WHERE ST_Contains(geom, ST_SetSRID(ST_MakePoint(%s, %s), 4674))
        LIMIT 1
    """
    with get_connection() as conn:
        row = conn.execute(sql, (lng, lat)).fetchone()  # PostGIS usa (lon, lat)

    logger.info("localizar_por_coordenada", lat=lat, lng=lng, found=row["cod_imovel"] if row else None)
    return row


def buscar_maiores_fazendas(
    uf: str | None = None,
    status: str | None = None,
    limit: int = 10,
) -> list[dict[str, Any]]:
    """
    Retorna as fazendas com maior área, ordenadas da maior para a menor.
    Use esta tool para perguntas como "qual a maior fazenda do RS?",
    "top 10 maiores fazendas ativas", "maior fazenda cancelada do MT", etc.

    Args:
        uf: Filtro opcional por estado (ex: RS, MT, GO)
        status: Filtro opcional — ativo | pendente | cancelado | suspenso
        limit: Número de resultados (padrão 10, máx 50)
    """
    limit = min(limit, 50)
    params: list[Any] = []
    filters: list[str] = []

    if uf:
        filters.append("uf = UPPER(%s)")
        params.append(uf)
    if status:
        filters.append("status = %s")
        params.append(status.lower())

    where = f"WHERE {' AND '.join(filters)}" if filters else ""
    params.append(limit)

    sql = f"""
        SELECT {_FIELDS_LIST}
        FROM fazendas
        {where}
        ORDER BY area_ha DESC NULLS LAST
        LIMIT %s
    """
    with get_connection() as conn:
        rows = conn.execute(sql, params).fetchall()

    logger.info("buscar_maiores_fazendas", uf=uf, status=status, found=len(rows))
    return rows


def contar_por_area(
    area_min_ha: float,
    area_max_ha: float = 999_999_999.0,
    uf: str | None = None,
) -> dict[str, Any]:
    """
    Conta o total de fazendas dentro de um intervalo de área em hectares.
    Use esta tool para perguntas do tipo "quantas fazendas têm mais de X hectares".

    Args:
        area_min_ha: Área mínima em hectares
        area_max_ha: Área máxima em hectares (padrão: sem limite superior)
        uf: Filtro opcional por estado
    """
    params: list[Any] = [area_min_ha, area_max_ha]
    uf_filter = ""
    if uf:
        uf_filter = "AND uf = UPPER(%s)"
        params.append(uf)

    sql = f"""
        SELECT COUNT(*) AS total
        FROM fazendas
        WHERE area_ha BETWEEN %s AND %s
        {uf_filter}
    """
    with get_connection() as conn:
        row = conn.execute(sql, params).fetchone()

    total = row["total"] if row else 0
    logger.info("contar_por_area", min=area_min_ha, max=area_max_ha, uf=uf, total=total)
    return {"total": total, "area_min_ha": area_min_ha, "area_max_ha": area_max_ha, "uf": uf}


def detalhes_da_fazenda(cod_imovel: str) -> dict[str, Any] | None:
    """
    Retorna a ficha completa de uma fazenda pelo código do imóvel (CAR).

    Args:
        cod_imovel: Código do imóvel (CAR)
    """
    sql = f"SELECT {_FIELDS_DETAIL} FROM fazendas WHERE cod_imovel = %s"
    with get_connection() as conn:
        row = conn.execute(sql, (cod_imovel,)).fetchone()

    logger.info("detalhes_da_fazenda", cod_imovel=cod_imovel, found=bool(row))
    return row


def estatisticas_municipio(municipio: str, uf: str) -> dict[str, Any] | None:
    """
    Retorna totais, área e distribuição por status de um município.

    Args:
        municipio: Nome do município
        uf: Sigla do estado
    """
    sql = """
        SELECT
            municipio,
            uf,
            COUNT(*)                              AS total_fazendas,
            ROUND(SUM(area_ha)::NUMERIC, 2)       AS area_total_ha,
            COUNT(*) FILTER (WHERE status = 'ativo')     AS ativas,
            COUNT(*) FILTER (WHERE status = 'pendente')  AS pendentes,
            COUNT(*) FILTER (WHERE status = 'cancelado') AS canceladas,
            COUNT(*) FILTER (WHERE status = 'suspenso')  AS suspensas
        FROM fazendas
        WHERE unaccent(municipio) ILIKE unaccent(%s) AND uf = UPPER(%s)
        GROUP BY municipio, uf
    """
    with get_connection() as conn:
        row = conn.execute(sql, (f"%{municipio}%", uf)).fetchone()

    logger.info("estatisticas_municipio", municipio=municipio, uf=uf, found=bool(row))
    return row


def contar_por_municipio(municipio: str, uf: str | None = None) -> dict[str, Any]:
    """
    Conta o total de fazendas em um município.

    Args:
        municipio: Nome do município
        uf: Sigla do estado (opcional)
    """
    params: list[Any] = [f"%{municipio}%"]
    uf_filter = ""
    if uf:
        uf_filter = "AND uf = UPPER(%s)"
        params.append(uf)

    sql = f"""
        SELECT municipio, uf, COUNT(*) AS total
        FROM fazendas
        WHERE unaccent(municipio) ILIKE unaccent(%s) {uf_filter}
        GROUP BY municipio, uf
        ORDER BY total DESC
    """
    with get_connection() as conn:
        rows = conn.execute(sql, params).fetchall()

    logger.info("contar_por_municipio", municipio=municipio, uf=uf, found=len(rows))
    return {"resultados": rows, "total_municipios_encontrados": len(rows)}


def buscar_por_raio(
    lat: float,
    lng: float,
    raio_km: float,
    limit: int = 20,
) -> list[dict[str, Any]]:
    """
    Retorna fazendas dentro de um raio a partir de uma coordenada.

    Args:
        lat: Latitude do ponto central (ex: -29.452)
        lng: Longitude do ponto central (ex: -51.975)
        raio_km: Raio de busca em quilômetros
        limit: Número máximo de resultados (padrão 20, máx 50)
    """
    limit = min(limit, 50)
    raio_metros = raio_km * 1000

    sql = f"""
        SELECT
            {_FIELDS_LIST},
            ROUND(
                (ST_Distance(
                    geom::geography,
                    ST_SetSRID(ST_MakePoint(%s, %s), 4674)::geography
                ) / 1000)::numeric, 2
            ) AS distancia_km
        FROM fazendas
        WHERE ST_DWithin(
            geom::geography,
            ST_SetSRID(ST_MakePoint(%s, %s), 4674)::geography,
            %s
        )
        ORDER BY distancia_km ASC
        LIMIT %s
    """
    # PostGIS usa (longitude, latitude)
    params = (lng, lat, lng, lat, raio_metros, limit)

    with get_connection() as conn:
        rows = conn.execute(sql, params).fetchall()

    logger.info("buscar_por_raio", lat=lat, lng=lng, raio_km=raio_km, found=len(rows))
    return rows
