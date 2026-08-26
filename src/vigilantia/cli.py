# src/vigilantia/cli.py

from datetime import datetime
from urllib.parse import urlparse

import typer
from dotenv import load_dotenv
from pydantic import BaseModel, HttpUrl, ValidationError

from vigilantia.scraper.main import build_site_data
from vigilantia.scraper.cookie_tester import analyze_cookies
from vigilantia.analyzer.privacy_text import (
    analyze_privacy_policy_multi_page,
    extract_plain_text,
    detect_language,
    check_required_elements,
)
from vigilantia.analyzer.rule_engine import load_rules_from_file, evaluate_rules
from vigilantia.reporter import generate_html_report
from vigilantia.paths import RULES_FILE, REPORTS_DIR
from vigilantia.db.connection import get_connection
from vigilantia.db.repository import WebsiteRepository, ScanRunRepository, FindingRepository
from vigilantia.db.dashboard import report_findings_to_dashboard
from collections import Counter
from typing import Optional


# Carrega o ficheiro .env (se existir) para os.environ, ANTES de qualquer
# scan correr. Bug corrigido (Semana 2): python-dotenv já estava listado
# em requirements.txt/pyproject.toml desde a Semana 1, mas load_dotenv()
# nunca era chamado em lado nenhum — DatabaseConfig.from_env() lê
# os.getenv() diretamente, pelo que sem esta chamada as variáveis
# VIGILANTIA_DB_* do .env nunca chegavam a ser vistas pela aplicação
# (só funcionava se estivessem exportadas manualmente na shell).
load_dotenv()

app = typer.Typer(help="Vigilantia - RGPD audit tool for websites (MVP).")


class UrlModel(BaseModel):
    target_url: HttpUrl


def _slugify_domain(url: str) -> str:
    """
    Extrai o domínio de um URL e transforma-o num texto seguro para usar
    como nome de ficheiro (substitui pontos por underscores).

    Exemplo: "https://www.exemplo.pt/pagina" -> "www_exemplo_pt"

    :param url: URL completo do site.
    :return: Domínio "limpo", pronto a usar num nome de ficheiro. Se o URL
        não tiver um hostname válido, devolve "site" como valor por omissão.
    """
    domain = urlparse(url).hostname or "site"
    return domain.replace(".", "_")


def _persist_scan_start(url: str) -> Optional[int]:
    """
    Regista o início do scan na base de dados: garante que o Website
    existe (get_or_create) e cria o registo de ScanRun com Status='Running'.

    Comportamento fail-soft (decisão explícita para a Semana 2): se a
    base de dados não estiver acessível (SQL Server em baixo, driver ODBC
    em falta, credenciais erradas, etc.), esta função NUNCA interrompe o
    scan — apenas avisa no terminal e devolve None. O resto de run_scan()
    trata None como "sem persistência disponível para este scan" e
    continua exatamente como se a base de dados não existisse, incluindo
    a geração do relatório HTML. Esta escolha segue o mesmo espírito do
    bug já corrigido no fetcher.py (networkidle best-effort): uma
    dependência auxiliar não deve impedir a entrega do resultado principal.

    :param url: URL do site a analisar, tal como recebido pelo CLI.
    :return: ScanRunId (int) se o registo foi criado com sucesso, ou None
        se a base de dados não estiver disponível.
    """
    try:
        with get_connection() as conn:
            website_id = WebsiteRepository(conn).get_or_create(url)
            scan_run_id = ScanRunRepository(conn).start(website_id)
            return scan_run_id
    except Exception as exc:
        typer.echo(
            f"[BD] Aviso: não foi possível registar o início do scan na "
            f"base de dados ({exc}). A continuar sem persistência.\n"
        )
        return None


def _persist_scan_result(
    scan_run_id: Optional[int],
    findings: list,
    report_id: str,
) -> None:
    """
    Grava o resultado de um scan bem-sucedido na base de dados: um registo
    dbo.Findings por cada não-conformidade encontrada, e marca o ScanRun
    correspondente como concluído (Status='Completed'), associando o
    report_id do relatório HTML gerado (ScanRuns.ReportRef).

    Fail-soft: se scan_run_id for None (a fase inicial já falhou) ou se a
    escrita falhar agora por qualquer motivo, apenas avisa e devolve —
    nunca interrompe o fluxo do CLI, que já gerou o relatório HTML antes
    de esta função ser chamada.

    :param scan_run_id: ScanRunId devolvido por _persist_scan_start(), ou
        None se a base de dados não estava disponível no início do scan.
    :param findings: Lista de Finding encontrados pelo motor de regras.
    :param report_id: ID curto do relatório HTML gerado por
        generate_html_report(), para cruzar o ScanRun com o ficheiro.
    """
    if scan_run_id is None:
        return

    try:
        with get_connection() as conn:
            FindingRepository(conn).insert_many(scan_run_id, findings)
            ScanRunRepository(conn).complete(scan_run_id, report_ref=report_id)
    except Exception as exc:
        typer.echo(
            f"[BD] Aviso: não foi possível gravar os resultados do scan na "
            f"base de dados ({exc}).\n"
        )


