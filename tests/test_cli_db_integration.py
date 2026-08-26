# tests/test_cli_db_integration.py
#
# Testes da integração CLI ↔ BD: garantem que run_scan() liga corretamente
# a camada de BD (WebsiteRepository / ScanRunRepository / FindingRepository)
# e que o comportamento é fail-soft — se a base de dados não estiver
# disponível em qualquer fase, o scan continua e o relatório HTML é gerado.
#
# Adaptado para funcionar com SQLite (padrão) e None (sem BD).

import sqlite3
from contextlib import contextmanager
from unittest.mock import MagicMock, patch

import pytest

from vigilantia.cli import _persist_scan_start, _persist_scan_result, _persist_scan_failure
from vigilantia.models.finding import Finding


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
"""


def _create_sqlite_db():
    """Cria uma BD SQLite em memória com o schema do Vigilantia."""
    conn = sqlite3.connect(":memory:")
    conn.execute("PRAGMA foreign_keys = ON;")
    conn.executescript(SQLITE_SCHEMA)
    return conn


def _fake_get_connection_sqlite(conn):
    """Simula vigilantia.db.connection.get_connection() com SQLite real."""
    @contextmanager
    def _cm(config=None):
        yield conn
    return _cm


def _fake_get_connection_raises(exc):
    """Simula vigilantia.db.connection.get_connection() a falhar."""
    @contextmanager
    def _cm(config=None):
        raise exc
        yield  # pragma: no cover - nunca alcançado
    return _cm


# =========================================================
# _persist_scan_start
# =========================================================

def test_persist_scan_start_returns_scan_run_id_on_success():
    conn = _create_sqlite_db()

    with patch("vigilantia.cli.get_connection", _fake_get_connection_sqlite(conn)):
        scan_run_id = _persist_scan_start("https://www.pcm.pt")

    assert scan_run_id >= 1

    # Verifica que o Website e ScanRun foram criados
    website_count = conn.execute("SELECT COUNT(*) FROM Websites").fetchone()[0]
    assert website_count == 1
    scan_status = conn.execute(
        "SELECT Status FROM ScanRuns WHERE ScanRunId = ?", (scan_run_id,)
    ).fetchone()[0]
    assert scan_status == "Running"
    conn.close()


def test_persist_scan_start_is_fail_soft_when_db_unavailable(capsys):
    with patch(
        "vigilantia.cli.get_connection",
        _fake_get_connection_raises(RuntimeError("SQL Server indisponível")),
    ):
        scan_run_id = _persist_scan_start("https://www.pcm.pt")

    # Fail-soft: nunca deve levantar exceção, apenas devolver None.
    assert scan_run_id is None
    # E deve avisar claramente o utilizador no terminal.
    assert "[BD]" in capsys.readouterr().out


# =========================================================
# _persist_scan_result
# =========================================================

def test_persist_scan_result_does_nothing_when_scan_run_id_is_none():
    """
    Se a fase inicial já falhou (scan_run_id=None), não deve sequer
    tentar abrir uma nova ligação à base de dados.
    """
    with patch("vigilantia.cli.get_connection") as mock_get_connection:
        _persist_scan_result(scan_run_id=None, findings=[], report_id="abc12345")

    mock_get_connection.assert_not_called()


def test_persist_scan_result_inserts_findings_and_completes_scan_run():
    conn = _create_sqlite_db()
    # Cria Website e ScanRun primeiro
    conn.execute("INSERT INTO Websites (Url, Domain) VALUES ('https://www.pcm.pt', 'www.pcm.pt')")
    conn.execute("INSERT INTO ScanRuns (WebsiteId, Status) VALUES (1, 'Running')")

    findings = [
        Finding(
            id="R09",
            severity="low",
            description="desc",
            recommendation="rec",
            evidence={"message": "x"},
        )
    ]

    with patch("vigilantia.cli.get_connection", _fake_get_connection_sqlite(conn)):
        _persist_scan_result(scan_run_id=1, findings=findings, report_id="beb9cc7d")

    # Verifica findings inseridos
    finding_count = conn.execute("SELECT COUNT(*) FROM Findings WHERE ScanRunId = 1").fetchone()[0]
    assert finding_count == 1

    # Verifica scan completado
    status = conn.execute("SELECT Status FROM ScanRuns WHERE ScanRunId = 1").fetchone()[0]
    assert status == "Completed"
    conn.close()


def test_persist_scan_result_is_fail_soft_when_db_write_fails(capsys):
    with patch(
        "vigilantia.cli.get_connection",
        _fake_get_connection_raises(RuntimeError("ligação perdida")),
    ):
        # Não deve levantar exceção.
        _persist_scan_result(scan_run_id=101, findings=[], report_id="beb9cc7d")

    assert "[BD]" in capsys.readouterr().out


# =========================================================
# _persist_scan_failure
# =========================================================

def test_persist_scan_failure_marks_scan_run_as_failed():
    conn = _create_sqlite_db()
    conn.execute("INSERT INTO Websites (Url, Domain) VALUES ('https://x.com', 'x.com')")
    conn.execute("INSERT INTO ScanRuns (WebsiteId, Status) VALUES (1, 'Running')")

    with patch("vigilantia.cli.get_connection", _fake_get_connection_sqlite(conn)):
        _persist_scan_failure(scan_run_id=1, error_message="Timeout error while fetching https://x")

    row = conn.execute(
        "SELECT Status, ErrorMessage FROM ScanRuns WHERE ScanRunId = 1"
    ).fetchone()
    assert row[0] == "Failed"
    assert row[1] == "Timeout error while fetching https://x"
    conn.close()


def test_persist_scan_failure_is_fail_soft_when_scan_run_id_is_none():
    with patch("vigilantia.cli.get_connection") as mock_get_connection:
        _persist_scan_failure(scan_run_id=None, error_message="qualquer erro")

    mock_get_connection.assert_not_called()
