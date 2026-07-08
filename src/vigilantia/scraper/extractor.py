# src/vigilantia/scraper/extractor.py

from typing import List, Optional
from urllib.parse import urlparse, urljoin

from bs4 import BeautifulSoup

from vigilantia.models.site_data import SiteData, Cookie, ThirdPartyScript, Form

# Comentário de cabeçalho:
# Este módulo trata da extração de elementos relevantes para RGPD
# a partir do HTML de uma página: scripts de terceiros, formulários,
# links de política de privacidade e bandeiras de consentimento de cookies.


def _get_domain(url: str) -> str:
    """
    Extract the domain from a URL string.

    :param url: URL as string.
    :return: Domain (hostname) or empty string if parsing fails.
    """
    # Comentário:
    # Esta função auxiliar simplifica a comparação entre domínios,
    # permitindo distinguir scripts internos de scripts de terceiros.
    parsed = urlparse(url)
    return parsed.hostname or ""


def classify_script_category(src: str) -> str:
    """
    Classify a third-party script into a simple category based on its URL.

    :param src: Script URL.
    :return: Category string (e.g. "analytics", "advertising", "social", "other").
    """
    # Comentário:
    # Esta função tenta identificar o tipo de script a partir de padrões
    # simples no URL. Isto ajuda a distinguir, por exemplo, analytics de ads.
    lower_src = src.lower()
    if "google-analytics" in lower_src or "gtag/js" in lower_src or "analytics" in lower_src:
        return "analytics"
    if "doubleclick" in lower_src or "ads" in lower_src or "adservice" in lower_src:
        return "advertising"
    if "facebook" in lower_src or "twitter" in lower_src or "linkedin" in lower_src:
        return "social"
    return "other"

def extract_third_party_scripts(html: str, page_url: str) -> List[ThirdPartyScript]:
    """
    Extract third-party scripts from the given HTML.

    :param html: HTML content of the page.
    :param page_url: Original page URL (used to determine the base domain).
    :return: List of ThirdPartyScript objects.
    """
    # Comentário:
    # Aqui percorremos todos os elementos <script> com atributo src
    # e comparamos o domínio do script com o domínio da página.
    # Se forem diferentes, consideramos que é um script de terceiros.
    soup = BeautifulSoup(html, "html.parser")
    base_domain = _get_domain(page_url)
    third_party_scripts: List[ThirdPartyScript] = []

    for script_tag in soup.find_all("script"):
        src = script_tag.get("src")
        if not src:
            continue

        # Comentário:
        # Alguns scripts usam URLs relativos; neste caso,
        # são resolvidos contra o URL base da página.
        absolute_src = urljoin(page_url, src)
        script_domain = _get_domain(absolute_src)

        # Comentário:
        # Se o domínio do script não corresponder ao domínio do site,
        # consideramos o script como de terceiros.
        if script_domain and script_domain != base_domain:
            category = classify_script_category(absolute_src)
            third_party_scripts.append(
                ThirdPartyScript(
                    src=absolute_src,
                    category=category,
                )
            )

    return third_party_scripts


# Comentário:
# Palavras-chave usadas para detetar um "aviso de privacidade" (texto que
# explica a finalidade do tratamento) perto de um formulário. É uma
# heurística simples baseada em texto, não uma análise jurídica.
_PRIVACY_NOTICE_KEYWORDS = [
    "dados pessoais", "política de privacidade", "privacidade",
    "rgpd", "gdpr", "finalidade", "tratamento dos seus dados",
    "tratamento de dados", "privacy policy", "personal data",
    "how we use your data", "how your data",
]


def _text_mentions_privacy_notice(text: str) -> bool:
    """
    Verifica se um bloco de texto contém alguma das palavras-chave
    associadas a um aviso de privacidade.

    :param text: Texto simples a analisar.
    :return: True se alguma palavra-chave for encontrada.
    """
    lower_text = (text or "").lower()
    return any(keyword in lower_text for keyword in _PRIVACY_NOTICE_KEYWORDS)


def _has_nearby_privacy_notice(form_tag) -> bool:
    """
    Procura um aviso de privacidade perto de um formulário: dentro do
    próprio formulário (ex.: texto de ajuda por baixo dos campos) ou no
    elemento pai imediato (onde costuma estar um texto introdutório).

    :param form_tag: Elemento <form> do BeautifulSoup.
    :return: True se for encontrado texto relacionado com privacidade.
    """
    # Texto dentro do próprio formulário (labels, notas, checkboxes de consentimento).
    if _text_mentions_privacy_notice(form_tag.get_text(separator=" ")):
        return True

    # Texto no elemento pai (comum ter uma frase introdutória antes do formulário).
    parent = form_tag.parent
    if parent is not None and _text_mentions_privacy_notice(parent.get_text(separator=" ")):
        return True

    return False