def _persist_scan_failure(scan_run_id: Optional[int], error_message: str) -> None:
    """
    Marca um ScanRun como falhado (Status='Failed') quando o scraper não
    consegue sequer obter os dados do site (ver ValueError em run_scan()).

    Fail-soft: se scan_run_id for None ou a própria escrita falhar, apenas
    avisa — o erro original do scraper já foi mostrado ao utilizador antes
    de chegarmos aqui.

    :param scan_run_id: ScanRunId devolvido por _persist_scan_start(), ou
        None se a base de dados não estava disponível.
    :param error_message: Mensagem de erro do scraper, guardada em
        ScanRuns.ErrorMessage para diagnóstico posterior.
    """
    if scan_run_id is None:
        return

    try:
        with get_connection() as conn:
            ScanRunRepository(conn).fail(scan_run_id, error_message)
    except Exception as exc:
        typer.echo(
            f"[BD] Aviso: não foi possível registar a falha do scan na "
            f"base de dados ({exc}).\n"
        )


def _report_to_dashboard(url: str, findings: list) -> None:
    """
    Reporta as não-conformidades encontradas para o dashboard de incidências (MSSQL remoto).
    Comportamento fail-soft: se o dashboard remoto falhar, avisa no terminal e continua.
    """
    try:
        report_findings_to_dashboard(url, findings)
    except Exception as exc:
        typer.echo(
            f"[DASHBOARD] Aviso: não foi possível enviar os dados para o "
            f"dashboard remoto ({exc}).\n"
        )


