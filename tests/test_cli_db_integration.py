# tests/test_cli_db_integration.py
#
# Testes da Semana 2 (Registo de Eventos): garantem que run_scan() liga
# corretamente a camada de BD (WebsiteRepository / ScanRunRepository /
# FindingRepository) e que o comportamento é fail-soft, tal como acordado
# explicitamente: se a base de dados não estiver disponível em qualquer
# fase, o scan continua e o relatório HTML é sempre gerado.

from contextlib import contextmanager
from unittest.mock import MagicMock, patch

import pytest

from vigilantia.cli import _persist_scan_start, _persist_scan_result, _persist_scan_failure
from vigilantia.models.finding import Finding


def _fake_get_connection_ok(conn):
    """Simula vigilantia.db.connection.get_connection() com sucesso."""
    @contextmanager
    def _cm(config=None):
        yield conn
    return _cm


def _fake_get_connection_raises(exc):
    """Simula vigilantia.db.connection.get_connection() a falhar (ex.: SQL Server em baixo)."""
    @contextmanager
    def _cm(config=None):
        raise exc
        yield  # pragma: no cover - nunca alcançado

    return _cm


# =========================================================
# _persist_scan_start
# =========================================================

def test_persist_scan_start_returns_scan_run_id_on_success():
    conn = MagicMock()
    cursor = conn.cursor.return_value
    # 1ª chamada: WebsiteRepository.get_or_create -> SELECT sem resultado, depois INSERT
    # 2ª chamada: ScanRunRepository.start -> INSERT ... OUTPUT
    cursor.fetchone.side_effect = [None, (42,), (101,)]

    with patch("vigilantia.cli.get_connection", _fake_get_connection_ok(conn)):
        scan_run_id = _persist_scan_start("https://www.pcm.pt")

    assert scan_run_id == 101


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
    conn = MagicMock()
    findings = [
        Finding(
            id="R09",
            severity="low",
            description="desc",
            recommendation="rec",
            evidence={"message": "x"},
        )
    ]

    with patch("vigilantia.cli.get_connection", _fake_get_connection_ok(conn)):
        _persist_scan_result(scan_run_id=101, findings=findings, report_id="beb9cc7d")

    executed_sql = [call.args[0] for call in conn.cursor.return_value.execute.call_args_list]
    assert any("INSERT INTO dbo.Findings" in sql for sql in executed_sql)
    assert any("UPDATE dbo.ScanRuns" in sql and "Completed" in sql for sql in executed_sql)


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
    conn = MagicMock()

    with patch("vigilantia.cli.get_connection", _fake_get_connection_ok(conn)):
        _persist_scan_failure(scan_run_id=101, error_message="Timeout error while fetching https://x")

    sql, error_message, scan_run_id = conn.cursor.return_value.execute.call_args.args
    assert "UPDATE dbo.ScanRuns" in sql
    assert "Failed" in sql
    assert error_message == "Timeout error while fetching https://x"
    assert scan_run_id == 101


def test_persist_scan_failure_is_fail_soft_when_scan_run_id_is_none():
    with patch("vigilantia.cli.get_connection") as mock_get_connection:
        _persist_scan_failure(scan_run_id=None, error_message="qualquer erro")

    mock_get_connection.assert_not_called()
