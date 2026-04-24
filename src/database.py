from typing import Generator
from contextlib import contextmanager

import psycopg
import psycopg.rows

from src.config import settings


def get_connection() -> psycopg.Connection:
    return psycopg.connect(settings.database_url, row_factory=psycopg.rows.dict_row)
