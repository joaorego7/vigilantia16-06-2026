# src/vigilantia/db/config.py

from __future__ import annotations

import os
from typing import Optional

from pydantic import BaseModel

# Comentário de cabeçalho:
# Configuração da ligação à base de dados local (SQLite ou nenhuma) e ao 
# dashboard de incidências remoto (MSSQL via SP).
# Centraliza a leitura das variáveis de ambiente definidas no .env.


def _env_bool(name: str, default: bool) -> bool:
    raw = os.getenv(name)
    if raw is None:
        return default
    return raw.strip().lower() in ("1", "true", "yes", "on")


class DatabaseConfig(BaseModel):
    """
    Parâmetros necessários para a base de dados local do Vigilantia.
    
    Campos:
      - db_type: Tipo de base de dados ('sqlite', 'none' ou 'mssql' para compatibilidade).
      - sqlite_path: Caminho para o ficheiro SQLite (ex: 'vigilantia.db').
    """
    db_type: str = "sqlite"
    sqlite_path: str = "vigilantia.db"
    
    # Parâmetros MSSQL mantidos para retrocompatibilidade
    server: Optional[str] = None
    database: str = "Vigilantia"
    driver: str = "ODBC Driver 18 for SQL Server"
    trusted_connection: bool = True
    username: Optional[str] = None
    password: Optional[str] = None
    trust_server_certificate: bool = True

    @classmethod
    def from_env(cls) -> "DatabaseConfig":
        """
        Constrói a configuração a partir de variáveis de ambiente.
        """
        return cls(
            db_type=os.getenv("VIGILANTIA_DB_TYPE", "sqlite"),
            sqlite_path=os.getenv("VIGILANTIA_SQLITE_PATH", "vigilantia.db"),
            server=os.getenv("VIGILANTIA_DB_SERVER", "localhost\\SQLEXPRESS"),
            database=os.getenv("VIGILANTIA_DB_NAME", "Vigilantia"),
            driver=os.getenv("VIGILANTIA_DB_DRIVER", "ODBC Driver 18 for SQL Server"),
            trusted_connection=_env_bool("VIGILANTIA_DB_TRUSTED", True),
            username=os.getenv("VIGILANTIA_DB_USER") or None,
            password=os.getenv("VIGILANTIA_DB_PASSWORD") or None,
            trust_server_certificate=_env_bool("VIGILANTIA_DB_TRUST_CERT", True),
        )

    def to_connection_string(self) -> str:
        """
        Monta a connection string ODBC se estiver a usar MSSQL local.
        """
        if not self.server:
            raise ValueError("MSSQL Server hostname não está configurado.")
            
        parts = [
            f"DRIVER={{{self.driver}}}",
            f"SERVER={self.server}",
            f"DATABASE={self.database}",
        ]

        if self.trusted_connection:
            parts.append("Trusted_Connection=yes")
        else:
            if not self.username or not self.password:
                raise ValueError(
                    "Autenticação SQL (trusted_connection=False) requer "
                    "username e password definidos."
                )
            parts.append(f"UID={self.username}")
            parts.append(f"PWD={self.password}")

        if self.trust_server_certificate:
            parts.append("TrustServerCertificate=yes")

        return ";".join(parts) + ";"


class DashboardConfig(BaseModel):
    """
    Parâmetros necessários para ligar ao dashboard de incidências (MSSQL remoto).
    """
    enabled: bool = False
    dry_run: bool = False  # Se True, imprime o SQL sem ligar à BD
    server: Optional[str] = None
    database: str = "Vigilantia"
    driver: str = "ODBC Driver 18 for SQL Server"
    trusted_connection: bool = False
    username: Optional[str] = None
    password: Optional[str] = None
    trust_server_certificate: bool = True
    
    # Parâmetros para a Stored Procedure [service].[create_notification]
    client_id: int = 1
    device_id: int = 0
    audit_type: str = "website_audit"

    @classmethod
    def from_env(cls) -> "DashboardConfig":
        """
        Carrega as definições do painel de incidências do ambiente.
        """
        try:
            client_id_val = int(os.getenv("VIGILANTIA_CLIENT_ID", "1"))
        except ValueError:
            client_id_val = 1
            
        try:
            device_id_val = int(os.getenv("VIGILANTIA_DEVICE_ID", "0"))
        except ValueError:
            device_id_val = 0

        return cls(
            enabled=_env_bool("VIGILANTIA_DASHBOARD_ENABLED", False),
            dry_run=_env_bool("VIGILANTIA_DASHBOARD_DRY_RUN", False),
            server=os.getenv("VIGILANTIA_DASHBOARD_SERVER"),
            database=os.getenv("VIGILANTIA_DASHBOARD_NAME", "Vigilantia"),
            driver=os.getenv("VIGILANTIA_DASHBOARD_DRIVER", "ODBC Driver 18 for SQL Server"),
            trusted_connection=_env_bool("VIGILANTIA_DASHBOARD_TRUSTED", False),
            username=os.getenv("VIGILANTIA_DASHBOARD_USER") or None,
            password=os.getenv("VIGILANTIA_DASHBOARD_PASSWORD") or None,
            trust_server_certificate=_env_bool("VIGILANTIA_DASHBOARD_TRUST_CERT", True),
            client_id=client_id_val,
            device_id=device_id_val,
            audit_type=os.getenv("VIGILANTIA_AUDIT_TYPE", "website_audit"),
        )

    def to_connection_string(self) -> str:
        """
        Gera a connection string para a ligação ao dashboard MSSQL remoto.
        """
        if not self.server:
            raise ValueError(
                "Configuração em falta: VIGILANTIA_DASHBOARD_SERVER é obrigatório "
                "quando o dashboard de incidências está ativo."
            )
            
        parts = [
            f"DRIVER={{{self.driver}}}",
            f"SERVER={self.server}",
            f"DATABASE={self.database}",
        ]

        if self.trusted_connection:
            parts.append("Trusted_Connection=yes")
        else:
            if not self.username or not self.password:
                raise ValueError(
                    "Autenticação SQL no dashboard requer VIGILANTIA_DASHBOARD_USER "
                    "e VIGILANTIA_DASHBOARD_PASSWORD definidos."
                )
            parts.append(f"UID={self.username}")
            parts.append(f"PWD={self.password}")

        if self.trust_server_certificate:
            parts.append("TrustServerCertificate=yes")

        return ";".join(parts) + ";"
