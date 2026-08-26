# tests/test_cli_company.py
#
# Testes da integração do GetCompanyUrl no comando `scan`:
#   - deteção do argumento (URL vs JSON com os dados da empresa)
#   - gate de confiança (low/medium/high, site inexistente, --force)
#   - passagem dos dados da empresa para o SiteData e para o relatório
#
# Nenhum destes testes toca na rede: get_company_urls() é sempre
# substituída por um duplo de teste, tal como o scraper.

from unittest.mock import MagicMock, patch

import pytest
from typer.testing import CliRunner

from vigilantia import cli
from vigilantia.models.site_data import SiteData
from vigilantia.reporter import generate_html_report

runner = CliRunner()


def _result(**overrides) -> dict:
    """Resultado-tipo do GetCompanyUrl, com os campos que interessam."""
    base = {
        "company_name": "Feedzai",
        "query_used": "Feedzai Portugal official website",
        "url": "https://www.feedzai.com/",
        "domain": "feedzai.com",
        "confidence": "high",
        "nif": "508771862",
        "email": "not available",
        "postal_code": "3030-199 Coimbra",
        "address": "Rua Pedro Nunes, 3030-199 Coimbra",
        "registry_verified": True,
        "note": "Dados confirmados através do Racius.com.",
        "nameservers": ["mary.ns.cloudflare.com", "pablo.ns.cloudflare.com"],
    }
    base.update(overrides)
    return base


def _site_data(**overrides) -> SiteData:
    base = dict(
        url="https://www.feedzai.com/",
        final_url="https://www.feedzai.com/",
        language="en",
        cookies=[],
        third_party_scripts=[],
        forms=[],
        consent_banner_detected=False,
    )
    base.update(overrides)
    return SiteData(**base)


# --------------------------------------------------------------------------
# Argumento: URL vs JSON
# --------------------------------------------------------------------------

def test_url_argument_keeps_working_and_does_not_touch_get_company_url():
    """Um URL normal continua a correr o scan sem envolver o GetCompanyUrl."""
    with patch.object(cli, "run_scan") as run_scan, \
            patch.object(cli, "_load_get_company_urls") as loader:
        result = runner.invoke(cli.app, ["https://exemplo.pt"])

    assert result.exit_code == 0
    loader.assert_not_called()
    run_scan.assert_called_once_with("https://exemplo.pt", company_result=None)


def test_company_json_argument_resolves_url_and_passes_result_to_run_scan():
    resolved = _result()
    with patch.object(cli, "run_scan") as run_scan, \
            patch.object(cli, "_load_get_company_urls", return_value=lambda c: resolved):
        result = runner.invoke(cli.app, ['{"company_name": "Feedzai", "country": "Portugal"}'])

    assert result.exit_code == 0
    called_url, kwargs = run_scan.call_args[0][0], run_scan.call_args[1]
    assert called_url == "https://www.feedzai.com/"
    assert kwargs["company_result"]["nif"] == "508771862"
    # Resumo da resolução impresso antes da análise.
    assert "Site: https://www.feedzai.com/" in result.output
    assert "508771862" in result.output


def test_invalid_json_fails_with_clear_message_and_no_traceback():
    with patch.object(cli, "run_scan") as run_scan:
        result = runner.invoke(cli.app, ["{json-invalido"])

    assert result.exit_code == 1
    assert "[ERRO]" in result.output
    assert "JSON válido" in result.output
    assert "Traceback" not in result.output
    run_scan.assert_not_called()


def test_missing_company_name_is_rejected():
    with patch.object(cli, "run_scan") as run_scan:
        result = runner.invoke(cli.app, ['{"country": "Portugal"}'])

    assert result.exit_code == 1
    assert "company_name" in result.output
    run_scan.assert_not_called()


# --------------------------------------------------------------------------
# Gate de confiança
# --------------------------------------------------------------------------

