# src/vigilantia/db/connection.py

from __future__ import annotations

import logging
import sqlite3
import os
from contextlib import contextmanager
from typing import Iterator, Optional, Union

try:
    import pyodbc
except ImportError:
    class _PyODBCMock:
        class Error(Exception):
            pass
        class Connection:
            pass
        def connect(self, *args, **kwargs):
            raise self.Error("pyodbc não está instalado (faltam C++ Build Tools).")
    pyodbc = _PyODBCMock()

from vigilantia.db.config import DatabaseConfig, DashboardConfig

logger = logging.getLogger(__name__)

# Comentário de cabeçalho:
# Este módulo gere as ligações à base de dados local (SQLite, MSSQL local ou nenhuma)
# e ao dashboard de incidências (MSSQL remoto).
# Automatiza a criação das tabelas SQLite quando o ficheiro da BD é inicializado.


SQLITE_SCHEMA = """
CREATE TABLE IF NOT EXISTS Websites (
    WebsiteId INTEGER PRIMARY KEY AUTOINCREMENT,
    Url TEXT NOT NULL UNIQUE,
    Domain TEXT NOT NULL,
    CreatedAt DATETIME DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS ScanRuns (
    ScanRunId INTEGER PRIMARY KEY AUTOINCREMENT,
    WebsiteId INTEGER NOT NULL,
    ReportRef CHAR(8) NULL,
    StartedAt DATETIME DEFAULT CURRENT_TIMESTAMP,
    FinishedAt DATETIME NULL,
    Status TEXT NOT NULL CHECK(Status IN ('Running', 'Completed', 'Failed')),
    ErrorMessage TEXT NULL,
    FOREIGN KEY(WebsiteId) REFERENCES Websites(WebsiteId)
);

CREATE TABLE IF NOT EXISTS Findings (
    FindingId INTEGER PRIMARY KEY AUTOINCREMENT,
    ScanRunId INTEGER NOT NULL,
    RuleId TEXT NOT NULL,
    Category TEXT NULL,
    Description TEXT NOT NULL,
    Recommendation TEXT NOT NULL,
    EvidenceJson TEXT NOT NULL,
    Status TEXT NOT NULL DEFAULT 'Open',
    CreatedAt DATETIME DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY(ScanRunId) REFERENCES ScanRuns(ScanRunId)
);

CREATE INDEX IF NOT EXISTS IX_Websites_Domain ON Websites (Domain);
CREATE INDEX IF NOT EXISTS IX_ScanRuns_WebsiteId_StartedAt ON ScanRuns (WebsiteId, StartedAt DESC);
CREATE INDEX IF NOT EXISTS IX_Findings_ScanRunId ON Findings (ScanRunId);
CREATE INDEX IF NOT EXISTS IX_Findings_RuleId ON Findings (RuleId);
"""


@contextmanager
def get_connection(
    config: Optional[DatabaseConfig] = None
) -> Iterator[Union[sqlite3.Connection, pyodbc.Connection, None]]:
    """
    Abre uma ligação à base de dados local de acordo com a configuração.
    Pode ser SQLite, SQL Server (MSSQL) ou None.
    
    Se usar SQLite e o ficheiro/tabelas não existirem, são criados no momento.
    """
    cfg = config or DatabaseConfig.from_env()

    if cfg.db_type == "none":
        yield None
        return

    if cfg.db_type == "sqlite":
        db_file = cfg.sqlite_path
        # Garante que a pasta pai existe
        parent_dir = os.path.dirname(os.path.abspath(db_file))
        if parent_dir and not os.path.exists(parent_dir):
            os.makedirs(parent_dir, exist_ok=True)

        try:
            conn = sqlite3.connect(db_file)
            conn.execute("PRAGMA foreign_keys = ON;")
        except Exception as exc:
            logger.error("Falha ao abrir ligação SQLite %s: %s", db_file, exc)
            raise

        # Auto-migração: cria tabelas se não existirem
        try:
            cursor = conn.cursor()
            cursor.execute("SELECT 1 FROM Websites LIMIT 1")
        except sqlite3.OperationalError:
            try:
                conn.executescript(SQLITE_SCHEMA)
                conn.commit()
            except Exception as exc:
                logger.error("Falha ao inicializar o esquema SQLite: %s", exc)
                conn.close()
                raise

        try:
            yield conn
            conn.commit()
        except Exception:
            conn.rollback()
            raise
        finally:
            conn.close()
        return

    # Fallback/Retrocompatibilidade com MSSQL
    conn_str = cfg.to_connection_string()
    try:
        conn = pyodbc.connect(conn_str, autocommit=False)
    except pyodbc.Error as exc:
        logger.error("Falha ao ligar à base de dados MSSQL %s@%s: %s", cfg.database, cfg.server, exc)
        raise

    try:
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


@contextmanager
def get_dashboard_connection(
    config: Optional[DashboardConfig] = None
) -> Iterator[pyodbc.Connection]:
    """
    Abre uma ligação dedicada ao SQL Server remoto para o Dashboard de Incidências.
    """
    cfg = config or DashboardConfig.from_env()
    if not cfg.enabled:
        raise ValueError("O dashboard de incidências não está ativo nas configurações.")

    conn_str = cfg.to_connection_string()
    try:
        conn = pyodbc.connect(conn_str, autocommit=False)
    except pyodbc.Error as exc:
        logger.error("Falha ao ligar ao dashboard remoto %s@%s: %s", cfg.database, cfg.server, exc)
        raise

    try:
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()
