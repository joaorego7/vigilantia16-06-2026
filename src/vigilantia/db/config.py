# src/vigilantia/db/config.py

from __future__ import annotations

import os
from typing import Optional

from pydantic import BaseModel

# Comentário de cabeçalho:
# Configuração da ligação ao SQL Server, construída a partir de variáveis
# de ambiente (ver .env.example). Segue o mesmo espírito de paths.py:
# centralizar num único sítio decisões que, de outra forma, apareceriam
# espalhadas por strings de ligação hardcoded.


def _env_bool(name: str, default: bool) -> bool:
    raw = os.getenv(name)
    if raw is None:
        return default
    return raw.strip().lower() in ("1", "true", "yes", "on")


class DatabaseConfig(BaseModel):
    """
    Parâmetros necessários para construir uma connection string ODBC
    para o SQL Server.

    Campos:
      - server: nome/instância do servidor (ex.: "localhost\\SQLEXPRESS").
      - database: nome da base de dados alvo.
      - driver: nome exato do driver ODBC instalado no sistema.
      - trusted_connection: se True, usa Windows Authentication; se False,
        exige username/password (SQL Authentication).
      - trust_server_certificate: necessário em dev local com certificados
        autoassinados; NÃO deve ser True em produção.
    """
    server: str
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
        Não lê o ficheiro .env diretamente (isso é feito por quem chama
        esta função, via python-dotenv, no ponto de entrada da aplicação),
        para manter este módulo sem efeitos secundários na importação.
        """
        return cls(
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
        Monta a connection string ODBC. Lança ValueError cedo se
        trusted_connection=False e faltarem credenciais, em vez de deixar
        o pyodbc falhar mais tarde com um erro menos claro.
        """
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
