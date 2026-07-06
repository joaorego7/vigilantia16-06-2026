# src/vigilantia/scraper/main.py

from vigilantia.models.site_data import SiteData
from vigilantia.scraper.fetcher import fetch_page
from vigilantia.scraper.extractor import extract_site_elements


# Comentário geral:
# Este módulo é o "ponto de entrada" do scraper.
# Junta a lógica de:
#  - obter o HTML da página (fetch_page)
#  - extrair elementos relevantes (cookies, scripts, formulários, link da política)
#  - construir o objeto SiteData que será usado pelo analisador RGPD.


def build_site_data(url: str) -> SiteData:
    """
    Constrói e devolve um objeto SiteData para o URL indicado.

    :param url: URL alvo do site a analisar.
    :return: Objeto SiteData com dados recolhidos pelo scraper.
    """
    # 1) Obter o HTML da página usando a função fetch_page
    #    (ela trata de decidir requests vs Playwright, conforme o teu design)
    fetch_result = fetch_page(url)
    html = fetch_result.html
    final_url = fetch_result.final_url
    raw_cookies = fetch_result.cookies

    # 2) Usar o extractor para analisar o HTML e extrair:
    #    - cookies
    #    - scripts de terceiros
    #    - formulários
    #    - link para política de privacidade
    #    - deteção de banner de consentimento, etc.
    #
    #    Vamos assumir que extract_site_elements devolve um dicionário
    #    com os campos necessários para criar o SiteData.
    extracted = extract_site_elements(url=final_url, html=html)

    # 3) Construir o objeto SiteData com base nos dados extraídos.
    #    Aqui estamos a mapear explicitamente o dicionário 'extracted'
    #    para os campos do modelo SiteData.
    from vigilantia.models.site_data import Cookie
    mapped_cookies = [
        Cookie(
            name=c.get("name", ""),
            domain=c.get("domain", ""),
            path=c.get("path", "/"),
            secure=c.get("secure", False),
            httpOnly=c.get("httpOnly", False),
            sameSite=c.get("sameSite", None)
        )
        for c in raw_cookies
    ]

    site_data = SiteData(
        url=url,
        final_url=final_url,
        language=extracted.get("language", "unknown"),
        cookies=mapped_cookies,
        third_party_scripts=extracted.get("third_party_scripts", []),
        forms=extracted.get("forms", []),
        privacy_policy_url=extracted.get("privacy_policy_url"),
        consent_banner_detected=extracted.get("consent_banner_detected", False),
    )

    return site_data