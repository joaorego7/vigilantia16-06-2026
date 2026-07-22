# src/vigilantia/analyzer/privacy_text.py

import logging
from typing import Dict, List, Optional, Tuple

import requests
from bs4 import BeautifulSoup
from langdetect import detect, LangDetectException

from vigilantia.scraper.extractor import find_related_legal_links

logger = logging.getLogger(__name__)

# Comentário geral do módulo:
# Este ficheiro trata da análise da política de privacidade:
# - faz o download da página da política;
# - extrai o texto simples (sem HTML);
# - deteta o idioma do texto;
# - verifica se a política menciona elementos obrigatórios do RGPD;
# - (analyze_privacy_policy_multi_page) agrega a mesma análise ao longo de
#   várias páginas legais relacionadas do mesmo site.


def download_privacy_policy(url: str, timeout_seconds: int = 10) -> str:
    """
    Faz o download da página da política de privacidade e devolve o HTML como string.

    :param url: URL da página da política de privacidade.
    :param timeout_seconds: Tempo máximo de espera pela resposta HTTP.
    :return: Conteúdo HTML da página em formato string.
    :raises ValueError: Se houver erro de rede ou código HTTP não-sucedido.
    """
    # Bug corrigido: sem cabeçalhos, o requests envia um User-Agent do tipo
    # "python-requests/2.x", que muitos WAFs/proteções anti-bot (Cloudflare,
    # Sucuri, etc.) bloqueiam automaticamente com HTTP 403 — mesmo que o
    # mesmo site responda normalmente a um browser real. O fetcher.py já usa
    # um User-Agent de browser via Playwright; usamos aqui o mesmo, para que
    # o download da política tenha a mesma probabilidade de sucesso que o
    # carregamento da página principal.
    headers = {
        "User-Agent": (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/123.0 Safari/537.36"
        ),
        "Accept-Language": "pt-PT,pt;q=0.9,en;q=0.8",
    }

    # Tenta fazer um pedido HTTP GET à URL indicada
    try:
        response = requests.get(url, timeout=timeout_seconds, headers=headers)
    except requests.exceptions.RequestException as exc:
        # Se acontecer qualquer erro de rede (timeout, DNS, etc.), lança ValueError
        raise ValueError(f"Erro de rede ao descarregar a política de privacidade: {exc}") from exc

    # Se o código HTTP não for "ok" (200–299), também consideramos erro
    if not response.ok:
        raise ValueError(f"Falha ao descarregar a política de privacidade: HTTP {response.status_code}")

    # Se tudo correr bem, devolvemos o HTML da resposta
    return response.text


def extract_plain_text(html: str) -> str:
    """
    Extrai texto simples a partir de HTML, removendo tags, scripts e estilos.

    :param html: Conteúdo HTML em formato string.
    :return: Texto plano (sem tags) adequado para análise.
    """
    # Cria um objeto BeautifulSoup para interpretar o HTML
    soup = BeautifulSoup(html, "html.parser")

    # Remove tags <script> e <style> para não poluir o texto com código
    for tag in soup(["script", "style"]):
        tag.decompose()

    # Extrai todo o texto visível da página, separando blocos com espaços
    text = soup.get_text(separator=" ")

    # Limpa espaços repetidos: transforma múltiplos espaços num só
    return " ".join(text.split())


def detect_language(text: str) -> str:
    """
    Deteta o idioma do texto fornecido usando a biblioteca langdetect.

    :param text: Texto plano da política ou da página.
    :return: Código de idioma (por exemplo "pt", "en", "es") ou "unknown" em caso de falha.
    """
    # Se o texto for vazio ou demasiado curto, a deteção de idioma é pouco fiável
    try:
        if not text or len(text.strip()) < 50:
            return "unknown"
        # A função detect devolve um código de língua, como "pt", "en", "es"
        lang_code = detect(text)
        return lang_code
    except LangDetectException:
        # Se langdetect não conseguir determinar a língua, devolve "unknown"
        return "unknown"


