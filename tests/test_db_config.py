# tests/test_db_config.py

import pytest

from vigilantia.db.config import DatabaseConfig, DashboardConfig


def test_default_db_type_is_sqlite():
    cfg = DatabaseConfig()
    assert cfg.db_type == "sqlite"
    assert cfg.sqlite_path == "vigilantia.db"


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
        "VIGILANTIA_DB_TYPE", "VIGILANTIA_SQLITE_PATH",
    ]:
        monkeypatch.delenv(var, raising=False)

    cfg = DatabaseConfig.from_env()

    assert cfg.db_type == "sqlite"
    assert cfg.sqlite_path == "vigilantia.db"
    assert cfg.server == "localhost\\SQLEXPRESS"
    assert cfg.database == "Vigilantia"
    assert cfg.trusted_connection is True


# =========================================================
# DashboardConfig
# =========================================================

def test_dashboard_disabled_by_default(monkeypatch):
    for var in [
        "VIGILANTIA_DASHBOARD_ENABLED", "VIGILANTIA_DASHBOARD_SERVER",
        "VIGILANTIA_DASHBOARD_NAME", "VIGILANTIA_DASHBOARD_USER",
        "VIGILANTIA_DASHBOARD_PASSWORD", "VIGILANTIA_CLIENT_ID",
        "VIGILANTIA_DEVICE_ID", "VIGILANTIA_AUDIT_TYPE",
    ]:
        monkeypatch.delenv(var, raising=False)

    cfg = DashboardConfig.from_env()
    assert cfg.enabled is False
    assert cfg.client_id == 1
    assert cfg.device_id == 0
    assert cfg.audit_type == "website_audit"


def test_dashboard_connection_string_requires_server():
    cfg = DashboardConfig(enabled=True, server=None)

    with pytest.raises(ValueError, match="VIGILANTIA_DASHBOARD_SERVER"):
        cfg.to_connection_string()


def test_dashboard_connection_string_with_sql_auth():
    cfg = DashboardConfig(
        enabled=True,
        server="dashboard.example.com",
        database="IncidentsDB",
        trusted_connection=False,
        username="svc_vigilantia",
        password="s3cret",
    )
    conn_str = cfg.to_connection_string()

    assert "SERVER=dashboard.example.com" in conn_str
    assert "DATABASE=IncidentsDB" in conn_str
    assert "UID=svc_vigilantia" in conn_str
    assert "PWD=s3cret" in conn_str


def test_dashboard_sql_auth_without_credentials_raises():
    cfg = DashboardConfig(
        enabled=True,
        server="dashboard.example.com",
        trusted_connection=False,
    )
    with pytest.raises(ValueError, match="VIGILANTIA_DASHBOARD_USER"):
        cfg.to_connection_string()
