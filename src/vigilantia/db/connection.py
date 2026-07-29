# src/vigilantia/db/connection.py

from __future__ import annotations

import logging
from contextlib import contextmanager
from typing import Iterator, Optional

import pyodbc

from vigilantia.db.config import DatabaseConfig

logger = logging.getLogger(__name__)

# Comentário de cabeçalho:
# Este módulo é o único ponto do projeto que abre ligações reais ao SQL
# Server. Usa um context manager para garantir commit/rollback e fecho da
# ligação, mesmo em caso de exceção — os repositórios (repository.py)
# nunca gerem a ligação diretamente, só recebem uma já aberta.


@contextmanager
def get_connection(config: Optional[DatabaseConfig] = None) -> Iterator[pyodbc.Connection]:
    """
    Abre uma ligação ao SQL Server e devolve-a como context manager.

    Em caso de sucesso do bloco 'with', faz commit. Em caso de exceção,
    faz rollback e relança a exceção original. A ligação é sempre fechada
    no fim, com ou sem erro.

    :param config: Configuração da ligação. Se omitida, é construída a
        partir das variáveis de ambiente (ver DatabaseConfig.from_env).
    :yield: Uma ligação pyodbc.Connection aberta.
    """
    cfg = config or DatabaseConfig.from_env()
    conn_str = cfg.to_connection_string()

    try:
        conn = pyodbc.connect(conn_str, autocommit=False)
    except pyodbc.Error as exc:
        logger.error("Falha ao ligar à base de dados %s@%s: %s", cfg.database, cfg.server, exc)
        raise

    try:
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()
