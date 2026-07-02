# src/vigilantia/cli.py

import typer
from pydantic import BaseModel, HttpUrl, ValidationError

from vigilantia.scraper.main import build_site_data
from vigilantia.analyzer.privacy_text import (
    download_privacy_policy,
    extract_plain_text,
    detect_language,
    check_required_elements,
)
from vigilantia.analyzer.rule_engine import load_rules_from_file, evaluate_rules
from collections import Counter


app = typer.Typer(help="Vigilantia - RGPD audit tool for websites (MVP).")


class UrlModel(BaseModel):
    target_url: HttpUrl


@app.command()
def scan(url: str = typer.Argument(..., help="Target website URL (e.g. https://example.com)")):
    try:
        UrlModel(target_url=url)
    except ValidationError:
        typer.echo("URL inválido. Por favor, forneça um URL completo (ex: https://example.com).")
        raise typer.Exit(code=1)

    typer.echo(f"Iniciar análise RGPD para {url} ...")

    # 1) Scraper → SiteData
    try:
        site_data = build_site_data(url)
    except ValueError as exc:
        typer.echo(f"Erro no scraper: {exc}")
        raise typer.Exit(code=1)

    # 2) Política de privacidade → flags
    policy_flags = {}
    if site_data.privacy_policy_url is not None:
        try:
            html = download_privacy_policy(str(site_data.privacy_policy_url))
            text = extract_plain_text(html)
            lang = detect_language(text)
            policy_flags = check_required_elements(text, language=lang)
        except ValueError as exc:
            typer.echo(f"Erro ao analisar política de privacidade: {exc}")

    # 3) Motor de regras → findings
    rules_config = load_rules_from_file("rules/gdpr_rules.yaml")
    findings = evaluate_rules(site_data, rules_config, policy_flags)

    # 4) Resumo de severidades
    severity_counts = Counter(f.severity for f in findings)
    num_high = severity_counts.get("high", 0)
    num_medium = severity_counts.get("medium", 0)
    num_low = severity_counts.get("low", 0)

    typer.echo("")
    typer.echo("=== Resumo de severidades ===")
    typer.echo(f"Problemas graves (high): {num_high}")
    typer.echo(f"Problemas médios (medium): {num_medium}")
    typer.echo(f"Problemas baixos (low): {num_low}")
    typer.echo("")

    # 5) Lista detalhada de não-conformidades
    if findings:
        print("=== Detalhe das não-conformidades ===")
    for f in findings:
        print(f"[{f.severity.upper()}] {f.id}")
        print(f"  {f.description}")
        print(f"  Recomendações: {f.recommendation}")
        # se evidence for dict, mostra a mensagem; caso contrário, mostra o valor bruto
        if isinstance(f.evidence, dict):
            print(f"  Evidência: {f.evidence.get('message')}")
        else:
            print(f"  Evidência: {f.evidence}")
        print("")
    else:
        print("Nenhuma não-conformidade RGPD detetada nas regras atuais.\n")


def main():
    app()


if __name__ == "__main__":
    main()