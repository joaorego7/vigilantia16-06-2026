# run_cookie_test.py

import sys
import os
from pydantic import ValidationError

# Adicionar a pasta 'src' ao sys.path para conseguir importar o 'vigilantia'
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'src'))

from vigilantia.scraper.fetcher import fetch_page
from vigilantia.scraper.cookie_tester import analyze_cookies

def main():
    print("=== Fase 2: Teste de Consentimento de Cookies Ativo ===")
    url = input("Digite o URL do site a analisar (ex: https://example.com): ").strip()

    if not url:
        print("URL vazio. A sair...")
        sys.exit(1)

    print(f"\n[1] A iniciar o browser num estado limpo (sem cookies prévios)...")
    print(f"[2] A visitar {url} e a aguardar que a página carregue completamente...")

    try:
        # fetch_page já usa playwright com um contexto limpo por omissão
        result = fetch_page(url)
    except Exception as e:
        print(f"Erro ao aceder à página: {e}")
        sys.exit(1)

    cookies = result.cookies
    print(f"\n[3] Análise concluída. Foram encontrados {len(cookies)} cookies instalados ANTES de qualquer consentimento.")

    analysis = analyze_cookies(cookies, url)

    print("\n" + "="*50)
    print("RELATÓRIO DE COOKIES (PRÉ-CONSENTIMENTO)")
    print("="*50)

    tracking_cookies = analysis.get("Tracking/Analytics", [])
    other_cookies = analysis.get("Desconhecido/Necessário/Funcional", [])

    print(f"\nCookies de Tracking/Analytics detetados: {len(tracking_cookies)}")
    if tracking_cookies:
        print(">> ATENÇÃO: Possível violação grave do RGPD! Estes cookies requerem consentimento prévio (opt-in).")
        for idx, c in enumerate(tracking_cookies, 1):
            print(f"  {idx}. Nome: {c.get('name')}")
            print(f"     Domínio: {c.get('domain')}")
            print(f"     Caminho: {c.get('path')}")
            print(f"     Seguro (Secure): {c.get('secure')}")
            print(f"     HttpOnly: {c.get('httpOnly')}")
            print(f"     SameSite: {c.get('sameSite', 'N/A')}")
            print("-" * 30)
    else:
        print(">> Excelente: Não foram detetados cookies de tracking óbvios antes do consentimento.")

    print(f"\nOutros Cookies (Necessários/Funcionais/Desconhecidos): {len(other_cookies)}")
    for idx, c in enumerate(other_cookies, 1):
        print(f"  {idx}. Nome: {c.get('name')} | Domínio: {c.get('domain')}")

    print("\n" + "="*50)
    print("NOTA: O RGPD e a Diretiva ePrivacy exigem que apenas cookies estritamente necessários")
    print("sejam instalados antes de o utilizador dar um consentimento explícito e informado.")
    print("="*50)

if __name__ == "__main__":
    main()
