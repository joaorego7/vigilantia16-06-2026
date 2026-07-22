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
    Extrai o domínio (hostname) de um URL.

    Exemplo: "https://www.exemplo.pt/pagina?x=1" -> "www.exemplo.pt"

    :param url: URL em formato string.
    :return: O domínio (hostname), ou string vazia se o URL não for válido.
    """
    # Comentário:
    # Esta função auxiliar simplifica a comparação entre domínios,
    # permitindo distinguir scripts internos de scripts de terceiros.
    parsed = urlparse(url)
    return parsed.hostname or ""


def classify_script_category(src: str) -> str:
    """
    Classifica um script de terceiros numa categoria simples, a partir do seu URL.

    Usa correspondência de padrões de texto no URL (ex.: "google-analytics"
    sugere analytics, "doubleclick" sugere publicidade). É uma heurística
    básica, não uma lista exaustiva de todos os serviços possíveis.

    :param src: URL do script (ex.: "https://www.google-analytics.com/analytics.js").
    :return: Categoria em texto: "analytics", "advertising", "social" ou "other".
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
    Extrai a lista de scripts de terceiros presentes no HTML da página.

    Um script é considerado "de terceiros" quando o seu domínio é diferente
    do domínio da própria página (ex.: um site "exemplo.pt" que carrega um
    script de "google-analytics.com"). Scripts inline (sem atributo src) e
    scripts do próprio domínio são ignorados.

    :param html: Conteúdo HTML da página.
    :param page_url: URL original da página (usado para determinar o domínio base).
    :return: Lista de objetos ThirdPartyScript, um por cada script externo encontrado.
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
    Extrai todos os formulários HTML (<form>) presentes na página.

    Para cada formulário, recolhe:
      - o destino do envio (action), já resolvido para URL absoluto;
      - o método HTTP (GET/POST);
      - os nomes dos campos (inputs e textareas com atributo name);
      - se existe algum aviso de privacidade próximo (ver _has_nearby_privacy_notice).

    Esta informação é usada depois pelo motor de regras (R11) para detetar
    formulários que recolhem dados pessoais sem explicar a finalidade.

    :param html: Conteúdo HTML da página.
    :param page_url: URL original da página (usado para resolver o "action" relativo).
    :return: Lista de objetos Form, um por cada <form> encontrado.
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
    Tenta encontrar, na página, um link (<a>) que aponte para a política de
    privacidade, termos de uso ou página de cookies.

    A deteção é feita por palavras-chave no TEXTO do link (ex.: um link cujo
    texto visível seja "Política de Privacidade" ou "Cookies"), não no URL —
    por isso funciona independentemente de como o site nomeia o ficheiro/página.

    :param html: Conteúdo HTML da página.
    :param page_url: URL original da página (usado para resolver o link relativo).
    :return: URL absoluto da política de privacidade, ou None se não for encontrado nenhum link.
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


# Comentário:
# Palavras-chave usadas para descobrir OUTRAS páginas legais/RGPD do mesmo
# site (para além da política de privacidade principal), a partir do texto
# visível de cada link. Cobrimos deliberadamente mais termos do que
# extract_privacy_policy_url() acima, porque aqui o objetivo é encontrar
# TODAS as páginas potencialmente relevantes (cookies, termos, contactos,
# DPO/RGPD dedicados), não só a política principal.
_RELATED_LEGAL_LINK_KEYWORDS = [
    "privacidade", "privacy", "cookies", "termos", "terms",
    "condições gerais", "condições de utilização", "terms and conditions",
    "rgpd", "gdpr", "proteção de dados", "data protection",
    "encarregado de proteção de dados", "data protection officer",
    "contactos", "contact us",
]