def test_no_site_found_blocks_even_with_force():
    resolved = _result(url="not available", domain="not available", confidence="not available")
    with patch.object(cli, "run_scan") as run_scan, \
            patch.object(cli, "_load_get_company_urls", return_value=lambda c: resolved):
        result = runner.invoke(cli.app, ['{"company_name": "XPTO"}', "--force"])

    assert result.exit_code == 1
    assert "Não foi encontrado nenhum site oficial" in result.output
    run_scan.assert_not_called()


def test_low_confidence_blocks_without_force():
    resolved = _result(confidence="low")
    with patch.object(cli, "run_scan") as run_scan, \
            patch.object(cli, "_load_get_company_urls", return_value=lambda c: resolved):
        result = runner.invoke(cli.app, ['{"company_name": "Consultores"}'])

    assert result.exit_code == 1
    assert "Confiança BAIXA" in result.output
    assert "--force" in result.output
    run_scan.assert_not_called()


def test_low_confidence_proceeds_with_force():
    resolved = _result(confidence="low")
    with patch.object(cli, "run_scan") as run_scan, \
            patch.object(cli, "_load_get_company_urls", return_value=lambda c: resolved):
        result = runner.invoke(cli.app, ['{"company_name": "Consultores"}', "--force"])

    assert result.exit_code == 0
    assert "[AVISO]" in result.output
    run_scan.assert_called_once()


def test_medium_confidence_proceeds_without_force_but_warns():
    resolved = _result(confidence="medium")
    with patch.object(cli, "run_scan") as run_scan, \
            patch.object(cli, "_load_get_company_urls", return_value=lambda c: resolved):
        result = runner.invoke(cli.app, ['{"company_name": "Feedzai"}'])

    assert result.exit_code == 0
    assert "Confiança MÉDIA" in result.output
    run_scan.assert_called_once()


def test_registry_not_verified_warns_but_never_blocks():
    resolved = _result(
        registry_verified=False,
        note="Dados de nif e address não foram confirmados automaticamente.",
    )
    with patch.object(cli, "run_scan") as run_scan, \
            patch.object(cli, "_load_get_company_urls", return_value=lambda c: resolved):
        result = runner.invoke(cli.app, ['{"company_name": "Feedzai"}'])

    assert result.exit_code == 0
    assert "NÃO confirmados" in result.output
    run_scan.assert_called_once()


def test_get_company_urls_failure_exits_with_code_1():
    def boom(_company):
        raise RuntimeError("rede indisponível")

    with patch.object(cli, "run_scan") as run_scan, \
            patch.object(cli, "_load_get_company_urls", return_value=boom):
        result = runner.invoke(cli.app, ['{"company_name": "Feedzai"}'])

    assert result.exit_code == 1
    assert "rede indisponível" in result.output
    run_scan.assert_not_called()


# --------------------------------------------------------------------------
# Normalização dos valores do GetCompanyUrl
# --------------------------------------------------------------------------

@pytest.mark.parametrize(
    "value, expected",
    [
        ("not available", None),
        ("", None),
        (None, None),
        ("508771862", "508771862"),
    ],
)
def test_clean_company_value(value, expected):
    assert cli._clean_company_value(value) == expected


def test_company_nameservers_handles_not_available_string():
    """O script devolve "not available" (string) quando o WHOIS não dá nada."""
    assert cli._company_nameservers({"nameservers": "not available"}) == []
    assert cli._company_nameservers({"nameservers": ["a.ns", "b.ns"]}) == ["a.ns", "b.ns"]


# --------------------------------------------------------------------------
# run_scan: dados da empresa acabam no SiteData e no relatório
# --------------------------------------------------------------------------

def _run_scan_with_stubs(company_result, tmp_path):
    """Corre run_scan com todo o I/O substituído, devolvendo o SiteData usado."""
    captured = {}

    def fake_report(**kwargs):
        captured["site_data"] = kwargs.get("site_data")
        return "<html></html>", "abc12345"

    with patch.object(cli, "build_site_data", return_value=_site_data()), \
            patch.object(cli, "load_rules_from_file", return_value=MagicMock()), \
            patch.object(cli, "evaluate_rules", return_value=[]), \
            patch.object(cli, "analyze_cookies", return_value={}), \
            patch.object(cli, "generate_html_report", side_effect=fake_report), \
            patch.object(cli, "REPORTS_DIR", tmp_path / "reports"), \
            patch.object(cli, "_persist_scan_start", return_value=None), \
            patch.object(cli, "_persist_scan_result"), \
            patch.object(cli, "_persist_company") as persist_company, \
            patch.object(cli, "_report_to_dashboard"):
        cli.run_scan("https://www.feedzai.com/", company_result=company_result)

    captured["persist_company"] = persist_company
    return captured["site_data"]


