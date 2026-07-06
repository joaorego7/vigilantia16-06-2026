# run_vigilantia_mvp.py

import typer
from collections import Counter
from bs4 import BeautifulSoup
from pydantic import ValidationError

from vigilantia.scraper.fetcher import fetch_page
from vigilantia.scraper.main import build_site_data
from vigilantia.analyzer.privacy_text import (
    download_privacy_policy,
    extract_plain_text,
    detect_language,
    check_required_elements,
)
from vigilantia.analyzer.rule_engine import load_rules_from_file, evaluate_rules

app = typer.Typer()


@app.command()
def scan():
    """
    Fluxo MVP + resumo RGPD:
    - pede URL
    - faz scraping mínimo (scripts, formulários, política, banner)
    - constrói SiteData
    - analisa política de privacidade
    - aplica regras RGPD
    - mostra resumo de severidades e detalhes de não-conformidades
    """
    url = input("Digite o URL do site a analisar (ex: https://example.com): ").strip()

    if not url:
        print("URL vazio. Saindo.")
        return

    print(f"\nA iniciar análise MVP para: {url}\n")

    # ==============================
    # Parte 1: MVP antigo (scraping simples)
    # ==============================
    try:
        fetch_result = fetch_page(url)
        html = fetch_result.html
    except ValueError as exc:
        print(f"Erro ao obter a página: {exc}")
        return

    soup = BeautifulSoup(html, "html.parser")

    # Scripts de terceiros (exemplo simplificado)
    script_tags = soup.find_all("script")
    third_party_scripts = []
    for s in script_tags:
        src = s.get("src")
        if src and not src.startswith(url):
            third_party_scripts.append(src)

    # Formulários
    form_tags = soup.find_all("form")
    forms = []
    for f in form_tags:
        method = f.get("method", "GET").upper()
        action = f.get("action")
        fields = [inp.get("name") for inp in f.find_all("input") if inp.get("name")]
        forms.append((method, action, fields))

    # Política de privacidade (procura simples)
    privacy_link = None
    for a in soup.find_all("a", href=True):
        text = (a.get_text() or "").lower()
        if "privacidade" in text or "privacy" in text:
            privacy_link = a["href"]
            break

    # Banner de consentimento (procura simples)
    banner_detected = False
    if soup.find(string=lambda t: t and "cookies" in t.lower()):
        banner_detected = True

    print("=== Vigilantia MVP Report ===")
    print(f"URL analisado: {url}")
    print(f"Número de scripts de terceiros encontrados: {len(third_party_scripts)}")
    for src in third_party_scripts[:5]:
        print(f"  - {src} (other)")

    print(f"\nNúmero de formulários encontrados: {len(forms)}")
    for method, action, fields in forms[:5]:
        print(f"  - Método: {method}, Action: {action}, Campos: {fields}")

    if privacy_link:
        print(f"\nPolítica de privacidade encontrada em: {privacy_link}")
    else:
        print("\nPolítica de privacidade não encontrada na análise simples.")

    print(f"\nBanner de consentimento detetado: {banner_detected}")
    print("\nNota: Esta ainda é uma análise mínima (MVP). A extração RGPD completa está a ser adicionada.\n")

    # ==============================
    # Parte 2: Fluxo RGPD com SiteData + regras
    # ==============================

    # 2.1 Construir SiteData com o scraper real
    try:
        site_data = build_site_data(url)
    except ValueError as exc:
        print(f"Erro ao construir SiteData: {exc}")
        return

    # 2.2 Analisar política de privacidade → flags
    policy_flags = {}
    if site_data.privacy_policy_url is not None:
        try:
            policy_html = download_privacy_policy(str(site_data.privacy_policy_url))
            policy_text = extract_plain_text(policy_html)
            lang = detect_language(policy_text)
            policy_flags = check_required_elements(policy_text, language=lang)
        except ValueError as exc:
            print(f"Erro ao analisar política de privacidade detalhada: {exc}")

    # 2.3 Carregar regras e avaliar
    rules_config = load_rules_from_file("rules/gdpr_rules.yaml")
    findings = evaluate_rules(site_data, rules_config, policy_flags)

    # 2.4 Resumo de severidades
    severity_counts = Counter(f.severity for f in findings)
    num_high = severity_counts.get("high", 0)
    num_medium = severity_counts.get("medium", 0)
    num_low = severity_counts.get("low", 0)

    print("=== Resumo RGPD (motor de regras) ===")
    print(f"Problemas graves (high): {num_high}")
    print(f"Problemas médios (medium): {num_medium}")
    print(f"Problemas baixos (low): {num_low}")
    print("")

    # 2.5 Detalhe das não-conformidades
    if findings:
        print("=== Detalhe das não-conformidades ===")
    for f in findings:
        print(f"[{f.severity.upper()}] {f.id}")
        print(f"  {f.description}")
        print(f"  Recomendações: {f.recommendation}")
        if isinstance(f.evidence, dict):
            print(f"  Evidência: {f.evidence.get('message')}")
        else:
            print(f"  Evidência: {f.evidence}")
        print("")
    else:
        print("Nenhuma não-conformidade RGPD detetada nas regras atuais.\n")

    input("Pressione Enter para sair...")


if __name__ == "__main__":
    app()