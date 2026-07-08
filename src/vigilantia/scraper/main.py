# src/vigilantia/scraper/main.py

from vigilantia.models.site_data import SiteData, Cookie
from vigilantia.scraper.fetcher import fetch_page
from vigilantia.scraper.extractor import build_site_data as _extract_full_site_data
from vigilantia.analyzer.privacy_text import extract_plain_text, detect_language


# Comentário geral:
# Este módulo é o "ponto de entrada" do scraper.
# Junta a lógica de:
#  - obter o HTML da página (fetch_page)
#  - extrair elementos relevantes (scripts, formulários, link da política,
#    banner de consentimento) usando as funções reais do extractor
#  - juntar os cookies capturados pelo Playwright (antes de qualquer
#    interação com a página, portanto "pré-consentimento")
#  - construir o objeto SiteData que será usado pelo analisador RGPD.
#
# Bug corrigido: esta função chamava antes extract_site_elements(), um
# "stub" que devolvia sempre dados vazios/fixos. As funções reais de
# extração (extract_third_party_scripts, extract_forms, etc.) existiam
# e tinham testes, mas nunca eram chamadas em produção. Agora usamos
# diretamente build_site_data() do extractor, que já as invoca todas.


def build_site_data(url: str) -> SiteData:
    """
    Constrói e devolve um objeto SiteData para o URL indicado.

    :param url: URL alvo do site a analisar.
    :return: Objeto SiteData com dados recolhidos pelo scraper.
    """
    # 1) Obter o HTML da página e os cookies reais (Playwright).
    fetch_result = fetch_page(url)
    html = fetch_result.html
    final_url = fetch_result.final_url
    raw_cookies = fetch_result.cookies

    # 2) Detetar o idioma da própria página (best-effort, reaproveitando
    #    a lógica já existente para a política de privacidade).
    plain_text = extract_plain_text(html)
    language = detect_language(plain_text)

    # 3) Extrair scripts de terceiros, formulários, política de privacidade
    #    e banner de consentimento usando as funções reais do extractor.
    site_data = _extract_full_site_data(
        html=html,
        page_url=url,
        final_url=final_url,
        language=language,
    )

    # 4) Substituir a lista de cookies (vazia por omissão no extractor)
    #    pelos cookies reais capturados pelo Playwright logo após o
    #    carregamento da página, sem qualquer interação com banners.
    site_data.cookies = [
        Cookie(
            name=c.get("name", ""),
            domain=c.get("domain", ""),
            path=c.get("path", "/"),
            secure=c.get("secure", False),
            httpOnly=c.get("httpOnly", False),
            sameSite=c.get("sameSite", None),
        )
        for c in raw_cookies
    ]

    return site_data