def test_run_scan_merges_company_data_into_site_data(tmp_path):
    site_data = _run_scan_with_stubs(_result(legal_name="Feedzai, S.A."), tmp_path)

    assert site_data.company_legal_name == "Feedzai, S.A."
    assert site_data.company_nif == "508771862"
    assert site_data.company_address == "Rua Pedro Nunes, 3030-199 Coimbra"
    assert site_data.company_registry_verified is True
    assert site_data.company_nameservers == ["mary.ns.cloudflare.com", "pablo.ns.cloudflare.com"]


def test_run_scan_falls_back_to_commercial_name_when_there_is_no_legal_name(tmp_path):
    site_data = _run_scan_with_stubs(_result(), tmp_path)  # sem legal_name
    assert site_data.company_legal_name == "Feedzai"


def test_run_scan_without_company_result_leaves_fields_empty(tmp_path):
    site_data = _run_scan_with_stubs(None, tmp_path)

    assert site_data.company_legal_name is None
    assert site_data.company_nif is None
    assert site_data.company_registry_verified is None
    assert site_data.company_nameservers == []


def test_run_scan_converts_not_available_to_none(tmp_path):
    site_data = _run_scan_with_stubs(
        _result(nif="not available", address="not available", nameservers="not available"),
        tmp_path,
    )

    assert site_data.company_nif is None
    assert site_data.company_address is None
    assert site_data.company_nameservers == []


# --------------------------------------------------------------------------
# Persistência dos dados da empresa (tabela Companies)
# --------------------------------------------------------------------------

def _sqlite_conn():
    """Ligação SQLite em memória com o mesmo esquema usado pela aplicação."""
    import sqlite3
    from vigilantia.db.connection import SQLITE_SCHEMA

    conn = sqlite3.connect(":memory:")
    conn.executescript(SQLITE_SCHEMA)
    return conn


def test_company_repository_inserts_and_then_updates_the_same_website():
    from vigilantia.db.repository import CompanyRepository, WebsiteRepository

    conn = _sqlite_conn()
    website_id = WebsiteRepository(conn).get_or_create("https://www.feedzai.com/")
    repo = CompanyRepository(conn)

    first = repo.upsert(
        website_id,
        name="Feedzai",
        legal_name="Feedzai, S.A.",
        nif="508771862",
        address="Coimbra",
        registry_verified=False,
        note="Não confirmado.",
        nameservers=["mary.ns.cloudflare.com"],
    )
    second = repo.upsert(
        website_id,
        name="Feedzai",
        legal_name="Feedzai - Consultadoria e Inovação Tecnológica, S.A.",
        nif="508771862",
        address="Rua Pedro Nunes, Coimbra",
        registry_verified=True,
        note="Confirmado no Racius.",
        nameservers=["mary.ns.cloudflare.com", "pablo.ns.cloudflare.com"],
    )

    assert first == second, "o segundo scan deve atualizar, não criar outra linha"

    rows = conn.execute(
        "SELECT Name, LegalName, Nif, Address, RegistryVerified, NameserversJson "
        "FROM Companies"
    ).fetchall()
    assert len(rows) == 1
    name, legal, nif, address, verified, ns_json = rows[0]
    assert name == "Feedzai"
    assert legal.endswith("S.A.")
    assert nif == "508771862"
    assert address == "Rua Pedro Nunes, Coimbra"
    assert verified == 1
    assert "pablo.ns.cloudflare.com" in ns_json
    conn.close()


