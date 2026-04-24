-- Habilita a extensão PostGIS (necessário uma vez por banco)
CREATE EXTENSION IF NOT EXISTS postgis;
CREATE EXTENSION IF NOT EXISTS postgis_topology;
CREATE EXTENSION IF NOT EXISTS unaccent;

-- Tabela principal de fazendas
CREATE TABLE IF NOT EXISTS fazendas (
    id             BIGSERIAL    PRIMARY KEY,
    cod_imovel     TEXT         NOT NULL UNIQUE,
    nome_fazenda   TEXT,
    municipio      TEXT         NOT NULL,
    uf             CHAR(2)      NOT NULL,
    area_ha        NUMERIC(14, 4),
    status         TEXT         NOT NULL
                   CHECK (status IN ('ativo', 'pendente', 'cancelado', 'suspenso')),
    modulos_fiscais NUMERIC(10, 4),
    tipo_imovel    TEXT,
    geom           GEOMETRY(MULTIPOLYGON, 4674),  -- pipeline converte Polygon → MultiPolygon na ingestão
    created_at     TIMESTAMPTZ  NOT NULL DEFAULT now()
);

-- Índice espacial GiST para queries geometry (ST_Contains, ST_Intersects, etc.)
CREATE INDEX IF NOT EXISTS idx_fazendas_geom
    ON fazendas USING GIST (geom);

-- Índice funcional para queries geography (ST_DWithin com metros reais)
CREATE INDEX IF NOT EXISTS idx_fazendas_geom_geography
    ON fazendas USING GIST ((geom::geography));

-- Índices B-tree para os filtros mais comuns
CREATE INDEX IF NOT EXISTS idx_fazendas_municipio ON fazendas (municipio);
CREATE INDEX IF NOT EXISTS idx_fazendas_uf        ON fazendas (uf);
CREATE INDEX IF NOT EXISTS idx_fazendas_status    ON fazendas (status);
CREATE INDEX IF NOT EXISTS idx_fazendas_area_ha   ON fazendas (area_ha);

-- Índice composto para consultas municipio+uf (muito comuns)
CREATE INDEX IF NOT EXISTS idx_fazendas_municipio_uf
    ON fazendas (municipio, uf);

-- Estatísticas atualizadas para o planner do Postgres
ANALYZE fazendas;