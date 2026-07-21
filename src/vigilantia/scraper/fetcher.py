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
      - timeout_seconds: tempo máximo (em segundos) de espera pelo carregamento
        base da página (DOM pronto) antes de desistir. É o único timeout que,
        se excedido, faz o fetch falhar.
      - networkidle_grace_seconds: tempo extra (em segundos), best-effort, que
        se dá à página depois do DOM carregado para tentar ficar em "network
        idle" (0.5s sem pedidos de rede). Muitos sites com anúncios, analytics,
        websockets ou widgets de chat NUNCA ficam network-idle — por isso este
        valor é propositadamente curto e, se esgotar, NÃO faz o fetch falhar:
        seguimos em frente com o HTML que já temos.
      - verify_tls: se True, valida certificados HTTPS normalmente; se False, ignora
        erros de certificado (útil para testar sites com certificados inválidos/autoassinados).
    """
    timeout_seconds: int = 20
    networkidle_grace_seconds: int = 5
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

    Estratégia em duas fases:
      1) Espera obrigatoriamente que o DOM esteja pronto ("domcontentloaded").
         Se isto falhar/exceder o timeout, o fetch falha (ValueError).
      2) Dá depois uma janela curta e best-effort para a rede "acalmar"
         (networkidle), para dar hipótese a scripts assíncronos de tracking
         de correrem. Se esta segunda espera exceder o timeout, NÃO falhamos
         — seguimos com o HTML já obtido na fase 1. Isto evita que domínios
         com anúncios/analytics/websockets em atividade contínua (que nunca
         ficam "idle") bloqueiem indefinidamente e impeçam a geração de
         relatório.

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

            # FASE 1 (obrigatória): navega para o URL e aguarda apenas que o DOM
            # esteja pronto ("domcontentloaded"). Isto é rápido e fiável em
            # praticamente qualquer site, ao contrário de "networkidle".
            #
            # Nota: o timeout é sempre em milissegundos na API do Playwright.
            # Bug corrigido: multiplicava-se por 3000 em vez de 1000, o que
            # inflacionava o timeout real (ex.: 15s configurados -> 45s reais).
            response = page.goto(
                url,
                timeout=config.timeout_seconds * 1000,
                wait_until="domcontentloaded",
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

            # FASE 2 (best-effort, NÃO fatal): agora que já temos um DOM válido,
            # damos à página uma janela curta de graça para tentar ficar
            # "network idle", o que costuma significar que scripts assíncronos
            # (trackers, widgets, chamadas a APIs) já correram.
            #
            # Bug corrigido: antes, esta espera por networkidle era a ÚNICA
            # condição de sucesso e o timeout era fatal. Em domínios com
            # anúncios, analytics, websockets ou chat widgets a rede nunca
            # "acalma" — a página ficava sempre a demorar o timeout completo
            # e o fetch falhava sempre, sem gerar relatório nenhum. Agora, se
            # esta espera extra esgotar, apenas seguimos em frente com o HTML
            # que já temos (que já inclui o DOM completo da fase 1).
            try:
                page.wait_for_load_state(
                    "networkidle",
                    timeout=config.networkidle_grace_seconds * 1000,
                )
            except PlaywrightTimeoutError:
                logger.info(
                    "Network idle nao atingido para %s dentro do periodo de "
                    "graca (%ss); a prosseguir com o HTML ja carregado.",
                    url,
                    config.networkidle_grace_seconds,
                )

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
    except ValueError:
        # Bug corrigido: estes são os ValueError que nós próprios lançamos acima
        # (URL inválido, sem resposta, HTTP não-2xx). Antes, o "except Exception"
        # abaixo apanhava-os também e reescrevia a mensagem para um genérico
        # "Error while fetching {url}", escondendo a causa real (ex.: "HTTP 500")
        # de quem consome esta função (CLI, logs). Aqui deixamo-los propagar tal
        # como foram lançados, com a mensagem específica intacta.
        raise
    except Exception as exc:
        # Qualquer outro erro verdadeiramente inesperado (rede em baixo, DNS não
        # resolve, etc.) é convertido em ValueError para manter uma interface de
        # erros consistente para quem chama esta função.
        logger.error("Error while fetching %s: %s", url, exc)
        raise ValueError(f"Error while fetching {url}") from exc