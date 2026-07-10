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
    Configuração usada na operação de fetch (obtenção da página) com o Playwright.

    Campos:
      - timeout_seconds: tempo máximo (em segundos) de espera pela página antes de desistir.
      - verify_tls: se True, valida certificados HTTPS normalmente; se False, ignora
        erros de certificado (útil para testar sites com certificados inválidos/autoassinados).
    """
    timeout_seconds: int = 15
    verify_tls: bool = True

class FetchResult(BaseModel):
    """
    Resultado devolvido por fetch_page() depois de carregar a página.

    Campos:
      - html: o HTML final da página, já com JavaScript executado.
      - final_url: o URL onde a página acabou por ficar (pode ser diferente do
        URL pedido, se tiver havido redirecionamentos).
      - cookies: lista de cookies presentes no browser logo após o carregamento,
        ou seja, ANTES de qualquer interação com banners de consentimento
        (é a isto que chamamos "cookies pré-consentimento").
    """
    html: str
    final_url: str
    cookies: list[dict]


class UrlModel(BaseModel):
    """
    Modelo simples para validar um URL alvo, usando o Pydantic.
    Serve só para confirmar que o texto recebido é mesmo um URL válido
    (com esquema http/https) antes de tentarmos usá-lo no Playwright.
    """
    target_url: HttpUrl


def fetch_page(url: str, config: Optional[FetchConfig] = None) -> FetchResult:
    """
    Vai buscar o conteúdo HTML do URL indicado, usando o Playwright (browser headless).

    Espera até a rede "acalmar" (networkidle) antes de ler o HTML, para garantir
    que scripts assíncronos, chamadas a APIs e conteúdo carregado por JavaScript
    já tiveram oportunidade de correr. Isto é importante para um scanner de RGPD,
    porque muitos scripts de tracking só disparam depois do carregamento inicial.

    :param url: URL do site a analisar (string).
    :param config: Configuração opcional (timeout, validação TLS). Se omitido,
        usa os valores por omissão de FetchConfig.
    :return: Um FetchResult com o HTML, o URL final e os cookies capturados.
    :raises ValueError: Se o URL for inválido, se não houver resposta, se a
        resposta tiver um código de erro HTTP, ou se ocorrer um timeout/erro
        de rede durante o carregamento.
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
                timeout=config.timeout_seconds * 3000,
                wait_until="networkidle"
            )
            
            if response is None:
                # Acontece em casos raros (ex.: navegação abortada); sem resposta,
                # não há HTML nenhum para analisar, por isso desistimos aqui.
                browser.close()
                raise ValueError(f"Failed to fetch {url}: No response received.")
            
            if not response.ok:
                # Código de estado fora do intervalo 2xx/3xx (ex.: 404, 500) —
                # registamos um aviso e desistimos, para não analisar uma página de erro.
                logger.warning("Non-success status code %s for URL %s", response.status, url)
                browser.close()
                raise ValueError(f"Failed to fetch {url}: HTTP {response.status}")
            
            # Neste ponto a página carregou com sucesso: extraímos o HTML final
            # (já com JavaScript executado), o URL final (após redirecionamentos)
            # e os cookies presentes no contexto do browser neste preciso momento.
            html_content = page.content()
            final_url = page.url
            cookies = context.cookies()
            browser.close()
            return FetchResult(html=html_content, final_url=final_url, cookies=cookies)
            
    except PlaywrightTimeoutError as exc:
        # A página demorou mais do que timeout_seconds a responder/carregar.
        logger.error("Timeout error while fetching %s: %s", url, exc)
        raise ValueError(f"Timeout error while fetching {url}") from exc
    except Exception as exc:
        # Qualquer outro erro inesperado (rede em baixo, DNS não resolve, etc.)
        # é convertido em ValueError para manter uma interface de erros consistente
        # para quem chama esta função.
        logger.error("Error while fetching %s: %s", url, exc)
        raise ValueError(f"Error while fetching {url}") from exc