def check_required_elements(text: str, language: str) -> Dict[str, bool]:
    """
    Verifica se o texto da política de privacidade menciona elementos-chave do RGPD.

    :param text: Texto plano da política de privacidade.
    :param language: Código de idioma detetado (por exemplo "pt", "en").
    :return: Dicionário com flags (True/False) para cada elemento analisado.
    """
    # Converte o texto para minúsculas para facilitar a procura de palavras-chave
    lower_text = text.lower()

    # Palavras-chave em português para cada elemento RGPD que queremos verificar
    keywords_pt = {
        # Identidade do responsável pelo tratamento
        "identity_controller": [
            "responsável pelo tratamento",
            "responsável pelo processamento",
            "responsável pelo tratamento dos dados",
            "responsável pelos seus dados",
        ],
        # Contactos do DPO / encarregado de proteção de dados
        "dpo_contact": [
            "encarregado de proteção de dados",
            "data protection officer",
            "dpo",
            "contacto do dpo",
            "contacto do encarregado de proteção de dados",
        ],
        # Base legal do tratamento
        "legal_basis": [
            "base legal",
            "fundamento jurídico",
            "fundamento legal",
            "base de legitimidade",
            "consentimento",
            "interesse legítimo",
            "obrigação legal",
            "execução de contrato",
        ],
        # Direito de acesso
        "right_access": [
            "direito de acesso",
            "acesso aos dados",
            "direito de acesso aos dados",
            "acesso aos dados pessoais",
            "aceder aos seus dados",
            "solicitar acesso aos seus dados",
            
        ],
        # Direito de retificação
        "right_rectification": [
            "direito de retificação",
            "direito de rectificação",  # (com c) - bug corrigido: faltava a vírgula
            "retificar os dados",
            "corrigir os seus dados",
        ],
        # Direito ao apagamento / direito a ser esquecido
        "right_erasure": [
            "direito ao apagamento",
            "direito a ser esquecido",
            "apagar os seus dados",
            "eliminar os seus dados",
        ],
        # Direito à portabilidade dos dados
        "right_portability": [
            "direito à portabilidade",
            "portabilidade dos dados",
            "transferir os seus dados",
        ],
        # Transferências internacionais de dados
        #
        # Bug corrigido: a lista original só apanhava terminologia jurídica
        # genérica ("transferência internacional", "fora da UE"). Políticas
        # reais muitas vezes não usam essa terminologia — simplesmente
        # nomeiam o destino (ex.: "servidores da Google nos Estados
        # Unidos"), o que é também uma transferência internacional à luz
        # do RGPD (Art. 44-49), mas passava despercebido. Adicionamos
        # menções diretas a destinos fora do EEE mais comuns em políticas
        # de sites portugueses (EUA sendo o mais frequente, via serviços
        # como Google/Meta/AWS/Microsoft).
        "international_transfers": [
            "transferência internacional",
            "transferências internacionais",
            "fora da união europeia",
            "transferência de dados para fora",
            "fora do espaço económico europeu",
            "estados unidos",
            "eua",
            "e.u.a",
            "país terceiro",
            "países terceiros",
            "cláusulas contratuais-tipo",
            "cláusulas contratuais tipo",
            "decisão de adequação",
        ],
        # Prazo de conservação dos dados
        "retention_period": [
            "prazo de conservação",
            "período de conservação",
            "tempo de conservação",
            "prazo de retenção",
            "período de retenção",
            "conservados pelo prazo",
            "durante quanto tempo guardamos os dados",
            "durante quanto tempo são conservados",
        ],
        # Direito a apresentar reclamação à autoridade (CNPD)
        "right_complaint": [
            "direito a apresentar reclamação",
            "cnpd",
            "autoridade de controlo",
            "direito a apresentar reclamação",
            "direito de reclamação",
            "apresentar reclamação",
            "comissão nacional de proteção de dados",
            "autoridade de controlo",
        ],
    }

    # Palavras-chave equivalentes em inglês
    keywords_en = {
        "identity_controller": [
            "data controller",
            "controller responsible for",
            "controller of your data",
        ],
        "dpo_contact": [
            "data protection officer",
            "dpo",
            "contact the dpo",
            "dpo contact details",
        ],
        "legal_basis": [
            "legal basis",
            "lawful basis",
            "consent",
            "legitimate interest",
            "basis for processing",
            "legal obligation",
            "contractual necessity",
            "performance of a contract",
        ],
        "right_access": [
            "right of access",
            "access to your data",
            "access to your personal data",
        ],
        "right_rectification": [
            "right to rectification",
            "rectify your data",
            "right to correct your data",
            "correct inaccurate data",
        ],
        "right_erasure": [
            "right to erasure",
            "right to be forgotten",
            "erase your data",
            "delete your data",
        ],
        "right_portability": [
            "right to data portability",
            "data portability",
            "transfer your data to another",
        ],
        "international_transfers": [
            "international transfers",
            "outside the european union",
            "outside the eea",
            "outside the eu",
            "united states",
            "third country",
            "standard contractual clauses",
            "adequacy decision",
        ],
        "retention_period": [
            "retention period",
            "storage period",
            "how long we keep",
            "how long your data is kept",
        ],
        "right_complaint": [
            "right to lodge a complaint",
            "supervisory authority",
            "lodge a complaint",
            "data protection authority",
        ],
    }

    # Escolhe o conjunto de palavras-chave a usar com base no idioma detetado
    if language.startswith("pt"):
        # Se for português, usamos só as palavras-chave em PT
        kw = keywords_pt
    elif language.startswith("en"):
        # Se for inglês, usamos só as palavras-chave em EN
        kw = keywords_en
    else:
        # Se o idioma não for reconhecido, usamos uma combinação de PT e EN como fallback
        kw = {
            key: keywords_pt[key] + keywords_en[key]
            for key in keywords_pt.keys()
        }

    # Dicionário onde vamos guardar o resultado para cada elemento RGPD
    flags: Dict[str, bool] = {}

    # Para cada elemento (por exemplo "right_access") e respetivas palavras-chave,
    # verificamos se alguma dessas palavras aparece no texto.
    for key, words in kw.items():
        # True se pelo menos uma palavra-chave estiver presente no texto
        flags[key] = any(word in lower_text for word in words)

    # No fim, devolvemos o dicionário com todas as flags True/False
    return flags


