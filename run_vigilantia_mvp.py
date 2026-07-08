# run_vigilantia_mvp.py
#
# Comentário:
# Este script é o ponto de entrada "interativo" do Vigilantia (pede o URL
# por input(), em vez de o receber como argumento de linha de comandos).
#
# Bug corrigido: este ficheiro tinha uma cópia quase inteira da lógica de
# scraping/regras/relatório que também existia em src/vigilantia/cli.py.
# As duas versões já tinham começado a divergir (esta tinha uma secção
# extra de teste de cookies que a outra não tinha). Agora ambos os pontos
# de entrada chamam a mesma função run_scan(), definida uma única vez.

import sys
import os

# Adicionar a pasta 'src' ao sys.path para conseguir importar o 'vigilantia'
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'src'))

from vigilantia.cli import run_scan, UrlModel
from pydantic import ValidationError


def main() -> None:
    url = input("Digite o URL do site a analisar (ex: https://example.com): ").strip()

    if not url:
        print("URL vazio. Saindo.")
        return

    try:
        UrlModel(target_url=url)
    except ValidationError:
        print("URL inválido. Por favor, forneça um URL completo (ex: https://example.com).")
        return

    run_scan(url)
    input("Pressione Enter para sair...")


if __name__ == "__main__":
    main()
