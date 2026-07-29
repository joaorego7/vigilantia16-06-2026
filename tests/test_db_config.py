# tests/test_db_config.py

import pytest

from vigilantia.db.config import DatabaseConfig


def test_trusted_connection_string_does_not_require_credentials():
    cfg = DatabaseConfig(server="localhost\\SQLEXPRESS", trusted_connection=True)
    conn_str = cfg.to_connection_string()

    assert "Trusted_Connection=yes" in conn_str
    assert "UID=" not in conn_str
    assert "PWD=" not in conn_str


def test_sql_auth_connection_string_includes_credentials():
    cfg = DatabaseConfig(
        server="localhost",
        trusted_connection=False,
        username="vigilantia_app",
        password="segredo",
    )
    conn_str = cfg.to_connection_string()

    assert "UID=vigilantia_app" in conn_str
    assert "PWD=segredo" in conn_str


def test_sql_auth_without_credentials_raises_value_error():
    cfg = DatabaseConfig(server="localhost", trusted_connection=False)

    with pytest.raises(ValueError, match="requer username e password"):
        cfg.to_connection_string()


def test_from_env_uses_defaults_when_unset(monkeypatch):
    for var in [
        "VIGILANTIA_DB_SERVER", "VIGILANTIA_DB_NAME", "VIGILANTIA_DB_DRIVER",
        "VIGILANTIA_DB_TRUSTED", "VIGILANTIA_DB_USER", "VIGILANTIA_DB_PASSWORD",
    ]:
        monkeypatch.delenv(var, raising=False)

    cfg = DatabaseConfig.from_env()

    assert cfg.server == "localhost\\SQLEXPRESS"
    assert cfg.database == "Vigilantia"
    assert cfg.trusted_connection is True
