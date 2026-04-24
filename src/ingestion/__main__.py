from pathlib import Path

import structlog
import typer

from src.ingestion.pipeline import ingest
from src.logging_config import configure_logging

app = typer.Typer()
log = structlog.get_logger()


@app.command()
def main(
    file: Path = typer.Argument(..., help="Caminho para o shapefile ou GeoJSON"),
    batch_size: int = typer.Option(10_000, help="Tamanho do lote para log de progresso"),
) -> None:
    configure_logging()

    if not file.exists():
        typer.echo(f"Arquivo não encontrado: {file}", err=True)
        raise typer.Exit(1)

    log.info("ingestion_started", file=str(file))
    ingest(file, batch_size=batch_size)


if __name__ == "__main__":
    app()
