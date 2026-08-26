# tests/test_db_repository.py

import json
import sqlite3
import os
import tempfile
from unittest.mock import MagicMock

from vigilantia.db.repository import WebsiteRepository, ScanRunRepository, FindingRepository
from vigilantia.models.finding import Finding


def _create_sqlite_db():
    """Cria uma BD SQLite temporária em memória com o schema do Vigilantia."""
    conn = sqlite3.connect(":memory:")
    conn.execute("PRAGMA foreign_keys = ON;")
    conn.executescript("""
        CREATE TABLE Websites (
            WebsiteId INTEGER PRIMARY KEY AUTOINCREMENT,
            Url TEXT NOT NULL UNIQUE,
            Domain TEXT NOT NULL,
            CreatedAt DATETIME DEFAULT CURRENT_TIMESTAMP
        );
        CREATE TABLE ScanRuns (
            ScanRunId INTEGER PRIMARY KEY AUTOINCREMENT,
            WebsiteId INTEGER NOT NULL,
            ReportRef CHAR(8) NULL,
            StartedAt DATETIME DEFAULT CURRENT_TIMESTAMP,
            FinishedAt DATETIME NULL,
            Status TEXT NOT NULL CHECK(Status IN ('Running', 'Completed', 'Failed')),
            ErrorMessage TEXT NULL,
            FOREIGN KEY(WebsiteId) REFERENCES Websites(WebsiteId)
        );
        CREATE TABLE Findings (
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
    """)
    return conn


# =========================================================
# WebsiteRepository (SQLite)
# =========================================================

def test_get_or_create_inserts_new_website_sqlite():
    conn = _create_sqlite_db()
    repo = WebsiteRepository(conn)
    website_id = repo.get_or_create("https://www.example.pt/pagina")

    assert website_id == 1

    # Confirma que os dados foram gravados corretamente
    row = conn.execute("SELECT Url, Domain FROM Websites WHERE WebsiteId = ?", (website_id,)).fetchone()
    assert row[0] == "https://www.example.pt/pagina"
    assert row[1] == "www.example.pt"
    conn.close()


def test_get_or_create_returns_existing_website_sqlite():
    conn = _create_sqlite_db()
    repo = WebsiteRepository(conn)

    first_id = repo.get_or_create("https://www.pcm.pt")
    second_id = repo.get_or_create("https://www.pcm.pt")

    assert first_id == second_id
    # Deve haver só 1 registo na tabela
    count = conn.execute("SELECT COUNT(*) FROM Websites").fetchone()[0]
    assert count == 1
    conn.close()


# =========================================================
# ScanRunRepository (SQLite)
# =========================================================

def test_scan_run_start_returns_new_id_sqlite():
    conn = _create_sqlite_db()
    website_repo = WebsiteRepository(conn)
    website_id = website_repo.get_or_create("https://www.pcm.pt")

    repo = ScanRunRepository(conn)
    scan_run_id = repo.start(website_id)

    assert scan_run_id >= 1
    row = conn.execute("SELECT Status FROM ScanRuns WHERE ScanRunId = ?", (scan_run_id,)).fetchone()
    assert row[0] == "Running"
    conn.close()


def test_scan_run_complete_updates_status_sqlite():
    conn = _create_sqlite_db()
    website_id = WebsiteRepository(conn).get_or_create("https://www.pcm.pt")
    repo = ScanRunRepository(conn)
    scan_run_id = repo.start(website_id)

    repo.complete(scan_run_id, report_ref="beb9cc7d")

    row = conn.execute(
        "SELECT Status, ReportRef, FinishedAt FROM ScanRuns WHERE ScanRunId = ?",
        (scan_run_id,),
    ).fetchone()
    assert row[0] == "Completed"
    assert row[1] == "beb9cc7d"
    assert row[2] is not None  # FinishedAt preenchido
    conn.close()


def test_scan_run_fail_records_error_message_sqlite():
    conn = _create_sqlite_db()
    website_id = WebsiteRepository(conn).get_or_create("https://www.pcm.pt")
    repo = ScanRunRepository(conn)
    scan_run_id = repo.start(website_id)

    repo.fail(scan_run_id, "Timeout ao carregar a página")

    row = conn.execute(
        "SELECT Status, ErrorMessage FROM ScanRuns WHERE ScanRunId = ?",
        (scan_run_id,),
    ).fetchone()
    assert row[0] == "Failed"
    assert row[1] == "Timeout ao carregar a página"
    conn.close()


# =========================================================
# FindingRepository (SQLite)
# =========================================================

def _make_finding(rule_id="R09") -> Finding:
    return Finding(
        id=rule_id,
        severity="low",
        description="Texto da política não menciona o DPO.",
        recommendation="Publicar os contactos do DPO.",
        evidence={"message": "não encontrado", "flag": "dpo_contact"},
    )


def test_finding_repository_inserts_one_row_per_finding_sqlite():
    conn = _create_sqlite_db()
    website_id = WebsiteRepository(conn).get_or_create("https://www.pcm.pt")
    scan_run_id = ScanRunRepository(conn).start(website_id)

    findings = [_make_finding("R09"), _make_finding("R05")]
    repo = FindingRepository(conn)
    repo.insert_many(scan_run_id, findings)

    rows = conn.execute("SELECT * FROM Findings WHERE ScanRunId = ?", (scan_run_id,)).fetchall()
    assert len(rows) == 2

    # Verifica que a evidência está serializada como JSON válido
    evidence_json = rows[0][6]  # EvidenceJson é a 7ª coluna (index 6)
    assert json.loads(evidence_json) == {"message": "não encontrado", "flag": "dpo_contact"}
    conn.close()


def test_finding_repository_does_nothing_for_empty_list_sqlite():
    conn = _create_sqlite_db()
    website_id = WebsiteRepository(conn).get_or_create("https://www.pcm.pt")
    scan_run_id = ScanRunRepository(conn).start(website_id)

    repo = FindingRepository(conn)
    repo.insert_many(scan_run_id, [])

    count = conn.execute("SELECT COUNT(*) FROM Findings").fetchone()[0]
    assert count == 0
    conn.close()


# =========================================================
# NoOp (db_type='none') — conexão é None
# =========================================================

def test_repositories_handle_none_connection():
    """Quando db_type='none', os repositórios devem funcionar sem fazer nada."""
    website_id = WebsiteRepository(None).get_or_create("https://www.pcm.pt")
    assert website_id == 0

    scan_run_id = ScanRunRepository(None).start(0)
    assert scan_run_id == 0

    ScanRunRepository(None).complete(0, report_ref="abc12345")
    ScanRunRepository(None).fail(0, "erro qualquer")

    FindingRepository(None).insert_many(0, [_make_finding()])
    # Nenhuma exceção — tudo funciona sem BD
