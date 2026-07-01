# run_vigilantia_mvp.py

from vigilantia.scraper.fetcher import fetch_page
from vigilantia.scraper.extractor import build_site_data
from bs4 import BeautifulSoup


def main():
    """
    Executável simples para o tutor experimentar o MVP da Vigilantia.
    Pede um URL, faz o fetch da página e imprime um relatório mínimo.
    """
    url = input("Digite o URL do site a analisar (ex: https://example.com): ").strip()

    print(f"\nA iniciar análise MVP para: {url}\n")

    try:
        html = fetch_page(url)
    except ValueError as exc:
        print("Erro ao obter a página.")
        print("Detalhe técnico:", exc)
        print("Sugestão: verifique se o URL está correto e se tem ligação à internet.")
        input("\nPressione Enter para sair...")
        return

    # Comentário:
    # Nesta fase, assumimos que o final_url é igual ao URL original
    # e que o idioma é desconhecido ("unknown"); isto será melhorado futuramente.
    final_url = url
    language = "unknown"

    site_data = build_site_data(html, page_url=url, final_url=final_url, language=language)

    print("=== Vigilantia MVP Report ===")
    print(f"URL analisado: {site_data.url}")
    print(f"Número de scripts de terceiros encontrados: {len(site_data.third_party_scripts)}")

    # Comentário:
    # Mostramos alguns exemplos de scripts de terceiros para o tutor ver
    # que tipos de serviços estão a ser identificados.
    for script in site_data.third_party_scripts[:5]:
        print(f"  - {script.src} ({script.category})")

    print(f"\nNúmero de formulários encontrados: {len(site_data.forms)}")
    for form in site_data.forms[:3]:
        print(f"  - Método: {form.method}, Action: {form.action}, Campos: {form.fields}")

    if site_data.privacy_policy_url:
        print(f"\nPolítica de privacidade encontrada em: {site_data.privacy_policy_url}")
    else:
        print("\nPolítica de privacidade: não encontrada (com base nas palavras-chave simples).")

    print(f"\nBanner de consentimento detetado: {site_data.consent_banner_detected}")
    print("\nNota: Esta ainda é uma análise mínima (MVP). A extração RGPD completa será adicionada nas próximas semanas.")

    input("\nPressione Enter para sair...")


if __name__ == "__main__":
    main()