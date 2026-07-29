# src/vigilantia/db/repository.py

from __future__ import annotations

from abc import ABC
from typing import Optional
from urllib.parse import urlparse

import pyodbc

# Comentário de cabeçalho:
# Camada de acesso a dados (Repository pattern). Cada repositório recebe
# uma ligação pyodbc já aberta (ver connection.get_connection) e expõe
# apenas operações com significado de domínio (ex.: "obter ou criar um
# website"), nunca SQL cru para quem os chama. Isto mantém o SQL
# concentrado e testável isoladamente com mocks, sem precisar de SQL
# Server real a correr durante os testes automáticos.


class BaseRepository(ABC):
    """
    Classe base para todos os repositórios. Não gere a ligação (não abre
    nem fecha) — só a guarda, para reutilizar no cursor de cada operação.
    A gestão da transação (commit/rollback) é responsabilidade de quem
    chama get_connection().
    """

    def __init__(self, connection: pyodbc.Connection):
        self._conn = connection


class WebsiteRepository(BaseRepository):
    """
    Repositório para a tabela dbo.Websites.
    """

    def get_or_create(self, url: str) -> int:
        """
        Devolve o WebsiteId correspondente ao URL indicado, criando um
        novo registo se ainda não existir (idempotente por UQ_Websites_Url).

        :param url: URL do site, tal como fornecido pelo utilizador ao CLI.
        :return: WebsiteId (int).
        """
        domain = urlparse(url).hostname or "unknown"
        cursor = self._conn.cursor()

        cursor.execute("SELECT WebsiteId FROM dbo.Websites WHERE Url = ?", url)
        row = cursor.fetchone()
        if row is not None:
            return int(row[0])

        cursor.execute(
            "INSERT INTO dbo.Websites (Url, Domain) "
            "OUTPUT INSERTED.WebsiteId VALUES (?, ?)",
            url,
            domain,
        )
        new_id_row = cursor.fetchone()
        return int(new_id_row[0])


class ScanRunRepository(BaseRepository):
    """
    Repositório para a tabela dbo.ScanRuns. Cobre só o ciclo de vida de
    uma execução (início / conclusão / falha) — sem qualquer ligação a
    findings, que só existirá a partir da Semana 2.
    """

    def start(self, website_id: int) -> int:
        """
        Regista o início de um scan para o website indicado.

        :param website_id: FK para dbo.Websites.
        :return: ScanRunId (int) do registo criado, com Status='Running'.
        """
        cursor = self._conn.cursor()
        cursor.execute(
            "INSERT INTO dbo.ScanRuns (WebsiteId, Status) "
            "OUTPUT INSERTED.ScanRunId VALUES (?, N'Running')",
            website_id,
        )
        return int(cursor.fetchone()[0])

    def complete(self, scan_run_id: int, report_ref: Optional[str] = None) -> None:
        """
        Marca um scan como concluído com sucesso.

        :param scan_run_id: PK do registo a atualizar.
        :param report_ref: report_id de 8 caracteres gerado por reporter.py,
            para cruzar este registo com o ficheiro HTML correspondente.
        """
        cursor = self._conn.cursor()
        cursor.execute(
            "UPDATE dbo.ScanRuns "
            "SET Status = N'Completed', FinishedAt = SYSUTCDATETIME(), ReportRef = ? "
            "WHERE ScanRunId = ?",
            report_ref,
            scan_run_id,
        )

    def fail(self, scan_run_id: int, error_message: str) -> None:
        """
        Marca um scan como falhado, guardando a mensagem de erro para
        diagnóstico posterior.

        :param scan_run_id: PK do registo a atualizar.
        :param error_message: Descrição do erro que interrompeu o scan.
        """
        cursor = self._conn.cursor()
        cursor.execute(
            "UPDATE dbo.ScanRuns "
            "SET Status = N'Failed', FinishedAt = SYSUTCDATETIME(), ErrorMessage = ? "
            "WHERE ScanRunId = ?",
            error_message,
            scan_run_id,
        )
