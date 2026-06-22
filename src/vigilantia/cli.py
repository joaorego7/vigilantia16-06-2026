# src/cli.py

import typer
from pydantic import BaseModel, HttpUrl, ValidationError

app = typer.Typer(help="Vigilantia - RGPD audit tool for websites.")

# Comentário de cabeçalho:
# Esta função é o ponto de entrada do subcomando 'scan'.
# Recebe um URL como argumento posicional, valida o seu formato
# e, nesta fase inicial, apenas imprime uma mensagem simples.
class UrlModel(BaseModel):
    target_url: HttpUrl


@app.command()
def scan(url: str = typer.Argument(..., help="Target website URL (e.g. https://exemplo.pt)")):
    """
    Start a basic scan for the given URL.
    """
    try:
        # Comentário:
        # Aqui usamos Pydantic para validar se o URL fornecido tem um formato válido.
        UrlModel(target_url=url)
    except ValidationError:
        typer.echo("URL inválido. Por favor, forneça um URL completo (ex: https://exemplo.pt).")
        raise typer.Exit(code=1)

    typer.echo(f"scan started for {url}")


def main():
    """
    Main entrypoint for the Vigilantia CLI.
    """
    # Comentário:
    # Esta função permite executar o CLI com 'python -m src.cli'.
    app()


if __name__ == "__main__":
    main()