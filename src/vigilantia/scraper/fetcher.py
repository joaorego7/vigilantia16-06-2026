# src/scraper/fetcher.py

from typing import Optional
import logging
from pydantic import BaseModel, HttpUrl, ValidationError
from playwright.sync_api import sync_playwright, TimeoutError as PlaywrightTimeoutError

# Comentário de cabeçalho:
# Este módulo trata da obtenção do HTML de uma página web usando Playwright (Headless Browser).
# Nesta fase, usamos a API síncrona do Playwright para garantir que o JavaScript é executado
# e todo o conteúdo dinâmico é carregado antes de extrairmos o HTML.

logger = logging.getLogger(__name__)


class FetchConfig(BaseModel):
    """
    Configuration for the Playwright fetch operation.
    """
    timeout_seconds: int = 15
    verify_tls: bool = True

class FetchResult(BaseModel):
    html: str
    final_url: str
    cookies: list[dict]


class UrlModel(BaseModel):
    """
    Simple model to validate a target URL using Pydantic.
    """
    target_url: HttpUrl


def fetch_page(url: str, config: Optional[FetchConfig] = None) -> FetchResult:
    """
    Fetch the HTML content of the given URL using Playwright.
    Wait for network idle to ensure dynamic content is loaded.

    :param url: Target website URL as a string.
    :param config: Optional FetchConfig with timeout and TLS verification options.
    :return: FetchResult containing HTML, final_url, and cookies.
    :raises ValueError: If the URL is invalid or the request fails.
    """
    try:
        UrlModel(target_url=url)
    except ValidationError:
        raise ValueError("Invalid URL format. Please provide a full URL, e.g. https://example.com")

    if config is None:
        config = FetchConfig()

    try:
        with sync_playwright() as p:
            # Lança o Chromium em modo headless
            browser = p.chromium.launch(headless=True)
            
            # Configura um contexto com ignore_https_errors opcional e um User-Agent realista
            context = browser.new_context(
                ignore_https_errors=not config.verify_tls,
                user_agent=(
                    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                    "AppleWebKit/537.36 (KHTML, like Gecko) "
                    "Chrome/123.0 Safari/537.36"
                )
            )
            page = context.new_page()
            
            # Navega para o URL e aguarda que o tráfego de rede acalme (networkidle)
            response = page.goto(
                url,
                timeout=config.timeout_seconds * 1000,
                wait_until="networkidle"
            )
            
            if response is None:
                browser.close()
                raise ValueError(f"Failed to fetch {url}: No response received.")
            
            if not response.ok:
                logger.warning("Non-success status code %s for URL %s", response.status, url)
                browser.close()
                raise ValueError(f"Failed to fetch {url}: HTTP {response.status}")
            
            html_content = page.content()
            final_url = page.url
            cookies = context.cookies()
            browser.close()
            return FetchResult(html=html_content, final_url=final_url, cookies=cookies)
            
    except PlaywrightTimeoutError as exc:
        logger.error("Timeout error while fetching %s: %s", url, exc)
        raise ValueError(f"Timeout error while fetching {url}") from exc
    except Exception as exc:
        logger.error("Error while fetching %s: %s", url, exc)
        raise ValueError(f"Error while fetching {url}") from exc