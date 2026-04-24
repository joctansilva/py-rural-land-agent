from contextlib import contextmanager
from typing import Generator

import psycopg
import structlog

from src.config import settings

logger = structlog.get_logger(__name__)


def get_connection() -> psycopg.Connection:
    return psycopg.connect(settings.database_url)


@contextmanager
def db_cursor() -> Generator[psycopg.Cursor, None, None]:
    with get_connection() as conn:
        with conn.cursor() as cur:
            yield cur
            conn.commit()