def run_scan(url: str) -> None:
    """
    Executa a análise RGPD completa para o URL indicado:
    - scraping real do site (Playwright + extractor)
    - análise da política de privacidade
    - avaliação das regras RGPD (motor de regras)
    - teste de cookies pré-consentimento
    - geração do relatório HTML (com histórico em /reports)

    Esta função é partilhada pelos dois pontos de entrada do projeto
    (o comando `vigilantia scan <url>` e o script interativo
    run_vigilantia_mvp.py), para evitar lógica duplicada e divergente.
    """
    typer.echo(f"\nA iniciar análise RGPD para: {url}\n")

    # 0) Regista o início do scan na base de dados (Website + ScanRun).
    # Fail-soft: se a BD não estiver disponível, scan_run_id fica None e
    # o resto do scan prossegue normalmente, só sem persistência.
    scan_run_id = _persist_scan_start(url)

    # 1) Scraper → SiteData (scripts, formulários, cookies, política, banner)
    try:
        site_data = build_site_data(url)
    except ValueError as exc:
        typer.echo(f"Erro no scraper: {exc}")
        _persist_scan_failure(scan_run_id, str(exc))
        raise typer.Exit(code=1)

    # 2) Política de privacidade → flags (direitos RGPD mencionados no texto)
    #
    # Bug corrigido: antes, uma falha de download deixava policy_flags={},
    # e o motor de regras interpretava "flag ausente" como "elemento RGPD
    # não mencionado", gerando 5 findings falsos (R06-R10). Agora marcamos
    # explicitamente com "_policy_unreachable" quando NENHUMA página pôde
    # ser lida, para o motor de regras gerar um único aviso (R12) em vez
    # disso.
    #
    # Melhoria: em vez de analisar só a página da política principal,
    # seguimos também um pequeno número de páginas legais relacionadas do
    # mesmo site (cookies, termos, contactos, RGPD/DPO dedicado), porque
    # muitos sites espalham a informação exigida pelo RGPD por várias
    # páginas (ex.: contacto do DPO só na página de "Contactos").
    policy_flags: dict = {}
    policy_pages_analyzed: list = []
    if site_data.privacy_policy_url is not None:
        try:
            policy_flags, policy_evidence_urls, policy_pages_analyzed = (
                analyze_privacy_policy_multi_page(str(site_data.privacy_policy_url))
            )
            if len(policy_pages_analyzed) > 1:
                typer.echo(
                    f"Política de privacidade analisada em {len(policy_pages_analyzed)} "
                    f"páginas relacionadas do site:"
                )
                for page in policy_pages_analyzed:
                    typer.echo(f"  - {page}")
                typer.echo("")
        except ValueError as exc:
            typer.echo(f"Erro ao analisar política de privacidade: {exc}")
            policy_flags = {"_policy_unreachable": True}

    # 3) Motor de regras → findings
    rules_config = load_rules_from_file(str(RULES_FILE))
    findings = evaluate_rules(site_data, rules_config, policy_flags)

    # 4) Resumo de severidades
    severity_counts = Counter(f.severity for f in findings)
    typer.echo("=== Resumo de severidades ===")
    typer.echo(f"Problemas graves (high): {severity_counts.get('high', 0)}")
    typer.echo(f"Problemas médios (medium): {severity_counts.get('medium', 0)}")
    typer.echo(f"Problemas baixos (low): {severity_counts.get('low', 0)}")
    typer.echo("")

    # 5) Lista detalhada de não-conformidades
    if findings:
        typer.echo("=== Detalhe das não-conformidades ===")
        for f in findings:
            typer.echo(f"[{f.severity.upper()}] {f.id}")
            typer.echo(f"  {f.description}")
            typer.echo(f"  Recomendação: {f.recommendation}")
            if isinstance(f.evidence, dict):
                typer.echo(f"  Evidência: {f.evidence.get('message')}")
            else:
                typer.echo(f"  Evidência: {f.evidence}")
            typer.echo("")
    else:
        typer.echo("Nenhuma não-conformidade RGPD detetada nas regras atuais.\n")

    # 6) Teste de cookies pré-consentimento
    typer.echo("=== Teste de Cookies Pré-Consentimento ===")
    cookies = site_data.cookies
    typer.echo(f"Foram encontrados {len(cookies)} cookies instalados ANTES de qualquer consentimento.")

    analysis = analyze_cookies(cookies, url)
    tracking_cookies = analysis.get("Tracking/Analytics", [])

    if tracking_cookies:
        typer.echo(f"\n>> ATENÇÃO: Foram detetados {len(tracking_cookies)} cookies de tracking/analytics!")
        for idx, c in enumerate(tracking_cookies, 1):
            typer.echo(f"  {idx}. Nome: {c.name} | Domínio: {c.domain}")
        typer.echo("Isto é uma possível violação grave do RGPD (falta de opt-in).")
    else:
        typer.echo("\n>> Não foram detetados cookies de tracking óbvios antes do consentimento.")
    typer.echo("")

    # 7) Geração do relatório HTML, com histórico por site + timestamp
    html, report_id = generate_html_report(
        site_url=url,
        findings=findings,
        total_cookies=len(cookies),
        tracking_cookies=tracking_cookies,
    )

    REPORTS_DIR.mkdir(parents=True, exist_ok=True)
    timestamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    report_path = REPORTS_DIR / f"vigilantia_{_slugify_domain(url)}_{timestamp}.html"
    report_path.write_text(html, encoding="utf-8")

    # Mantém também uma cópia "relatorio.html" na raiz, com o resultado mais recente,
    # para compatibilidade com quem já usa esse nome de ficheiro.
    latest_path = REPORTS_DIR.parent / "relatorio.html"
    latest_path.write_text(html, encoding="utf-8")

    typer.echo(f"[+] Relatório guardado em: {report_path}")
    typer.echo(f"[+] Última versão também disponível em: {latest_path}\n")

    # 8) Grava os findings na base de dados e conclui o ScanRun.
    # Fail-soft: corre DEPOIS do relatório já estar em disco, para que uma
    # falha aqui nunca ponha em causa a entrega do relatório ao utilizador.
    _persist_scan_result(scan_run_id, findings, report_id)

    # 9) Envia as não-conformidades para o dashboard de incidências (MSSQL remoto).
    # Fail-soft: falhas no dashboard não impedem o fim do scan.
    _report_to_dashboard(url, findings)


@app.command()
def scan(url: str = typer.Argument(..., help="Target website URL (e.g. https://example.com)")):
    """
    Comando do Typer que expõe run_scan() na linha de comandos.

    Como esta é a única @app.command() definida, o Typer trata-a como
    comando por omissão da aplicação — ou seja, usa-se
    "vigilantia https://exemplo.pt" diretamente, sem escrever a palavra
    "scan" (isso daria erro de "unexpected extra argument").

    Antes de chamar run_scan(), valida o formato do URL com o UrlModel
    (Pydantic), para dar um erro claro em português caso o URL esteja
    mal formado, em vez de deixar o erro rebentar mais fundo no scraper.

    :param url: URL do site a analisar, passado como argumento na linha de comandos.
    """
    try:
        UrlModel(target_url=url)
    except ValidationError:
        typer.echo("URL inválido. Por favor, forneça um URL completo (ex: https://example.com).")
        raise typer.Exit(code=1)

    run_scan(url)


def main():
    """
    Ponto de entrada do pacote instalado (ver [project.scripts] em
    pyproject.toml, que liga o comando "vigilantia" a esta função).
    Delega toda a lógica de parsing de argumentos para a aplicação Typer.
    """
    app()


if __name__ == "__main__":
    main()