def find_related_legal_links(
    html: str,
    page_url: str,
    exclude_urls: Optional[set] = None,
    max_links: int = 5,
) -> List[str]:
    """
    Descobre, na página indicada, links para OUTRAS páginas legais/RGPD do
    MESMO domínio (política de cookies separada, termos e condições,
    contactos, página dedicada ao RGPD/DPO, etc.).

    Usado para permitir uma análise "recursiva" limitada: em vez de
    verificar só a página principal da política de privacidade, seguimos
    também um pequeno número de páginas relacionadas, porque muitos sites
    espalham a informação exigida pelo RGPD por várias páginas (ex.:
    contacto do DPO só na página de "Contactos").

    Deliberadamente NÃO é um crawler genérico: só segue links cujo TEXTO
    visível sugira ser uma página legal/RGPD, fica sempre dentro do mesmo
    domínio, e está limitado a max_links resultados — para não arriscar
    percorrer o site inteiro (lento, e desnecessário para este objetivo).

    :param html: Conteúdo HTML da página onde procurar os links.
    :param page_url: URL da página atual (para resolver links relativos e
        determinar o domínio "próprio").
    :param exclude_urls: Conjunto de URLs a ignorar (já visitados/já
        conhecidos), para evitar repetir páginas.
    :param max_links: Número máximo de links novos a devolver.
    :return: Lista de URLs absolutos, únicos, do mesmo domínio, ainda não
        visitados, até ao limite de max_links.
    """
    soup = BeautifulSoup(html, "html.parser")
    base_domain = _get_domain(page_url)
    exclude_urls = exclude_urls or set()

    found: List[str] = []
    seen_in_this_page: set = set()

    for link_tag in soup.find_all("a"):
        href = link_tag.get("href")
        if not href:
            continue

        text = (link_tag.get_text() or "").strip().lower()
        if not any(keyword in text for keyword in _RELATED_LEGAL_LINK_KEYWORDS):
            continue

        absolute_url = urljoin(page_url, href)

        # Só seguimos links dentro do mesmo domínio — um link de texto
        # "Política de Privacidade" que aponte para outro site (ex.: a
        # política da Google Analytics) não nos interessa aqui.
        if _get_domain(absolute_url) != base_domain:
            continue

        if absolute_url in exclude_urls or absolute_url in seen_in_this_page:
            continue

        seen_in_this_page.add(absolute_url)
        found.append(absolute_url)

        if len(found) >= max_links:
            break

    return found


def detect_consent_banner(html: str) -> bool:
    """
    Deteta se a página tem, aparentemente, um banner de consentimento de cookies.

    A deteção é feita por palavras-chave típicas de banners de CMP (Consent
    Management Platform), como "aceitar cookies" ou "this site uses cookies".
    É uma heurística de texto simples: não confirma se o banner é funcional
    nem se bloqueia mesmo os cookies antes do consentimento — só confirma
    que existe TEXTO desse tipo algures na página.

    :param html: Conteúdo HTML da página.
    :return: True se for encontrado texto sugestivo de um banner de consentimento, False caso contrário.
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
    Constrói um objeto SiteData completo a partir do HTML e metadados de uma página.

    É a função "orquestradora" da extração: chama, por ordem, os extractores
    de scripts de terceiros, formulários, link da política de privacidade e
    deteção de banner de consentimento, e junta tudo num único SiteData.

    Nota: os cookies aqui ficam sempre como lista vazia — os cookies REAIS
    (capturados pelo Playwright antes de qualquer interação) são atribuídos
    depois, em scraper/main.py, porque este módulo (extractor.py) só trabalha
    sobre uma string de HTML e não tem acesso ao browser/contexto do Playwright.

    :param html: Conteúdo HTML da página.
    :param page_url: URL original pedido para a página.
    :param final_url: URL final após eventuais redirecionamentos.
    :param language: Código de idioma detetado (ex.: "pt", "en").
    :return: Objeto SiteData preenchido com os dados extraídos do HTML.
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
    # A lista de cookies fica vazia aqui de propósito — este módulo só vê
    # HTML em texto, não tem acesso ao browser. Quem preenche os cookies
    # reais é scraper/main.py, logo a seguir a esta chamada.
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