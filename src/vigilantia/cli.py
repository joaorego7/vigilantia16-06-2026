# src/vigilantia/cli.py

from datetime import datetime
from urllib.parse import urlparse

import typer
from pydantic import BaseModel, HttpUrl, ValidationError

from vigilantia.scraper.main import build_site_data
from vigilantia.scraper.cookie_tester import analyze_cookies
from vigilantia.analyzer.privacy_text import (
    download_privacy_policy,
    extract_plain_text,
    detect_language,
    check_required_elements,
)
from vigilantia.analyzer.rule_engine import load_rules_from_file, evaluate_rules
from vigilantia.reporter import generate_html_report
from vigilantia.paths import RULES_FILE, REPORTS_DIR
from collections import Counter


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

    # 1) Scraper → SiteData (scripts, formulários, cookies, política, banner)
    try:
        site_data = build_site_data(url)
    except ValueError as exc:
        typer.echo(f"Erro no scraper: {exc}")
        raise typer.Exit(code=1)

    # 2) Política de privacidade → flags (direitos RGPD mencionados no texto)
    policy_flags = {}
    if site_data.privacy_policy_url is not None:
        try:
            policy_html = download_privacy_policy(str(site_data.privacy_policy_url))
            policy_text = extract_plain_text(policy_html)
            lang = detect_language(policy_text)
            policy_flags = check_required_elements(policy_text, language=lang)
        except ValueError as exc:
            typer.echo(f"Erro ao analisar política de privacidade: {exc}")

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
    html = generate_html_report(
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