def test_company_repository_accepts_missing_optional_fields():
    from vigilantia.db.repository import CompanyRepository, WebsiteRepository

    conn = _sqlite_conn()
    website_id = WebsiteRepository(conn).get_or_create("https://exemplo.pt")
    company_id = CompanyRepository(conn).upsert(website_id, name="Exemplo")

    row = conn.execute(
        "SELECT Nif, Address, RegistryVerified, NameserversJson FROM Companies "
        "WHERE CompanyId = ?",
        (company_id,),
    ).fetchone()
    assert row == (None, None, None, None)
    conn.close()


def test_company_repository_handles_none_connection():
    from vigilantia.db.repository import CompanyRepository

    assert CompanyRepository(None).upsert(1, name="Exemplo") == 0


def test_persist_company_does_nothing_without_company_result():
    with patch("vigilantia.cli.get_connection") as get_conn:
        cli._persist_company("https://exemplo.pt", None)
    get_conn.assert_not_called()


def test_persist_company_is_fail_soft_when_db_unavailable(capsys):
    with patch("vigilantia.cli.get_connection", side_effect=RuntimeError("BD em baixo")):
        cli._persist_company("https://exemplo.pt", _result())

    saida = capsys.readouterr().out
    assert "[BD]" in saida
    assert "BD em baixo" in saida


def test_run_scan_persists_company_data(tmp_path):
    resolved = _result()
    with patch.object(cli, "build_site_data", return_value=_site_data()), \
            patch.object(cli, "load_rules_from_file", return_value=MagicMock()), \
            patch.object(cli, "evaluate_rules", return_value=[]), \
            patch.object(cli, "analyze_cookies", return_value={}), \
            patch.object(cli, "generate_html_report", return_value=("<html></html>", "abc12345")), \
            patch.object(cli, "REPORTS_DIR", tmp_path / "reports"), \
            patch.object(cli, "_persist_scan_start", return_value=None), \
            patch.object(cli, "_persist_scan_result"), \
            patch.object(cli, "_report_to_dashboard"), \
            patch.object(cli, "_persist_company") as persist_company:
        cli.run_scan("https://www.feedzai.com/", company_result=resolved)
        cli.run_scan("https://www.feedzai.com/")

    assert persist_company.call_count == 2
    assert persist_company.call_args_list[0][0][1] == resolved
    # Scan normal por URL: nada de empresa para gravar.
    assert persist_company.call_args_list[1][0][1] is None


# --------------------------------------------------------------------------
# Relatório HTML
# --------------------------------------------------------------------------

def test_report_shows_company_section_when_data_is_present():
    site_data = _site_data(
        company_legal_name="Feedzai - Consultadoria e Inovação Tecnológica, S.A.",
        company_nif="508771862",
        company_address="Rua Pedro Nunes, 3030-199 Coimbra",
        company_registry_verified=True,
        company_note="Dados confirmados através do Racius.com.",
        company_nameservers=["mary.ns.cloudflare.com"],
    )
    html, _ = generate_html_report("https://www.feedzai.com/", [], site_data=site_data)

    assert "Dados da empresa" in html
    assert "508771862" in html
    assert "Rua Pedro Nunes, 3030-199 Coimbra" in html
    assert "mary.ns.cloudflare.com" in html
    assert "Dados confirmados no Racius.com" in html
    # Site e domínio do site que foi mesmo analisado.
    assert "https://www.feedzai.com/" in html
    assert "feedzai.com</dd>" in html, "o domínio deve aparecer sem o www."


def test_report_highlights_unverified_registry_note():
    site_data = _site_data(
        company_nif="123456789",
        company_registry_verified=False,
        company_note="Dados não confirmados automaticamente — validar manualmente.",
    )
    html, _ = generate_html_report("https://www.feedzai.com/", [], site_data=site_data)

    assert "alert-banner" in html
    assert "validar manualmente" in html


def test_report_without_company_data_has_no_company_section():
    html, _ = generate_html_report("https://exemplo.pt", [], site_data=_site_data())
    assert "Dados da empresa" not in html

    html_sem_site_data, _ = generate_html_report("https://exemplo.pt", [])
    assert "Dados da empresa" not in html_sem_site_data
