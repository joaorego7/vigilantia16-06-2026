# src/scraper/fetcher.py

from typing import Optional

import logging
import requests
from pydantic import BaseModel, HttpUrl, ValidationError

# Comentário de cabeçalho:
# Este módulo trata da obtenção do HTML de uma página web usando pedidos HTTP.
# Nesta fase, apenas fazemos scraping estático com a biblioteca requests,
# com timeout, user-agent customizado e tratamento de erros.


logger = logging.getLogger(__name__)


class FetchConfig(BaseModel):
    """
    Configuration for the HTTP fetch operation.
    """

    timeout_seconds: int = 10
    verify_tls: bool = True


class UrlModel(BaseModel):
    """
    Simple model to validate a target URL using Pydantic.
    """

    target_url: HttpUrl


def fetch_page(url: str, config: Optional[FetchConfig] = None) -> str:
    """
    Fetch the HTML content of the given URL using an HTTP GET request.

    :param url: Target website URL as a string.
    :param config: Optional FetchConfig with timeout and TLS verification options.
    :return: HTML content of the page as a string.
    :raises ValueError: If the URL is invalid or the request fails.
    """
    # Comentário:
    # Primeiro, validamos o URL com Pydantic para garantir que tem um formato correto.
    try:
        UrlModel(target_url=url)
    except ValidationError:
        raise ValueError("Invalid URL format. Please provide a full URL, e.g. https://example.com")

    if config is None:
        config = FetchConfig()

    headers = {
        # Comentário:
        # Este User-Agent simula um browser real para reduzir a probabilidade
        # de o pedido ser bloqueado por mecanismos anti-bot básicos.
        "User-Agent": (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/123.0 Safari/537.36"
        )
    }

    try:
        # Comentário:
        # Aqui fazemos o pedido HTTP com timeout configurável e verificação de TLS.
        response = requests.get(
            url,
            headers=headers,
            timeout=config.timeout_seconds,
            verify=config.verify_tls,
        )
    except requests.exceptions.RequestException as exc:
        # Comentário:
        # Qualquer erro de rede (DNS, timeout, etc.) é registado e convertido
        # numa exceção genérica para o resto da aplicação.
        logger.error("Network error while fetching %s: %s", url, exc)
        raise ValueError(f"Network error while fetching {url}") from exc

    # Comentário:
    # Verificamos se o código de estado é 200 OK. Outros códigos podem indicar
    # erros do lado do servidor ou do cliente.
    if not response.ok:
        logger.warning("Non-success status code %s for URL %s", response.status_code, url)
        raise ValueError(f"Failed to fetch {url}: HTTP {response.status_code}")

    # Comentário:
    # Se tudo correu bem, devolvemos o conteúdo HTML como texto.
    return response.text