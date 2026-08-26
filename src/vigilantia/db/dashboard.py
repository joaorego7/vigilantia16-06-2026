# src/vigilantia/db/dashboard.py

from __future__ import annotations

import json
import logging
from typing import Optional, Sequence
from urllib.parse import urlparse

from vigilantia.db.config import DashboardConfig
from vigilantia.db.connection import get_dashboard_connection
from vigilantia.models.finding import Finding

logger = logging.getLogger(__name__)

# Comentário de cabeçalho:
# Este módulo trata do envio de incidentes/findings para o painel MSSQL remoto
# chamando a Stored Procedure [service].[create_notification].
#
# Exemplo de chamada gerada:
#   EXEC [service].[create_notification]
#       @ClientId = 1840264,
#       @DeviceId = 0,
#       @RemoteAddress = N'https://tretas.eu/',
#       @DeviceName = N'tretas.eu',
#       @Category = N'missing_cookie_consent',
#       @NotificationId = N'missing_cookie_consent',
#       @Level = 3,
#       @LogTimestamp = NULL,
#       @Description = N'Tracking cookies found but no consent banner detected',
#       @Type = N'website_audit'


# Mapeamento de RuleId para categoria snake_case usada no dashboard.
# @Category e @NotificationId recebem o mesmo valor.
_RULE_CATEGORY_MAP = {
    "R01": "missing_cookie_consent",
    "R02": "tracking_cookies_before_consent",
    "R03": "analytics_no_ip_anonymization",
    "R04": "cookies_missing_secure_flags",
    "R05": "missing_privacy_policy",
    "R06": "policy_missing_right_of_access",
    "R07": "policy_missing_right_to_erasure",
    "R08": "policy_missing_international_transfers",
    "R09": "policy_missing_dpo_contact",
    "R10": "policy_missing_retention_period",
    "R11": "forms_without_purpose_notice",
    "R12": "privacy_policy_unreachable",
}


def _map_category(rule_id: str) -> str:
    """
    Mapeia o RuleId (ex: R01) para uma categoria snake_case para o Dashboard.
    Usado tanto em @Category como em @NotificationId.
    """
    return _RULE_CATEGORY_MAP.get(rule_id, "generic_compliance_issue")


def _map_level(severity: str) -> int:
    """
    Mapeia a severidade de string para o nível inteiro esperado pela SP.
    Conforme definido pelo Geada:
    - 'high'   -> 1 (crítico)
    - 'medium' -> 2 (médio)
    - 'low'    -> 3 (recomendação)
    """
    sev = (severity or "").lower()
    if sev == "high":
        return 1
    elif sev == "medium":
        return 2
    return 3


def _format_exec_sql(
    client_id: int,
    device_id: int,
    remote_address: str,
    category: str,
    level: int,
    description: str,
    audit_type: str,
) -> str:
    """Formata a chamada EXEC exatamente como seria enviada ao SQL Server."""
    return (
        "EXEC [service].[create_notification]\n"
        f"    @ClientId = {client_id},\n"
        f"    @DeviceId = {device_id},\n"
        f"    @RemoteAddress = N'{remote_address}',\n"
        f"    @DeviceName = NULL,\n"
        f"    @Category = N'{category}',\n"
        f"    @NotificationId = N'{category}',\n"
        f"    @Level = {level},\n"
        f"    @Description = N'{description}',\n"
        f"    @Type = N'{audit_type}'"
    )


def report_findings_to_dashboard(
    url: str,
    findings: Sequence[Finding],
    config: Optional[DashboardConfig] = None
) -> None:
    """
    Envia todos os findings de um scan para o Dashboard remoto através do MSSQL,
    chamando a Stored Procedure [service].[create_notification] para cada não-conformidade.
    
    Se cfg.dry_run=True, imprime o SQL que seria executado sem ligar à BD.
    
    Esta operação é fail-soft: erros de ligação ou execução são registados nos logs
    e relançados para o CLI tratar (que apenas emitirá um aviso para não parar o fluxo principal).
    """
    cfg = config or DashboardConfig.from_env()
    if not cfg.enabled:
        logger.info("Envio para o dashboard remoto desativado.")
        return

    if not findings:
        logger.info("Nenhum finding detetado para reportar ao dashboard.")
        return

    # Pré-calcula campos que são iguais para todos os findings do mesmo scan
    parsed = urlparse(url)
    # @RemoteAddress: URL base com esquema, sem trailing slash (ex: "https://pcm.pt")
    hostname = parsed.hostname or "unknown"
    remote_address = f"{parsed.scheme}://{hostname}"[:50]
    # @DeviceName: NULL — a SP usa o @RemoteAddress como fallback

    # ── Modo Dry-Run ──────────────────────────────────────────────
    if cfg.dry_run:
        print(f"\n{'='*60}")
        print(f"[DASHBOARD DRY-RUN] {len(findings)} chamada(s) à SP para: {url}")
        print(f"{'='*60}")
        for i, finding in enumerate(findings, 1):
            category = _map_category(finding.id)
            level = _map_level(finding.severity)
            description = f"{url} — {finding.description}"
            sql = _format_exec_sql(
                cfg.client_id, cfg.device_id, remote_address,
                category, level, description, cfg.audit_type,
            )
            print(f"\n-- Finding {i}/{len(findings)} (Rule: {finding.id}, Severity: {finding.severity})")
            print(sql)
        print(f"\n{'='*60}")
        print("[DASHBOARD DRY-RUN] Nenhuma ligação à BD foi feita.")
        print(f"{'='*60}\n")
        return

    # ── Modo Real ─────────────────────────────────────────────────
    logger.info("A reportar %d incidentes para o dashboard remoto (%s)...", len(findings), cfg.server)

    with get_dashboard_connection(cfg) as conn:
        cursor = conn.cursor()
        for finding in findings:
            category = _map_category(finding.id)
            level = _map_level(finding.severity)

            # @Description: texto descritivo do finding
            description = f"{url} — {finding.description}"

            # Executa a SP com parâmetros posicionais no padrão do SQL Server via pyodbc
            # @DeviceName = NULL (SP faz fallback para @RemoteAddress)
            # @Category = @NotificationId (mesmo valor, conforme padrão do dashboard)
            cursor.execute(
                "EXEC [service].[create_notification] ?, ?, ?, ?, ?, ?, ?, ?, ?, ?",
                cfg.client_id,
                cfg.device_id,
                remote_address,
                None,           # @DeviceName = NULL (fallback para RemoteAddress)
                category,
                category,       # @NotificationId = @Category
                level,
                None,           # @LogTimestamp = NULL (usa GETDATE())
                description,
                cfg.audit_type
            )

