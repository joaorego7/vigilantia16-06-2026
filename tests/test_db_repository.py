# tests/test_db_repository.py

import json
from unittest.mock import MagicMock

from vigilantia.db.repository import WebsiteRepository, ScanRunRepository, FindingRepository
from vigilantia.models.finding import Finding


def test_get_or_create_returns_existing_website_id():
    conn = MagicMock()
    cursor = conn.cursor.return_value
    cursor.fetchone.return_value = (42,)

    repo = WebsiteRepository(conn)
    website_id = repo.get_or_create("https://www.pcm.pt")

    assert website_id == 42
    # Só a SELECT deve ter sido executada; não há INSERT quando já existe.
    assert cursor.execute.call_count == 1
    assert "SELECT WebsiteId" in cursor.execute.call_args.args[0]


def test_get_or_create_inserts_new_website_when_not_found():
    conn = MagicMock()
    cursor = conn.cursor.return_value
    # 1ª chamada (SELECT) não encontra nada; 2ª chamada (INSERT ... OUTPUT) devolve o novo id.
    cursor.fetchone.side_effect = [None, (7,)]

    repo = WebsiteRepository(conn)
    website_id = repo.get_or_create("https://www.example.pt/pagina")

    assert website_id == 7
    assert cursor.execute.call_count == 2
    insert_sql, insert_url, insert_domain = cursor.execute.call_args_list[1].args
    assert "INSERT INTO dbo.Websites" in insert_sql
    assert insert_url == "https://www.example.pt/pagina"
    assert insert_domain == "www.example.pt"


def test_scan_run_start_returns_new_id():
    conn = MagicMock()
    cursor = conn.cursor.return_value
    cursor.fetchone.return_value = (101,)

    repo = ScanRunRepository(conn)
    scan_run_id = repo.start(website_id=42)

    assert scan_run_id == 101
    sql = cursor.execute.call_args.args[0]
    assert "INSERT INTO dbo.ScanRuns" in sql
    assert "Running" in sql


def test_scan_run_complete_updates_status_and_report_ref():
    conn = MagicMock()
    cursor = conn.cursor.return_value

    repo = ScanRunRepository(conn)
    repo.complete(scan_run_id=101, report_ref="beb9cc7d")

    sql, report_ref, scan_run_id = cursor.execute.call_args.args
    assert "UPDATE dbo.ScanRuns" in sql
    assert "Completed" in sql
    assert report_ref == "beb9cc7d"
    assert scan_run_id == 101


def test_scan_run_fail_records_error_message():
    conn = MagicMock()
    cursor = conn.cursor.return_value

    repo = ScanRunRepository(conn)
    repo.fail(scan_run_id=101, error_message="Timeout ao carregar a página")

    sql, error_message, scan_run_id = cursor.execute.call_args.args
    assert "UPDATE dbo.ScanRuns" in sql
    assert "Failed" in sql
    assert error_message == "Timeout ao carregar a página"
    assert scan_run_id == 101


# =========================================================
# FindingRepository (Semana 2 — Registo de Eventos)
# =========================================================

def _make_finding(rule_id="R09") -> Finding:
    return Finding(
        id=rule_id,
        severity="low",
        description="Texto da política não menciona o DPO.",
        recommendation="Publicar os contactos do DPO.",
        evidence={"message": "não encontrado", "flag": "dpo_contact"},
    )


def test_finding_repository_inserts_one_row_per_finding():
    conn = MagicMock()
    cursor = conn.cursor.return_value

    findings = [_make_finding("R09"), _make_finding("R05")]
    repo = FindingRepository(conn)
    repo.insert_many(scan_run_id=101, findings=findings)

    assert cursor.execute.call_count == 2

    first_call_args = cursor.execute.call_args_list[0].args
    sql, scan_run_id, rule_id, description, recommendation, evidence_json = first_call_args

    assert "INSERT INTO dbo.Findings" in sql
    assert scan_run_id == 101
    assert rule_id == "R09"
    assert description == "Texto da política não menciona o DPO."
    assert recommendation == "Publicar os contactos do DPO."
    # A evidência tem de ser gravada como JSON válido, não como dict cru
    # (pyodbc não sabe serializar dicts Python diretamente).
    assert json.loads(evidence_json) == {"message": "não encontrado", "flag": "dpo_contact"}


def test_finding_repository_does_nothing_for_empty_list():
    """
    Quando o site não tem não-conformidades, não deve haver nenhum
    round-trip à base de dados (evita esforço desnecessário).
    """
    conn = MagicMock()
    cursor = conn.cursor.return_value

    repo = FindingRepository(conn)
    repo.insert_many(scan_run_id=101, findings=[])

    cursor.execute.assert_not_called()