def analyze_privacy_policy_multi_page(
    start_url: str,
    max_pages: int = 5,
    timeout_seconds: int = 10,
) -> Tuple[Dict[str, bool], Dict[str, str], List[str]]:
    """
    Analisa a política de privacidade E outras páginas legais relacionadas
    do mesmo site (cookies, termos, contactos, RGPD/DPO dedicado, etc.),
    agregando os elementos RGPD encontrados em qualquer uma delas.

    Motivação: muitos sites espalham a informação exigida pelo RGPD por
    várias páginas em vez de a concentrarem toda numa única política (ex.:
    o contacto do DPO só aparece na página de "Contactos", ou a política de
    cookies está separada da política de privacidade). Analisar só a
    página principal produzia falsos negativos nesses casos.

    Estratégia (busca em largura, limitada, NÃO um crawler genérico):
      1) Começa em start_url.
      2) Para cada página analisada com sucesso, faz merge das flags com OR
         (se o elemento for encontrado em QUALQUER página, fica True) e
         guarda a URL onde foi encontrado pela primeira vez (evidence_urls).
      3) Descobre novas páginas candidatas a partir dos links da própria
         página (find_related_legal_links), só do mesmo domínio, só com
         texto de link que sugira ser uma página legal/RGPD.
      4) Para, o mais tardar, ao atingir max_pages páginas analisadas —
         para nunca arriscar percorrer o site inteiro.

    Se uma página individual falhar a descarregar (rede, 403, etc.), essa
    página é simplemente ignorada e a análise continua com as restantes —
    uma falha pontual não deve deitar fora o que já foi encontrado noutras
    páginas.

    :param start_url: URL da política de privacidade principal (ponto de partida).
    :param max_pages: Número máximo de páginas a analisar no total.
    :param timeout_seconds: Timeout HTTP por página.
    :return: Tuplo (flags, evidence_urls, pages_analyzed):
      - flags: Dict[str, bool] com o resultado agregado de todas as páginas.
      - evidence_urls: Dict[str, str] com a URL onde cada flag True foi
        primeiro encontrada (só inclui as flags True).
      - pages_analyzed: lista de URLs efetivamente descarregadas com sucesso
        (para transparência no relatório/CLI).
    :raises ValueError: Se nem sequer a página inicial (start_url) puder ser
        descarregada — nesse caso não há nada para agregar.
    """
    aggregated_flags: Dict[str, bool] = {}
    evidence_urls: Dict[str, str] = {}
    pages_analyzed: List[str] = []
    visited: set = set()
    queue: List[str] = [start_url]
    first_page_failed_exc: Optional[ValueError] = None

    while queue and len(pages_analyzed) < max_pages:
        url = queue.pop(0)
        if url in visited:
            continue
        visited.add(url)

        try:
            html = download_privacy_policy(url, timeout_seconds=timeout_seconds)
        except ValueError as exc:
            logger.info("Não foi possível analisar %s (a ignorar): %s", url, exc)
            if url == start_url:
                # Guardamos o erro da página inicial: se NENHUMA página do
                # site for acessível, é isto que devolvemos ao chamador.
                first_page_failed_exc = exc
            continue

        pages_analyzed.append(url)

        text = extract_plain_text(html)
        lang = detect_language(text)
        page_flags = check_required_elements(text, language=lang)

        for key, value in page_flags.items():
            if value and not aggregated_flags.get(key, False):
                aggregated_flags[key] = True
                evidence_urls[key] = url
            elif key not in aggregated_flags:
                aggregated_flags[key] = False

        if len(pages_analyzed) < max_pages:
            related = find_related_legal_links(
                html,
                url,
                exclude_urls=visited,
                max_links=max_pages,
            )
            queue.extend(related)

    if not pages_analyzed:
        # Nem a página inicial nem nenhuma relacionada foi acessível.
        raise first_page_failed_exc or ValueError(
            f"Falha ao descarregar a política de privacidade: {start_url}"
        )

    return aggregated_flags, evidence_urls, pages_analyzed