def extract_forms(html: str, page_url: str) -> List[Form]:
    """
    Extract HTML forms from the given page.

    :param html: HTML content of the page.
    :param page_url: Original page URL (used to resolve relative actions).
    :return: List of Form objects.
    """
    # Comentário:
    # Este método identifica todos os <form> e recolhe:
    # - action (URL de submissão)
    # - method (GET/POST)
    # - fields (nomes dos campos de input/textarea)
    # - has_nearby_privacy_notice (se há texto de privacidade perto).
    soup = BeautifulSoup(html, "html.parser")
    forms: List[Form] = []

    for form_tag in soup.find_all("form"):
        action = form_tag.get("action")
        if action:
            action = urljoin(page_url, action)
        method = (form_tag.get("method") or "GET").upper()

        fields: List[str] = []

        # Comentário:
        # Percorremos inputs e textareas dentro do formulário
        # para recolher os nomes dos campos (atributo name).
        for input_tag in form_tag.find_all("input"):
            name = input_tag.get("name")
            if name:
                fields.append(name)

        for textarea_tag in form_tag.find_all("textarea"):
            name = textarea_tag.get("name")
            if name:
                fields.append(name)

        forms.append(
            Form(
                action=action,
                method=method,
                fields=fields,
                has_nearby_privacy_notice=_has_nearby_privacy_notice(form_tag),
            )
        )

    return forms


def extract_privacy_policy_url(html: str, page_url: str) -> Optional[str]:
    """
    Try to find a link to the privacy policy in the HTML.

    :param html: HTML content of the page.
    :param page_url: Original page URL (used to resolve relative links).
    :return: URL string of the privacy policy, or None if not found.
    """
    # Comentário:
    # Este método procura <a> cujo texto sugira um link para a política
    # de privacidade, termos ou cookies, usando palavras-chave simples.
    soup = BeautifulSoup(html, "html.parser")
    keywords = ["privacy", "privacidade", "política de privacidade", "cookies", "terms", "termos"]

    for link_tag in soup.find_all("a"):
        href = link_tag.get("href")
        if not href:
            continue

        text = (link_tag.get_text() or "").strip().lower()
        if any(keyword in text for keyword in keywords):
            return urljoin(page_url, href)

    return None


def detect_consent_banner(html: str) -> bool:
    """
    Detect whether a cookie consent banner is present in the HTML.

    :param html: HTML content of the page.
    :return: True if a consent banner is likely present, False otherwise.
    """
    # Comentário:
    # Aqui tentamos detectar um banner de consentimento de cookies
    # com base em texto típico encontrado em banners de CMP.
    soup = BeautifulSoup(html, "html.parser")

    banner_keywords = [
        "aceitar cookies",
        "accept cookies",
        "cookie consent",
        "este site utiliza cookies",
        "we use cookies",
    ]

    # Comentário:
    # Procuramos texto que contenha estas expressões, de forma simples.
    for text_node in soup.find_all(string=True):
        if not text_node:
            continue
        lower_text = text_node.lower()
        if any(keyword in lower_text for keyword in banner_keywords):
            return True

    return False


def build_site_data(html: str, page_url: str, final_url: str, language: str) -> SiteData:
    """
    Build a SiteData instance from the given HTML and metadata.

    :param html: HTML content of the page.
    :param page_url: Original page URL.
    :param final_url: Final URL after redirects (for now, may be same as page_url).
    :param language: Detected language code (e.g. "pt", "en").
    :return: SiteData object populated with extracted data.
    """
    # Comentário:
    # Esta função é o ponto central da extração: recebe o HTML e metadados,
    # chama os extractores de scripts, formulários e política de privacidade,
    # e devolve um SiteData pronto a ser analisado pelo motor RGPD.
    third_party_scripts = extract_third_party_scripts(html, page_url)
    forms = extract_forms(html, page_url)
    privacy_policy_url = extract_privacy_policy_url(html, page_url)
    consent_banner_detected = detect_consent_banner(html)

    # Comentário:
    # Por enquanto, a lista de cookies fica vazia; será preenchida em fases seguintes.
    cookies: List[Cookie] = []

    return SiteData(
        url=page_url,
        final_url=final_url,
        language=language,
        cookies=cookies,
        third_party_scripts=third_party_scripts,
        forms=forms,
        privacy_policy_url=privacy_policy_url,
        consent_banner_detected=consent_banner_detected,
    )