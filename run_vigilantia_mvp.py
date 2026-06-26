# run_vigilantia_mvp.py

from vigilantia.scraper.fetcher import fetch_page
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

    soup = BeautifulSoup(html, "html.parser")

    scripts = soup.find_all("script")
    forms = soup.find_all("form")
    privacy_mentions = soup.find_all(string=lambda text: text and "privacy" in text.lower())

    print("=== Vigilantia MVP Report ===")
    print(f"URL analisado: {url}")
    print(f"Número de scripts encontrados: {len(scripts)}")
    print(f"Número de formulários encontrados: {len(forms)}")
    print(f"Número de menções a 'privacy' no texto: {len(privacy_mentions)}")
    print("\nNota: Esta é apenas uma análise mínima (MVP).")

    # Comentário:
    # Esta linha garante que a janela de terminal não fecha imediatamente
    # após apresentar os resultados, permitindo ao tutor ler o relatório
    # com calma antes de sair.
    input("\nPressione Enter para sair...")


if __name__ == "__main__":
    main()