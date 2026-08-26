# src/vigilantia/db/repository.py

from __future__ import annotations

import json
import sqlite3
from abc import ABC
from typing import Optional, Sequence, Union
from urllib.parse import urlparse

try:
    import pyodbc
except ImportError:
    from typing import Any
    class _MockPyODBC:
        Connection = Any
    pyodbc = _MockPyODBC()

from vigilantia.models.finding import Finding

# Comentário de cabeçalho:
# Camada de acesso a dados (Repository pattern) adaptada para SQLite, MSSQL e None.
# Detecta automaticamente o tipo de ligação e ajusta a sintaxe SQL
# (removendo prefixos dbo. e adaptando cláusulas OUTPUT/lastrowid).
#
# NOTA IMPORTANTE: O SQLite e o pyodbc têm interfaces cursor.execute() diferentes:
#   - sqlite3: cursor.execute(sql, (param1, param2, ...))  ← tuplo
#   - pyodbc:  cursor.execute(sql, param1, param2, ...)    ← args posicionais
# Este módulo usa tuplos para SQLite e args posicionais para pyodbc.


class BaseRepository(ABC):
    """
    Classe base para todos os repositórios. Suporta ligações SQLite, MSSQL ou None.
    """

    def __init__(self, connection: Optional[Union[sqlite3.Connection, pyodbc.Connection]]):
        self._conn = connection
        self._is_none = connection is None
        self._is_sqlite = (
            connection is not None 
            and type(connection).__module__.startswith("sqlite3")
        )


class WebsiteRepository(BaseRepository):
    """
    Repositório para a tabela Websites (local).
    """

    def get_or_create(self, url: str) -> int:
        """
        Devolve o WebsiteId correspondente ao URL, criando-o se não existir.
        """
        if self._is_none:
            return 0

        domain = urlparse(url).hostname or "unknown"
        cursor = self._conn.cursor()

        if self._is_sqlite:
            cursor.execute("SELECT WebsiteId FROM Websites WHERE Url = ?", (url,))
        else:
            cursor.execute("SELECT WebsiteId FROM Websites WHERE Url = ?", url)

        row = cursor.fetchone()
        if row is not None:
            return int(row[0])

        if self._is_sqlite:
            cursor.execute(
                "INSERT INTO Websites (Url, Domain) VALUES (?, ?)",
                (url, domain),
            )
            return int(cursor.lastrowid)
        else:
            # Sintaxe MSSQL com OUTPUT INSERTED
            cursor.execute(
                "INSERT INTO Websites (Url, Domain) "
                "OUTPUT INSERTED.WebsiteId VALUES (?, ?)",
                url,
                domain,
            )
            new_id_row = cursor.fetchone()
            return int(new_id_row[0])


class ScanRunRepository(BaseRepository):
    """
    Repositório para a tabela ScanRuns (local).
    """

    def start(self, website_id: int) -> int:
        """
        Regista o início de um scan.
        """
        if self._is_none:
            return 0

        cursor = self._conn.cursor()
        if self._is_sqlite:
            cursor.execute(
                "INSERT INTO ScanRuns (WebsiteId, Status) VALUES (?, 'Running')",
                (website_id,),
            )
            return int(cursor.lastrowid)
        else:
            # Sintaxe MSSQL
            cursor.execute(
                "INSERT INTO ScanRuns (WebsiteId, Status) "
                "OUTPUT INSERTED.ScanRunId VALUES (?, N'Running')",
                website_id,
            )
            return int(cursor.fetchone()[0])

    def complete(self, scan_run_id: int, report_ref: Optional[str] = None) -> None:
        """
        Marca um scan como concluído com sucesso.
        """
        if self._is_none:
            return

        cursor = self._conn.cursor()
        if self._is_sqlite:
            cursor.execute(
                "UPDATE ScanRuns "
                "SET Status = 'Completed', FinishedAt = datetime('now'), ReportRef = ? "
                "WHERE ScanRunId = ?",
                (report_ref, scan_run_id),
            )
        else:
            cursor.execute(
                "UPDATE ScanRuns "
                "SET Status = N'Completed', FinishedAt = SYSUTCDATETIME(), ReportRef = ? "
                "WHERE ScanRunId = ?",
                report_ref,
                scan_run_id,
            )

    def fail(self, scan_run_id: int, error_message: str) -> None:
        """
        Marca um scan como falhado.
        """
        if self._is_none:
            return

        cursor = self._conn.cursor()
        if self._is_sqlite:
            cursor.execute(
                "UPDATE ScanRuns "
                "SET Status = 'Failed', FinishedAt = datetime('now'), ErrorMessage = ? "
                "WHERE ScanRunId = ?",
                (error_message, scan_run_id),
            )
        else:
            cursor.execute(
                "UPDATE ScanRuns "
                "SET Status = N'Failed', FinishedAt = SYSUTCDATETIME(), ErrorMessage = ? "
                "WHERE ScanRunId = ?",
                error_message,
                scan_run_id,
            )


