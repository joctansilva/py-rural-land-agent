import time
from pathlib import Path

import geopandas as gpd
import psycopg
import structlog
from shapely import set_srid, to_wkb
from shapely.geometry import MultiPolygon

from src.config import settings

logger = structlog.get_logger(__name__)

# Nomes reais do shapefile AREA_IMOVEL_1.shp → colunas do banco
COLUMN_MAP = {
    "cod_imovel": "cod_imovel",
    "municipio":  "municipio",
    "cod_estado": "uf",
    "num_area":   "area_ha",
    "ind_status": "status",
    "mod_fiscal": "modulos_fiscais",
    "ind_tipo":   "tipo_imovel",
}

STATUS_NORMALIZE = {
    "AT": "ativo",
    "PE": "pendente",
    "CA": "cancelado",
    "SU": "suspenso",
}


def _to_multipolygon(geom) -> MultiPolygon:
    if geom.geom_type == "MultiPolygon":
        return geom
    if geom.geom_type == "Polygon":
        return MultiPolygon([geom])
    raise ValueError(f"Tipo de geometria não suportado: {geom.geom_type}")


def _to_ewkb_hex(geom, srid: int = 4674) -> str:
    return to_wkb(set_srid(geom, srid), hex=True, include_srid=True)


def load_geodataframe(file_path: Path) -> gpd.GeoDataFrame:
    log = logger.bind(file=str(file_path))
    log.info("reading_geodata")

    gdf = gpd.read_file(file_path)

    if gdf.crs is None:
        gdf = gdf.set_crs(epsg=4674)
    elif gdf.crs.to_epsg() != 4674:
        log.warning("reprojecting", from_crs=gdf.crs.to_string(), to_crs="EPSG:4674")
        gdf = gdf.to_crs(epsg=4674)

    log.info("geodata_loaded", rows=len(gdf), crs=str(gdf.crs))
    return gdf


def normalize(gdf: gpd.GeoDataFrame) -> gpd.GeoDataFrame:
    # Normaliza nomes de colunas (lowercase) antes de remapear
    gdf.columns = [c.lower() for c in gdf.columns]

    rename = {k: v for k, v in COLUMN_MAP.items() if k in gdf.columns and k != v}
    if rename:
        gdf = gdf.rename(columns=rename)

    # Após rename, a coluna geometry ainda se chama "geometry" — registra explicitamente
    gdf = gdf.set_geometry("geometry")

    # Normaliza status (AT → ativo, etc.)
    if "status" in gdf.columns:
        raw = gdf["status"].astype(str).str.strip().str.upper()
        unknown = set(raw.unique()) - set(STATUS_NORMALIZE.keys())
        if unknown:
            logger.warning("unknown_status_codes", values=sorted(unknown), fallback="ativo")
        gdf["status"] = raw.map(lambda v: STATUS_NORMALIZE.get(v, "ativo"))

    # Remove linhas sem geometria
    before = len(gdf)
    gdf = gdf[gdf.geometry.notna() & ~gdf.geometry.is_empty].copy()
    dropped = before - len(gdf)
    if dropped:
        logger.warning("dropped_empty_geometries", count=dropped)

    # Converte Polygon → MultiPolygon (tabela exige MULTIPOLYGON)
    gdf["geom"] = gdf.geometry.apply(_to_multipolygon)

    # Remove duplicatas de cod_imovel (shapefile pode ter registros repetidos)
    before = len(gdf)
    gdf = gdf.drop_duplicates(subset=["cod_imovel"], keep="first")
    dupes = before - len(gdf)
    if dupes:
        logger.warning("dropped_duplicate_cod_imovel", count=dupes)

    return gdf


def ingest(file_path: Path, batch_size: int = 10_000) -> None:
    start = time.perf_counter()
    log = logger.bind(file=str(file_path))

    gdf = load_geodataframe(file_path)
    gdf = normalize(gdf)

    required_cols = ["cod_imovel", "municipio", "uf", "status", "geom"]
    missing = [c for c in required_cols if c not in gdf.columns]
    if missing:
        raise ValueError(f"Colunas obrigatórias ausentes: {missing}. Disponíveis: {gdf.columns.tolist()}")

    db_columns = [
        "cod_imovel", "nome_fazenda", "municipio", "uf",
        "area_ha", "status", "modulos_fiscais", "tipo_imovel", "geom",
    ]

    log.info("starting_bulk_copy", rows=len(gdf), batch_size=batch_size)

    total_inserted = 0

    with psycopg.connect(settings.database_url) as conn:
        conn.execute("TRUNCATE TABLE fazendas RESTART IDENTITY CASCADE")
        conn.commit()

        with conn.cursor() as cur:
            with cur.copy(f"COPY fazendas ({', '.join(db_columns)}) FROM STDIN") as copy:
                for row in gdf.itertuples(index=False):
                    copy.write_row((
                        getattr(row, "cod_imovel", None),
                        None,  # nome_fazenda — não existe no dataset
                        getattr(row, "municipio", None),
                        getattr(row, "uf", None),
                        getattr(row, "area_ha", None),
                        getattr(row, "status", "ativo"),
                        getattr(row, "modulos_fiscais", None),
                        getattr(row, "tipo_imovel", None),
                        _to_ewkb_hex(row.geom),
                    ))

                    total_inserted += 1
                    if total_inserted % batch_size == 0:
                        log.info("progress", inserted=total_inserted, total=len(gdf))

        conn.commit()

    elapsed = time.perf_counter() - start
    log.info(
        "ingestion_complete",
        total=total_inserted,
        elapsed_s=round(elapsed, 2),
        rows_per_sec=round(total_inserted / elapsed if elapsed > 0 else 0),
    )
