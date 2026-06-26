# src/vigilantia/cli.py

import typer
from pydantic import BaseModel, HttpUrl, ValidationError
from bs4 import BeautifulSoup

from vigilantia.scraper.fetcher import fetch_page

app = typer.Typer(help="Vigilantia - RGPD audit tool for websites (MVP).")


class UrlModel(BaseModel):
    """
    Simple model to validate a target URL using Pydantic.
    """
    target_url: HttpUrl


@app.command()
def scan(url: str = typer.Argument(..., help="Target website URL (e.g. https://example.com)")):
    """
    Minimal viable scan: fetches HTML and prints simple statistics.
    """
    # Comentário:
    # Validação básica do URL usando Pydantic para garantir que é bem formado.
    try:
        UrlModel(target_url=url)
    except ValidationError:
        typer.echo("URL inválido. Por favor, forneça um URL completo (ex: https://example.com).")
        raise typer.Exit(code=1)

    typer.echo(f"Starting MVP scan for {url} ...")

    # Comentário:
    # Usamos o fetcher para obter o HTML da página alvo, com timeout e tratamento de erros.
    try:
        html = fetch_page(url)
    except ValueError as exc:
        typer.echo(f"Erro ao obter a página: {exc}")
        raise typer.Exit(code=1)

    # Comentário:
    # A partir daqui, fazemos uma análise muito simples do HTML:
    # contamos scripts, formulários e procuramos referências a "privacy".
    soup = BeautifulSoup(html, "html.parser")

    script_tags = soup.find_all("script")
    form_tags = soup.find_all("form")
    privacy_mentions = soup.find_all(string=lambda text: text and "privacy" in text.lower())

    num_scripts = len(script_tags)
    num_forms = len(form_tags)
    num_privacy_mentions = len(privacy_mentions)

    typer.echo("")
    typer.echo("=== Vigilantia MVP Report ===")
    typer.echo(f"URL analisado: {url}")
    typer.echo(f"Número de scripts encontrados: {num_scripts}")
    typer.echo(f"Número de formulários encontrados: {num_forms}")
    typer.echo(f"Número de menções a 'privacy' no texto: {num_privacy_mentions}")
    typer.echo("")
    typer.echo("Nota: Esta é apenas uma análise mínima (MVP). A extração RGPD completa será adicionada nas próximas semanas.")


def main():
    """
    Main entrypoint for the Vigilantia CLI.
    """
    app()


if __name__ == "__main__":
    main()