class FindingRepository(BaseRepository):
    """
    Repositório para a tabela Findings (local).
    """

    def insert_many(self, scan_run_id: int, findings: Sequence[Finding]) -> None:
        """
        Grava a lista de findings no banco de dados local.
        """
        if self._is_none or not findings:
            return

        cursor = self._conn.cursor()
        for finding in findings:
            evidence_json = json.dumps(finding.evidence, ensure_ascii=False)
            if self._is_sqlite:
                cursor.execute(
                    "INSERT INTO Findings "
                    "(ScanRunId, RuleId, Description, Recommendation, EvidenceJson, Status) "
                    "VALUES (?, ?, ?, ?, ?, 'Open')",
                    (scan_run_id, finding.id, finding.description,
                     finding.recommendation, evidence_json),
                )
            else:
                cursor.execute(
                    "INSERT INTO Findings "
                    "(ScanRunId, RuleId, Description, Recommendation, EvidenceJson, Status) "
                    "VALUES (?, ?, ?, ?, ?, N'Open')",
                    scan_run_id,
                    finding.id,
                    finding.description,
                    finding.recommendation,
                    evidence_json,
                )

class CompanyRepository(BaseRepository):
    """
    Repositório para a tabela Companies: os dados da empresa dona de um
    Website, quando o scan foi iniciado a partir dos dados da empresa em vez
    de um URL (ver company_info.py e o comando `scan` no cli.py).

    Um Website tem no máximo uma empresa — por isso a operação é um upsert:
    o scan seguinte da mesma empresa atualiza a linha em vez de acumular
    duplicados.
    """

    def upsert(
        self,
        website_id: int,
        name: str,
        legal_name: Optional[str] = None,
        nif: Optional[str] = None,
        address: Optional[str] = None,
        registry_verified: Optional[bool] = None,
        note: Optional[str] = None,
        nameservers: Optional[Sequence[str]] = None,
    ) -> int:
        """
        Grava (ou atualiza) os dados da empresa associada a um Website.

        :param website_id: WebsiteId devolvido por WebsiteRepository.get_or_create().
        :param name: Nome comercial pesquisado (obrigatório).
        :param legal_name: Nome legal completo, se conhecido.
        :param nif: NIF/número de contribuinte, se encontrado.
        :param address: Morada da sede, se encontrada.
        :param registry_verified: True/False/None conforme o registo público
            confirmou, não confirmou, ou não foi consultado.
        :param note: Nota sobre a origem/fiabilidade dos dados.
        :param nameservers: Lista de nameservers do domínio (WHOIS).
        :return: CompanyId do registo criado ou atualizado (0 se não houver BD).
        """
        if self._is_none or not website_id:
            return 0

        verified = None if registry_verified is None else int(bool(registry_verified))
        nameservers_json = json.dumps(list(nameservers), ensure_ascii=False) if nameservers else None
        values = (name, legal_name, nif, address, verified, note, nameservers_json)

        cursor = self._conn.cursor()

        if self._is_sqlite:
            cursor.execute(
                "SELECT CompanyId FROM Companies WHERE WebsiteId = ?", (website_id,)
            )
        else:
            cursor.execute(
                "SELECT CompanyId FROM Companies WHERE WebsiteId = ?", website_id
            )

        row = cursor.fetchone()

        if row is not None:
            company_id = int(row[0])
            if self._is_sqlite:
                cursor.execute(
                    "UPDATE Companies SET Name = ?, LegalName = ?, Nif = ?, "
                    "Address = ?, RegistryVerified = ?, Note = ?, "
                    "NameserversJson = ?, UpdatedAt = datetime('now') "
                    "WHERE CompanyId = ?",
                    values + (company_id,),
                )
            else:
                cursor.execute(
                    "UPDATE Companies SET Name = ?, LegalName = ?, Nif = ?, "
                    "Address = ?, RegistryVerified = ?, Note = ?, "
                    "NameserversJson = ?, UpdatedAt = SYSUTCDATETIME() "
                    "WHERE CompanyId = ?",
                    *(values + (company_id,)),
                )
            return company_id

        if self._is_sqlite:
            cursor.execute(
                "INSERT INTO Companies "
                "(WebsiteId, Name, LegalName, Nif, Address, RegistryVerified, "
                "Note, NameserversJson) VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
                (website_id,) + values,
            )
            return int(cursor.lastrowid)

        cursor.execute(
            "INSERT INTO Companies "
            "(WebsiteId, Name, LegalName, Nif, Address, RegistryVerified, "
            "Note, NameserversJson) "
            "OUTPUT INSERTED.CompanyId VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
            *((website_id,) + values),
        )
        return int(cursor.fetchone()[0])
